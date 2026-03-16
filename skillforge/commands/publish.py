from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import typer

REQUIRED_SOURCE_FILES = (
    Path("SKILL.md"),
    Path(".env.example"),
    Path("config.example.json"),
    Path("requirements.txt"),
    Path("scripts/agent.py"),
    Path("tests/test_smoke.py"),
)
ALLOWED_CHANGE_TYPES = {"feat", "fix", "docs", "chore", "refactor", "test"}
CONVENTIONAL_SUBJECT_RE = re.compile(
    r"^(feat|fix|docs|chore|refactor|test)(\([^)]+\))?: .+"
)


class PublishError(Exception):
    """Raised when publish cannot complete safely."""


@dataclass
class ShellAdapter:
    def run(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _ensure_source_layout(source: Path) -> None:
    if not source.exists() or not source.is_dir():
        raise PublishError(f"Source directory does not exist: {source}")
    missing = [
        relative.as_posix()
        for relative in REQUIRED_SOURCE_FILES
        if not (source / relative).exists()
    ]
    if missing:
        raise PublishError(
            "Source directory is missing required generated artifacts: " + ", ".join(missing)
        )


def _ensure_target_repo(target: Path) -> None:
    if not target.exists() or not target.is_dir():
        raise PublishError(f"Target repository path does not exist: {target}")
    if not (target / ".git").exists():
        raise PublishError(
            f"Target path is not a git repository clone (missing .git): {target}"
        )


def _require_gh_cli(create_pr: bool) -> None:
    if create_pr and shutil.which("gh") is None:
        raise PublishError("gh CLI is required for --create-pr but was not found in PATH.")


def _copy_skill_tree(*, source: Path, destination: Path, force: bool) -> Path:
    if destination.exists():
        if not force:
            raise PublishError(
                f"Destination {destination} already exists. Re-run with --force to overwrite."
            )
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination


def _require_shell_success(
    result: subprocess.CompletedProcess[str],
    *,
    action: str,
) -> None:
    if result.returncode == 0:
        return
    details = result.stderr.strip() or result.stdout.strip() or "no output"
    raise PublishError(f"{action} failed: {details}")


def _default_branch_name(org: str, name: str) -> str:
    ts = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
    return f"skillforge/publish-{org}-{name}-{ts}"


def _normalize_change_type(change_type: str) -> str:
    normalized = change_type.strip().lower()
    if normalized not in ALLOWED_CHANGE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_CHANGE_TYPES))
        raise PublishError(
            f"Unsupported --change-type '{change_type}'. Allowed values: {allowed}"
        )
    return normalized


def _semantic_prefix(change_type: str, scope: str | None) -> str:
    normalized_type = _normalize_change_type(change_type)
    normalized_scope = (scope or "").strip()
    if normalized_scope:
        return f"{normalized_type}({normalized_scope})"
    return normalized_type


def _require_conventional_subject(subject: str, *, label: str) -> None:
    normalized = subject.strip()
    if CONVENTIONAL_SUBJECT_RE.match(normalized):
        return
    allowed = ", ".join(sorted(ALLOWED_CHANGE_TYPES))
    raise PublishError(
        f"{label} must follow conventional format '<type>(<scope>)?: <summary>' "
        f"with type in [{allowed}]. Got: {subject!r}"
    )


def _default_commit_message(
    *,
    change_type: str,
    scope: str | None,
    org: str,
    name: str,
) -> str:
    prefix = _semantic_prefix(change_type, scope)
    return f"{prefix}: publish skill {org}/{name} via SkillForge"


def _default_pr_title(
    *,
    change_type: str,
    scope: str | None,
    org: str,
    name: str,
) -> str:
    prefix = _semantic_prefix(change_type, scope)
    return f"{prefix}: publish skill {org}/{name}"


def _create_pr(
    *,
    shell: ShellAdapter,
    target: Path,
    org: str,
    name: str,
    base_branch: str,
    branch_name: str | None,
    change_type: str,
    scope: str | None,
) -> str:
    branch = branch_name or _default_branch_name(org, name)
    skill_path = f"{org}/{name}"
    commit_message = _default_commit_message(
        change_type=change_type,
        scope=scope,
        org=org,
        name=name,
    )
    pr_title = _default_pr_title(
        change_type=change_type,
        scope=scope,
        org=org,
        name=name,
    )
    _require_conventional_subject(commit_message, label="Commit message")
    _require_conventional_subject(pr_title, label="PR title")

    checkout = shell.run(["git", "checkout", "-b", branch], cwd=target)
    if checkout.returncode != 0:
        fallback = shell.run(["git", "checkout", branch], cwd=target)
        _require_shell_success(fallback, action=f"git checkout {branch}")

    add = shell.run(["git", "add", skill_path], cwd=target)
    _require_shell_success(add, action=f"git add {skill_path}")

    diff = shell.run(["git", "diff", "--cached", "--quiet"], cwd=target)
    if diff.returncode == 0:
        raise PublishError(
            f"No changes detected in {skill_path}. Nothing to include in a pull request."
        )
    if diff.returncode not in (0, 1):
        _require_shell_success(diff, action="git diff --cached --quiet")

    commit = shell.run(
        [
            "git",
            "-c",
            "user.name=SkillForge Bot",
            "-c",
            "user.email=skillforge-bot@example.com",
            "commit",
            "-m",
            commit_message,
        ],
        cwd=target,
    )
    _require_shell_success(commit, action="git commit")

    push = shell.run(["git", "push", "-u", "origin", branch], cwd=target)
    _require_shell_success(push, action=f"git push -u origin {branch}")

    pr = shell.run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            pr_title,
            "--body",
            f"Automated publish for `{org}/{name}` generated by SkillForge.",
            "--base",
            base_branch,
            "--head",
            branch,
        ],
        cwd=target,
    )
    _require_shell_success(pr, action="gh pr create")
    return pr.stdout.strip() or "PR created"


def run(
    *,
    source: Path,
    target: Path,
    org: str,
    name: str,
    force: bool,
    create_pr: bool,
    base_branch: str,
    branch_name: str | None,
    change_type: str,
    scope: str | None,
    shell: ShellAdapter | None = None,
) -> tuple[Path, str | None]:
    _ensure_source_layout(source)
    _ensure_target_repo(target)
    _require_gh_cli(create_pr)
    _normalize_change_type(change_type)

    destination = _copy_skill_tree(
        source=source,
        destination=target / org / name,
        force=force,
    )

    if not create_pr:
        return destination, None

    shell_adapter = shell or ShellAdapter()
    pr_url = _create_pr(
        shell=shell_adapter,
        target=target,
        org=org,
        name=name,
        base_branch=base_branch,
        branch_name=branch_name,
        change_type=change_type,
        scope=scope,
    )
    return destination, pr_url


def command(
    source: Path = typer.Option(
        Path("."),
        "--source",
        help="Directory containing generated skill artifacts to publish.",
    ),
    target: Path = typer.Option(
        ...,
        "--target",
        help="Path to local seren-skills git clone.",
    ),
    org: str = typer.Option(..., "--org", help="Target org directory in seren-skills."),
    name: str = typer.Option(..., "--name", help="Target skill directory name."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow overwriting an existing target skill directory.",
    ),
    create_pr: bool = typer.Option(
        False,
        "--create-pr",
        help="Create a pull request via gh after publishing.",
    ),
    base_branch: str = typer.Option(
        "main",
        "--base-branch",
        help="Base branch to target when creating a pull request.",
    ),
    branch_name: str | None = typer.Option(
        None,
        "--branch-name",
        help="Optional branch name override for PR creation.",
    ),
    change_type: str = typer.Option(
        "feat",
        "--change-type",
        help=(
            "Conventional type for commit message and PR title "
            "(feat|fix|docs|chore|refactor|test)."
        ),
    ),
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="Optional conventional scope for commit message and PR title.",
    ),
) -> None:
    try:
        destination, pr_url = run(
            source=source,
            target=target,
            org=org,
            name=name,
            force=force,
            create_pr=create_pr,
            base_branch=base_branch,
            branch_name=branch_name,
            change_type=change_type,
            scope=scope,
        )
    except PublishError as exc:
        typer.echo(f"FAIL [publish] {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(f"Published {source} -> {destination}")
    if pr_url:
        typer.echo(f"Opened PR: {pr_url}")
