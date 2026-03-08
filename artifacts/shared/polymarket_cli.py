#!/usr/bin/env python3
"""Shared Polymarket CLI wrapper for local skill runtimes."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
DEFAULT_CLOB_BASE_URL = "https://clob.polymarket.com"
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class PolymarketCliConfig:
    command: tuple[str, ...]
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    gamma_markets_url: str = DEFAULT_GAMMA_MARKETS_URL
    clob_base_url: str = DEFAULT_CLOB_BASE_URL


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str) -> str:
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


def _parse_command(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        parsed = tuple(shlex.split(value))
        return parsed if parsed else default_cli_command()
    if isinstance(value, list):
        parsed = tuple(_safe_str(item, "").strip() for item in value if _safe_str(item, "").strip())
        return parsed if parsed else default_cli_command()
    return default_cli_command()


def shared_cli_path() -> Path:
    return Path(__file__).resolve()


def default_cli_command() -> tuple[str, ...]:
    return (sys.executable, str(shared_cli_path()))


def load_polymarket_cli_config(raw: dict[str, Any] | None) -> PolymarketCliConfig:
    payload = raw if isinstance(raw, dict) else {}
    return PolymarketCliConfig(
        command=_parse_command(payload.get("command")),
        timeout_seconds=max(1, _safe_int(payload.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS)),
        gamma_markets_url=_safe_str(payload.get("gamma_markets_url"), DEFAULT_GAMMA_MARKETS_URL),
        clob_base_url=_safe_str(payload.get("clob_base_url"), DEFAULT_CLOB_BASE_URL).rstrip("/"),
    )


def _http_get_json(url: str, timeout_seconds: int) -> dict[str, Any] | list[Any]:
    request = Request(
        url,
        headers={
            "User-Agent": "seren-polymarket-cli/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _bool_flag(name: str, enabled: bool) -> list[str]:
    if enabled:
        return [name]
    return []


def run_polymarket_cli_json(
    config: PolymarketCliConfig,
    action: str,
    *,
    args: Sequence[str] | None = None,
) -> dict[str, Any] | list[Any]:
    command = list(config.command)
    command.append(action)
    command.extend(args or [])
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=config.timeout_seconds,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"CLI exited with {result.returncode}"
        raise RuntimeError(f"Polymarket CLI {action!r} failed: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Polymarket CLI {action!r} returned invalid JSON.") from exc


def cli_get_markets(
    config: PolymarketCliConfig,
    *,
    limit: int,
    offset: int = 0,
    order: str = "volume24hr",
    ascending: bool = False,
    active: bool = True,
    closed: bool = False,
) -> dict[str, Any] | list[Any]:
    return run_polymarket_cli_json(
        config,
        "markets",
        args=[
            "--limit",
            str(limit),
            "--offset",
            str(offset),
            "--order",
            order,
            "--gamma-markets-url",
            config.gamma_markets_url,
            *_bool_flag("--ascending", ascending),
            *_bool_flag("--active", active),
            *_bool_flag("--closed", closed),
            "--timeout-seconds",
            str(config.timeout_seconds),
        ],
    )


def cli_get_prices_history(
    config: PolymarketCliConfig,
    *,
    market: str,
    interval: str,
    fidelity: int,
) -> dict[str, Any] | list[Any]:
    return run_polymarket_cli_json(
        config,
        "prices-history",
        args=[
            "--market",
            market,
            "--interval",
            interval,
            "--fidelity",
            str(fidelity),
            "--clob-base-url",
            config.clob_base_url,
            "--timeout-seconds",
            str(config.timeout_seconds),
        ],
    )


def cli_get_book(config: PolymarketCliConfig, *, token_id: str) -> dict[str, Any] | list[Any]:
    return run_polymarket_cli_json(
        config,
        "book",
        args=[
            "--token-id",
            token_id,
            "--clob-base-url",
            config.clob_base_url,
            "--timeout-seconds",
            str(config.timeout_seconds),
        ],
    )


def cli_get_midpoint(config: PolymarketCliConfig, *, token_id: str) -> dict[str, Any] | list[Any]:
    return run_polymarket_cli_json(
        config,
        "midpoint",
        args=[
            "--token-id",
            token_id,
            "--clob-base-url",
            config.clob_base_url,
            "--timeout-seconds",
            str(config.timeout_seconds),
        ],
    )


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket CLI JSON wrapper.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    markets = subparsers.add_parser("markets", help="Fetch Polymarket markets.")
    markets.add_argument("--limit", type=int, default=100)
    markets.add_argument("--offset", type=int, default=0)
    markets.add_argument("--order", default="volume24hr")
    markets.add_argument("--ascending", action="store_true")
    markets.add_argument("--active", action="store_true")
    markets.add_argument("--closed", action="store_true")
    markets.add_argument("--gamma-markets-url", default=DEFAULT_GAMMA_MARKETS_URL)
    markets.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    history = subparsers.add_parser("prices-history", help="Fetch Polymarket price history.")
    history.add_argument("--market", required=True)
    history.add_argument("--interval", default="max")
    history.add_argument("--fidelity", type=int, default=60)
    history.add_argument("--clob-base-url", default=DEFAULT_CLOB_BASE_URL)
    history.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    book = subparsers.add_parser("book", help="Fetch a Polymarket order book snapshot.")
    book.add_argument("--token-id", required=True)
    book.add_argument("--clob-base-url", default=DEFAULT_CLOB_BASE_URL)
    book.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    midpoint = subparsers.add_parser("midpoint", help="Fetch a Polymarket midpoint.")
    midpoint.add_argument("--token-id", required=True)
    midpoint.add_argument("--clob-base-url", default=DEFAULT_CLOB_BASE_URL)
    midpoint.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    return parser.parse_args()


def _run_action(args: argparse.Namespace) -> dict[str, Any] | list[Any]:
    timeout_seconds = max(1, int(args.timeout_seconds))
    if args.action == "markets":
        query = urlencode(
            {
                "limit": args.limit,
                "offset": args.offset,
                "order": args.order,
                "ascending": "true" if args.ascending else "false",
                "active": "true" if args.active else "false",
                "closed": "true" if args.closed else "false",
            }
        )
        return _http_get_json(f"{args.gamma_markets_url}?{query}", timeout_seconds)
    if args.action == "prices-history":
        query = urlencode(
            {
                "market": args.market,
                "interval": args.interval,
                "fidelity": args.fidelity,
            }
        )
        return _http_get_json(f"{args.clob_base_url}/prices-history?{query}", timeout_seconds)
    if args.action == "book":
        query = urlencode({"token_id": args.token_id})
        return _http_get_json(f"{args.clob_base_url}/book?{query}", timeout_seconds)
    if args.action == "midpoint":
        query = urlencode({"token_id": args.token_id})
        return _http_get_json(f"{args.clob_base_url}/midpoint?{query}", timeout_seconds)
    raise RuntimeError(f"Unsupported action: {args.action}")


def main() -> int:
    args = _parse_cli_args()
    payload = _run_action(args)
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
