from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent.py"
CONFIG_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "config.example.json"


def _read_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _build_history_and_orderbooks(now_ts: int, points: int = 240) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    start_ts = now_ts - (points * 3600)
    history: list[dict[str, float]] = []
    orderbooks: list[dict[str, float]] = []
    for i in range(points):
        px = max(0.05, min(0.95, 0.5 + (0.012 * math.sin(i / 5.0)) + (0.003 * math.cos(i / 11.0))))
        ts = start_ts + (i * 3600)
        history.append({"t": ts, "p": round(px, 6)})
        orderbooks.append(
            {
                "t": ts,
                "best_bid": round(px - 0.0015, 6),
                "best_ask": round(px + 0.0015, 6),
                "bid_size_usd": 250.0,
                "ask_size_usd": 250.0,
            }
        )
    return history, orderbooks


def _base_payload(now_ts: int, telemetry_path: Path) -> dict:
    history, orderbooks = _build_history_and_orderbooks(now_ts)
    return {
        "execution": {"dry_run": True, "live_mode": False},
        "polymarket_cli": {"command": [], "timeout_seconds": 5},
        "backtest": {
            "days": 90,
            "fidelity_minutes": 60,
            "participation_rate": 0.25,
            "volatility_window_points": 24,
            "min_history_points": 120,
            "min_liquidity_usd": 0,
            "require_orderbook_history": True,
            "spread_decay_bps": 45,
            "join_best_queue_factor": 0.85,
            "off_best_queue_factor": 0.35,
            "telemetry_path": str(telemetry_path),
        },
        "strategy": {
            "bankroll_usd": 1000,
            "markets_max": 1,
            "min_seconds_to_resolution": 21600,
            "min_edge_bps": 2,
            "default_rebate_bps": 3,
            "expected_unwind_cost_bps": 1.5,
            "adverse_selection_bps": 1.0,
            "min_spread_bps": 20,
            "max_spread_bps": 60,
            "volatility_spread_multiplier": 0.0,
            "base_order_notional_usd": 40,
            "max_notional_per_market_usd": 120,
            "max_total_notional_usd": 120,
            "max_position_notional_usd": 90,
            "inventory_skew_strength_bps": 25,
        },
        "backtest_markets": [
            {
                "market_id": "TEST-STATEFUL",
                "question": "Synthetic stateful market",
                "token_id": "TEST-STATEFUL",
                "rebate_bps": 3,
                "end_ts": now_ts + (14 * 24 * 3600),
                "history": history,
                "orderbooks": orderbooks,
            }
        ],
    }


def _run_backtest(tmp_path: Path, payload: dict) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--config",
            str(config_path),
            "--run-type",
            "backtest",
            "--backtest-days",
            "90",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.stdout, result.stderr
    output = json.loads(result.stdout)
    assert result.returncode == (0 if output["status"] == "ok" else 1), result.stderr
    return output


def test_happy_path_fixture_is_successful() -> None:
    payload = _read_fixture("happy_path.json")
    assert payload["status"] == "ok"
    assert payload["skill"] == "polymarket-maker-rebate-bot"
    assert payload["mode"] == "dry-run"


def test_negative_edge_fixture_skips_all_quotes() -> None:
    payload = _read_fixture("negative_edge.json")
    assert payload["status"] == "ok"
    assert payload["strategy_summary"]["markets_quoted"] == 0
    assert payload["strategy_summary"]["markets_skipped"] >= 1


def test_live_guard_fixture_blocks_execution() -> None:
    payload = _read_fixture("live_guard.json")
    assert payload["status"] == "error"
    assert payload["error_code"] == "live_confirmation_required"


def test_backtest_run_type_returns_stateful_result_and_telemetry(tmp_path: Path) -> None:
    now_ts = int(time.time())
    telemetry_path = tmp_path / "telemetry.jsonl"
    payload = _base_payload(now_ts, telemetry_path)

    output = _run_backtest(tmp_path, payload)

    assert output["status"] == "ok"
    assert output["mode"] == "backtest"
    assert output["backtest_summary"]["source"] == "config"
    assert output["backtest_summary"]["markets_selected"] == 1
    assert output["backtest_summary"]["orderbook_mode"] == "historical"
    assert output["results"]["events"] > 0
    assert output["results"]["telemetry_path"] == str(telemetry_path)
    telemetry_lines = telemetry_path.read_text(encoding="utf-8").strip().splitlines()
    assert telemetry_lines
    first = json.loads(telemetry_lines[0])
    assert first["market_id"] == "TEST-STATEFUL"
    assert "fill_fraction" in first or first["status"] == "skipped"


def test_stateful_backtest_enforces_risk_caps_in_replay(tmp_path: Path) -> None:
    now_ts = int(time.time())
    telemetry_path = tmp_path / "risk-caps.jsonl"
    payload = _base_payload(now_ts, telemetry_path)
    payload["strategy"].update(
        {
            "base_order_notional_usd": 200,
            "max_notional_per_market_usd": 60,
            "max_total_notional_usd": 60,
            "max_position_notional_usd": 40,
        }
    )

    output = _run_backtest(tmp_path, payload)
    assert output["status"] == "ok"
    records = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    quoted = [record for record in records if record.get("status") == "quoted"]
    assert quoted
    assert all((record["bid_notional_usd"] + record["ask_notional_usd"]) <= 60.0001 for record in quoted)
    assert all(abs(record.get("inventory_notional_after_usd", 0.0)) <= 40.0001 for record in records if "inventory_notional_after_usd" in record)


def test_spread_decay_reduces_filled_notional_when_spread_widens(tmp_path: Path) -> None:
    now_ts = int(time.time())
    narrow_payload = _base_payload(now_ts, tmp_path / "narrow.jsonl")
    narrow_payload["strategy"].update({"min_spread_bps": 20, "max_spread_bps": 20, "volatility_spread_multiplier": 0.0})
    wide_payload = _base_payload(now_ts, tmp_path / "wide.jsonl")
    wide_payload["strategy"].update({"min_spread_bps": 120, "max_spread_bps": 120, "volatility_spread_multiplier": 0.0})

    narrow_output = _run_backtest(tmp_path / "narrow", narrow_payload)
    wide_output = _run_backtest(tmp_path / "wide", wide_payload)

    assert narrow_output["status"] == "ok"
    assert wide_output["status"] == "ok"
    assert wide_output["results"]["filled_notional_usd"] < narrow_output["results"]["filled_notional_usd"]


def test_backtest_requires_orderbook_history_when_configured(tmp_path: Path) -> None:
    now_ts = int(time.time())
    telemetry_path = tmp_path / "missing-books.jsonl"
    payload = _base_payload(now_ts, telemetry_path)
    payload["backtest_markets"][0].pop("orderbooks")

    output = _run_backtest(tmp_path, payload)

    assert output["status"] == "error"
    assert output["error_code"] == "backtest_data_load_failed"
    assert "historical order-book snapshots" in output["message"]


def test_live_backtest_uses_polymarket_cli_command(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_polymarket_cli.py"
    history, _ = _build_history_and_orderbooks(int(time.time()), points=160)
    fake_cli.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "action = sys.argv[1]",
                "if action == 'markets':",
                "    print(json.dumps([{'id': 'CLI-1', 'question': 'CLI market', 'clobTokenIds': ['CLI-TOKEN'], 'liquidity': 250000, 'endDate': '2030-01-01T00:00:00Z', 'volume24hr': 99999, 'rebate_bps': 3}]))",
                "elif action == 'prices-history':",
                f"    print(json.dumps({{'history': {json.dumps(history)}}}))",
                "elif action == 'book':",
                "    print(json.dumps({'bids': [{'price': 0.498, 'size': 300}], 'asks': [{'price': 0.502, 'size': 300}]}))",
                "else:",
                "    raise SystemExit(1)",
            ]
        ),
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)

    payload = {
        "execution": {"dry_run": True, "live_mode": False},
        "polymarket_cli": {"command": [sys.executable, str(fake_cli)], "timeout_seconds": 5},
        "backtest": {
            "days": 90,
            "fidelity_minutes": 60,
            "participation_rate": 0.2,
            "volatility_window_points": 24,
            "min_history_points": 100,
            "min_liquidity_usd": 0,
            "markets_fetch_limit": 1,
            "require_orderbook_history": False
        },
        "strategy": {
            "bankroll_usd": 1000,
            "markets_max": 1,
            "min_seconds_to_resolution": 21600,
            "min_edge_bps": 2,
            "default_rebate_bps": 3,
            "expected_unwind_cost_bps": 1.5,
            "adverse_selection_bps": 1.0,
            "min_spread_bps": 20,
            "max_spread_bps": 40,
            "volatility_spread_multiplier": 0.0,
            "base_order_notional_usd": 25,
            "max_notional_per_market_usd": 125,
            "max_total_notional_usd": 125,
            "max_position_notional_usd": 125,
            "inventory_skew_strength_bps": 25,
        },
    }

    output = _run_backtest(tmp_path, payload)

    assert output["status"] == "ok"
    assert output["backtest_summary"]["source"] == "live-polymarket-cli"
    assert output["backtest_summary"]["orderbook_mode"] == "synthetic-from-cli-book"


def test_config_example_uses_polymarket_cli_defaults() -> None:
    payload = json.loads(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"))
    cli = payload.get("polymarket_cli", {})
    backtest = payload.get("backtest", {})
    expected_gamma_url = "https://gamma" + "-api." + "polymarket.com/markets"
    expected_clob_url = "https://clob." + "polymarket.com"
    assert cli.get("gamma_markets_url") == expected_gamma_url
    assert cli.get("clob_base_url") == expected_clob_url
    assert "clob_history_url" not in backtest
    assert "gamma_markets_url" not in backtest
