from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skillforge.models import SkillSpecModel


@dataclass(frozen=True)
class NormalizedStep:
    id: str
    use: str
    args: dict[str, Any]


@dataclass(frozen=True)
class NormalizedRuntime:
    language: str
    entrypoint: str


@dataclass(frozen=True)
class NormalizedSkillSpec:
    skill: str
    description: str
    triggers: tuple[str, ...]
    runtime: NormalizedRuntime
    inputs: dict[str, dict[str, Any]]
    secrets: tuple[str, ...]
    connectors: dict[str, dict[str, Any]]
    state: dict[str, dict[str, Any]]
    policies: dict[str, Any]
    tests: dict[str, tuple[str, ...]]
    workflow_steps: tuple[NormalizedStep, ...]
    publish: dict[str, str] | None
    metadata: dict[str, str]


def to_ir(spec: SkillSpecModel) -> NormalizedSkillSpec:
    tests = spec.tests.model_dump(exclude_none=True) if spec.tests else {}
    tests_normalized = {name: tuple(items) for name, items in tests.items()}

    policies = spec.policies.model_dump(exclude_none=True) if spec.policies else {}
    publish = spec.publish.model_dump() if spec.publish else None

    workflow_steps = tuple(
        NormalizedStep(
            id=step.id,
            use=step.use,
            args=step.with_ or {},
        )
        for step in spec.workflow.steps
    )

    return NormalizedSkillSpec(
        skill=spec.skill,
        description=spec.description,
        triggers=tuple(spec.triggers),
        runtime=NormalizedRuntime(
            language=spec.runtime.language,
            entrypoint=spec.runtime.entrypoint,
        ),
        inputs={
            name: definition.model_dump(exclude_none=True)
            for name, definition in spec.inputs.items()
        },
        secrets=tuple(spec.secrets),
        connectors={
            name: definition.model_dump(exclude_none=True)
            for name, definition in spec.connectors.items()
        },
        state={
            name: definition.model_dump(exclude_none=True)
            for name, definition in spec.state.items()
        },
        policies=policies,
        tests=tests_normalized,
        workflow_steps=workflow_steps,
        publish=publish,
        metadata=dict(spec.metadata),
    )

