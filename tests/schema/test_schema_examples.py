from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "skillforge/schema/skillspec_v0.json"
VALID_EXAMPLES = [
    REPO_ROOT / "examples/minimal/skill.spec.yaml",
    REPO_ROOT / "examples/browser-automation/skill.spec.yaml",
    REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml",
]
INVALID_FIXTURES = [
    REPO_ROOT / "tests/schema/fixtures/invalid_missing_required.yaml",
    REPO_ROOT / "tests/schema/fixtures/invalid_unknown_top_level.yaml",
]


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"Expected mapping YAML in {path}"
    return parsed


def test_valid_examples_match_schema() -> None:
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    for example in VALID_EXAMPLES:
        data = _load_yaml(example)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        assert not errors, f"{example} failed schema checks: {[error.message for error in errors]}"


def test_invalid_fixtures_fail_schema() -> None:
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    failing_messages: list[str] = []
    for fixture in INVALID_FIXTURES:
        data = _load_yaml(fixture)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        assert errors, f"{fixture} unexpectedly passed schema validation"
        failing_messages.extend(error.message for error in errors)

    joined = " | ".join(failing_messages)
    assert "is a required property" in joined
    assert "Additional properties are not allowed" in joined

