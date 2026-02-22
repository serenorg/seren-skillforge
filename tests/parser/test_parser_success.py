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

