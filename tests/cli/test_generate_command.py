from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import skillforge.commands.resolve_publishers as resolve_module
from skillforge.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_generate_writes_expected_artifacts(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(REPO_ROOT / "examples/browser-automation/skill.spec.yaml"),
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    expected_paths = {
        "SKILL.md",
        "scripts/agent.py",
        ".env.example",
        "config.example.json",
        "tests/test_smoke.py",
        "tests/fixtures/happy_path.json",
        "tests/fixtures/connector_failure.json",
        "tests/fixtures/policy_violation.json",
        "tests/fixtures/dry_run_guard.json",
    }
    existing_paths = {
        str(path.relative_to(tmp_path).as_posix())
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert expected_paths <= existing_paths
    assert "Generated" in result.output


def test_generate_check_fails_when_outputs_are_stale(tmp_path: Path) -> None:
    spec = REPO_ROOT / "examples/browser-automation/skill.spec.yaml"

    initial = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(spec),
            "--out",
            str(tmp_path),
        ],
    )
    assert initial.exit_code == 0, initial.output

    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# stale file\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(spec),
            "--out",
            str(tmp_path),
            "--check",
        ],
    )

    assert result.exit_code != 0
    assert "stale" in result.output.lower()
    assert "SKILL.md" in result.output


def test_generate_check_passes_when_outputs_match(tmp_path: Path) -> None:
    spec = REPO_ROOT / "examples/minimal/skill.spec.yaml"
    generated = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(spec),
            "--out",
            str(tmp_path),
        ],
    )
    assert generated.exit_code == 0, generated.output

    check = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(spec),
            "--out",
            str(tmp_path),
            "--check",
        ],
    )

    assert check.exit_code == 0, check.output
    assert "up-to-date" in check.output.lower()


def test_generate_with_resolve_publishers_fails_when_stale_slugs_detected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = REPO_ROOT / "examples/minimal/skill.spec.yaml"

    def _fake_resolve(**_kwargs: object) -> resolve_module.ResolveResult:
        return resolve_module.ResolveResult(
            ok=True,
            catalog_size=1,
            changes=(
                resolve_module.ResolveChange(
                    connector="rpc_ethereum",
                    from_slug="rpc-ethereum",
                    to_slug="seren-ethereum",
                    source="rpc_guess",
                ),
            ),
            issues=(),
            wrote=False,
        )

    monkeypatch.setattr(resolve_module, "run", _fake_resolve)

    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(spec),
            "--out",
            str(tmp_path),
            "--resolve-publishers",
        ],
    )

    assert result.exit_code != 0
    assert "Run `skillforge resolve-publishers --write` first." in result.output
