"""SkillForge CLI."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="skillforge",
    no_args_is_help=True,
    add_completion=False,
    help="SkillForge CLI for generating and validating skills from SkillSpec.",
)


@app.command("version")
def version() -> None:
    """Print SkillForge version."""
    from skillforge import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()

