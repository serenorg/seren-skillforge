from __future__ import annotations

from pathlib import Path

import typer

from skillforge.codegen.config_files import render_config_example_json, render_env_example
from skillforge.codegen.generated_tests import render_fixture_payloads, render_smoke_test
from skillforge.codegen.runtime_python import render_agent_py
from skillforge.codegen.skill_md import render_skill_md
from skillforge.commands import validate as validate_command
from skillforge.parser import parse_spec


def _render_outputs(spec_path: Path) -> dict[Path, str]:
    parsed = parse_spec(spec_path)
    spec = parsed.ir
    outputs: dict[Path, str] = {
        Path("SKILL.md"): render_skill_md(spec),
        Path("scripts/agent.py"): render_agent_py(spec),
        Path(".env.example"): render_env_example(spec),
        Path("config.example.json"): render_config_example_json(spec),
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
) -> None:
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
