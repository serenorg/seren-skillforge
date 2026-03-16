from __future__ import annotations

from pathlib import Path

import typer

from skillforge.codegen.config_files import (
    render_config_example_json,
    render_env_example,
    render_requirements_txt,
)
from skillforge.codegen.generated_tests import render_fixture_payloads, render_smoke_test
from skillforge.codegen.runtime_python import render_agent_py
from skillforge.codegen.skill_md import render_skill_md
from skillforge.commands import resolve_publishers as resolve_publishers_command
from skillforge.commands import validate as validate_command
from skillforge.parser import parse_spec
from skillforge.publisher_catalog import DEFAULT_GATEWAY_URL


def _render_outputs(spec_path: Path) -> dict[Path, str]:
    parsed = parse_spec(spec_path)
    spec = parsed.ir
    outputs: dict[Path, str] = {
        Path("SKILL.md"): render_skill_md(spec),
        Path("scripts/agent.py"): render_agent_py(spec),
        Path(".env.example"): render_env_example(spec),
        Path("config.example.json"): render_config_example_json(spec),
        Path("requirements.txt"): render_requirements_txt(spec),
        Path("tests/test_smoke.py"): render_smoke_test(spec),
    }
    for fixture_name, payload in render_fixture_payloads(spec).items():
        outputs[Path("tests/fixtures") / fixture_name] = payload
    return outputs


def _stale_paths(*, out_dir: Path, outputs: dict[Path, str]) -> list[Path]:
    stale: list[Path] = []
    for relative_path in sorted(outputs.keys()):
        destination = out_dir / relative_path
        if not destination.exists():
            stale.append(relative_path)
            continue
        existing = destination.read_text(encoding="utf-8")
        if existing != outputs[relative_path]:
            stale.append(relative_path)
    return stale


def _write_outputs(*, out_dir: Path, outputs: dict[Path, str]) -> list[Path]:
    written_paths: list[Path] = []
    for relative_path in sorted(outputs.keys()):
        destination = out_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(outputs[relative_path], encoding="utf-8")
        written_paths.append(destination)
    return written_paths


def command(
    spec: Path = typer.Option(
        Path("skill.spec.yaml"),
        "--spec",
        help="Path to skill.spec.yaml.",
    ),
    out: Path = typer.Option(
        Path("."),
        "--out",
        help="Output directory for generated artifacts.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Check whether generated outputs are up-to-date without writing.",
    ),
    resolve_publishers: bool = typer.Option(
        False,
        "--resolve-publishers/--no-resolve-publishers",
        help="Require connectors to resolve against live publisher catalog before generation.",
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
    if resolve_publishers:
        resolved = resolve_publishers_command.run(
            spec=spec,
            gateway_url=gateway_url,
            api_key_env=api_key_env,
            require_api_key=require_api_key,
            allow_inactive=False,
            write=False,
        )
        if not resolved.ok:
            typer.echo(
                f"FAIL [generate] publisher resolution failed catalog={resolved.catalog_size}"
            )
            for issue in resolved.issues:
                typer.echo(f"[{issue.code}] {issue.path}: {issue.message}")
            raise typer.Exit(code=1)
        if resolved.changes:
            typer.echo(
                f"FAIL [generate] unresolved publisher slugs={len(resolved.changes)}. "
                "Run `skillforge resolve-publishers --write` first."
            )
            for change in resolved.changes:
                typer.echo(
                    f"{change.connector}: {change.from_slug or '<empty>'} -> "
                    f"{change.to_slug} ({change.source})"
                )
            raise typer.Exit(code=1)

    validation = validate_command.run(spec=spec)
    if not validation.ok:
        typer.echo(f"FAIL [generate] spec validation failed checks={validation.checks_run}")
        validate_command.print_failures(validation)
        raise typer.Exit(code=1)

    outputs = _render_outputs(spec)

    if check:
        stale = _stale_paths(out_dir=out, outputs=outputs)
        if stale:
            typer.echo(f"FAIL [generate --check] stale outputs: {len(stale)}")
            for relative_path in stale:
                typer.echo(relative_path.as_posix())
            raise typer.Exit(code=1)

        typer.echo("PASS [generate --check] outputs are up-to-date")
        return

    written_paths = _write_outputs(out_dir=out, outputs=outputs)
    typer.echo(f"Generated {len(written_paths)} files in {out}")
