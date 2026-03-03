from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skillforge.cli import app

runner = CliRunner()


def test_auth_check_passes_for_safe_placeholders(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text(
        "# Skill\n\nUse Desktop session auth. If needed, run `auth_bootstrap`.\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text("SEREN_API_KEY=<required>\n", encoding="utf-8")

    result = runner.invoke(app, ["auth-check", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "PASS [auth-check]" in result.output


def test_auth_check_flags_manual_seren_api_key_setup(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Setup:\nexport SEREN_API_KEY=abc123\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["auth-check", "--path", str(tmp_path)])

    assert result.exit_code != 0
    assert "AUTH001" in result.output


def test_auth_check_writes_json_report(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("SEREN_API_KEY=sk-live-12345\n", encoding="utf-8")
    report = tmp_path / "reports" / "auth-check.json"

    result = runner.invoke(
        app,
        ["auth-check", "--path", str(tmp_path), "--json-out", str(report)],
    )

    assert result.exit_code != 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["violations"][0]["rule_id"] == "AUTH004"

