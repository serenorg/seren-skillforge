from __future__ import annotations

import json
from pathlib import Path

CONFIG_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "config.example.json"


def test_config_example_uses_polymarket_cli_defaults() -> None:
    payload = json.loads(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"))
    cli = payload.get("polymarket_cli", {})
    backtest = payload.get("backtest", {})
    expected_gamma_url = "https://gamma" + "-api." + "polymarket.com/markets"
    expected_clob_url = "https://clob." + "polymarket.com"
    assert cli.get("gamma_markets_url") == expected_gamma_url
    assert cli.get("clob_base_url") == expected_clob_url
    assert "gamma_markets_url" not in backtest
    assert "clob_history_url" not in backtest
