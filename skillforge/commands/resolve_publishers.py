from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
import yaml

from skillforge.parser import parse_spec
from skillforge.publisher_catalog import (
    DEFAULT_GATEWAY_URL,
    PublisherCatalogError,
    publisher_index,
    resolve_publisher_slug,
)


@dataclass(frozen=True)
class ResolveIssue:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ResolveChange:
    connector: str
    from_slug: str
    to_slug: str
    source: str


@dataclass(frozen=True)
class ResolveResult:
    ok: bool
    catalog_size: int
    changes: tuple[ResolveChange, ...]
    issues: tuple[ResolveIssue, ...]
    wrote: bool


def _load_spec_yaml(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected YAML mapping in {path}.")
    return parsed


def _connectors(raw_spec: dict[str, Any]) -> dict[str, Any]:
    connectors = raw_spec.get("connectors", {})
    if not isinstance(connectors, dict):
        raise RuntimeError("Spec field 'connectors' must be an object.")
    return connectors


def run(
    *,
    spec: Path,
    gateway_url: str,
    api_key_env: str,
    require_api_key: bool,
    allow_inactive: bool,
    write: bool,
) -> ResolveResult:
    # Parse first to ensure schema-valid spec before in-place edits.
    parse_spec(spec)
    raw = _load_spec_yaml(spec)
    connectors = _connectors(raw)

    api_key = os.environ.get(api_key_env, "").strip() or None
    if require_api_key and not api_key:
        return ResolveResult(
            ok=False,
            catalog_size=0,
            changes=(),
            issues=(
                ResolveIssue(
                    code="missing_api_key",
                    path=f"env.{api_key_env}",
                    message=f"Required API key env var '{api_key_env}' is not set.",
                ),
            ),
            wrote=False,
        )

    try:
        index = publisher_index(
            gateway_url=gateway_url,
            api_key=api_key,
            include_inactive=True,
        )
    except PublisherCatalogError as exc:
        return ResolveResult(
            ok=False,
            catalog_size=0,
            changes=(),
            issues=(
                ResolveIssue(
                    code="publisher_catalog_error",
                    path="<online>",
                    message=str(exc),
                ),
            ),
            wrote=False,
        )

    changes: list[ResolveChange] = []
    issues: list[ResolveIssue] = []
    for connector_name, connector_def in connectors.items():
        if not isinstance(connector_def, dict):
            continue
        if connector_def.get("kind") != "seren_publisher":
            continue

        path = f"connectors.{connector_name}.publisher"
        publisher_value = connector_def.get("publisher")
        requested = str(publisher_value).strip() if publisher_value is not None else ""
        resolution = resolve_publisher_slug(requested_slug=requested, index=index)
        if not resolution.ok:
            suggestion_suffix = (
                f" Suggestions: {', '.join(resolution.suggestions)}."
                if resolution.suggestions
                else ""
            )
            issues.append(
                ResolveIssue(
                    code="publisher_not_found",
                    path=path,
                    message=f"{resolution.reason}{suggestion_suffix}",
                )
            )
            continue

        resolved_slug = str(resolution.resolved)
        record = index[resolved_slug]
        if not record.is_active and not allow_inactive:
            issues.append(
                ResolveIssue(
                    code="publisher_inactive",
                    path=path,
                    message=(
                        f"Publisher '{resolved_slug}' for connector '{connector_name}' is inactive."
                    ),
                )
            )
            continue

        if requested != resolved_slug:
            changes.append(
                ResolveChange(
                    connector=connector_name,
                    from_slug=requested,
                    to_slug=resolved_slug,
                    source=resolution.source,
                )
            )
            connector_def["publisher"] = resolved_slug

    wrote = False
    ok = not issues
    if ok and write and changes:
        spec.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        wrote = True

    return ResolveResult(
        ok=ok,
        catalog_size=len(index),
        changes=tuple(changes),
        issues=tuple(issues),
        wrote=wrote,
    )


def _print_issues(issues: tuple[ResolveIssue, ...]) -> None:
    for issue in issues:
        typer.echo(f"[{issue.code}] {issue.path}: {issue.message}")


def _print_changes(changes: tuple[ResolveChange, ...]) -> None:
    for change in changes:
        typer.echo(
            f"{change.connector}: {change.from_slug or '<empty>'} -> "
            f"{change.to_slug} ({change.source})"
        )


def command(
    spec: Path = typer.Option(
        Path("skill.spec.yaml"),
        "--spec",
        help="Path to skill.spec.yaml.",
    ),
    gateway_url: str = typer.Option(
        DEFAULT_GATEWAY_URL,
        "--gateway-url",
        help="Seren gateway base URL.",
    ),
    api_key_env: str = typer.Option(
        "SEREN_API_KEY",
        "--api-key-env",
        help="Environment variable name for optional Bearer API key.",
    ),
    require_api_key: bool = typer.Option(
        False,
        "--require-api-key",
        help="Fail if API key env var is missing.",
    ),
    allow_inactive: bool = typer.Option(
        False,
        "--allow-inactive",
        help="Allow inactive publishers in resolution output.",
    ),
    write: bool = typer.Option(
        True,
        "--write/--no-write",
        help="Write resolved slugs back into the spec.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Check-only mode: fail if unresolved publishers or stale slugs are found.",
    ),
) -> None:
    should_write = write and not check
    result = run(
        spec=spec,
        gateway_url=gateway_url,
        api_key_env=api_key_env,
        require_api_key=require_api_key,
        allow_inactive=allow_inactive,
        write=should_write,
    )

    if not result.ok:
        typer.echo(f"FAIL [resolve-publishers] catalog={result.catalog_size}")
        _print_issues(result.issues)
        raise typer.Exit(code=1)

    if check and result.changes:
        typer.echo(
            f"FAIL [resolve-publishers --check] stale connectors={len(result.changes)} "
            f"catalog={result.catalog_size}"
        )
        _print_changes(result.changes)
        raise typer.Exit(code=1)

    if result.changes:
        action = "updated" if result.wrote else "pending"
        typer.echo(
            f"PASS [resolve-publishers] {action} connectors={len(result.changes)} "
            f"catalog={result.catalog_size}"
        )
        _print_changes(result.changes)
    else:
        typer.echo(f"PASS [resolve-publishers] no changes catalog={result.catalog_size}")
