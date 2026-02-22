"""Module entrypoint for `python -m skillforge`."""

from skillforge.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()

