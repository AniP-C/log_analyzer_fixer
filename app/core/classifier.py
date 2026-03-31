from __future__ import annotations

from dataclasses import dataclass

from app.utils.logger import log_flow_trace

ISSUE_TYPES = (
    "workflow_stuck",
    "bulk_orders_created",
    "workflow_failure",
    "faulty_order_paypal",
    "delayed_batch_export",
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
        log_flow_trace(
            "classification",
            "app.core.classifier.IssueClassifier.classify",
            "classify_begin",
            {"input_length": len(raw_input)},
        )
        normalized = raw_input.lower()

        if ("created" in normalized) and any(k in normalized for k in ("many", "bulk", "spike")):
            result = ClassificationResult(
                issue_type="bulk_orders_created",
                confidence=0.9,
                rationale="Matched bulk/spike wording with CREATED status.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "bulk_orders_created"},
            )
            return result

        if ("paypal" in normalized) and any(k in normalized for k in ("missing billing address", "billing address missing", "no billing address")):
            result = ClassificationResult(
                issue_type="faulty_order_paypal",
                confidence=0.92,
                rationale="Matched PayPal + missing billing address pattern.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "faulty_order_paypal"},
            )
            return result

        if any(k in normalized for k in ("delayed", "delay", "late")) and any(
            k in normalized for k in ("next run", "combined", "two batches", "double batch", "spike")
        ):
            result = ClassificationResult(
                issue_type="delayed_batch_export",
                confidence=0.88,
                rationale="Matched delayed then spike/combined batch export pattern.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "delayed_batch_export"},
            )
            return result

        if any(k in normalized for k in ("timeout", "timed out", "dependency failure", "service unavailable", "502", "503", "504")):
            result = ClassificationResult(
                issue_type="workflow_failure",
                confidence=0.86,
                rationale="Matched downstream timeout/dependency failure indicators.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "workflow_failure_downstream"},
            )
            return result

        if any(k in normalized for k in ("validation", "invalid", "bad data", "schema", "missing required", "cannot parse")):
            result = ClassificationResult(
                issue_type="workflow_failure",
                confidence=0.84,
                rationale="Matched upstream validation/bad-data failure indicators.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "workflow_failure_upstream"},
            )
            return result

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
            result = ClassificationResult(
                issue_type="data_issue_invalid_chars",
                confidence=0.91,
                rationale="Matched invalid character and data quality indicators.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "data_issue_invalid_chars"},
            )
            return result

        if any(keyword in normalized for keyword in ("file failed", "batch failed", "processing failure", "workflow execution failed", "job failed")):
            result = ClassificationResult(
                issue_type="file_processing_failure",
                confidence=0.83,
                rationale="Matched file or workflow execution failure indicators.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "file_processing_failure"},
            )
            return result

        if any(keyword in normalized for keyword in ("stuck", "queued", "hung", "processing", "waiting")):
            result = ClassificationResult(
                issue_type="workflow_stuck",
                confidence=0.8,
                rationale="Matched workflow delay and stuck-state indicators.",
            )
            log_flow_trace(
                "classification",
                "app.core.classifier.IssueClassifier.classify",
                "classify_end",
                {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "workflow_stuck"},
            )
            return result

        result = ClassificationResult(
            issue_type="workflow_stuck",
            confidence=0.55,
            rationale="Defaulted to the most common operational issue due to weak signal.",
        )
        log_flow_trace(
            "classification",
            "app.core.classifier.IssueClassifier.classify",
            "classify_end",
            {"issue_type": result.issue_type, "confidence": result.confidence, "branch": "default_weak_signal"},
        )
        return result
