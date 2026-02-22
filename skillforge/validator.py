from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillforge.models import SkillSpecModel
from skillforge.parser import parse_spec

GUESSED_RPC_SLUG_PATTERN = re.compile(r"^rpc-[a-z0-9-]+$")


@dataclass(frozen=True)
class SemanticDiagnostic:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class SemanticValidationResult:
    diagnostics: list[SemanticDiagnostic]

    @property
    def ok(self) -> bool:
        return not self.diagnostics


def _is_risk_skill(spec: SkillSpecModel) -> bool:
    if "trader" in spec.skill:
        return True
    category = spec.metadata.get("category", "").lower()
    return category in {"trading", "execution"}


def _extract_step_reference_targets(step_args: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("body_from", "from_step", "step", "depends_on"):
        value = step_args.get(key)
        if isinstance(value, str):
            refs.append(value)
        elif key == "depends_on" and isinstance(value, list):
            refs.extend(item for item in value if isinstance(item, str))
    return refs


def validate_semantics(
    spec: SkillSpecModel,
    *,
    allow_guessed_publisher_slugs: set[str] | None = None,
) -> SemanticValidationResult:
    diagnostics: list[SemanticDiagnostic] = []
    allow_guessed = allow_guessed_publisher_slugs or set()

    # Rule: workflow step IDs must be unique.
    seen_step_ids: set[str] = set()
    for index, step in enumerate(spec.workflow.steps):
        if step.id in seen_step_ids:
            diagnostics.append(
                SemanticDiagnostic(
                    code="duplicate_step_id",
                    path=f"workflow.steps[{index}].id",
                    message=f"Duplicate workflow step id '{step.id}'.",
                )
            )
        seen_step_ids.add(step.id)

    # Rule: connector references in `use` must resolve.
    for index, step in enumerate(spec.workflow.steps):
        if step.use.startswith("connector."):
            parts = step.use.split(".")
            if len(parts) < 3:
                diagnostics.append(
                    SemanticDiagnostic(
                        code="invalid_connector_use",
                        path=f"workflow.steps[{index}].use",
                        message=(
                            f"Connector use '{step.use}' must follow "
                            "connector.<name>.<action>."
                        ),
                    )
                )
                continue
            connector_name = parts[1]
            if connector_name not in spec.connectors:
                diagnostics.append(
                    SemanticDiagnostic(
                        code="missing_connector",
                        path=f"workflow.steps[{index}].use",
                        message=(
                            f"Workflow step '{step.id}' references missing connector "
                            f"'{connector_name}'."
                        ),
                    )
                )

    # Rule: explicit step references must point to prior steps.
    available_step_ids: set[str] = set()
    for index, step in enumerate(spec.workflow.steps):
        for ref in _extract_step_reference_targets(step.with_ or {}):
            if ref not in available_step_ids:
                diagnostics.append(
                    SemanticDiagnostic(
                        code="invalid_step_reference",
                        path=f"workflow.steps[{index}].with",
                        message=(
                            f"Workflow step '{step.id}' references unknown or future step '{ref}'."
                        ),
                    )
                )
        available_step_ids.add(step.id)

    # Rule: publisher connector slugs must be explicit, non-empty values.
    for connector_name, connector in spec.connectors.items():
        publisher = connector.publisher
        if publisher is None or not str(publisher).strip():
            diagnostics.append(
                SemanticDiagnostic(
                    code="missing_publisher_slug",
                    path=f"connectors.{connector_name}.publisher",
                    message=(
                        f"Connector '{connector_name}' must define a non-empty publisher slug."
                    ),
                )
            )
            continue

        publisher_slug = str(publisher).strip()
        if (
            GUESSED_RPC_SLUG_PATTERN.fullmatch(publisher_slug)
            and publisher_slug not in allow_guessed
        ):
            diagnostics.append(
                SemanticDiagnostic(
                    code="guessed_publisher_slug",
                    path=f"connectors.{connector_name}.publisher",
                    message=(
                        f"Connector '{connector_name}' uses guessed publisher slug "
                        f"'{publisher_slug}'. Resolve against live catalog or allowlist it."
                    ),
                )
            )

    # Rule: risk skills need explicit safety policy configuration.
    if _is_risk_skill(spec):
        if spec.policies is None:
            diagnostics.append(
                SemanticDiagnostic(
                    code="missing_policies",
                    path="policies",
                    message="Risk skills require a policies section.",
                )
            )
        else:
            if spec.policies.dry_run_default is not True:
                diagnostics.append(
                    SemanticDiagnostic(
                        code="dry_run_default_required",
                        path="policies.dry_run_default",
                        message="Risk skills must set policies.dry_run_default to true.",
                    )
                )
            if spec.policies.idempotency_required is not True:
                diagnostics.append(
                    SemanticDiagnostic(
                        code="idempotency_required",
                        path="policies.idempotency_required",
                        message="Risk skills must set policies.idempotency_required to true.",
                    )
                )
            if (
                spec.policies.max_daily_spend_usd is None
                and spec.policies.max_notional_usd is None
            ):
                diagnostics.append(
                    SemanticDiagnostic(
                        code="risk_budget_cap_required",
                        path="policies",
                        message=(
                            "Risk skills must define at least one spend cap "
                            "(max_daily_spend_usd or max_notional_usd)."
                        ),
                    )
                )

    return SemanticValidationResult(diagnostics=diagnostics)


def validate_semantics_from_path(
    path: Path,
    *,
    allow_guessed_publisher_slugs: set[str] | None = None,
) -> SemanticValidationResult:
    parsed = parse_spec(path)
    return validate_semantics(
        parsed.model,
        allow_guessed_publisher_slugs=allow_guessed_publisher_slugs,
    )
