from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from skillforge.testing.harness import HarnessMode, HarnessResult, run_harness


def run(*, mode: HarnessMode, spec: Path, fixture: Path | None) -> HarnessResult:
    return run_harness(mode=mode, spec_path=spec, fixture_path=fixture)


def _print_failures(result: HarnessResult) -> None:
    for failure in result.failures:
        typer.echo(f"[{failure.code}] {failure.path}: {failure.message}")


def command(
    mode: Literal["quick", "smoke"] = typer.Option(
        "quick",
        "--mode",
        help="Test mode to run: quick or smoke.",
    ),
    spec: Path = typer.Option(
        Path("skill.spec.yaml"),
        "--spec",
        help="Path to skill.spec.yaml.",
    ),
    fixture: Path | None = typer.Option(
        None,
        "--fixture",
        help="Optional fixture JSON file for smoke mode.",
    ),
) -> None:
    result = run(mode=mode, spec=spec, fixture=fixture)
    if result.ok:
        typer.echo(f"PASS [{mode}] checks={result.checks_run}")
        return

    typer.echo(f"FAIL [{mode}] checks={result.checks_run}")
    _print_failures(result)
    raise typer.Exit(code=1)

