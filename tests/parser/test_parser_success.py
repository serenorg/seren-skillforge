from __future__ import annotations

from pathlib import Path

from skillforge.parser import parse_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_parse_minimal_example_to_ir() -> None:
    result = parse_spec(REPO_ROOT / "examples/minimal/skill.spec.yaml")

    assert result.model.skill == "hello-skill"
    assert result.ir.skill == "hello-skill"
    assert result.ir.runtime.language == "python"
    assert result.ir.runtime.entrypoint == "scripts/agent.py"
    assert result.ir.workflow_steps[0].id == "announce"
    assert result.ir.workflow_steps[0].use == "transform.echo"


def test_parse_minimal_example_applies_empty_defaults() -> None:
    result = parse_spec(REPO_ROOT / "examples/minimal/skill.spec.yaml")

    assert result.ir.inputs == {}
    assert result.ir.secrets == ()
    assert result.ir.connectors == {}
    assert result.ir.state == {}
    assert result.ir.policies == {}
    assert result.ir.tests == {}
    assert result.ir.publish is None


def test_parse_richer_example_keeps_structured_sections() -> None:
    result = parse_spec(REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml")

    assert result.ir.connectors["market_data"]["publisher"] == "polymarket-data"
    assert result.ir.connectors["model"]["publisher"] == "seren-models"
    assert result.ir.state["positions"]["kind"] == "sqlite"
    assert result.ir.policies["dry_run_default"] is True
    assert len(result.ir.workflow_steps) == 4
    assert result.ir.workflow_steps[-1].id == "plan"
    assert result.ir.publish == {"org": "polymarket", "slug": "trader"}


def test_parse_customer_support_example_keeps_connectors_and_state() -> None:
    result = parse_spec(REPO_ROOT / "examples/customer-support-intake/skill.spec.yaml")

    assert result.ir.skill == "customer-support-intake"
    assert result.ir.connectors["diagnostics"]["publisher"] == "seren-desktop-diagnostics"
    assert result.ir.connectors["playwright"]["publisher"] == "playwright-local-mcp"
    assert result.ir.connectors["storage"]["publisher"] == "serendb"
    assert result.ir.connectors["discord"]["publisher"] == "discord"
    assert result.ir.state["incidents"]["kind"] == "serendb"
    assert result.ir.state["incidents"]["database"] == "support_intake"
    assert "support_org_id" not in result.ir.inputs
    assert "support_access_grant_token" not in result.ir.inputs
    assert "consent_confirmed" in result.ir.inputs
    assert "bot_display_name" in result.ir.inputs
    assert "discord_username" in result.ir.inputs
    assert "incident_url" in result.ir.inputs
    assert "include_screenshot" in result.ir.inputs
    assert result.ir.workflow_steps[0].id == "verify_consent"
    assert result.ir.workflow_steps[-1].id == "summary"
