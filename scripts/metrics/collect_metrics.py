#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from skillforge.commands.generate import _render_outputs
from skillforge.parser import parse_spec
from skillforge.testing.harness import run_harness


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _load_retries(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Retries file must be a JSON object mapping skill -> retry count.")
    retries: dict[str, int] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, int) or value < 0:
            raise ValueError("Retries file values must be non-negative integers.")
        retries[key] = value
    return retries


def _discover_specs(input_dir: Path) -> list[Path]:
    specs = sorted(input_dir.rglob("skill.spec.yaml"))
    if not specs:
        raise ValueError(f"No skill.spec.yaml files found under {input_dir}")
    return specs


def _manual_files_touched(spec_path: Path) -> int:
    fixture_override = spec_path.parent / "fixture.override.json"
    return 2 if fixture_override.exists() else 1


def _round(value: float) -> float:
    return round(value, 4)


def collect_metrics(
    *,
    input_dir: Path,
    retries_by_skill: dict[str, int] | None = None,
) -> dict[str, Any]:
    retries_lookup = retries_by_skill or {}
    specs = _discover_specs(input_dir)

    skills: list[dict[str, Any]] = []
    authored_total = 0
    generated_total = 0
    quick_pass_count = 0
    smoke_pass_count = 0
    total_retries = 0
    total_manual_files = 0

    for spec_path in specs:
        parsed = parse_spec(spec_path)
        outputs = _render_outputs(spec_path)

        skill_name = parsed.ir.skill
        authored_loc = _line_count(spec_path.read_text(encoding="utf-8"))
        generated_loc = sum(_line_count(content) for content in outputs.values())
        quick_result = run_harness(mode="quick", spec_path=spec_path)
        smoke_result = run_harness(mode="smoke", spec_path=spec_path)
        retries = retries_lookup.get(skill_name, 0)
        manual_files = _manual_files_touched(spec_path)

        authored_total += authored_loc
        generated_total += generated_loc
        quick_pass_count += int(quick_result.ok)
        smoke_pass_count += int(smoke_result.ok)
        total_retries += retries
        total_manual_files += manual_files

        ratio = generated_loc / authored_loc if authored_loc else 0.0
        skills.append(
            {
                "skill": skill_name,
                "spec_path": spec_path.relative_to(input_dir).as_posix(),
                "authored_loc": authored_loc,
                "generated_loc": generated_loc,
                "generated_authored_loc_ratio": _round(ratio),
                "manual_files_touched": manual_files,
                "quick_pass": quick_result.ok,
                "smoke_pass": smoke_result.ok,
                "retries_to_green": retries,
            }
        )

    skill_count = len(skills)
    overall_ratio = generated_total / authored_total if authored_total else 0.0
    mean_manual_files = total_manual_files / skill_count if skill_count else 0.0
    mean_retries = total_retries / skill_count if skill_count else 0.0

    return {
        "metrics_version": 1,
        "input_dir": input_dir.as_posix(),
        "skills": skills,
        "summary": {
            "skill_count": skill_count,
            "density": {
                "authored_total_loc": authored_total,
                "generated_total_loc": generated_total,
                "generated_authored_loc_ratio": _round(overall_ratio),
                "mean_manual_files_touched": _round(mean_manual_files),
            },
            "integration": {
                "quick_pass_rate": _round(quick_pass_count / skill_count),
                "smoke_pass_rate": _round(smoke_pass_count / skill_count),
                "mean_retries_to_green": _round(mean_retries),
            },
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect SkillForge pilot metrics as JSON.")
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing skill migration specs.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Optional output file path. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--retries-json",
        type=Path,
        help="Optional JSON file mapping skill name to retries_to_green.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = collect_metrics(
        input_dir=args.input_dir,
        retries_by_skill=_load_retries(args.retries_json),
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

