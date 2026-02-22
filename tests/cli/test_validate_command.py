from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import skillforge.commands.validate as validate_module
from skillforge.cli import app
from skillforge.publisher_catalog import PublisherRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_validate_passes_for_valid_spec() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            "--spec",
            str(REPO_ROOT / "examples/minimal/skill.spec.yaml"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "PASS [validate]" in result.output


def test_validate_fails_for_invalid_spec() -> None:
    result = runner.invoke(
        app,
        [
            "validate",
            "--spec",
            str(REPO_ROOT / "tests/schema/fixtures/invalid_missing_required.yaml"),
        ],
    )

    assert result.exit_code != 0
    assert "FAIL [validate]" in result.output
    assert "schema_validation_error" in result.output


def test_validate_online_publishers_detects_stale_slug_resolution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = tmp_path / "skill.spec.yaml"
    spec.write_text(
        "\n".join(
            (
                "skill: stale-slug",
                "description: stale slug check",
                "triggers:",
                "  - test",
                "runtime:",
                "  language: python",
                "  entrypoint: scripts/agent.py",
                "connectors:",
                "  rpc_ethereum:",
                "    kind: seren_publisher",
                "    publisher: rpc-ethereum",
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

    monkeypatch.setattr(validate_module, "publisher_index", _fake_index)

    result = runner.invoke(
        app,
        [
            "validate",
            "--spec",
            str(spec),
            "--online-publishers",
            "--allow-guessed-publisher-slug",
            "rpc-ethereum",
        ],
    )

    assert result.exit_code != 0
    assert "publisher_slug_unresolved" in result.output


def test_validate_online_publishers_passes_for_resolved_active_slug(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = tmp_path / "skill.spec.yaml"
    spec.write_text(
        "\n".join(
            (
                "skill: active-slug",
                "description: active slug check",
                "triggers:",
                "  - test",
                "runtime:",
                "  language: python",
                "  entrypoint: scripts/agent.py",
                "connectors:",
                "  rpc_ethereum:",
                "    kind: seren_publisher",
                "    publisher: seren-ethereum",
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

    monkeypatch.setattr(validate_module, "publisher_index", _fake_index)

    result = runner.invoke(
        app,
        [
            "validate",
            "--spec",
            str(spec),
            "--online-publishers",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "PASS [validate]" in result.output
