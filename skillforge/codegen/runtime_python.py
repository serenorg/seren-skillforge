from __future__ import annotations

from pathlib import Path

from skillforge.ir import NormalizedSkillSpec

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "agent.py.j2"
LEDGER_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "agent_ledger_signing.py.j2"
)


def _as_python_bool(value: bool) -> str:
    return "True" if value else "False"


def render_agent_py(spec: NormalizedSkillSpec) -> str:
    template_path = TEMPLATE_PATH
    if spec.skill == "ledger-signing":
        template_path = LEDGER_TEMPLATE_PATH
    template = template_path.read_text(encoding="utf-8")
    default_dry_run = bool(spec.policies.get("dry_run_default", True))
    connectors = sorted(spec.connectors.keys())
    connector_repr = ", ".join(repr(name) for name in connectors)
    if connector_repr:
        connector_repr = f"[{connector_repr}]"
    else:
        connector_repr = "[]"

    rendered = (
        template.replace("{{skill_name}}", spec.skill)
        .replace("{{default_dry_run}}", _as_python_bool(default_dry_run))
        .replace("{{connectors}}", connector_repr)
    )
    return rendered


def write_runtime_python(spec: NormalizedSkillSpec, output_dir: Path) -> Path:
    output_path = output_dir / "scripts" / "agent.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_agent_py(spec), encoding="utf-8")
    return output_path
