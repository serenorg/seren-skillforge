from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_FILES = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").rglob("*.md"))]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _is_external_link(link: str) -> bool:
    return link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:")


def test_required_docs_exist() -> None:
    required = [
        REPO_ROOT / "docs/architecture/0001_skillforge_context.md",
        REPO_ROOT / "docs/testing/TEST_STRATEGY.md",
        REPO_ROOT / "docs/testing/ANTI_PATTERNS.md",
        REPO_ROOT / "docs/metrics/METRIC_DEFINITIONS.md",
        REPO_ROOT / "docs/plans/20260222_SkillForge_Implementation_Plan.md",
    ]
    for path in required:
        assert path.exists(), f"Missing required doc: {path}"


def test_markdown_local_links_resolve() -> None:
    broken: list[tuple[str, str, str]] = []
    for markdown in MARKDOWN_FILES:
        content = markdown.read_text(encoding="utf-8")
        for raw_link in LINK_PATTERN.findall(content):
            link = raw_link.strip()
            if not link or _is_external_link(link) or link.startswith("#"):
                continue
            link_path = link.split("#", 1)[0]
            target = (markdown.parent / link_path).resolve()
            if not target.exists():
                broken.append((str(markdown.relative_to(REPO_ROOT)), link, str(target)))

    assert not broken, "Broken local links:\n" + "\n".join(
        f"- {src}: {link} -> {resolved}" for src, link, resolved in broken
    )
