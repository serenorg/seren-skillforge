from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillforge.ir import NormalizedSkillSpec

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
SMOKE_TEMPLATE_PATH = TEMPLATE_DIR / "test_smoke.py.j2"
FIXTURE_TEMPLATE_DIR = TEMPLATE_DIR / "fixtures"


def _replace_tokens(
    template: str,
    *,
    skill_name: str,
    workflow_step_count: int,
    dry_run: bool,
    first_connector: str,
) -> str:
    rendered = template.replace("{{skill_name}}", skill_name)
    rendered = rendered.replace("{{workflow_step_count}}", str(workflow_step_count))
    rendered = rendered.replace("{{dry_run}}", "true" if dry_run else "false")
    rendered = rendered.replace("{{first_connector}}", first_connector)
    return rendered


def render_smoke_test(spec: NormalizedSkillSpec) -> str:
    template = SMOKE_TEMPLATE_PATH.read_text(encoding="utf-8")
    first_connector = sorted(spec.connectors.keys())[0] if spec.connectors else "unknown_connector"
    return _replace_tokens(
        template,
        skill_name=spec.skill,
        workflow_step_count=len(spec.workflow_steps),
        dry_run=bool(spec.policies.get("dry_run_default", True)),
        first_connector=first_connector,
    )


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


def _connector_actions(spec: NormalizedSkillSpec) -> dict[str, set[str]]:
    actions: dict[str, set[str]] = {}
    for step in spec.workflow_steps:
        if not step.use.startswith("connector."):
            continue
        parts = step.use.split(".")
        if len(parts) < 3:
            continue
        actions.setdefault(parts[1], set()).add(parts[2])
    return actions


def _build_connector_payloads(
    spec: NormalizedSkillSpec,
    *,
    failure: bool,
) -> dict[str, dict[str, dict[str, Any]]]:
    connectors: dict[str, dict[str, dict[str, Any]]] = {}
    action_map = _connector_actions(spec)
    first_connector = sorted(action_map.keys())[0] if action_map else None

    for connector_name in sorted(action_map.keys()):
        connectors[connector_name] = {}
        for action in sorted(action_map[connector_name]):
            payload: dict[str, Any] = {
                "status": "ok",
                "connector": connector_name,
                "action": action,
            }
            if failure and connector_name == first_connector:
                payload["status"] = "error"
                payload["error_code"] = "connector_failure"
            connectors[connector_name][action] = payload

    return connectors


def _with_harness_metadata(
    *,
    fixture_name: str,
    payload: dict[str, Any],
    spec: NormalizedSkillSpec,
) -> dict[str, Any]:
    if fixture_name == "happy_path.json":
        payload["inputs"] = {
            input_name: _default_input_value(definition)
            for input_name, definition in sorted(spec.inputs.items())
        }
        payload["connectors"] = _build_connector_payloads(spec, failure=False)

    if fixture_name == "connector_failure.json":
        payload["connectors"] = _build_connector_payloads(spec, failure=True)

    return payload


def render_fixture_payloads(spec: NormalizedSkillSpec) -> dict[str, str]:
    first_connector = sorted(spec.connectors.keys())[0] if spec.connectors else "unknown_connector"
    context = {
        "skill_name": spec.skill,
        "workflow_step_count": len(spec.workflow_steps),
        "dry_run": bool(spec.policies.get("dry_run_default", True)),
        "first_connector": first_connector,
    }

    rendered: dict[str, str] = {}
    for template_path in sorted(FIXTURE_TEMPLATE_DIR.glob("*.json")):
        template = template_path.read_text(encoding="utf-8")
        content = _replace_tokens(template, **context)
        payload = json.loads(content)
        if isinstance(payload, dict):
            payload = _with_harness_metadata(
                fixture_name=template_path.name,
                payload=payload,
                spec=spec,
            )
        normalized = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        rendered[template_path.name] = normalized
    return rendered


def write_generated_tests(spec: NormalizedSkillSpec, output_dir: Path) -> list[Path]:
    tests_dir = output_dir / "tests"
    fixture_dir = tests_dir / "fixtures"
    tests_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []

    smoke_test_path = tests_dir / "test_smoke.py"
    smoke_test_path.write_text(render_smoke_test(spec), encoding="utf-8")
    written_paths.append(smoke_test_path)

    for fixture_name, payload in render_fixture_payloads(spec).items():
        fixture_path = fixture_dir / fixture_name
        fixture_path.write_text(payload, encoding="utf-8")
        written_paths.append(fixture_path)

    return written_paths
