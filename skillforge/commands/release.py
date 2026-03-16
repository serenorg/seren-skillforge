from __future__ import annotations

import tempfile
from pathlib import Path

import typer

from skillforge.commands import generate as generate_command
from skillforge.commands import publish as publish_command
from skillforge.parser import SkillSpecParseError, parse_spec
from skillforge.publisher_catalog import DEFAULT_GATEWAY_URL


class ReleaseError(Exception):
    """Raised when release cannot complete safely."""


def _load_publish_target(spec: Path) -> tuple[str, str]:
    try:
        parsed = parse_spec(spec)
    except SkillSpecParseError as exc:
        lines = [f"Failed to parse spec: {exc}"]
        lines.extend(f"[{item.path}] {item.message}" for item in exc.diagnostics)
        raise ReleaseError("\n".join(lines)) from exc

    publish = parsed.ir.publish
    if publish is None:
        raise ReleaseError(
            f"Spec {spec} is missing publish metadata. Add publish.org and publish.slug."
        )
    return publish["org"], publish["slug"]


def run(
    *,
    spec: Path,
    target: Path,
    force: bool,
    create_pr: bool,
    base_branch: str,
    branch_name: str | None,
    change_type: str,
    scope: str | None,
    resolve_publishers: bool,
    gateway_url: str,
    api_key_env: str,
    require_api_key: bool,
) -> tuple[Path, str | None]:
    org, name = _load_publish_target(spec)

    try:
        with tempfile.TemporaryDirectory(prefix="skillforge-release-") as tmp_dir:
            source = Path(tmp_dir)
            generate_command.run(
                spec=spec,
                out=source,
                check=False,
                resolve_publishers=resolve_publishers,
                gateway_url=gateway_url,
                api_key_env=api_key_env,
                require_api_key=require_api_key,
            )
            return publish_command.run(
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
    except generate_command.GenerateError as exc:
        raise ReleaseError(str(exc)) from exc
    except publish_command.PublishError as exc:
        raise ReleaseError(str(exc)) from exc


def command(
    spec: Path = typer.Option(
        Path("skill.spec.yaml"),
        "--spec",
        help="Path to skill.spec.yaml.",
    ),
    target: Path = typer.Option(
        ...,
        "--target",
        help="Path to local seren-skills git clone.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow overwriting an existing target skill directory.",
    ),
    create_pr: bool = typer.Option(
        False,
        "--create-pr",
        help="Create a pull request via gh after releasing.",
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
    resolve_publishers: bool = typer.Option(
        False,
        "--resolve-publishers/--no-resolve-publishers",
        help="Require connectors to resolve against live publisher catalog before release.",
    ),
    gateway_url: str = typer.Option(
        DEFAULT_GATEWAY_URL,
        "--gateway-url",
        help="Seren gateway base URL for publisher resolution.",
    ),
    api_key_env: str = typer.Option(
        "SEREN_API_KEY",
        "--api-key-env",
        help="Environment variable name for optional Bearer API key.",
    ),
    require_api_key: bool = typer.Option(
        False,
        "--require-api-key",
        help="Fail if publisher resolution is enabled and API key env var is missing.",
    ),
) -> None:
    try:
        destination, pr_url = run(
            spec=spec,
            target=target,
            force=force,
            create_pr=create_pr,
            base_branch=base_branch,
            branch_name=branch_name,
            change_type=change_type,
            scope=scope,
            resolve_publishers=resolve_publishers,
            gateway_url=gateway_url,
            api_key_env=api_key_env,
            require_api_key=require_api_key,
        )
    except ReleaseError as exc:
        typer.echo(f"FAIL [release] {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(f"Released {spec} -> {destination}")
    if pr_url:
        typer.echo(f"Opened PR: {pr_url}")
