from __future__ import annotations

from pathlib import Path

import yaml

from skillforge.testing.harness import run_harness

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "examples" / "migrations"
MIGRATION_SPECS = [
    MIGRATIONS_DIR / "browser-automation" / "skill.spec.yaml",
    MIGRATIONS_DIR / "polymarket-trader" / "skill.spec.yaml",
    MIGRATIONS_DIR / "job-seeker" / "skill.spec.yaml",
    MIGRATIONS_DIR / "revoke-cash" / "skill.spec.yaml",
]


def test_migration_specs_pass_quick_and_smoke() -> None:
    for spec_path in MIGRATION_SPECS:
        quick = run_harness(mode="quick", spec_path=spec_path)
        smoke = run_harness(mode="smoke", spec_path=spec_path)

        assert quick.ok, f"quick failed for {spec_path}: {quick.failures}"
        assert smoke.ok, f"smoke failed for {spec_path}: {smoke.failures}"


def test_trader_migration_requires_explicit_risk_policies(tmp_path: Path) -> None:
    trader_spec = MIGRATIONS_DIR / "polymarket-trader" / "skill.spec.yaml"
    payload = yaml.safe_load(trader_spec.read_text(encoding="utf-8"))
    payload.pop("policies", None)

    broken_spec = tmp_path / "missing_policies.spec.yaml"
    broken_spec.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = run_harness(mode="quick", spec_path=broken_spec)
    assert result.ok is False
    assert any(failure.code == "missing_policies" for failure in result.failures)
