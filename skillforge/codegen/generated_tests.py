from __future__ import annotations

import json
from pathlib import Path

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
        normalized = json.dumps(json.loads(content), indent=2, sort_keys=False) + "\n"
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
