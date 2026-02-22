from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["python"]
    entrypoint: str


class InputDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["string", "number", "integer", "boolean"]
    description: str | None = None
    default: Any | None = None
    enum: list[Any] | None = None
    min: float | None = None
    max: float | None = None


class ConnectorDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["seren_publisher"]
    publisher: str | None = None
    base_path: str | None = None


class StateDefinitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["sqlite", "postgres", "serendb"]
    file: str | None = None
    database: str | None = None
    table: str | None = None


class PoliciesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run_default: bool | None = None
    idempotency_required: bool | None = None
    max_daily_spend_usd: float | None = Field(default=None, ge=0)
    max_notional_usd: float | None = Field(default=None, ge=0)
    max_slippage_bps: int | None = Field(default=None, ge=0, le=10000)


class WorkflowStepModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    use: str
    with_: dict[str, Any] | None = Field(default=None, alias="with")


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[WorkflowStepModel]


class TestsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quick: list[str] | None = None
    smoke: list[str] | None = None
    live: list[str] | None = None


class PublishModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org: str
    slug: str


class SkillSpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    description: str
    triggers: list[str]
    runtime: RuntimeModel
    workflow: WorkflowModel
    inputs: dict[str, InputDefinitionModel] = Field(default_factory=dict)
    secrets: list[str] = Field(default_factory=list)
    connectors: dict[str, ConnectorDefinitionModel] = Field(default_factory=dict)
    state: dict[str, StateDefinitionModel] = Field(default_factory=dict)
    policies: PoliciesModel | None = None
    tests: TestsModel | None = None
    publish: PublishModel | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

