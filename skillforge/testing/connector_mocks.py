from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from skillforge.ir import NormalizedSkillSpec


class ConnectorMockError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _coerce_default_input_value(definition: dict[str, Any]) -> Any:
    if "default" in definition:
        return definition["default"]

    input_type = definition.get("type")
    if input_type == "string":
        return ""
    if input_type == "number":
        return 0.0
    if input_type == "integer":
        return 0
    if input_type == "boolean":
        return False
    return None


def _workflow_connector_actions(spec: NormalizedSkillSpec) -> dict[str, set[str]]:
    actions: dict[str, set[str]] = {}
    for step in spec.workflow_steps:
        if not step.use.startswith("connector."):
            continue
        parts = step.use.split(".")
        if len(parts) < 3:
            continue
        connector_name = parts[1]
        action = parts[2]
        actions.setdefault(connector_name, set()).add(action)
    return actions


def build_default_happy_fixture(spec: NormalizedSkillSpec) -> dict[str, Any]:
    connectors: dict[str, dict[str, Any]] = {}
    for connector_name, actions in sorted(_workflow_connector_actions(spec).items()):
        connectors[connector_name] = {
            action: {
                "status": "ok",
                "connector": connector_name,
                "action": action,
            }
            for action in sorted(actions)
        }

    inputs = {
        input_name: _coerce_default_input_value(definition)
        for input_name, definition in sorted(spec.inputs.items())
    }

    return {
        "skill": spec.skill,
        "dry_run": bool(spec.policies.get("dry_run_default", True)),
        "inputs": inputs,
        "connectors": connectors,
    }


def load_fixture_payload(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConnectorMockError(
            code="fixture_not_found",
            message=f"Fixture file does not exist: {path}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise ConnectorMockError(
            code="fixture_parse_error",
            message=f"Fixture file is not valid JSON: {path} ({exc})",
        ) from exc

    if not isinstance(parsed, dict):
        raise ConnectorMockError(
            code="invalid_fixture_shape",
            message=f"Fixture must be a top-level JSON object: {path}",
        )
    return parsed


class FixtureConnectorMocks:
    def __init__(self, connector_payloads: dict[str, Any]):
        self._connector_payloads = connector_payloads

    @classmethod
    def from_fixture_payload(cls, payload: dict[str, Any]) -> "FixtureConnectorMocks":
        connectors = payload.get("connectors", {})
        if not isinstance(connectors, dict):
            raise ConnectorMockError(
                code="invalid_fixture_shape",
                message="Fixture field 'connectors' must be an object.",
            )
        return cls(connector_payloads=connectors)

    def invoke(self, connector: str, action: str, request: dict[str, Any]) -> dict[str, Any]:
        connector_payload = self._connector_payloads.get(connector)
        if connector_payload is None:
            raise ConnectorMockError(
                code="missing_connector_fixture",
                message=f"Missing fixture for connector '{connector}'.",
            )
        if not isinstance(connector_payload, dict):
            raise ConnectorMockError(
                code="invalid_fixture_shape",
                message=f"Fixture for connector '{connector}' must be an object.",
            )

        payload = connector_payload.get(action)
        if payload is None:
            payload = connector_payload.get("*")
        if payload is None:
            raise ConnectorMockError(
                code="missing_connector_fixture",
                message=(
                    f"Missing fixture for connector '{connector}' action '{action}'. "
                    "Add an explicit action payload or a '*' fallback."
                ),
            )

        if not isinstance(payload, dict):
            raise ConnectorMockError(
                code="invalid_fixture_shape",
                message=(
                    f"Fixture payload for connector '{connector}' action '{action}' "
                    "must be an object."
                ),
            )

        response = copy.deepcopy(payload)
        response.setdefault("request", request)
        return response

