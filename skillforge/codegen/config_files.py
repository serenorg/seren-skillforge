from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillforge.ir import NormalizedSkillSpec

ENV_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "env.example.j2"
CONFIG_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "config.example.json.j2"


def _default_input_value(definition: dict[str, Any]) -> Any:
    if "default" in definition:
        return definition["default"]

    input_type = definition.get("type")
    if input_type == "string":
        return ""
    if input_type == "number":
        return 0.0
    if input_type == "integer":
        return 0
    if input_type == "boolean":
        return False
    return None


def render_env_example(spec: NormalizedSkillSpec) -> str:
    template = ENV_TEMPLATE_PATH.read_text(encoding="utf-8")
    secret_lines = ""
    if spec.secrets:
        secret_lines = "\n".join(f"{secret}=" for secret in spec.secrets)
    else:
        secret_lines = "# No required secrets for this skill."

    return template.replace("{{skill_name}}", spec.skill).replace("{{secret_lines}}", secret_lines)


def render_config_example_json(spec: NormalizedSkillSpec) -> str:
    _ = CONFIG_TEMPLATE_PATH.read_text(encoding="utf-8")
    inputs = {
        key: _default_input_value(spec.inputs[key])
        for key in sorted(spec.inputs.keys())
    }
    config = {
        "skill": spec.skill,
        "dry_run": bool(spec.policies.get("dry_run_default", True)),
        "inputs": inputs,
        "connectors": sorted(spec.connectors.keys()),
    }
    return json.dumps(config, indent=2, sort_keys=True) + "\n"


def write_config_files(spec: NormalizedSkillSpec, output_dir: Path) -> list[Path]:
    env_path = output_dir / ".env.example"
    config_path = output_dir / "config.example.json"
    env_path.write_text(render_env_example(spec), encoding="utf-8")
    config_path.write_text(render_config_example_json(spec), encoding="utf-8")
    return [env_path, config_path]

