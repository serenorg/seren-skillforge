from __future__ import annotations

from pathlib import Path

from skillforge.parser import parse_spec
from skillforge.testing.harness import run_harness

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "examples/customer-support-intake/skill.spec.yaml"
PINNED_ORG_ID = "f7f18722-a9c0-4cfe-bc2e-366463bb69bb"
TICKET_CHANNEL_ID = "1447063573804355687"
DISCORD_OAUTH_URL = (
    "https://discord.com/oauth2/authorize?client_id=1476455052209160234&permissions=67584"
    "&integration_type=0&scope=bot"
)


def test_customer_support_spec_wires_consent_collection_and_storage() -> None:
    spec = parse_spec(SPEC_PATH).ir
    steps_by_id = {step.id: step for step in spec.workflow_steps}
    uses_by_step = {step.id: step.use for step in spec.workflow_steps}
    step_ids = [step.id for step in spec.workflow_steps]

    assert spec.publish == {"org": "seren", "slug": "customer-support-intake"}
    assert spec.connectors["playwright"]["publisher"] == "playwright-local-mcp"
    assert spec.connectors["discord"]["publisher"] == "discord"
    assert uses_by_step["verify_consent"] == "transform.assert_consent"
    assert uses_by_step["verify_support_org_db_access"] == "connector.storage.post"
    assert (
        steps_by_id["verify_support_org_db_access"].args["path"]
        == "/support/access/verify-default-context"
    )
    assert (
        steps_by_id["verify_support_org_db_access"].args["body"]["support_org_id_source"]
        == "auth_context"
    )
    assert (
        steps_by_id["verify_support_org_db_access"].args["body"]["expected_support_org_id"]
        == PINNED_ORG_ID
    )
    assert steps_by_id["verify_support_org_db_access"].args["body"]["fail_on_org_mismatch"] is True
    assert "support_org_id" not in steps_by_id["verify_support_org_db_access"].args["body"]
    assert step_ids.index("verify_support_org_db_access") < step_ids.index("register_incident")
    assert step_ids.index("register_incident") < step_ids.index("upsert_incident")
    assert step_ids.index("persist_evidence") < step_ids.index("enqueue_tickettool_command")
    assert step_ids.index("enqueue_tickettool_command") < step_ids.index("persist_ticket_mapping")
    assert uses_by_step["collect_environment"] == "connector.diagnostics.post"
    assert uses_by_step["open_incident_view"] == "connector.playwright.post"
    assert steps_by_id["open_incident_view"].args["path"] == "/_mcp/tools/playwright_navigate"
    assert uses_by_step["capture_screenshot"] == "connector.playwright.post"
    assert steps_by_id["capture_screenshot"].args["path"] == "/_mcp/tools/playwright_screenshot"
    assert uses_by_step["enqueue_tickettool_command"] == "connector.discord.post"
    assert (
        steps_by_id["enqueue_tickettool_command"].args["path"]
        == f"/channels/{TICKET_CHANNEL_ID}/messages"
    )
    assert uses_by_step["persist_ticket_mapping"] == "connector.storage.post"
    assert steps_by_id["persist_ticket_mapping"].args["path"] == "/support/incidents/ticket-link"
    assert uses_by_step["persist_evidence"] == "connector.storage.post"
    assert uses_by_step["summary"] == "transform.support_summary"


def test_customer_support_spec_redaction_and_state_are_explicit() -> None:
    spec = parse_spec(SPEC_PATH).ir
    steps_by_id = {step.id: step for step in spec.workflow_steps}
    redact = steps_by_id["redact_and_minimize"].args
    metadata = spec.metadata

    assert spec.state["incidents"]["kind"] == "serendb"
    assert spec.state["incidents"]["database"] == "support_intake"
    assert spec.state["incidents"]["table"] == "customer_incidents"
    assert redact["depends_on"] == [
        "register_incident",
        "collect_environment",
        "collect_logs",
        "collect_chat_history",
        "open_incident_view",
        "capture_screenshot",
    ]
    assert "access_token" in redact["redact"]
    assert "private_key" in redact["redact"]
    assert "ssn" in redact["redact"]
    assert "support_org_id" not in spec.inputs
    assert "support_access_grant_token" not in spec.inputs
    assert "consent_confirmed" in spec.inputs
    assert "incident_url" in spec.inputs
    assert "include_screenshot" in spec.inputs
    assert steps_by_id["upsert_incident"].args["body"]["step"] == "verify_support_org_db_access"
    assert steps_by_id["persist_evidence"].args["body"]["step"] == "verify_support_org_db_access"
    assert steps_by_id["enqueue_tickettool_command"].args["body"]["step"] == "verify_support_org_db_access"
    assert steps_by_id["enqueue_tickettool_command"].args["body"]["destination"] == "tickettool_xyz"
    assert steps_by_id["enqueue_tickettool_command"].args["body"]["channel_id"] == TICKET_CHANNEL_ID
    assert (
        steps_by_id["enqueue_tickettool_command"].args["body"]["bot_display_name"]
        == "{bot_display_name}"
    )
    assert (
        steps_by_id["enqueue_tickettool_command"].args["body"]["command_template"]
        == "$new @{discord_username} {reason}"
    )
    assert (
        steps_by_id["enqueue_tickettool_command"].args["body"]["oauth_install_url"]
        == DISCORD_OAUTH_URL
    )
    assert steps_by_id["persist_ticket_mapping"].args["body"]["step"] == "verify_support_org_db_access"
    assert steps_by_id["persist_ticket_mapping"].args["body"]["ticket_provider"] == "tickettool_xyz"
    assert (
        steps_by_id["persist_ticket_mapping"].args["body"]["ticket_from"]
        == "enqueue_tickettool_command"
    )
    assert steps_by_id["set_retention"].args["body"]["step"] == "verify_support_org_db_access"
    assert metadata["support_org_db_access_required"] == "true"
    assert metadata["support_org_id_source"] == "auth_context"
    assert metadata["pinned_support_org_id"] == PINNED_ORG_ID
    assert metadata["fail_on_non_pinned_org_id"] == "true"
    assert (
        metadata["customer_db_access_model"]
        == "auth_context_with_pinned_support_org"
    )
    assert metadata["redaction_mode"] == "automatic_default"
    assert metadata["ticketing_backend"] == "tickettool_xyz_discord_command"
    assert metadata["support_alerting"] == "discord_tickettool_channel_command"
    assert metadata["ticket_channel_id"] == TICKET_CHANNEL_ID
    assert metadata["discord_oauth_install_url"] == DISCORD_OAUTH_URL
    assert metadata["bot_name_policy"] == "user_defined_with_default"
    assert metadata["bot_default_name_template"] == "{server_name} Support Bot"


def test_customer_support_spec_passes_quick_and_smoke_harness() -> None:
    quick = run_harness(mode="quick", spec_path=SPEC_PATH)
    smoke = run_harness(mode="smoke", spec_path=SPEC_PATH)

    assert quick.ok, f"quick failed: {quick.failures}"
    assert smoke.ok, f"smoke failed: {smoke.failures}"
