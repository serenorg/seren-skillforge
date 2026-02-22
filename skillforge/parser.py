from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from jsonschema.exceptions import ValidationError

from skillforge.ir import NormalizedSkillSpec, to_ir
from skillforge.models import SkillSpecModel

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "skillspec_v0.json"


@dataclass(frozen=True)
class ParserDiagnostic:
    path: str
    message: str


@dataclass(frozen=True)
class ParseResult:
    source_path: Path
    raw: dict[str, Any]
    model: SkillSpecModel
    ir: NormalizedSkillSpec


class SkillSpecParseError(Exception):
    def __init__(self, message: str, diagnostics: list[ParserDiagnostic] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or []


class SkillSpecSchemaError(SkillSpecParseError):
    pass


def _format_error_path(error: ValidationError) -> str:
    if not error.path:
        return "<root>"
    return ".".join(str(part) for part in error.path)


@lru_cache(maxsize=1)
def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SkillSpecParseError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SkillSpecParseError(f"Expected top-level YAML mapping in {path}")
    return parsed


def validate_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[ParserDiagnostic]:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    return [
        ParserDiagnostic(path=_format_error_path(error), message=error.message) for error in errors
    ]


def parse_spec(path: Path) -> ParseResult:
    raw = load_yaml(path)
    diagnostics = validate_schema(raw, load_schema())
    if diagnostics:
        raise SkillSpecSchemaError(
            f"Schema validation failed for {path}", diagnostics=diagnostics
        )

    try:
        model = SkillSpecModel.model_validate(raw)
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise SkillSpecParseError(f"Failed to map parsed spec to model: {exc}") from exc

    return ParseResult(
        source_path=path,
        raw=raw,
        model=model,
        ir=to_ir(model),
    )

