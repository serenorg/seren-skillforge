from __future__ import annotations

from pathlib import Path

from skillforge.codegen.skill_md import render_skill_md
from skillforge.parser import parse_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def _render_from_example(example_path: Path) -> str:
    parsed = parse_spec(example_path)
    return render_skill_md(parsed.ir)


def test_generate_skill_md_matches_minimal_golden() -> None:
    generated = _render_from_example(REPO_ROOT / "examples/minimal/skill.spec.yaml")
    expected = (REPO_ROOT / "tests/golden/skill_md/minimal.expected.md").read_text(
        encoding="utf-8"
    )
    assert generated == expected


def test_generate_skill_md_matches_polymarket_golden() -> None:
    generated = _render_from_example(REPO_ROOT / "examples/polymarket-trader/skill.spec.yaml")
    expected = (REPO_ROOT / "tests/golden/skill_md/polymarket-trader.expected.md").read_text(
        encoding="utf-8"
    )
    assert generated == expected


def test_generate_skill_md_has_required_frontmatter_fields() -> None:
    generated = _render_from_example(REPO_ROOT / "examples/browser-automation/skill.spec.yaml")
    lines = generated.splitlines()

    assert lines[0] == "---"
    assert any(line.startswith("name: ") for line in lines)
    assert any(line.startswith("description: ") for line in lines)
    assert generated.count("---") >= 2


def test_generate_skill_md_is_idempotent() -> None:
    first = _render_from_example(REPO_ROOT / "examples/browser-automation/skill.spec.yaml")
    second = _render_from_example(REPO_ROOT / "examples/browser-automation/skill.spec.yaml")
    assert first == second


def test_generate_skill_md_places_claude_section_before_when_to_use() -> None:
    generated = _render_from_example(REPO_ROOT / "examples/browser-automation/skill.spec.yaml")
    claude_heading = "## For Claude: How to Use This Skill"
    when_to_use_heading = "## When to Use"

    assert claude_heading in generated
    assert generated.index(claude_heading) < generated.index(when_to_use_heading)
