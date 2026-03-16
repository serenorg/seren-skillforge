from __future__ import annotations

import os
from pathlib import Path

import typer

from skillforge.parser import parse_spec
from skillforge.publisher_catalog import (
    DEFAULT_GATEWAY_URL,
    PublisherCatalogError,
    publisher_index,
    resolve_publisher_slug,
)
from skillforge.testing.harness import HarnessFailure, HarnessResult, run_harness


def run(
    *,
    spec: Path,
    allow_guessed_publisher_slugs: tuple[str, ...] = (),
    online_publishers: bool = False,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    api_key_env: str = "SEREN_API_KEY",
    require_api_key: bool = False,
    allow_inactive_publishers: bool = False,
) -> HarnessResult:
    base = run_harness(
        mode="quick",
        spec_path=spec,
        allow_guessed_publisher_slugs=set(allow_guessed_publisher_slugs),
    )
    if not online_publishers or not base.ok:
        return base

    try:
        parsed = parse_spec(spec)
    except Exception as exc:
        return HarnessResult(
            mode="quick",
            ok=False,
            checks_run=base.checks_run + 1,
            failures=(
                *base.failures,
                HarnessFailure(
                    code="parse_error",
                    path="<root>",
                    message=f"Failed to parse spec before online validation: {exc}",
                ),
            ),
        )

    api_key = os.environ.get(api_key_env, "").strip() or None
    if require_api_key and not api_key:
        return HarnessResult(
            mode="quick",
            ok=False,
            checks_run=base.checks_run + 1,
            failures=(
                *base.failures,
                HarnessFailure(
                    code="missing_api_key",
                    path=f"env.{api_key_env}",
                    message=f"Required API key env var '{api_key_env}' is not set.",
                ),
            ),
        )

    try:
        index = publisher_index(
            gateway_url=gateway_url,
            api_key=api_key,
            include_inactive=True,
        )
    except PublisherCatalogError as exc:
        return HarnessResult(
            mode="quick",
            ok=False,
            checks_run=base.checks_run + 1,
            failures=(
                *base.failures,
                HarnessFailure(
                    code="publisher_catalog_error",
                    path="<online>",
                    message=str(exc),
                ),
            ),
        )

    failures = list(base.failures)

    for connector_name, connector in parsed.model.connectors.items():
        if connector.kind != "seren_publisher":
            continue

        path = f"connectors.{connector_name}.publisher"
        requested = str(connector.publisher).strip() if connector.publisher is not None else ""
        resolution = resolve_publisher_slug(requested_slug=requested, index=index)
        if not resolution.ok:
            suggestion_suffix = (
                f" Suggestions: {', '.join(resolution.suggestions)}."
                if resolution.suggestions
                else ""
            )
            failures.append(
                HarnessFailure(
                    code="publisher_not_found",
                    path=path,
                    message=f"{resolution.reason}{suggestion_suffix}",
                )
            )
            continue

        resolved_slug = str(resolution.resolved)
        if requested != resolved_slug:
            failures.append(
                HarnessFailure(
                    code="publisher_slug_unresolved",
                    path=path,
                    message=(
                        f"Connector '{connector_name}' uses '{requested}', "
                        f"but catalog resolves to '{resolved_slug}'. "
                        "Run resolve-publishers to rewrite."
                    ),
                )
            )

        record = index[resolved_slug]
        if not record.is_active and not allow_inactive_publishers:
            failures.append(
                HarnessFailure(
                    code="publisher_inactive",
                    path=path,
                    message=f"Publisher '{resolved_slug}' is inactive.",
                )
            )

    return HarnessResult(
        mode="quick",
        ok=not failures,
        checks_run=base.checks_run + 1,
        failures=tuple(failures),
    )


def print_failures(result: HarnessResult) -> None:
    for line in format_failures(result):
        typer.echo(line)


def format_failures(result: HarnessResult) -> list[str]:
    return [f"[{failure.code}] {failure.path}: {failure.message}" for failure in result.failures]


def command(
    spec: Path = typer.Option(
        Path("skill.spec.yaml"),
        "--spec",
        help="Path to skill.spec.yaml.",
    ),
    allow_guessed_publisher_slug: list[str] = typer.Option(
        [],
        "--allow-guessed-publisher-slug",
        help="Allowlist specific guessed publisher slugs (for temporary migrations).",
    ),
    online_publishers: bool = typer.Option(
        False,
        "--online-publishers/--no-online-publishers",
        help="Validate connector publishers against live gateway catalog.",
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
        help="Fail when online validation is enabled and API key env var is missing.",
    ),
    allow_inactive_publishers: bool = typer.Option(
        False,
        "--allow-inactive-publishers",
        help="Allow inactive publishers to pass online validation.",
    ),
) -> None:
    result = run(
        spec=spec,
        allow_guessed_publisher_slugs=tuple(allow_guessed_publisher_slug),
        online_publishers=online_publishers,
        gateway_url=gateway_url,
        api_key_env=api_key_env,
        require_api_key=require_api_key,
        allow_inactive_publishers=allow_inactive_publishers,
    )
    if result.ok:
        typer.echo(f"PASS [validate] checks={result.checks_run}")
        return

    typer.echo(f"FAIL [validate] checks={result.checks_run}")
    print_failures(result)
    raise typer.Exit(code=1)
