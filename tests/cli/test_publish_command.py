from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from skillforge.cli import app
from skillforge.commands import publish as publish_command

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


def _create_generated_source(base_dir: Path) -> Path:
    source = base_dir / "generated"
    (source / "scripts").mkdir(parents=True)
    (source / "tests" / "fixtures").mkdir(parents=True)

    (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (source / "scripts" / "agent.py").write_text("print('ok')\n", encoding="utf-8")
    (source / ".env.example").write_text("SEREN_API_KEY=\n", encoding="utf-8")
    (source / "config.example.json").write_text("{}\n", encoding="utf-8")
    (source / "tests" / "test_smoke.py").write_text("def test_smoke(): pass\n", encoding="utf-8")
    (source / "tests" / "fixtures" / "happy_path.json").write_text(
        '{"status":"ok"}\n',
        encoding="utf-8",
    )
    return source


def test_publish_copies_generated_skill_into_target_repo(tmp_path: Path) -> None:
    source = _create_generated_source(tmp_path)
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)

    result = runner.invoke(
        app,
        [
            "publish",
            "--source",
            str(source),
            "--target",
            str(target_repo),
            "--org",
            "curve",
            "--name",
            "gauge-reward-screener",
        ],
    )

    assert result.exit_code == 0, result.output
    published_dir = target_repo / "curve" / "gauge-reward-screener"
    assert (published_dir / "SKILL.md").exists()
    assert (published_dir / "scripts" / "agent.py").exists()
    assert "Published" in result.output


def test_publish_requires_force_to_overwrite_existing_output(tmp_path: Path) -> None:
    source = _create_generated_source(tmp_path)
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)
    args = [
        "publish",
        "--source",
        str(source),
        "--target",
        str(target_repo),
        "--org",
        "curve",
        "--name",
        "gauge-reward-screener",
    ]

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output

    (source / "SKILL.md").write_text("# Updated Skill\n", encoding="utf-8")

    second = runner.invoke(app, args)
    assert second.exit_code != 0
    assert "already exists" in second.output

    forced = runner.invoke(app, [*args, "--force"])
    assert forced.exit_code == 0, forced.output
    assert (
        target_repo / "curve" / "gauge-reward-screener" / "SKILL.md"
    ).read_text(encoding="utf-8") == "# Updated Skill\n"


def test_publish_create_pr_fails_clearly_when_gh_missing(tmp_path: Path) -> None:
    source = _create_generated_source(tmp_path)
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)

    result = runner.invoke(
        app,
        [
            "publish",
            "--source",
            str(source),
            "--target",
            str(target_repo),
            "--org",
            "curve",
            "--name",
            "gauge-reward-screener",
            "--create-pr",
        ],
        env={"PATH": ""},
    )

    assert result.exit_code != 0
    assert "gh CLI" in result.output


class _RecordingShell(publish_command.ShellAdapter):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:4] == ["git", "diff", "--cached", "--quiet"]:
            # non-zero means changes are staged
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")
        if args[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="https://github.com/serenorg/seren-skills/pull/1\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def test_publish_create_pr_uses_conventional_pr_and_commit_messages(tmp_path: Path) -> None:
    source = _create_generated_source(tmp_path)
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)

    shell = _RecordingShell()
    destination, pr_url = publish_command.run(
        source=source,
        target=target_repo,
        org="curve",
        name="gauge-reward-screener",
        force=False,
        create_pr=True,
        base_branch="main",
        branch_name="skillforge/test-pr-title",
        change_type="feat",
        scope=None,
        shell=shell,
    )

    assert destination.exists()
    assert pr_url == "https://github.com/serenorg/seren-skills/pull/1"

    commit_call = next(call for call in shell.calls if call[:1] == ["git"] and "commit" in call)
    assert commit_call[-1] == "feat: publish skill curve/gauge-reward-screener via SkillForge"

    pr_call = next(call for call in shell.calls if call[:3] == ["gh", "pr", "create"])
    title_index = pr_call.index("--title") + 1
    assert pr_call[title_index] == "feat: publish skill curve/gauge-reward-screener"


def test_publish_rejects_unknown_conventional_change_type(tmp_path: Path) -> None:
    source = _create_generated_source(tmp_path)
    target_repo = tmp_path / "seren-skills"
    target_repo.mkdir()
    _init_git_repo(target_repo)

    result = runner.invoke(
        app,
        [
            "publish",
            "--source",
            str(source),
            "--target",
            str(target_repo),
            "--org",
            "curve",
            "--name",
            "gauge-reward-screener",
            "--change-type",
            "perf",
        ],
    )

    assert result.exit_code != 0
    assert "Unsupported --change-type" in result.output
