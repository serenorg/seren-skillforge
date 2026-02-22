from __future__ import annotations

from pathlib import Path

import pytest

from skillforge.parser import parse_spec
from skillforge.validator import validate_semantics

REPO_ROOT = Path(__file__).resolve().parents[2]


def _diagnostic_codes(path: Path) -> set[str]:
    parsed = parse_spec(path)
    result = validate_semantics(parsed.model)
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_valid_fixture_passes_semantic_checks() -> None:
    path = REPO_ROOT / "tests/validator/fixtures/valid_api_skill.yaml"

    parsed = parse_spec(path)
    result = validate_semantics(parsed.model)

    assert result.ok
    assert result.diagnostics == []


@pytest.mark.parametrize(
    ("fixture", "expected_code"),
    [
        ("invalid_connector_reference.yaml", "missing_connector"),
        ("invalid_duplicate_step_ids.yaml", "duplicate_step_id"),
        ("invalid_step_reference_future.yaml", "invalid_step_reference"),
        ("invalid_risk_missing_policies.yaml", "missing_policies"),
        ("invalid_risk_missing_budget_caps.yaml", "risk_budget_cap_required"),
        ("invalid_guessed_rpc_slug.yaml", "guessed_publisher_slug"),
    ],
)
def test_invalid_fixtures_produce_expected_semantic_codes(
    fixture: str,
    expected_code: str,
) -> None:
    path = REPO_ROOT / "tests/validator/fixtures" / fixture

    assert expected_code in _diagnostic_codes(path)


def test_allowlist_can_permit_intentional_guessed_slug() -> None:
    path = REPO_ROOT / "tests/validator/fixtures/invalid_guessed_rpc_slug.yaml"
    parsed = parse_spec(path)
    result = validate_semantics(
        parsed.model,
        allow_guessed_publisher_slugs={"rpc-ethereum"},
    )
    assert "guessed_publisher_slug" not in {diagnostic.code for diagnostic in result.diagnostics}
