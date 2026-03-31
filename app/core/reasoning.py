from __future__ import annotations

import re
from typing import Any

from app.models.schemas import Impact, ReasoningResult
from app.utils.llm_utils import llm_reason_about_issue


class ReasoningEngine:
    def reason(self, raw_input: str, issue_type: str, similar_cases: list[dict[str, Any]]) -> ReasoningResult:
        normalized = raw_input.lower()

        # --- Mandatory scenario logic (deterministic, fast, and safe) ---
        # 1) Bulk Orders stuck in CREATED: detect spike/bulk, correlate, retry if safe.
        if ("created" in normalized) and any(k in normalized for k in ("many", "bulk", "spike")):
            impact = Impact(orders_affected=_extract_count(normalized) or 25, scope="batch", notes="Bulk spike indicated.")
            return ReasoningResult(
                decision="retry_workflow",
                confidence=0.8,
                severity="high",
                impact=impact,
                root_cause="Likely workflow orchestration stall impacting many orders in CREATED.",
                why=[
                    "Input indicates many orders stuck in CREATED (bulk/spike pattern).",
                    "Bulk stuck states typically reflect a shared workflow failure or dependency slowdown.",
                    _rag_success_why(similar_cases),
                ],
                recovery_plan=["validate_state", "check_downstream", "retry_workflow", "confirm_progress"],
                correlated_incidents=True,
                common_root_cause="workflow_or_dependency_stall",
                possible_actions=[
                    {"action": "retry_workflow", "confidence": 0.8},
                    {"action": "escalate", "confidence": 0.2},
                ],
            )

        # 2) Workflow Failure (Upstream vs Downstream): retry downstream; escalate upstream.
        if any(k in normalized for k in ("timeout", "timed out", "dependency failure", "service unavailable", "502", "503", "504")):
            impact = Impact(orders_affected=_extract_count(normalized) or 1, scope=_scope(normalized))
            return ReasoningResult(
                decision="retry_workflow",
                confidence=0.78,
                severity="medium" if impact.scope == "single" else "high",
                impact=impact,
                root_cause="Downstream dependency transient failure (timeout/unavailable).",
                why=["Error signature indicates downstream transient failure.", _rag_success_why(similar_cases)],
                recovery_plan=["check_downstream", "retry_workflow", "validate_state"],
                correlated_incidents=impact.scope == "batch",
                common_root_cause="downstream_transient_failure" if impact.scope == "batch" else None,
                possible_actions=[
                    {"action": "retry_workflow", "confidence": 0.78},
                    {"action": "escalate", "confidence": 0.22},
                ],
            )

        if any(k in normalized for k in ("validation", "invalid", "bad data", "schema", "missing required", "cannot parse")):
            impact = Impact(orders_affected=_extract_count(normalized) or 1, scope=_scope(normalized))
            return ReasoningResult(
                decision="escalate",
                confidence=0.82,
                severity="high" if impact.scope == "batch" else "medium",
                impact=impact,
                root_cause="Upstream data validation failure; retry would re-fail deterministically.",
                why=["Error signature indicates upstream validation/bad data.", "Retries will not fix invalid payloads; escalate for data correction."],
                recovery_plan=["collect_diagnostics", "escalate_to_oncall"],
                correlated_incidents=impact.scope == "batch",
                common_root_cause="upstream_validation_failure" if impact.scope == "batch" else None,
                possible_actions=[
                    {"action": "escalate", "confidence": 0.82},
                    {"action": "no_action", "confidence": 0.18},
                ],
            )

        # 3) Faulty Order in File (PayPal case): missing billing address when paid via PayPal.
        if ("paypal" in normalized) and any(k in normalized for k in ("missing billing address", "billing address missing", "no billing address")):
            impact = Impact(orders_affected=1, scope="batch", notes="Single faulty record blocks batch/file processing.")
            return ReasoningResult(
                decision="remove_and_reprocess",
                confidence=0.86,
                severity="medium",
                impact=impact,
                root_cause="A PayPal-paid order is missing billing address; validation blocks file processing.",
                why=[
                    "Pattern matches known PayPal billing-address missing validation blocker.",
                    "Safest recovery is to remove the faulty order and reprocess the file to unblock others.",
                    _rag_success_why(similar_cases),
                ],
                recovery_plan=["identify_faulty_order", "remove_faulty_order", "reprocess_file", "confirm_batch_success"],
                correlated_incidents=True,
                common_root_cause="paypal_missing_billing_address",
                possible_actions=[
                    {"action": "remove_and_reprocess", "confidence": 0.86},
                    {"action": "escalate", "confidence": 0.14},
                ],
            )

        # 4) Delayed Batch Export (False Alert): previous run delayed, next run spike (2 batches combined).
        if any(k in normalized for k in ("delayed", "delay", "late")) and any(k in normalized for k in ("next run", "combined", "two batches", "double batch", "spike")):
            impact = Impact(orders_affected=_extract_count(normalized) or 0, scope="batch", notes="Likely combined batches due to prior delay.")
            return ReasoningResult(
                decision="no_action",
                confidence=0.77,
                severity="low",
                impact=impact,
                root_cause="Delayed prior export caused the next run to include two batches; this is expected behavior.",
                why=[
                    "Pattern matches delayed-then-spike scenario (combined batches) without failure signals.",
                    "No remediation required; monitoring only.",
                ],
                recovery_plan=[],
                correlated_incidents=False,
                common_root_cause=None,
                possible_actions=[
                    {"action": "no_action", "confidence": 0.77},
                    {"action": "escalate", "confidence": 0.23},
                ],
            )

        # --- Grok reasoning (optional): enrich decision when not matched above ---
        llm_result = llm_reason_about_issue(raw_input, issue_type, similar_cases)
        if llm_result:
            return ReasoningResult(**llm_result)

        top_case = similar_cases[0] if similar_cases else {}
        suggested_fix = top_case.get("fix", "manual_check")

        if issue_type == "workflow_stuck":
            return ReasoningResult(
                decision="retry_workflow",
                root_cause="Order-processing workflow appears blocked at an intermediate step.",
                possible_actions=[
                    {"action": "retry_workflow", "confidence": 0.86},
                    {"action": "escalate", "confidence": 0.14},
                ],
                confidence=0.86,
                severity="medium",
                impact=Impact(orders_affected=_extract_count(normalized) or 1, scope=_scope(normalized)),
                why=[_rag_success_why(similar_cases), "Stuck-state indicators suggest a recoverable workflow stall."],
                recovery_plan=["validate_state", "check_downstream", "retry_workflow"],
            )

        if issue_type == "data_issue_invalid_chars":
            return ReasoningResult(
                decision="remove_and_reprocess",
                root_cause="Malformed billing or file data contains unsupported characters that break validation.",
                possible_actions=[
                    {"action": "remove_and_reprocess", "confidence": 0.88},
                    {"action": "escalate", "confidence": 0.12},
                ],
                confidence=0.88,
                severity="medium",
                impact=Impact(orders_affected=_extract_count(normalized) or 1, scope=_scope(normalized)),
                why=[_rag_success_why(similar_cases), "Data/validation errors are fixed by isolating faulty records and reprocessing."],
                recovery_plan=["identify_faulty_order", "remove_faulty_order", "reprocess_file"],
            )

        if issue_type == "file_processing_failure":
            return ReasoningResult(
                decision="isolate_and_rerun_batch",
                root_cause="Batch or file handling failed while processing one or more orders.",
                possible_actions=[
                    {"action": "isolate_and_rerun_batch", "confidence": 0.82},
                    {"action": suggested_fix, "confidence": 0.18},
                ],
                confidence=0.82,
                severity="high",
                impact=Impact(orders_affected=_extract_count(normalized) or 10, scope="batch"),
                why=[_rag_success_why(similar_cases), "Batch/file failures often recover via isolation + rerun."],
                recovery_plan=["validate_state", "isolate_and_rerun_batch", "confirm_batch_success"],
                correlated_incidents=True,
                common_root_cause="batch_processing_failure",
            )

        return ReasoningResult(
            decision="escalate" if suggested_fix == "manual_check" else "escalate",
            root_cause="Insufficient signal for a precise diagnosis.",
            possible_actions=[{"action": "escalate", "confidence": 0.6}],
            confidence=0.6,
            severity="low",
            impact=Impact(orders_affected=_extract_count(normalized) or 0, scope=_scope(normalized)),
            why=["Low signal; safest path is escalation for manual triage."],
            recovery_plan=["collect_diagnostics", "escalate_to_oncall"],
        )


def _extract_count(normalized: str) -> int | None:
    match = re.search(r"(\d+)\s+(orders|order)", normalized)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _scope(normalized: str) -> str:
    if any(k in normalized for k in ("many", "bulk", "batch", "file", "spike")):
        return "batch"
    return "single"


def _rag_success_why(similar_cases: list[dict[str, Any]]) -> str:
    if not similar_cases:
        return "No similar cases retrieved; using best-effort operational heuristics."
    top = similar_cases[0]
    rate = top.get("success_rate")
    fix = top.get("fix")
    if isinstance(rate, (int, float)) and fix:
        pct = round(rate * 100)
        return f"{pct}% similar cases resolved via {fix}."
    return "Similar cases suggest a standard remediation path."
