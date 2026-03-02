from __future__ import annotations

import json
from pathlib import Path

from skillforge.codegen.runtime_python import render_agent_py
from skillforge.parser import parse_spec

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "examples/ledger-signing/skill.spec.yaml"
FIXTURE_DIR = REPO_ROOT / "examples/ledger-signing/tests/fixtures"


def test_ledger_signing_spec_has_explicit_live_gates() -> None:
    spec = parse_spec(SPEC_PATH).ir

    assert spec.tests["live"] == (
        "hitl_clear_signing_displays_human_readable_fields",
        "hitl_blind_signing_requires_explicit_opt_in",
        "hitl_blind_signing_disallowed_blocks_fallback",
    )


def test_ledger_signing_workflow_includes_clear_and_blind_paths() -> None:
    spec = parse_spec(SPEC_PATH).ir
    uses = tuple(step.use for step in spec.workflow_steps)

    assert "transform.render_ledger_clear_signing_guide" in uses
    assert "transform.render_ledger_blind_signing_guide" in uses
    assert uses[-1] == "transform.render_dual_signing_response"


def test_ledger_signing_hitl_fixtures_have_expected_policy_modes() -> None:
    clear = json.loads((FIXTURE_DIR / "clear_sign_happy.json").read_text(encoding="utf-8"))
    blind_allowed = json.loads(
        (FIXTURE_DIR / "blind_sign_allowed.json").read_text(encoding="utf-8")
    )
    blind_blocked = json.loads(
        (FIXTURE_DIR / "blind_sign_disallowed.json").read_text(encoding="utf-8")
    )

    assert clear["inputs"]["signing_mode"] == "auto"
    assert clear["inputs"]["clear_sign_required"] is True
    assert clear["inputs"]["blind_sign_allowed"] is False

    assert blind_allowed["inputs"]["signing_mode"] == "blind"
    assert blind_allowed["inputs"]["blind_sign_allowed"] is True

    assert blind_blocked["inputs"]["signing_mode"] == "blind"
    assert blind_blocked["inputs"]["blind_sign_allowed"] is False


def test_ledger_signing_runtime_is_hid_execution_capable() -> None:
    spec = parse_spec(SPEC_PATH).ir
    runtime = render_agent_py(spec)

    assert "from ledgerblue.comm import getDongle" in runtime
    assert '"--execute"' in runtime
    assert "INS_SIGN_TX = 0x04" in runtime
    assert "INS_SIGN_PERSONAL_MESSAGE = 0x08" in runtime
    assert "inputs.payload_hex is required for HID signing" in runtime


def test_ledger_signing_runtime_requires_explicit_execute_and_dry_run_off() -> None:
    spec = parse_spec(SPEC_PATH).ir
    runtime = render_agent_py(spec)

    assert "Pass --execute to run USB/HID signing" in runtime
    assert "Refusing to sign while dry_run=true" in runtime
