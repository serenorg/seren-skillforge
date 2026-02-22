from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from skillforge.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_validate_passes_for_valid_spec() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            "--spec",
            str(REPO_ROOT / "examples/minimal/skill.spec.yaml"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "PASS [validate]" in result.output


def test_validate_fails_for_invalid_spec() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            "--spec",
            str(REPO_ROOT / "tests/schema/fixtures/invalid_missing_required.yaml"),
        ],
    )

    assert result.exit_code != 0
    assert "FAIL [validate]" in result.output
    assert "schema_validation_error" in result.output
