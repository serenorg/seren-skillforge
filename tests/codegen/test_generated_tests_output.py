from __future__ import annotations

import json
from pathlib import Path

from skillforge.codegen.generated_tests import (
    render_fixture_payloads,
    render_smoke_test,
    write_generated_tests,
)
from skillforge.parser import parse_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_render_smoke_test_includes_required_assertions() -> None:
    spec = parse_spec(REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml").ir
    generated = render_smoke_test(spec)

    assert "test_happy_path_fixture_is_successful" in generated
    assert "test_connector_failure_fixture_has_error_code" in generated
    assert "test_policy_violation_fixture_has_error_code" in generated
    assert "test_dry_run_fixture_blocks_live_execution" in generated
    assert 'payload["skill"] == "polymarket-trader"' in generated


def test_render_fixture_payloads_include_happy_and_failure_cases() -> None:
    spec = parse_spec(REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml").ir
    fixtures = render_fixture_payloads(spec)

    assert set(fixtures.keys()) == {
        "connector_failure.json",
        "dry_run_guard.json",
        "happy_path.json",
        "policy_violation.json",
    }

    happy = json.loads(fixtures["happy_path.json"])
    connector_failure = json.loads(fixtures["connector_failure.json"])
    policy_violation = json.loads(fixtures["policy_violation.json"])
    dry_run_guard = json.loads(fixtures["dry_run_guard.json"])

    assert happy["status"] == "ok"
    assert connector_failure["error_code"] == "connector_failure"
    assert policy_violation["error_code"] == "policy_violation"
    assert dry_run_guard["blocked_action"] == "live_execution"


def test_write_generated_tests_outputs_expected_file_set(tmp_path: Path) -> None:
    spec = parse_spec(REPO_ROOT / "examples/browser-automation/skill.spec.yaml").ir
    written_paths = write_generated_tests(spec, tmp_path)

    relative_paths = {path.relative_to(tmp_path).as_posix() for path in written_paths}
    assert relative_paths == {
        "tests/test_smoke.py",
        "tests/fixtures/happy_path.json",
        "tests/fixtures/connector_failure.json",
        "tests/fixtures/policy_violation.json",
        "tests/fixtures/dry_run_guard.json",
    }

    smoke_test = (tmp_path / "tests/test_smoke.py").read_text(encoding="utf-8")
    assert "browser-automation" in smoke_test

