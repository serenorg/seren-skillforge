from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from skillforge.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    (path / "README.md").write_text("# temp repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=SkillForge Test",
            "-c",
            "user.email=skillforge@example.com",
            "commit",
            "-m",
            "init",
        ],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_release_generates_and_publishes_from_spec_metadata(tmp_path: Path) -> None:
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)

    result = runner.invoke(
        app,
        [
            "release",
            "--spec",
            str(REPO_ROOT / "examples/browser-automation/skill.spec.yaml"),
            "--target",
            str(target_repo),
        ],
    )

    assert result.exit_code == 0, result.output
    published_dir = target_repo / "seren" / "browser-automation"
    assert (published_dir / "SKILL.md").exists()
    assert (published_dir / "requirements.txt").exists()
    assert (published_dir / "scripts" / "agent.py").exists()
    assert "Released" in result.output


def test_release_requires_publish_metadata(tmp_path: Path) -> None:
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)

    result = runner.invoke(
        app,
        [
            "release",
            "--spec",
            str(REPO_ROOT / "examples/minimal/skill.spec.yaml"),
            "--target",
            str(target_repo),
        ],
    )

    assert result.exit_code != 0
    assert "missing publish metadata" in result.output
