from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskFamily(StrEnum):
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    CONTEXT_QA = "context_qa"


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"
    ERROR = "error"


class TaskContract(StrictModel):
    id: str
    version: str
    family: TaskFamily
    description: str
    output_schema: dict[str, Any]
    taxonomy: dict[str, str] | None = None
    required_checks: list[str]
    allow_abstention: bool = False
    min_quality: float = Field(ge=0, le=1)
    max_source_chars: int = Field(gt=0)

    @model_validator(mode="after")
    def classification_has_taxonomy(self) -> "TaskContract":
        if self.family == TaskFamily.CLASSIFICATION and not self.taxonomy:
            raise ValueError("classification contracts require taxonomy")
        return self


class ModelProfile(StrictModel):
    contract_id: str
    model_alias: str
    successes: int = Field(ge=0)
    sample_size: int = Field(gt=0)
    quality_lower_bound: float = Field(ge=0, le=1)
    p95_latency_ms: int = Field(gt=0)
    expected_cost_microusd: int = Field(ge=0)
    qualified_fallback: bool = False


class DecisionSignals(StrictModel):
    task_family: TaskFamily | Literal["other"] | None = None
    missing_evidence_probability: float | None = Field(default=None, ge=0, le=1)
    difficulty_score: float | None = Field(default=None, ge=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class CallResult(StrictModel):
    status: Literal["succeeded", "failed", "unknown"]
    content: Any = None
    requested_model: str
    resolved_model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_microusd: int | None = None
    latency_ms: int
    error_code: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CheckResult(StrictModel):
    check_id: str
    version: str = "1"
    status: CheckStatus
    evidence: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class PolicySnapshot(StrictModel):
    id: str
    version: str
    profile_hash: str
    mode: Literal["fixture", "shadow", "active"]


class GenerateRequest(StrictModel):
    contract_id: str
    request: str
    source: str
    max_budget_microusd: int | None = Field(default=None, gt=0)
    deadline_ms: int | None = Field(default=None, gt=0)
    stream: bool = False


class GenerateResponse(StrictModel):
    request_id: str
    status: Literal["accepted", "rejected"]
    output: Any = None
    contract_passed: bool
    attempts: int
    final_model: str | None = None
    checks: list[CheckResult]
    cost_microusd: int | None = None
    cost_status: Literal["final", "estimated", "incomplete"]
    policy: PolicySnapshot
    error_code: str | None = None

