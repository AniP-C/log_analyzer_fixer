from __future__ import annotations

from dataclasses import dataclass

from app.utils.llm_utils import llm_classify_issue


ISSUE_TYPES = (
    "workflow_stuck",
    "data_issue_invalid_chars",
    "file_processing_failure",
)


@dataclass
class ClassificationResult:
    issue_type: str
    confidence: float
    rationale: str


class IssueClassifier:
    def classify(self, raw_input: str) -> ClassificationResult:
        llm_result = llm_classify_issue(raw_input, ISSUE_TYPES)
        if llm_result:
            return ClassificationResult(**llm_result)

        normalized = raw_input.lower()

        if any(
            keyword in normalized
            for keyword in (
                "invalid character",
                "invalid chars",
                "billing address",
                "bad character",
                "unsupported character",
                "parse error",
                "malformed",
            )
        ):
            return ClassificationResult(
                issue_type="data_issue_invalid_chars",
                confidence=0.91,
                rationale="Matched invalid character and data quality indicators.",
            )

        if any(keyword in normalized for keyword in ("file failed", "batch failed", "processing failure", "workflow execution failed", "job failed")):
            return ClassificationResult(
                issue_type="file_processing_failure",
                confidence=0.83,
                rationale="Matched file or workflow execution failure indicators.",
            )

        if any(keyword in normalized for keyword in ("stuck", "queued", "hung", "processing", "waiting")):
            return ClassificationResult(
                issue_type="workflow_stuck",
                confidence=0.8,
                rationale="Matched workflow delay and stuck-state indicators.",
            )

        return ClassificationResult(
            issue_type="workflow_stuck",
            confidence=0.55,
            rationale="Defaulted to the most common operational issue due to weak signal.",
        )
