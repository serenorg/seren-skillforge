from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

import skillforge.commands.resolve_publishers as resolve_module
from skillforge.cli import app
from skillforge.publisher_catalog import PublisherRecord

runner = CliRunner()


def _write_spec(path: Path, publisher_slug: str) -> None:
    path.write_text(
        "\n".join(
            (
                "skill: resolve-test",
                "description: resolve command test",
                "triggers:",
                "  - test",
                "runtime:",
                "  language: python",
                "  entrypoint: scripts/agent.py",
                "connectors:",
                "  rpc_ethereum:",
                "    kind: seren_publisher",
                f"    publisher: {publisher_slug}",
                "workflow:",
                "  steps:",
                "    - id: probe",
                "      use: connector.rpc_ethereum.post",
                "      with:",
                "        path: /",
                "",
            )
        ),
        encoding="utf-8",
    )


def _fake_index(**_kwargs: object) -> dict[str, PublisherRecord]:
    return {
        "seren-ethereum": PublisherRecord(
            slug="seren-ethereum",
            name="SerenBlockchain",
            description="Ethereum JSON-RPC endpoint.",
            categories=("blockchain", "rpc", "ethereum"),
            is_active=True,
        )
    }


def test_resolve_publishers_check_mode_fails_when_rewrite_needed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = tmp_path / "skill.spec.yaml"
    _write_spec(spec, publisher_slug="rpc-ethereum")
    monkeypatch.setattr(resolve_module, "publisher_index", _fake_index)

    result = runner.invoke(
        app,
        [
            "resolve-publishers",
            "--spec",
            str(spec),
            "--check",
        ],
    )

    assert result.exit_code != 0
    assert "stale connectors=1" in result.output
    assert "rpc_ethereum: rpc-ethereum -> seren-ethereum" in result.output


def test_resolve_publishers_write_mode_updates_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = tmp_path / "skill.spec.yaml"
    _write_spec(spec, publisher_slug="rpc-ethereum")
    monkeypatch.setattr(resolve_module, "publisher_index", _fake_index)

    result = runner.invoke(
        app,
        [
            "resolve-publishers",
            "--spec",
            str(spec),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "updated connectors=1" in result.output

    parsed = yaml.safe_load(spec.read_text(encoding="utf-8"))
    assert parsed["connectors"]["rpc_ethereum"]["publisher"] == "seren-ethereum"
