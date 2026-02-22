from __future__ import annotations

import json
from pathlib import Path

from skillforge.testing.harness import run_harness

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_quick_mode_fails_for_invalid_spec() -> None:
    invalid_spec = REPO_ROOT / "tests/schema/fixtures/invalid_missing_required.yaml"

    result = run_harness(mode="quick", spec_path=invalid_spec)

    assert result.ok is False
    assert result.mode == "quick"
    assert any(failure.code == "schema_validation_error" for failure in result.failures)


def test_smoke_mode_fails_for_broken_connector_fixture(tmp_path: Path) -> None:
    spec_path = REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml"
    broken_fixture = {
        "connectors": {
            "market_data": {
                "get": {"status": "ok", "markets": []},
            }
        }
    }
    fixture_path = tmp_path / "broken_fixture.json"
    fixture_path.write_text(json.dumps(broken_fixture), encoding="utf-8")

    result = run_harness(mode="smoke", spec_path=spec_path, fixture_path=fixture_path)

    assert result.ok is False
    assert result.mode == "smoke"
    assert any(failure.code == "missing_connector_fixture" for failure in result.failures)


def test_smoke_mode_passes_with_default_happy_fixture() -> None:
    spec_path = REPO_ROOT / "examples/browser-automation/skill.spec.yaml"

    result = run_harness(mode="smoke", spec_path=spec_path)

    assert result.ok is True
    assert result.mode == "smoke"
    assert result.failures == ()
