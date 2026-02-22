from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from skillforge.cli import app

runner = CliRunner()


def _spec_path(base: Path, org: str, name: str) -> Path:
    return base / org / name / "skill.spec.yaml"


def test_init_creates_spec_from_archetype(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--archetype",
            "api-worker",
            "--org",
            "curve",
            "--name",
            "gauge-reward-screener",
            "--target",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    output_file = _spec_path(tmp_path, "curve", "gauge-reward-screener")
    assert output_file.exists()

    generated = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    assert generated["skill"] == "gauge-reward-screener"
    assert generated["publish"]["org"] == "curve"
    assert generated["publish"]["slug"] == "gauge-reward-screener"


def test_init_fails_for_unknown_archetype(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--archetype",
            "not-real",
            "--org",
            "curve",
            "--name",
            "gauge-reward-screener",
            "--target",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Unknown archetype" in result.output


def test_init_requires_force_to_overwrite_existing_file(tmp_path: Path) -> None:
    args = [
        "init",
        "--archetype",
        "guide",
        "--org",
        "curve",
        "--name",
        "liquidity-guide",
        "--target",
        str(tmp_path),
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, args)
    assert second.exit_code != 0
    assert "already exists" in second.output

    forced = runner.invoke(app, [*args, "--force"])
    assert forced.exit_code == 0, forced.output

