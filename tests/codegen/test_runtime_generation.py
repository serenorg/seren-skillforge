from __future__ import annotations

import json
from pathlib import Path

from skillforge.codegen.config_files import (
    render_config_example_json,
    render_env_example,
    render_requirements_txt,
    write_config_files,
    write_requirements_txt,
)
from skillforge.codegen.runtime_python import render_agent_py, write_runtime_python
from skillforge.parser import parse_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_render_agent_matches_minimal_golden() -> None:
    spec = parse_spec(REPO_ROOT / "examples/minimal/skill.spec.yaml").ir
    generated = render_agent_py(spec)
    expected = (REPO_ROOT / "tests/golden/runtime/minimal.agent.expected.txt").read_text(
        encoding="utf-8"
    )
    assert generated == expected


def test_render_env_and_config_match_polymarket_goldens() -> None:
    spec = parse_spec(REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml").ir

    generated_env = render_env_example(spec)
    generated_config = render_config_example_json(spec)
    generated_requirements = render_requirements_txt(spec)

    expected_env = (REPO_ROOT / "tests/golden/runtime/polymarket.env.expected").read_text(
        encoding="utf-8"
    )
    expected_config = (
        REPO_ROOT / "tests/golden/runtime/polymarket.config.expected.json"
    ).read_text(encoding="utf-8")

    assert generated_env == expected_env
    assert generated_config == expected_config
    assert (
        generated_requirements
        == "# No third-party runtime dependencies are required for polymarket-trader.\n"
    )


def test_write_runtime_and_config_outputs_files(tmp_path: Path) -> None:
    spec = parse_spec(REPO_ROOT / "examples/browser-automation/skill.spec.yaml").ir

    runtime_path = write_runtime_python(spec, tmp_path)
    env_path, config_path = write_config_files(spec, tmp_path)
    requirements_path = write_requirements_txt(spec, tmp_path)

    assert runtime_path == tmp_path / "scripts" / "agent.py"
    assert env_path == tmp_path / ".env.example"
    assert config_path == tmp_path / "config.example.json"
    assert requirements_path == tmp_path / "requirements.txt"
    assert runtime_path.exists()
    assert env_path.exists()
    assert config_path.exists()
    assert requirements_path.exists()

    runtime_text = runtime_path.read_text(encoding="utf-8")
    assert "DEFAULT_DRY_RUN = True" in runtime_text

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["skill"] == "browser-automation"
    assert config["dry_run"] is True
    assert config["inputs"]["url"] == ""
    assert (
        requirements_path.read_text(encoding="utf-8")
        == "# No third-party runtime dependencies are required for browser-automation.\n"
    )


def test_render_agent_defaults_to_dry_run_when_policy_missing() -> None:
    spec = parse_spec(REPO_ROOT / "examples/minimal/skill.spec.yaml").ir
    generated = render_agent_py(spec)
    assert "DEFAULT_DRY_RUN = True" in generated


def test_render_agent_wraps_long_connector_lists_for_ruff() -> None:
    spec = parse_spec(REPO_ROOT / "examples/peer-to-peer-payments-exchange/skill.spec.yaml").ir
    generated = render_agent_py(spec)

    assert "\n\n\nDEFAULT_DRY_RUN" not in generated
    assert max(len(line) for line in generated.splitlines()) <= 100


def test_render_agent_for_ledger_signing_contains_hid_signing_runtime() -> None:
    spec = parse_spec(REPO_ROOT / "examples/ledger-signing/skill.spec.yaml").ir
    generated = render_agent_py(spec)

    assert "Generated SkillForge Ledger runtime for ledger-signing." in generated
    assert "from ledgerblue.comm import getDongle" in generated
    assert "INS_SIGN_TX = 0x04" in generated
    assert "INS_SIGN_PERSONAL_MESSAGE = 0x08" in generated
    assert '"--execute"' in generated
    assert "inputs.payload_hex is required for HID signing" in generated
