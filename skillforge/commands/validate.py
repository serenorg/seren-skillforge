from __future__ import annotations

from pathlib import Path

import typer

from skillforge.testing.harness import HarnessResult, run_harness


def run(*, spec: Path) -> HarnessResult:
    return run_harness(mode="quick", spec_path=spec)


def print_failures(result: HarnessResult) -> None:
    for failure in result.failures:
        typer.echo(f"[{failure.code}] {failure.path}: {failure.message}")


def command(
    spec: Path = typer.Option(
        Path("skill.spec.yaml"),
        "--spec",
        help="Path to skill.spec.yaml.",
    ),
) -> None:
    result = run(spec=spec)
    if result.ok:
        typer.echo(f"PASS [validate] checks={result.checks_run}")
        return

    typer.echo(f"FAIL [validate] checks={result.checks_run}")
    print_failures(result)
    raise typer.Exit(code=1)
