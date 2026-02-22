from skillforge import __version__
from skillforge.cli import app


def test_package_has_version() -> None:
    assert __version__


def test_cli_app_is_initialized() -> None:
    assert app is not None

