from __future__ import annotations

from pathlib import Path

import typer
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHETYPES_DIR = REPO_ROOT / "archetypes"


def _load_archetype(archetype: str) -> dict:
    archetype_path = ARCHETYPES_DIR / archetype / "skill.spec.yaml"
    if not archetype_path.exists():
        available = ", ".join(sorted(p.name for p in ARCHETYPES_DIR.iterdir() if p.is_dir()))
        raise typer.BadParameter(
            f"Unknown archetype '{archetype}'. Available archetypes: {available}"
        )
    return yaml.safe_load(archetype_path.read_text(encoding="utf-8"))


def run(
    archetype: str,
    org: str,
    name: str,
    target: Path,
    force: bool,
) -> Path:
    spec = _load_archetype(archetype)

    output_dir = target / org / name
    output_file = output_dir / "skill.spec.yaml"

    if output_file.exists() and not force:
        raise typer.BadParameter(
            f"{output_file} already exists. Re-run with --force to overwrite."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    spec["skill"] = name
    publish = spec.get("publish")
    if isinstance(publish, dict):
        publish["org"] = org
        publish["slug"] = name

    output_file.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    return output_file


def command(
    archetype: str = typer.Option(..., help="Archetype name from ./archetypes."),
    org: str = typer.Option(..., help="Org directory under the target repository."),
    name: str = typer.Option(..., help="Skill name (kebab-case)."),
    target: Path = typer.Option(Path("."), help="Base output directory."),
    force: bool = typer.Option(False, help="Overwrite existing skill.spec.yaml."),
) -> None:
    output_file = run(
        archetype=archetype,
        org=org,
        name=name,
        target=target,
        force=force,
    )
    typer.echo(f"Created {output_file}")

