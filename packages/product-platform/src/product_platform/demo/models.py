"""Demo Lab API models and JSON helpers."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DemoRequiredService(BaseModel):
    """A service the local demo scenario expects to be available."""

    key: str
    label: str
    required: bool = True
    health_endpoint: str | None = None
    evidence_route: str | None = None

    @field_validator("key")
    @classmethod
    def _normalize_key(cls, value: str) -> str:
        normalized = value.strip().lower().replace("_", "-")
        if not normalized:
            raise ValueError("service key must not be blank.")
        return normalized

    @field_validator("label")
    @classmethod
    def _strip_label(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("service label must not be blank.")
        return stripped


class DemoProofLink(BaseModel):
    """Expected product evidence link for a scenario step."""

    area: str
    label: str
    route: str
    resource_hint: str | None = None


class DemoEvidenceLink(BaseModel):
    """Concrete evidence link generated from a completed step result."""

    area: str
    label: str
    route: str
    resource_id: str | None = None
    correlation_id: str | None = None


class DemoProofChecklistItem(BaseModel):
    """Proof checklist row for expected versus actual scenario evidence."""

    area: str
    label: str
    status: str
    route: str
    expected_result: str
    actual_result: str | None = None


class DemoScenarioStepResponse(BaseModel):
    """A single ordered scenario definition step."""

    id: str
    scenario_id: str
    step_order: int
    title: str
    expected_result: str
    action_type: str
    action_config: dict[str, Any] = Field(default_factory=dict)
    proof_links: list[DemoProofLink] = Field(default_factory=list)
    created_at: str
    updated_at: str


class DemoScenarioSummaryResponse(BaseModel):
    """Scenario catalog item shown before a run starts."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    slug: str
    description: str
    value_proof: str
    status: str
    required_services: list[DemoRequiredService] = Field(default_factory=list)
    created_at: str
    updated_at: str


class DemoScenarioDetailResponse(DemoScenarioSummaryResponse):
    """Scenario detail with ordered executable steps."""

    steps: list[DemoScenarioStepResponse] = Field(default_factory=list)


class DemoRunStatus:
    """Terminal and non-terminal demo run statuses."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class DemoStepRunStatus:
    """Step execution statuses for one demo run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class DemoStepRunResponse(BaseModel):
    """Execution state for one scenario step in a run."""

    id: str
    demo_run_id: str
    demo_step_id: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str
    updated_at: str
    step: DemoScenarioStepResponse | None = None
    actual_result: str | None = None
    evidence_links: list[DemoEvidenceLink] = Field(default_factory=list)
    proof_checklist: list[DemoProofChecklistItem] = Field(default_factory=list)


class DemoRunResponse(BaseModel):
    """Scenario run state returned by the Demo Lab API."""

    id: str
    organization_id: str
    environment_id: str
    scenario_id: str
    status: str
    started_by: str
    started_at: str
    finished_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    scenario: DemoScenarioSummaryResponse | None = None
    step_runs: list[DemoStepRunResponse] = Field(default_factory=list)


class DemoResetStatus:
    """Demo environment reset run statuses."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DemoResetRequest(BaseModel):
    """Request to reset the selected local demo environment."""

    confirmation: str | None = None
    reason: str | None = None


class DemoResetRunResponse(BaseModel):
    """Reset execution history returned by the Demo Lab API."""

    id: str
    organization_id: str
    environment_id: str
    status: str
    requested_by: str
    started_at: str
    finished_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class DemoBaselineCheck(BaseModel):
    """One prerequisite check for the local demo baseline."""

    key: str
    label: str
    status: str
    required: bool
    detail: str
    count: int = 0
    expected_count: int | None = None
    missing: list[str] = Field(default_factory=list)


class DemoBaselineStatusResponse(BaseModel):
    """Overall local demo baseline status."""

    organization_id: str
    environment_id: str
    overall_status: str
    checked_at: str
    checks: list[DemoBaselineCheck] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)


def parse_required_services(raw_json: str) -> list[DemoRequiredService]:
    """Parse and validate a scenario required-services JSON list."""

    parsed = json.loads(raw_json)
    if not isinstance(parsed, list):
        raise ValueError("required services JSON must be a list.")
    return [DemoRequiredService.model_validate(item) for item in parsed]


def parse_proof_links(raw_json: str) -> list[DemoProofLink]:
    """Parse and validate a scenario step proof-link JSON list."""

    parsed = json.loads(raw_json)
    if not isinstance(parsed, list):
        raise ValueError("proof links JSON must be a list.")
    return [DemoProofLink.model_validate(item) for item in parsed]
