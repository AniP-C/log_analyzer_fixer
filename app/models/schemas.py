from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    input: str = Field(..., min_length=5, description="Operational issue description or log excerpt.")


class HealthResponse(BaseModel):
    status: str
    service: str


class ReasoningResult(BaseModel):
    root_cause: str
    possible_actions: list[dict]
    final_action: str
    confidence: float


class AnalyzeResponse(BaseModel):
    issue_type: str
    root_cause: str
    action_taken: str
    execution_status: str
    notification: str
    confidence: float
    reasoning: list[dict]
    similar_cases: list[dict]
    execution_log: list[str]
    target: str
    response_time_ms: float


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
    overall_score: float


class BenchmarkResponse(BaseModel):
    summary: BenchmarkSummary
    results: list[CaseResult]
