from __future__ import annotations

from pathlib import Path

from skillforge.ir import NormalizedSkillSpec

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "skill_md.j2"


def _to_title(skill_name: str) -> str:
    return " ".join(part.capitalize() for part in skill_name.split("-"))


def _render_frontmatter(spec: NormalizedSkillSpec) -> str:
    return (
        "---\n"
        f"name: {spec.skill}\n"
        f'description: "{spec.description}"\n'
        "---\n"
    )


def render_skill_md(spec: NormalizedSkillSpec) -> str:
    trigger_lines = "\n".join(f"- {trigger}" for trigger in spec.triggers)
    workflow_lines = "\n".join(
        f"{index}. `{step.id}` uses `{step.use}`"
        for index, step in enumerate(spec.workflow_steps, start=1)
    )

    return (
        f"{_render_frontmatter(spec)}\n"
        f"# {_to_title(spec.skill)}\n\n"
        "## For Claude: How to Use This Skill\n\n"
        "Skill instructions are preloaded in context when this skill is active. "
        "Do not perform filesystem searches or tool-driven exploration to "
        "rediscover them; use the guidance below directly.\n\n"
        "## When to Use\n\n"
        f"{trigger_lines}\n\n"
        "## Workflow Summary\n\n"
        f"{workflow_lines}\n"
    )


def write_skill_md(spec: NormalizedSkillSpec, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_skill_md(spec), encoding="utf-8")
    return output_path
