from __future__ import annotations

from pathlib import Path

import pytest

from skillforge.parser import SkillSpecParseError, SkillSpecSchemaError, parse_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_parse_invalid_yaml_raises_parse_error() -> None:
    path = REPO_ROOT / "tests/parser/fixtures/invalid_yaml.yaml"

    with pytest.raises(SkillSpecParseError) as exc_info:
        parse_spec(path)

    assert "Invalid YAML" in str(exc_info.value)


def test_parse_missing_required_fields_raises_schema_error() -> None:
    path = REPO_ROOT / "tests/schema/fixtures/invalid_missing_required.yaml"

    with pytest.raises(SkillSpecSchemaError) as exc_info:
        parse_spec(path)

    diagnostics = exc_info.value.diagnostics
    assert diagnostics
    assert any("required property" in diag.message for diag in diagnostics)


def test_parse_unknown_top_level_field_raises_schema_error() -> None:
    path = REPO_ROOT / "tests/schema/fixtures/invalid_unknown_top_level.yaml"

    with pytest.raises(SkillSpecSchemaError) as exc_info:
        parse_spec(path)

    diagnostics = exc_info.value.diagnostics
    assert diagnostics
    assert any("Additional properties are not allowed" in diag.message for diag in diagnostics)

