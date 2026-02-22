from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from skillforge.ir import NormalizedSkillSpec, NormalizedStep
from skillforge.parser import SkillSpecParseError, SkillSpecSchemaError, parse_spec
from skillforge.testing.connector_mocks import (
    ConnectorMockError,
    FixtureConnectorMocks,
    build_default_happy_fixture,
    load_fixture_payload,
)
from skillforge.validator import validate_semantics

HarnessMode = Literal["quick", "smoke"]
STEP_REFERENCE_KEYS = {"body_from", "from_step", "step"}


@dataclass(frozen=True)
class HarnessFailure:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class HarnessResult:
    mode: HarnessMode
    ok: bool
    checks_run: int
    failures: tuple[HarnessFailure, ...] = ()


@dataclass(frozen=True)
class _QuickOutcome:
    result: HarnessResult
    parsed_spec: Any | None


def _format_parse_error(
    code: str,
    message: str,
    diagnostics: list[Any],
) -> tuple[HarnessFailure, ...]:
    if diagnostics:
        return tuple(
            HarnessFailure(code=code, path=diag.path, message=diag.message) for diag in diagnostics
        )
    return (HarnessFailure(code=code, path="<root>", message=message),)


def _resolve_scalar(
    key: str | None,
    value: str,
    *,
    inputs: dict[str, Any],
    step_outputs: dict[str, Any],
) -> Any:
    if value.startswith("{") and value.endswith("}"):
        input_name = value[1:-1]
        if input_name in inputs:
            return inputs[input_name]
    if key in STEP_REFERENCE_KEYS and value in step_outputs:
        return step_outputs[value]
    return value


def _resolve_step_args(
    value: Any,
    *,
    inputs: dict[str, Any],
    step_outputs: dict[str, Any],
    key: str | None = None,
) -> Any:
    if isinstance(value, dict):
        return {
            inner_key: _resolve_step_args(
                inner_value,
                inputs=inputs,
                step_outputs=step_outputs,
                key=inner_key,
            )
            for inner_key, inner_value in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_step_args(item, inputs=inputs, step_outputs=step_outputs, key=key)
            for item in value
        ]
    if isinstance(value, str):
        return _resolve_scalar(key, value, inputs=inputs, step_outputs=step_outputs)
    return value


def _run_transform(step: NormalizedStep, resolved_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "step": step.id,
        "use": step.use,
        "args": resolved_args,
    }


def _run_smoke(
    *,
    spec: NormalizedSkillSpec,
    fixture_payload: dict[str, Any],
) -> HarnessResult:
    try:
        connector_mocks = FixtureConnectorMocks.from_fixture_payload(fixture_payload)
    except ConnectorMockError as exc:
        return HarnessResult(
            mode="smoke",
            ok=False,
            checks_run=1,
            failures=(HarnessFailure(code=exc.code, path="fixture.connectors", message=str(exc)),),
        )

    step_outputs: dict[str, Any] = {}
    fixture_inputs = fixture_payload.get("inputs", {})
    if not isinstance(fixture_inputs, dict):
        return HarnessResult(
            mode="smoke",
            ok=False,
            checks_run=1,
            failures=(
                HarnessFailure(
                    code="invalid_fixture_shape",
                    path="fixture.inputs",
                    message="Fixture field 'inputs' must be an object when provided.",
                ),
            ),
        )

    checks_run = 0
    failures: list[HarnessFailure] = []

    for index, step in enumerate(spec.workflow_steps):
        checks_run += 1
        resolved_args = _resolve_step_args(
            step.args,
            inputs=fixture_inputs,
            step_outputs=step_outputs,
        )

        if not step.use.startswith("connector."):
            step_outputs[step.id] = _run_transform(step, resolved_args)
            continue

        parts = step.use.split(".")
        if len(parts) < 3:
            failures.append(
                HarnessFailure(
                    code="invalid_connector_use",
                    path=f"workflow.steps[{index}].use",
                    message=f"Connector step '{step.id}' has invalid use value '{step.use}'.",
                )
            )
            break

        connector_name = parts[1]
        action = parts[2]

        try:
            response = connector_mocks.invoke(
                connector=connector_name,
                action=action,
                request=resolved_args,
            )
        except ConnectorMockError as exc:
            failures.append(
                HarnessFailure(
                    code=exc.code,
                    path=f"workflow.steps[{index}]",
                    message=str(exc),
                )
            )
            break

        if response.get("status") == "error":
            failures.append(
                HarnessFailure(
                    code=str(response.get("error_code", "connector_failure")),
                    path=f"workflow.steps[{index}]",
                    message=(
                        f"Connector '{connector_name}.{action}' returned error status from fixture."
                    ),
                )
            )
            break

        step_outputs[step.id] = response

    return HarnessResult(
        mode="smoke",
        ok=not failures,
        checks_run=checks_run,
        failures=tuple(failures),
    )


def run_harness(
    *,
    mode: HarnessMode,
    spec_path: Path,
    fixture_path: Path | None = None,
    allow_guessed_publisher_slugs: set[str] | None = None,
) -> HarnessResult:
    quick_outcome = _run_quick_with_parse_with_options(
        spec_path,
        allow_guessed_publisher_slugs=allow_guessed_publisher_slugs,
    )
    if mode == "quick":
        return quick_outcome.result

    if mode != "smoke":
        raise ValueError(f"Unsupported test mode: {mode}")

    if not quick_outcome.result.ok:
        return HarnessResult(
            mode="smoke",
            ok=False,
            checks_run=quick_outcome.result.checks_run,
            failures=quick_outcome.result.failures,
        )

    assert quick_outcome.parsed_spec is not None  # safety for static type checking
    spec = quick_outcome.parsed_spec.ir

    try:
        if fixture_path is not None:
            fixture_payload = load_fixture_payload(fixture_path)
        else:
            default_fixture = spec_path.parent / "tests" / "fixtures" / "happy_path.json"
            if default_fixture.exists():
                fixture_payload = load_fixture_payload(default_fixture)
            else:
                fixture_payload = build_default_happy_fixture(spec)
    except ConnectorMockError as exc:
        return HarnessResult(
            mode="smoke",
            ok=False,
            checks_run=quick_outcome.result.checks_run,
            failures=(HarnessFailure(code=exc.code, path="fixture", message=str(exc)),),
        )

    smoke_result = _run_smoke(spec=spec, fixture_payload=fixture_payload)
    return HarnessResult(
        mode="smoke",
        ok=smoke_result.ok,
        checks_run=quick_outcome.result.checks_run + smoke_result.checks_run,
        failures=smoke_result.failures,
    )


def _run_quick_with_parse_with_options(
    spec_path: Path,
    *,
    allow_guessed_publisher_slugs: set[str] | None,
) -> _QuickOutcome:
    try:
        parsed = parse_spec(spec_path)
    except SkillSpecSchemaError as exc:
        return _QuickOutcome(
            result=HarnessResult(
                mode="quick",
                ok=False,
                checks_run=1,
                failures=_format_parse_error(
                    code="schema_validation_error",
                    message=str(exc),
                    diagnostics=exc.diagnostics,
                ),
            ),
            parsed_spec=None,
        )
    except SkillSpecParseError as exc:
        return _QuickOutcome(
            result=HarnessResult(
                mode="quick",
                ok=False,
                checks_run=1,
                failures=_format_parse_error(
                    code="parse_error",
                    message=str(exc),
                    diagnostics=exc.diagnostics,
                ),
            ),
            parsed_spec=None,
        )

    semantic_result = validate_semantics(
        parsed.model,
        allow_guessed_publisher_slugs=allow_guessed_publisher_slugs or set(),
    )
    if semantic_result.diagnostics:
        failures = tuple(
            HarnessFailure(
                code=diagnostic.code,
                path=diagnostic.path,
                message=diagnostic.message,
            )
            for diagnostic in semantic_result.diagnostics
        )
        return _QuickOutcome(
            result=HarnessResult(
                mode="quick",
                ok=False,
                checks_run=2,
                failures=failures,
            ),
            parsed_spec=parsed,
        )

    return _QuickOutcome(
        result=HarnessResult(
            mode="quick",
            ok=True,
            checks_run=2,
            failures=(),
        ),
        parsed_spec=parsed,
    )
