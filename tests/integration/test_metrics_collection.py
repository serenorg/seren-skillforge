from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = REPO_ROOT / "scripts" / "metrics" / "collect_metrics.py"
MIGRATIONS = REPO_ROOT / "examples" / "migrations"


def _copy_specs(tmp_path: Path, names: list[str]) -> Path:
    input_dir = tmp_path / "migrations"
    for name in names:
        source = MIGRATIONS / name / "skill.spec.yaml"
        destination = input_dir / name / "skill.spec.yaml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return input_dir


def _run_collector(*, input_dir: Path, out_path: Path, retries_json: Path | None = None) -> None:
    cmd = [
        sys.executable,
        str(COLLECTOR),
        "--input-dir",
        str(input_dir),
        "--out",
        str(out_path),
    ]
    if retries_json is not None:
        cmd.extend(["--retries-json", str(retries_json)])
    subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_collect_metrics_outputs_reproducible_json(tmp_path: Path) -> None:
    input_dir = _copy_specs(tmp_path, ["browser-automation", "job-seeker"])
    out_one = tmp_path / "metrics-one.json"
    out_two = tmp_path / "metrics-two.json"

    _run_collector(input_dir=input_dir, out_path=out_one)
    _run_collector(input_dir=input_dir, out_path=out_two)

    text_one = out_one.read_text(encoding="utf-8")
    text_two = out_two.read_text(encoding="utf-8")
    assert text_one == text_two

    payload = json.loads(text_one)
    assert payload["metrics_version"] == 1
    assert payload["summary"]["skill_count"] == 2
    assert payload["summary"]["integration"]["quick_pass_rate"] == 1.0
    assert payload["summary"]["integration"]["smoke_pass_rate"] == 1.0
    assert payload["summary"]["density"]["generated_authored_loc_ratio"] > 0
    assert {skill["skill"] for skill in payload["skills"]} == {"browser-automation", "job-seeker"}
    assert all(skill["manual_files_touched"] == 1 for skill in payload["skills"])


def test_collect_metrics_applies_retry_overrides(tmp_path: Path) -> None:
    input_dir = _copy_specs(tmp_path, ["browser-automation"])
    retries_file = tmp_path / "retries.json"
    retries_file.write_text('{"browser-automation": 2}', encoding="utf-8")
    out_path = tmp_path / "metrics.json"

    _run_collector(input_dir=input_dir, out_path=out_path, retries_json=retries_file)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["summary"]["integration"]["mean_retries_to_green"] == 2.0
    assert payload["skills"][0]["retries_to_green"] == 2
