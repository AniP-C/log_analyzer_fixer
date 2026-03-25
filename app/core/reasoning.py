from __future__ import annotations

from typing import Any

from app.models.schemas import ReasoningResult
from app.utils.llm_utils import llm_reason_about_issue


class ReasoningEngine:
    def reason(self, raw_input: str, issue_type: str, similar_cases: list[dict[str, Any]]) -> ReasoningResult:
        llm_result = llm_reason_about_issue(raw_input, issue_type, similar_cases)
        if llm_result:
            return ReasoningResult(**llm_result)

        top_case = similar_cases[0] if similar_cases else {}
        suggested_fix = top_case.get("fix", "manual_check")

        if issue_type == "workflow_stuck":
            return ReasoningResult(
                root_cause="Order-processing workflow appears blocked at an intermediate step.",
                possible_actions=[
                    {"action": "retry_workflow", "confidence": 0.86},
                    {"action": "manual_check", "confidence": 0.14},
                ],
                final_action="retry_workflow",
                confidence=0.86,
            )

        if issue_type == "data_issue_invalid_chars":
            return ReasoningResult(
                root_cause="Malformed billing or file data contains unsupported characters that break validation.",
                possible_actions=[
                    {"action": "remove_and_reprocess", "confidence": 0.88},
                    {"action": "manual_check", "confidence": 0.12},
                ],
                final_action="remove_and_reprocess",
                confidence=0.88,
            )

        if issue_type == "file_processing_failure":
            return ReasoningResult(
                root_cause="Batch or file handling failed while processing one or more orders.",
                possible_actions=[
                    {"action": "isolate_and_rerun_batch", "confidence": 0.82},
                    {"action": suggested_fix, "confidence": 0.18},
                ],
                final_action="isolate_and_rerun_batch",
                confidence=0.82,
            )

        return ReasoningResult(
            root_cause="Insufficient signal for a precise diagnosis.",
            possible_actions=[{"action": suggested_fix, "confidence": 0.6}],
            final_action=suggested_fix,
            confidence=0.6,
        )
