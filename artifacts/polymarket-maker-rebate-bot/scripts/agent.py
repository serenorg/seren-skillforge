#!/usr/bin/env python3
"""Rebate-aware maker strategy scaffold for Polymarket binary markets."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev
from typing import Any


def _shared_artifacts_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "shared" / "polymarket_cli.py"
        if candidate.exists():
            return candidate.parent
    raise RuntimeError("Unable to locate artifacts/shared/polymarket_cli.py")


SHARED_DIR = _shared_artifacts_dir()
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from polymarket_cli import (  # noqa: E402
    PolymarketCliConfig,
    cli_get_book,
    cli_get_markets,
    cli_get_prices_history,
    load_polymarket_cli_config,
)


@dataclass(frozen=True)
class StrategyParams:
    bankroll_usd: float = 1000.0
    markets_max: int = 8
    min_seconds_to_resolution: int = 6 * 60 * 60
    min_edge_bps: float = 2.0
    default_rebate_bps: float = 3.0
    expected_unwind_cost_bps: float = 1.5
    adverse_selection_bps: float = 1.0
    min_spread_bps: float = 20.0
    max_spread_bps: float = 150.0
    volatility_spread_multiplier: float = 0.35
    base_order_notional_usd: float = 25.0
    max_notional_per_market_usd: float = 125.0
    max_total_notional_usd: float = 500.0
    max_position_notional_usd: float = 150.0
    inventory_skew_strength_bps: float = 25.0


@dataclass(frozen=True)
class BacktestParams:
    days: int = 90
    fidelity_minutes: int = 60
    participation_rate: float = 0.2
    volatility_window_points: int = 24
    min_liquidity_usd: float = 100000.0
    markets_fetch_limit: int = 300
    min_history_points: int = 480
    require_orderbook_history: bool = False
    spread_decay_bps: float = 45.0
    join_best_queue_factor: float = 0.85
    off_best_queue_factor: float = 0.35
    synthetic_orderbook_half_spread_bps: float = 18.0
    synthetic_orderbook_depth_usd: float = 125.0
    telemetry_path: str = ""


@dataclass(frozen=True)
class OrderBookSnapshot:
    t: int
    best_bid: float
    best_ask: float
    bid_size_usd: float
    ask_size_usd: float


@dataclass(frozen=True)
class QuotePlan:
    status: str
    market_id: str
    edge_bps: float
    spread_bps: float
    rebate_bps: float
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_notional_usd: float = 0.0
    ask_notional_usd: float = 0.0
    inventory_notional_usd: float = 0.0
    reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Polymarket maker/rebate strategy.")
    parser.add_argument("--config", default="config.json", help="Config file path.")
    parser.add_argument(
        "--markets-file",
        default=None,
        help="Optional path to market snapshot JSON file.",
    )
    parser.add_argument(
        "--run-type",
        default="backtest",
        choices=("quote", "monitor", "backtest"),
        help="Run type. Use backtest to run a 90-day replay before executing quotes.",
    )
    parser.add_argument(
        "--yes-live",
        action="store_true",
        help="Explicit live execution confirmation flag.",
    )
    parser.add_argument(
        "--backtest-file",
        default=None,
        help="Optional path to pre-saved backtest market history JSON.",
    )
    parser.add_argument(
        "--backtest-days",
        type=int,
        default=None,
        help="Override backtest lookback window in days (default from config: 90).",
    )
    return parser.parse_args()


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(config_path: str) -> dict[str, Any]:
    return load_json_file(Path(config_path))


def load_markets(config: dict[str, Any], markets_file: str | None) -> list[dict[str, Any]]:
    if markets_file:
        payload = load_json_file(Path(markets_file))
        if isinstance(payload, dict) and isinstance(payload.get("markets"), list):
            return payload["markets"]
        if isinstance(payload, list):
            return payload
        return []
    return list(config.get("markets", []))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def to_params(config: dict[str, Any]) -> StrategyParams:
    strategy = config.get("strategy", {})
    return StrategyParams(
        bankroll_usd=_safe_float(strategy.get("bankroll_usd"), 1000.0),
        markets_max=_safe_int(strategy.get("markets_max"), 8),
        min_seconds_to_resolution=_safe_int(strategy.get("min_seconds_to_resolution"), 21600),
        min_edge_bps=_safe_float(strategy.get("min_edge_bps"), 2.0),
        default_rebate_bps=_safe_float(strategy.get("default_rebate_bps"), 3.0),
        expected_unwind_cost_bps=_safe_float(strategy.get("expected_unwind_cost_bps"), 1.5),
        adverse_selection_bps=_safe_float(strategy.get("adverse_selection_bps"), 1.0),
        min_spread_bps=_safe_float(strategy.get("min_spread_bps"), 20.0),
        max_spread_bps=_safe_float(strategy.get("max_spread_bps"), 150.0),
        volatility_spread_multiplier=_safe_float(
            strategy.get("volatility_spread_multiplier"),
            0.35,
        ),
        base_order_notional_usd=_safe_float(strategy.get("base_order_notional_usd"), 25.0),
        max_notional_per_market_usd=_safe_float(strategy.get("max_notional_per_market_usd"), 125.0),
        max_total_notional_usd=_safe_float(strategy.get("max_total_notional_usd"), 500.0),
        max_position_notional_usd=_safe_float(strategy.get("max_position_notional_usd"), 150.0),
        inventory_skew_strength_bps=_safe_float(strategy.get("inventory_skew_strength_bps"), 25.0),
    )


def to_backtest_params(config: dict[str, Any]) -> BacktestParams:
    backtest = config.get("backtest", {})
    return BacktestParams(
        days=max(1, _safe_int(backtest.get("days"), 90)),
        fidelity_minutes=max(1, _safe_int(backtest.get("fidelity_minutes"), 60)),
        participation_rate=clamp(
            _safe_float(backtest.get("participation_rate"), 0.2),
            0.0,
            1.0,
        ),
        volatility_window_points=max(3, _safe_int(backtest.get("volatility_window_points"), 24)),
        min_liquidity_usd=max(0.0, _safe_float(backtest.get("min_liquidity_usd"), 100000.0)),
        markets_fetch_limit=max(1, _safe_int(backtest.get("markets_fetch_limit"), 300)),
        min_history_points=max(10, _safe_int(backtest.get("min_history_points"), 480)),
        require_orderbook_history=_safe_bool(backtest.get("require_orderbook_history"), False),
        spread_decay_bps=max(1.0, _safe_float(backtest.get("spread_decay_bps"), 45.0)),
        join_best_queue_factor=clamp(
            _safe_float(backtest.get("join_best_queue_factor"), 0.85),
            0.0,
            1.0,
        ),
        off_best_queue_factor=clamp(
            _safe_float(backtest.get("off_best_queue_factor"), 0.35),
            0.0,
            1.0,
        ),
        synthetic_orderbook_half_spread_bps=max(
            1.0,
            _safe_float(backtest.get("synthetic_orderbook_half_spread_bps"), 18.0),
        ),
        synthetic_orderbook_depth_usd=max(
            1.0,
            _safe_float(backtest.get("synthetic_orderbook_depth_usd"), 125.0),
        ),
        telemetry_path=_safe_str(backtest.get("telemetry_path"), ""),
    )


def to_polymarket_cli_config(config: dict[str, Any]) -> PolymarketCliConfig:
    return load_polymarket_cli_config(config.get("polymarket_cli"))


def compute_spread_bps(volatility_bps: float, p: StrategyParams) -> float:
    spread = p.min_spread_bps + volatility_bps * p.volatility_spread_multiplier
    return clamp(spread, p.min_spread_bps, p.max_spread_bps)


def expected_edge_bps(spread_bps: float, rebate_bps: float, p: StrategyParams) -> float:
    half_spread_capture = spread_bps / 2.0
    return half_spread_capture + rebate_bps - p.expected_unwind_cost_bps - p.adverse_selection_bps


def should_skip_market(market: dict[str, Any], p: StrategyParams) -> tuple[bool, str]:
    ttl = _safe_int(market.get("seconds_to_resolution"), 0)
    if ttl < p.min_seconds_to_resolution:
        return True, "near_resolution"

    mid = _safe_float(market.get("mid_price"), -1.0)
    if mid <= 0.01 or mid >= 0.99:
        return True, "extreme_probability"

    bid = _safe_float(market.get("best_bid"), -1.0)
    ask = _safe_float(market.get("best_ask"), -1.0)
    if not (0.0 <= bid <= 1.0 and 0.0 <= ask <= 1.0 and bid <= ask):
        return True, "invalid_book"

    return False, ""


def _parse_iso_ts(value: Any) -> int | None:
    raw = _safe_str(value, "")
    if not raw:
        return None
    try:
        return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _json_to_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []


def _extract_size_usd(raw: dict[str, Any], price: float) -> float:
    direct = _safe_float(raw.get("size_usd"), -1.0)
    if direct >= 0.0:
        return direct
    size = _safe_float(
        raw.get("size", raw.get("quantity", raw.get("amount", raw.get("shares", 0.0)))),
        0.0,
    )
    if size <= 0.0:
        return 0.0
    if price <= 0.0:
        return size
    return size * price


def _top_level_price(levels: Any, fallback_key: str) -> tuple[float, float]:
    if isinstance(levels, list) and levels:
        first = levels[0]
        if isinstance(first, dict):
            price = _safe_float(first.get("price"), -1.0)
            size_usd = _extract_size_usd(first, price=max(price, 0.0))
            return price, size_usd
    return -1.0, 0.0


def _normalize_orderbook_snapshots(
    raw_snapshots: Any,
    history: list[tuple[int, float]],
    bt: BacktestParams,
) -> tuple[dict[int, OrderBookSnapshot], str]:
    snapshots: dict[int, OrderBookSnapshot] = {}
    if isinstance(raw_snapshots, list):
        for item in raw_snapshots:
            if not isinstance(item, dict):
                continue
            ts = _safe_int(item.get("t"), -1)
            if ts < 0:
                continue
            best_bid = _safe_float(item.get("best_bid"), -1.0)
            best_ask = _safe_float(item.get("best_ask"), -1.0)
            bid_size_usd = _safe_float(item.get("bid_size_usd"), -1.0)
            ask_size_usd = _safe_float(item.get("ask_size_usd"), -1.0)
            if best_bid < 0.0:
                best_bid, inferred_size = _top_level_price(item.get("bids"), "best_bid")
                if bid_size_usd < 0.0:
                    bid_size_usd = inferred_size
            if best_ask < 0.0:
                best_ask, inferred_size = _top_level_price(item.get("asks"), "best_ask")
                if ask_size_usd < 0.0:
                    ask_size_usd = inferred_size
            if best_bid < 0.0 or best_ask < 0.0 or best_bid > best_ask:
                continue
            snapshots[ts] = OrderBookSnapshot(
                t=ts,
                best_bid=best_bid,
                best_ask=best_ask,
                bid_size_usd=max(0.0, bid_size_usd),
                ask_size_usd=max(0.0, ask_size_usd),
            )
    if snapshots:
        return snapshots, "historical"

    if bt.require_orderbook_history:
        raise RuntimeError(
            "Stateful backtest requires historical order-book snapshots. "
            "Provide orderbooks in --backtest-file / backtest_markets or disable require_orderbook_history."
        )

    synthetic: dict[int, OrderBookSnapshot] = {}
    half_spread = bt.synthetic_orderbook_half_spread_bps / 10000.0
    for ts, mid in history:
        synthetic[ts] = OrderBookSnapshot(
            t=ts,
            best_bid=clamp(mid - half_spread, 0.001, 0.999),
            best_ask=clamp(mid + half_spread, 0.001, 0.999),
            bid_size_usd=bt.synthetic_orderbook_depth_usd,
            ask_size_usd=bt.synthetic_orderbook_depth_usd,
        )
    return synthetic, "synthetic"


def _write_telemetry_records(path: str, records: list[dict[str, Any]]) -> None:
    if not path or not records:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")


def _normalize_history(
    history_payload: list[Any],
    start_ts: int,
    end_ts: int,
) -> list[tuple[int, float]]:
    cleaned: list[tuple[int, float]] = []
    seen: set[int] = set()
    for point in history_payload:
        t: int | None = None
        p: float | None = None
        if isinstance(point, dict):
            t = _safe_int(point.get("t"), -1)
            p = _safe_float(point.get("p"), -1.0)
        elif isinstance(point, list | tuple) and len(point) >= 2:
            t = _safe_int(point[0], -1)
            p = _safe_float(point[1], -1.0)

        if t is None or p is None:
            continue
        if t < 0 or not (0.0 <= p <= 1.0):
            continue
        if t < start_ts or t > end_ts or t in seen:
            continue
        seen.add(t)
        cleaned.append((t, p))
    cleaned.sort(key=lambda x: x[0])
    return cleaned


def _load_markets_from_fixture(
    payload: dict[str, Any] | list[Any],
    start_ts: int,
    end_ts: int,
    backtest_params: BacktestParams,
) -> list[dict[str, Any]]:
    raw_markets: list[Any]
    if isinstance(payload, dict):
        raw_markets = _json_to_list(payload.get("markets"))
    elif isinstance(payload, list):
        raw_markets = payload
    else:
        raw_markets = []

    markets: list[dict[str, Any]] = []
    for raw in raw_markets:
        if not isinstance(raw, dict):
            continue
        history = _normalize_history(
            history_payload=_json_to_list(raw.get("history")),
            start_ts=start_ts,
            end_ts=end_ts,
        )
        if len(history) < 2:
            continue
        orderbooks, orderbook_mode = _normalize_orderbook_snapshots(
            raw_snapshots=raw.get("orderbooks", raw.get("book_history")),
            history=history,
            bt=backtest_params,
        )
        market_id = _safe_str(raw.get("market_id"), _safe_str(raw.get("token_id"), "unknown"))
        markets.append(
            {
                "market_id": market_id,
                "question": _safe_str(raw.get("question"), market_id),
                "token_id": _safe_str(raw.get("token_id"), market_id),
                "end_ts": _safe_int(raw.get("end_ts"), _parse_iso_ts(raw.get("endDate")) or 0),
                "rebate_bps": _safe_float(raw.get("rebate_bps"), 0.0),
                "history": history,
                "orderbooks": orderbooks,
                "orderbook_mode": orderbook_mode,
                "source": "fixture",
            }
        )
    return markets


def _snapshot_from_live_book(
    payload: dict[str, Any] | list[Any] | None,
    history: list[tuple[int, float]],
    bt: BacktestParams,
) -> dict[int, OrderBookSnapshot]:
    if not history:
        return {}
    last_ts, last_mid = history[-1]
    best_bid = -1.0
    best_ask = -1.0
    bid_size = 0.0
    ask_size = 0.0
    if isinstance(payload, dict):
        best_bid = _safe_float(payload.get("best_bid", payload.get("bid")), -1.0)
        best_ask = _safe_float(payload.get("best_ask", payload.get("ask")), -1.0)
        bid_size = _safe_float(payload.get("bid_size_usd"), -1.0)
        ask_size = _safe_float(payload.get("ask_size_usd"), -1.0)
        if best_bid < 0.0:
            best_bid, inferred = _top_level_price(payload.get("bids"), "best_bid")
            if bid_size < 0.0:
                bid_size = inferred
        if best_ask < 0.0:
            best_ask, inferred = _top_level_price(payload.get("asks"), "best_ask")
            if ask_size < 0.0:
                ask_size = inferred
    if best_bid < 0.0 or best_ask < 0.0 or best_bid >= best_ask:
        synthetic, _ = _normalize_orderbook_snapshots([], history=history, bt=bt)
        return synthetic

    half_spread = max((best_ask - best_bid) / 2.0, bt.synthetic_orderbook_half_spread_bps / 10000.0)
    reference_bid_size = max(0.0, bid_size) or bt.synthetic_orderbook_depth_usd
    reference_ask_size = max(0.0, ask_size) or bt.synthetic_orderbook_depth_usd
    snapshots: dict[int, OrderBookSnapshot] = {}
    for ts, mid in history:
        snapshots[ts] = OrderBookSnapshot(
            t=ts,
            best_bid=clamp(mid - half_spread, 0.001, 0.999),
            best_ask=clamp(mid + half_spread, 0.001, 0.999),
            bid_size_usd=reference_bid_size,
            ask_size_usd=reference_ask_size,
        )
    return snapshots


def _fetch_live_markets(
    strategy_params: StrategyParams,
    backtest_params: BacktestParams,
    cli_config: PolymarketCliConfig,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, Any]]:
    if backtest_params.require_orderbook_history:
        raise RuntimeError(
            "Historical order-book replay is required. Provide --backtest-file or backtest_markets "
            "with orderbooks because live CLI fetch does not supply historical book snapshots."
        )
    raw = cli_get_markets(
        cli_config,
        limit=backtest_params.markets_fetch_limit,
        order="volume24hr",
        ascending=False,
        active=True,
        closed=False,
    )
    if not isinstance(raw, list):
        return []

    candidates: list[dict[str, Any]] = []
    for market in raw:
        if not isinstance(market, dict):
            continue
        liquidity = _safe_float(market.get("liquidity"), 0.0)
        if liquidity < backtest_params.min_liquidity_usd:
            continue
        end_market = _parse_iso_ts(market.get("endDate")) or 0
        if end_market <= start_ts + strategy_params.min_seconds_to_resolution:
            continue
        token_ids = _json_to_list(market.get("clobTokenIds"))
        if not token_ids:
            continue
        token_id = _safe_str(token_ids[0], "")
        if not token_id:
            continue
        candidates.append(
            {
                "market_id": _safe_str(market.get("id"), token_id),
                "question": _safe_str(market.get("question"), token_id),
                "token_id": token_id,
                "end_ts": end_market,
                "rebate_bps": _safe_float(market.get("rebate_bps"), 0.0),
                "volume24hr": _safe_float(market.get("volume24hr"), 0.0),
            }
        )

    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        if len(selected) >= strategy_params.markets_max:
            break
        payload = cli_get_prices_history(
            cli_config,
            market=candidate["token_id"],
            interval="max",
            fidelity=backtest_params.fidelity_minutes,
        )
        if not isinstance(payload, dict):
            continue
        history = _normalize_history(
            history_payload=_json_to_list(payload.get("history")),
            start_ts=start_ts,
            end_ts=end_ts,
        )
        if len(history) < backtest_params.min_history_points:
            continue
        book_payload: dict[str, Any] | list[Any] | None
        try:
            book_payload = cli_get_book(cli_config, token_id=candidate["token_id"])
        except Exception:
            book_payload = None
        orderbooks = _snapshot_from_live_book(
            payload=book_payload,
            history=history,
            bt=backtest_params,
        )
        selected.append(
            {
                **candidate,
                "history": history,
                "orderbooks": orderbooks,
                "orderbook_mode": "synthetic-from-cli-book",
                "source": "live-polymarket-cli",
            }
        )
    return selected


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        max_dd = max(max_dd, peak - value)
    return max_dd


def _build_quote_plan(
    market_id: str,
    mid: float,
    vol_bps: float,
    rebate_bps: float,
    inventory_notional: float,
    outstanding_notional: float,
    p: StrategyParams,
) -> QuotePlan:
    spread_bps = compute_spread_bps(vol_bps, p)
    edge_bps = expected_edge_bps(spread_bps, rebate_bps, p)
    if edge_bps < p.min_edge_bps:
        return QuotePlan(
            status="skipped",
            market_id=market_id,
            reason="negative_or_thin_edge",
            edge_bps=round(edge_bps, 3),
            spread_bps=round(spread_bps, 3),
            rebate_bps=round(rebate_bps, 3),
            inventory_notional_usd=round(inventory_notional, 2),
        )

    inventory_ratio = 0.0
    if p.max_position_notional_usd > 0:
        inventory_ratio = clamp(inventory_notional / p.max_position_notional_usd, -1.0, 1.0)
    skew_bps = -inventory_ratio * p.inventory_skew_strength_bps
    half_spread_prob = (spread_bps / 2.0) / 10000.0
    skew_prob = skew_bps / 10000.0
    bid_px = clamp(mid - half_spread_prob + skew_prob, 0.001, 0.999)
    ask_px = clamp(mid + half_spread_prob + skew_prob, 0.001, 0.999)
    if bid_px >= ask_px:
        return QuotePlan(
            status="skipped",
            market_id=market_id,
            reason="crossed_quote_after_skew",
            edge_bps=round(edge_bps, 3),
            spread_bps=round(spread_bps, 3),
            rebate_bps=round(rebate_bps, 3),
            inventory_notional_usd=round(inventory_notional, 2),
        )

    remaining_market = max(0.0, p.max_notional_per_market_usd - abs(inventory_notional))
    remaining_total = max(0.0, p.max_total_notional_usd - max(0.0, outstanding_notional))
    bid_position_capacity = max(0.0, p.max_position_notional_usd - inventory_notional)
    ask_position_capacity = max(0.0, p.max_position_notional_usd + inventory_notional)
    per_side_market_budget = remaining_market / 2.0
    per_side_total_budget = remaining_total / 2.0
    bid_notional = min(
        p.base_order_notional_usd,
        per_side_market_budget,
        per_side_total_budget,
        bid_position_capacity,
    )
    ask_notional = min(
        p.base_order_notional_usd,
        per_side_market_budget,
        per_side_total_budget,
        ask_position_capacity,
    )
    if bid_notional <= 0.0 and ask_notional <= 0.0:
        return QuotePlan(
            status="skipped",
            market_id=market_id,
            reason="risk_capacity_exhausted",
            edge_bps=round(edge_bps, 3),
            spread_bps=round(spread_bps, 3),
            rebate_bps=round(rebate_bps, 3),
            inventory_notional_usd=round(inventory_notional, 2),
        )

    return QuotePlan(
        status="quoted",
        market_id=market_id,
        edge_bps=round(edge_bps, 3),
        spread_bps=round(spread_bps, 3),
        rebate_bps=round(rebate_bps, 3),
        bid_price=round(bid_px, 4),
        ask_price=round(ask_px, 4),
        bid_notional_usd=round(max(0.0, bid_notional), 2),
        ask_notional_usd=round(max(0.0, ask_notional), 2),
        inventory_notional_usd=round(inventory_notional, 2),
    )


def _liquidation_equity(cash_usd: float, position_shares: float, mark_price: float, unwind_cost_bps: float) -> float:
    inventory_value = position_shares * mark_price
    liquidation_cost = abs(inventory_value) * unwind_cost_bps / 10000.0
    return cash_usd + inventory_value - liquidation_cost


def _fill_fraction(
    *,
    side: str,
    quote_price: float,
    quote_notional: float,
    current_book: OrderBookSnapshot,
    next_book: OrderBookSnapshot,
    next_mid: float,
    spread_bps: float,
    bt: BacktestParams,
    p: StrategyParams,
) -> float:
    if quote_notional <= 0.0:
        return 0.0
    if side == "buy":
        touched_price = min(next_mid, next_book.best_bid)
        touched_distance_bps = max(0.0, (quote_price - touched_price) * 10000.0)
        displayed_size = next_book.ask_size_usd
        queue_factor = bt.join_best_queue_factor if quote_price >= current_book.best_bid else bt.off_best_queue_factor
    else:
        touched_price = max(next_mid, next_book.best_ask)
        touched_distance_bps = max(0.0, (touched_price - quote_price) * 10000.0)
        displayed_size = next_book.bid_size_usd
        queue_factor = bt.join_best_queue_factor if quote_price <= current_book.best_ask else bt.off_best_queue_factor
    if touched_distance_bps <= 0.0:
        return 0.0
    half_spread_bps = max(spread_bps / 2.0, 1.0)
    touch_ratio = clamp(touched_distance_bps / half_spread_bps, 0.0, 1.0)
    spread_decay = math.exp(-max(0.0, spread_bps - p.min_spread_bps) / bt.spread_decay_bps)
    depth_factor = clamp(displayed_size / max(quote_notional, 1e-9), 0.0, 1.0)
    return clamp(
        bt.participation_rate * touch_ratio * spread_decay * queue_factor * depth_factor,
        0.0,
        1.0,
    )


def _apply_fill(
    *,
    side: str,
    fill_notional: float,
    fill_price: float,
    rebate_bps: float,
    cash_usd: float,
    position_shares: float,
) -> tuple[float, float]:
    shares = fill_notional / max(fill_price, 0.01)
    if side == "buy":
        cash_usd -= shares * fill_price
        position_shares += shares
    else:
        cash_usd += shares * fill_price
        position_shares -= shares
    cash_usd += fill_notional * rebate_bps / 10000.0
    return cash_usd, position_shares


def _simulate_market_backtest(
    market: dict[str, Any],
    strategy_params: StrategyParams,
    backtest_params: BacktestParams,
) -> dict[str, Any]:
    history: list[tuple[int, float]] = market["history"]
    orderbooks: dict[int, OrderBookSnapshot] = market.get("orderbooks", {})
    window = backtest_params.volatility_window_points
    if len(history) < window + 2:
        return {
            "market_id": market["market_id"],
            "question": market["question"],
            "considered_points": 0,
            "quoted_points": 0,
            "skipped_points": 0,
            "fill_events": 0,
            "filled_notional_usd": 0.0,
            "pnl_usd": 0.0,
            "equity_curve": [strategy_params.bankroll_usd],
            "telemetry": [],
            "orderbook_mode": market.get("orderbook_mode", "unknown"),
        }

    rebate_bps = _safe_float(market.get("rebate_bps"), strategy_params.default_rebate_bps)
    if rebate_bps <= 0:
        rebate_bps = strategy_params.default_rebate_bps
    end_ts = _safe_int(market.get("end_ts"), 0)
    moves_bps = [abs((history[i][1] - history[i - 1][1]) * 10000.0) for i in range(1, len(history))]

    cash_usd = strategy_params.bankroll_usd
    position_shares = 0.0
    considered = 0
    quoted = 0
    skipped = 0
    fill_events = 0
    filled_notional = 0.0
    telemetry: list[dict[str, Any]] = []
    equity_curve = [strategy_params.bankroll_usd]

    for i in range(window, len(history) - 1):
        t, mid_price = history[i]
        next_t, next_mid = history[i + 1]
        current_book = orderbooks.get(t)
        next_book = orderbooks.get(next_t, current_book)
        if current_book is None or next_book is None:
            skipped += 1
            continue
        considered += 1

        record: dict[str, Any] = {
            "t": t,
            "market_id": market["market_id"],
            "mid_price": round(mid_price, 6),
            "next_mid_price": round(next_mid, 6),
            "best_bid": round(current_book.best_bid, 6),
            "best_ask": round(current_book.best_ask, 6),
            "inventory_notional_before_usd": round(position_shares * mid_price, 6),
            "orderbook_mode": market.get("orderbook_mode", "unknown"),
        }

        if end_ts and end_ts - t < strategy_params.min_seconds_to_resolution:
            skipped += 1
            record["status"] = "skipped"
            record["reason"] = "near_resolution"
            telemetry.append(record)
            continue
        if mid_price <= 0.01 or mid_price >= 0.99:
            skipped += 1
            record["status"] = "skipped"
            record["reason"] = "extreme_probability"
            telemetry.append(record)
            continue

        vol_slice = moves_bps[i - window : i]
        vol_bps = pstdev(vol_slice) if len(vol_slice) > 1 else strategy_params.min_spread_bps
        outstanding_notional = abs(position_shares * mid_price)
        quote_plan = _build_quote_plan(
            market_id=_safe_str(market.get("market_id"), "unknown"),
            mid=mid_price,
            vol_bps=vol_bps,
            rebate_bps=rebate_bps,
            inventory_notional=position_shares * mid_price,
            outstanding_notional=outstanding_notional,
            p=strategy_params,
        )
        record.update(
            {
                "status": quote_plan.status,
                "reason": quote_plan.reason,
                "spread_bps": quote_plan.spread_bps,
                "edge_bps": quote_plan.edge_bps,
                "bid_price": quote_plan.bid_price,
                "ask_price": quote_plan.ask_price,
                "bid_notional_usd": quote_plan.bid_notional_usd,
                "ask_notional_usd": quote_plan.ask_notional_usd,
            }
        )
        if quote_plan.status != "quoted":
            skipped += 1
            telemetry.append(record)
            equity_curve.append(_liquidation_equity(cash_usd, position_shares, next_mid, strategy_params.expected_unwind_cost_bps))
            continue

        quoted += 1
        side: str | None = None
        if next_mid < mid_price and quote_plan.bid_notional_usd > 0.0:
            side = "buy"
        elif next_mid > mid_price and quote_plan.ask_notional_usd > 0.0:
            side = "sell"

        fill_fraction = 0.0
        fill_notional = 0.0
        fill_price = 0.0
        previous_equity = _liquidation_equity(
            cash_usd,
            position_shares,
            mid_price,
            strategy_params.expected_unwind_cost_bps,
        )
        if side == "buy":
            fill_fraction = _fill_fraction(
                side="buy",
                quote_price=quote_plan.bid_price,
                quote_notional=quote_plan.bid_notional_usd,
                current_book=current_book,
                next_book=next_book,
                next_mid=next_mid,
                spread_bps=quote_plan.spread_bps,
                bt=backtest_params,
                p=strategy_params,
            )
            fill_notional = quote_plan.bid_notional_usd * fill_fraction
            fill_price = quote_plan.bid_price
        elif side == "sell":
            fill_fraction = _fill_fraction(
                side="sell",
                quote_price=quote_plan.ask_price,
                quote_notional=quote_plan.ask_notional_usd,
                current_book=current_book,
                next_book=next_book,
                next_mid=next_mid,
                spread_bps=quote_plan.spread_bps,
                bt=backtest_params,
                p=strategy_params,
            )
            fill_notional = quote_plan.ask_notional_usd * fill_fraction
            fill_price = quote_plan.ask_price

        if fill_notional > 0.0 and side is not None:
            cash_usd, position_shares = _apply_fill(
                side=side,
                fill_notional=fill_notional,
                fill_price=fill_price,
                rebate_bps=rebate_bps,
                cash_usd=cash_usd,
                position_shares=position_shares,
            )
            filled_notional += fill_notional
            fill_events += 1

        equity_after = _liquidation_equity(
            cash_usd,
            position_shares,
            next_mid,
            strategy_params.expected_unwind_cost_bps,
        )
        equity_curve.append(equity_after)
        record.update(
            {
                "fill_side": side or "",
                "fill_fraction": round(fill_fraction, 6),
                "fill_notional_usd": round(fill_notional, 6),
                "inventory_notional_after_usd": round(position_shares * next_mid, 6),
                "equity_before_usd": round(previous_equity, 6),
                "equity_after_usd": round(equity_after, 6),
                "event_pnl_usd": round(equity_after - previous_equity, 6),
            }
        )
        telemetry.append(record)

    ending_equity = _liquidation_equity(
        cash_usd,
        position_shares,
        history[-1][1],
        strategy_params.expected_unwind_cost_bps,
    )
    if not equity_curve or ending_equity != equity_curve[-1]:
        equity_curve.append(ending_equity)
    return {
        "market_id": market["market_id"],
        "question": market["question"],
        "considered_points": considered,
        "quoted_points": quoted,
        "skipped_points": skipped,
        "fill_events": fill_events,
        "filled_notional_usd": round(filled_notional, 4),
        "pnl_usd": round(ending_equity - strategy_params.bankroll_usd, 6),
        "equity_curve": equity_curve,
        "telemetry": telemetry,
        "orderbook_mode": market.get("orderbook_mode", "unknown"),
    }


def run_backtest(
    config: dict[str, Any],
    backtest_file: str | None,
    backtest_days_override: int | None,
) -> dict[str, Any]:
    strategy_params = to_params(config)
    backtest_params = to_backtest_params(config)
    cli_config = to_polymarket_cli_config(config)
    days = max(1, backtest_days_override or backtest_params.days)
    end_ts = int(time.time())
    start_ts = end_ts - (days * 24 * 3600)

    try:
        if backtest_file:
            fixture_payload = load_json_file(Path(backtest_file))
            markets = _load_markets_from_fixture(
                payload=fixture_payload,
                start_ts=start_ts,
                end_ts=end_ts,
                backtest_params=backtest_params,
            )
            source = "file"
        elif config.get("backtest_markets"):
            markets = _load_markets_from_fixture(
                payload=config.get("backtest_markets", []),
                start_ts=start_ts,
                end_ts=end_ts,
                backtest_params=backtest_params,
            )
            source = "config"
        else:
            markets = _fetch_live_markets(
                strategy_params=strategy_params,
                backtest_params=backtest_params,
                cli_config=cli_config,
                start_ts=start_ts,
                end_ts=end_ts,
            )
            source = "live-polymarket-cli"
    except Exception as exc:  # pragma: no cover - defensive runtime path
        return {
            "status": "error",
            "error_code": "backtest_data_load_failed",
            "message": str(exc),
            "hint": (
                "Provide --backtest-file with pre-saved history JSON if "
                "network/API access is blocked."
            ),
            "dry_run": True,
        }

    if not markets:
        return {
            "status": "error",
            "error_code": "no_backtest_markets",
            "message": "No markets with sufficient history were available for backtest.",
            "dry_run": True,
        }

    market_summaries: list[dict[str, Any]] = []
    equity_curve = [strategy_params.bankroll_usd]
    total_considered = 0
    total_quoted = 0
    total_notional = 0.0
    total_fill_events = 0
    telemetry_records: list[dict[str, Any]] = []
    orderbook_modes: set[str] = set()

    for market in markets[: strategy_params.markets_max]:
        summary = _simulate_market_backtest(
            market=market,
            strategy_params=strategy_params,
            backtest_params=backtest_params,
        )
        market_summaries.append(
            {
                "market_id": summary["market_id"],
                "question": summary["question"],
                "considered_points": summary["considered_points"],
                "quoted_points": summary["quoted_points"],
                "skipped_points": summary["skipped_points"],
                "fill_events": summary["fill_events"],
                "filled_notional_usd": summary["filled_notional_usd"],
                "pnl_usd": summary["pnl_usd"],
                "orderbook_mode": summary["orderbook_mode"],
            }
        )
        total_considered += int(summary["considered_points"])
        total_quoted += int(summary["quoted_points"])
        total_notional += float(summary["filled_notional_usd"])
        total_fill_events += int(summary["fill_events"])
        telemetry_records.extend(summary["telemetry"])
        orderbook_modes.add(_safe_str(summary.get("orderbook_mode"), "unknown"))
        market_equity_curve = summary["equity_curve"]
        if len(market_equity_curve) > len(equity_curve):
            equity_curve.extend([equity_curve[-1]] * (len(market_equity_curve) - len(equity_curve)))
        for idx, value in enumerate(market_equity_curve):
            if idx < len(equity_curve):
                equity_curve[idx] += value - strategy_params.bankroll_usd

    ending_equity = equity_curve[-1]
    total_pnl = ending_equity - strategy_params.bankroll_usd
    return_pct = (total_pnl / strategy_params.bankroll_usd) * 100.0
    max_drawdown = _max_drawdown(equity_curve)
    decision = "consider_live_guarded" if total_pnl > 0 else "paper_only_or_tune"
    _write_telemetry_records(backtest_params.telemetry_path, telemetry_records)

    return {
        "status": "ok",
        "skill": "polymarket-maker-rebate-bot",
        "mode": "backtest",
        "dry_run": True,
        "backtest_summary": {
            "days": days,
            "source": source,
            "start_utc": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat(),
            "end_utc": datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(),
            "markets_selected": len(market_summaries),
            "considered_points": total_considered,
            "quoted_points": total_quoted,
            "fill_events": total_fill_events,
            "orderbook_mode": ",".join(sorted(orderbook_modes)),
            "quote_rate_pct": round(
                (total_quoted / total_considered) * 100.0 if total_considered else 0.0,
                4,
            ),
        },
        "results": {
            "starting_bankroll_usd": round(strategy_params.bankroll_usd, 4),
            "ending_bankroll_usd": round(ending_equity, 4),
            "total_pnl_usd": round(total_pnl, 4),
            "return_pct": round(return_pct, 4),
            "filled_notional_usd": round(total_notional, 4),
            "events": total_fill_events,
            "max_drawdown_usd": round(max_drawdown, 4),
            "telemetry_path": backtest_params.telemetry_path or None,
            "decision_hint": decision,
            "disclaimer": (
                "Backtests are estimates and do not guarantee future performance."
            ),
        },
        "markets": sorted(market_summaries, key=lambda item: item["pnl_usd"], reverse=True),
        "next_steps": [
            "Review negative-PnL markets and edge assumptions.",
            "Tune spread, participation, and risk caps before live mode.",
            "Run quote mode only after backtest results are acceptable.",
        ],
    }


def quote_market(
    market: dict[str, Any],
    inventory_notional: float,
    outstanding_notional: float,
    p: StrategyParams,
) -> dict[str, Any]:
    market_id = str(market.get("market_id", "unknown"))
    mid = _safe_float(market.get("mid_price"), 0.5)
    vol_bps = _safe_float(market.get("volatility_bps"), p.min_spread_bps)
    rebate_bps = _safe_float(market.get("rebate_bps"), p.default_rebate_bps)
    quote_plan = _build_quote_plan(
        market_id=market_id,
        mid=mid,
        vol_bps=vol_bps,
        rebate_bps=rebate_bps,
        inventory_notional=inventory_notional,
        outstanding_notional=outstanding_notional,
        p=p,
    )
    if quote_plan.status != "quoted":
        return {
            "market_id": market_id,
            "status": "skipped",
            "reason": quote_plan.reason,
            "edge_bps": quote_plan.edge_bps,
        }
    total_notional = quote_plan.bid_notional_usd + quote_plan.ask_notional_usd
    return {
        "market_id": market_id,
        "status": quote_plan.status,
        "edge_bps": quote_plan.edge_bps,
        "spread_bps": quote_plan.spread_bps,
        "rebate_bps": quote_plan.rebate_bps,
        "quote_notional_usd": round(total_notional, 2),
        "bid_notional_usd": quote_plan.bid_notional_usd,
        "ask_notional_usd": quote_plan.ask_notional_usd,
        "bid_price": quote_plan.bid_price,
        "ask_price": quote_plan.ask_price,
        "inventory_notional_usd": quote_plan.inventory_notional_usd,
    }


def run_once(
    config: dict[str, Any],
    markets: list[dict[str, Any]],
    yes_live: bool,
) -> dict[str, Any]:
    params = to_params(config)
    execution = config.get("execution", {})
    live_mode = bool(execution.get("live_mode", False))
    dry_run = bool(execution.get("dry_run", True))

    # Hard safety rail: both config + CLI flag are required.
    if live_mode and not yes_live:
        return {
            "status": "error",
            "error_code": "live_confirmation_required",
            "message": "Set --yes-live to enable live execution.",
            "dry_run": True,
        }

    if live_mode and dry_run:
        return {
            "status": "error",
            "error_code": "invalid_execution_mode",
            "message": "dry_run must be false when live_mode is true.",
            "dry_run": True,
        }

    inventory = config.get("state", {}).get("inventory", {})
    inventory_notional_by_market = {
        str(k): _safe_float(v, 0.0) for k, v in inventory.items()
    }

    proposals: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    outstanding_notional = 0.0
    selected = 0

    for market in markets:
        if selected >= params.markets_max:
            break

        skip, reason = should_skip_market(market, params)
        market_id = str(market.get("market_id", "unknown"))
        if skip:
            rejected.append({"market_id": market_id, "reason": reason})
            continue

        inv = inventory_notional_by_market.get(market_id, 0.0)
        proposal = quote_market(
            market=market,
            inventory_notional=inv,
            outstanding_notional=outstanding_notional,
            p=params,
        )
        if proposal.get("status") == "quoted":
            outstanding_notional += float(proposal["quote_notional_usd"])
            proposals.append(proposal)
            selected += 1
        else:
            rejected.append(
                {
                    "market_id": market_id,
                    "reason": proposal.get("reason", "unknown"),
                    "edge_bps": proposal.get("edge_bps"),
                }
            )

    mode = "live" if live_mode and yes_live and not dry_run else "dry-run"
    return {
        "status": "ok",
        "skill": "polymarket-maker-rebate-bot",
        "mode": mode,
        "dry_run": mode != "live",
        "strategy_summary": {
            "bankroll_usd": params.bankroll_usd,
            "markets_considered": len(markets),
            "markets_quoted": len(proposals),
            "markets_skipped": len(rejected),
            "outstanding_notional_usd": round(outstanding_notional, 2),
            "min_edge_bps": params.min_edge_bps,
        },
        "quotes": proposals,
        "skips": rejected,
    }


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.run_type == "backtest":
        result = run_backtest(
            config=config,
            backtest_file=args.backtest_file,
            backtest_days_override=args.backtest_days,
        )
    else:
        markets = load_markets(config=config, markets_file=args.markets_file)
        result = run_once(config=config, markets=markets, yes_live=args.yes_live)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
