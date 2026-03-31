from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    input: str = Field(..., min_length=5, description="Operational issue description or log excerpt.")


class HealthResponse(BaseModel):
    status: str
    service: str


DecisionType = Literal["retry_workflow", "remove_and_reprocess", "isolate_and_rerun_batch", "escalate", "no_action"]
SeverityType = Literal["low", "medium", "high"]
NotificationType = Literal["none", "email", "slack", "slack+email", "escalate"]


class Impact(BaseModel):
    orders_affected: int = 0
    scope: Literal["single", "batch"] = "single"
    notes: str | None = None


class ExecutionStepLog(BaseModel):
    step: str
    status: Literal["success", "failed", "skipped"] = "success"
    detail: str | None = None


class ReasoningResult(BaseModel):
    decision: DecisionType
    root_cause: str
    confidence: float
    severity: SeverityType
    impact: Impact
    why: list[str] = Field(default_factory=list)
    recovery_plan: list[str] = Field(default_factory=list)
    correlated_incidents: bool = False
    common_root_cause: str | None = None
    possible_actions: list[dict[str, Any]] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    issue_type: str
    root_cause: str
    decision: DecisionType
    confidence: float
    severity: SeverityType
    impact: Impact
    why: list[str]
    recovery_plan: list[str]
    execution_log: list[ExecutionStepLog]
    timeline: list[str]
    notification: NotificationType
    correlated_incidents: bool
    common_root_cause: str | None = None

    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    execution_status: Literal["success", "partial", "failed", "skipped"] = "skipped"
    target: str = "unknown_target"
    response_time_ms: float

    comparison: dict[str, Any] | None = None


class CaseResult(BaseModel):
    input: str
    expected_issue_type: str
    expected_action: str
    actual_issue_type: str
    actual_action: str
    confidence: float
    response_time_ms: float
    passed_issue_type: bool
    passed_action: bool
    execution_status: str


class BenchmarkSummary(BaseModel):
    total_cases: int
    detection_accuracy: float
    action_accuracy: float
    resolution_success: float
    response_time_score: float
    overall_score: int


class BenchmarkResponse(BaseModel):
    summary: BenchmarkSummary
    results: list[CaseResult]
