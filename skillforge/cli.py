"""SkillForge CLI."""

from __future__ import annotations

import typer

from skillforge.commands import init as init_command
from skillforge.commands import test as test_command

app = typer.Typer(
    name="skillforge",
    no_args_is_help=True,
    add_completion=False,
    help="SkillForge CLI for generating and validating skills from SkillSpec.",
)


@app.callback()
def main() -> None:
    """SkillForge command group."""


@app.command("version")
def version() -> None:
    """Print SkillForge version."""
    from skillforge import __version__

    typer.echo(__version__)


app.command("init")(init_command.command)
app.command("test")(test_command.command)


if __name__ == "__main__":
    app()
