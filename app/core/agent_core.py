from __future__ import annotations

import json
import time
from pathlib import Path

from app.config.settings import get_settings
from app.core.classifier import IssueClassifier
from app.core.reasoning import ReasoningEngine
from app.models.schemas import AnalyzeResponse, BenchmarkResponse, BenchmarkSummary, CaseResult, ExecutionStepLog
from app.services.executor import ActionExecutor
from app.services.notifier import Notifier
from app.services.rag_engine import RAGEngine
from app.utils.logger import get_logger, log_event
from evaluation.scorer import score_benchmark


logger = get_logger(__name__)


class FlowFixAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.classifier = IssueClassifier()
        self.rag_engine = RAGEngine()
        self.reasoning_engine = ReasoningEngine()
        self.executor = ActionExecutor()
        self.notifier = Notifier()

    async def analyze_issue(self, raw_input: str) -> AnalyzeResponse:
        started_at = time.perf_counter()
        timeline: list[str] = ["detected issue"]
        classification = self.classifier.classify(raw_input)
        timeline.append("classified")
        similar_cases = self.rag_engine.retrieve(classification.issue_type, raw_input)
        timeline.append("retrieved similar cases")
        reasoning = self.reasoning_engine.reason(raw_input, classification.issue_type, similar_cases)
        timeline.append("reasoned")

        # Confidence-based execution gating (production safety)
        low_confidence_escalate = reasoning.confidence < 0.5
        warn_execution = 0.5 <= reasoning.confidence < 0.75
        auto_execute = reasoning.confidence >= 0.75

        decision = reasoning.decision
        effective_decision = decision
        if low_confidence_escalate:
            effective_decision = "escalate"

        execution = self.executor.execute(
            reasoning.recovery_plan,
            raw_input,
            classification.issue_type,
            effective_decision,
        )
        timeline.append("decision made")

        exec_steps = [ExecutionStepLog(**step) for step in execution.get("steps", [])]
        if warn_execution and effective_decision not in ("no_action", "escalate"):
            exec_steps.insert(
                0,
                ExecutionStepLog(
                    step="warning",
                    status="skipped",
                    detail="Confidence between 0.5 and 0.75; executed with caution.",
                ),
            )
        if not auto_execute and effective_decision not in ("no_action", "escalate") and not warn_execution:
            # (Should not occur due to gating above; keep defensive.)
            exec_steps.insert(0, ExecutionStepLog(step="gated", status="skipped", detail="Execution gated by policy."))

        notification = self.notifier.send(
            severity=reasoning.severity,
            confidence=reasoning.confidence,
            decision=effective_decision,
            execution_status=execution["status"],
            target=execution["target"],
            low_confidence_escalate=low_confidence_escalate,
        )
        timeline.append("executed")
        timeline.append("notified")

        # Learning loop: append outcome into incidents.json for future retrieval.
        self._append_learning(
            issue_type=classification.issue_type,
            raw_input=raw_input,
            decision=effective_decision,
            success=execution["status"] in ("success", "partial"),
        )
        timeline.append("logged")

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

        response = AnalyzeResponse(
            issue_type=classification.issue_type,
            root_cause=reasoning.root_cause,
            decision=effective_decision,
            confidence=reasoning.confidence,
            severity=reasoning.severity,
            impact=reasoning.impact,
            why=reasoning.why,
            recovery_plan=reasoning.recovery_plan,
            execution_log=exec_steps,
            timeline=timeline,
            notification=notification["channel"],
            correlated_incidents=reasoning.correlated_incidents,
            common_root_cause=reasoning.common_root_cause,
            similar_cases=similar_cases,
            execution_status=execution["status"],
            target=execution["target"],
            response_time_ms=duration_ms,
            comparison={
                "default_llm": {
                    "behavior": "explanation_only",
                    "output": "Likely suggests generic troubleshooting steps without executing, notifying, or learning.",
                },
                "flowfix": {
                    "behavior": "detect_decide_execute_notify_learn",
                    "decision": effective_decision,
                    "executed": effective_decision not in ("no_action", "escalate") and execution["status"] != "skipped",
                },
            },
        )

        log_event(
            "analysis_completed",
            {
                "query": raw_input,
                "issue_type": classification.issue_type,
                "classification_confidence": classification.confidence,
                "classification_rationale": classification.rationale,
                "root_cause": reasoning.root_cause,
                "possible_actions": reasoning.possible_actions,
                "decision": effective_decision,
                "confidence": reasoning.confidence,
                "severity": reasoning.severity,
                "impact": reasoning.impact.model_dump(),
                "why": reasoning.why,
                "recovery_plan": reasoning.recovery_plan,
                "execution_status": execution["status"],
                "execution_log": [step.model_dump() for step in exec_steps],
                "notification": notification["status"],
                "target": execution["target"],
                "response_time_ms": duration_ms,
                "similar_cases": similar_cases,
                "timeline": timeline,
                "correlated_incidents": reasoning.correlated_incidents,
                "common_root_cause": reasoning.common_root_cause,
            },
        )
        logger.info("Completed analysis for input '%s' with decision '%s'", raw_input, effective_decision)
        return response

    async def run_benchmark(self) -> BenchmarkResponse:
        test_cases_path = Path(self.settings.data_dir) / "test_cases.json"
        if not test_cases_path.exists():
            raise FileNotFoundError(f"Missing benchmark cases at {test_cases_path}")

        cases = json.loads(test_cases_path.read_text(encoding="utf-8"))
        case_results: list[CaseResult] = []

        for case in cases:
            result = await self.analyze_issue(case["input"])
            case_results.append(
                CaseResult(
                    input=case["input"],
                    expected_issue_type=case["expected_issue_type"],
                    expected_action=case["expected_action"],
                    actual_issue_type=result.issue_type,
                    actual_action=result.action_taken,
                    confidence=result.confidence,
                    response_time_ms=result.response_time_ms,
                    passed_issue_type=result.issue_type == case["expected_issue_type"],
                    passed_action=result.action_taken == case["expected_action"],
                    execution_status=result.execution_status,
                )
            )

        summary: BenchmarkSummary = score_benchmark(case_results, self.settings.response_time_target_ms)

        results_dir = Path("evaluation")
        results_dir.mkdir(parents=True, exist_ok=True)
        results_path = results_dir / "results.json"
        payload = {
            "summary": summary.model_dump(),
            "results": [result.model_dump() for result in case_results],
        }
        results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        log_event(
            "benchmark_completed",
            {
                "total_cases": summary.total_cases,
                "overall_score": summary.overall_score,
                "detection_accuracy": summary.detection_accuracy,
                "action_accuracy": summary.action_accuracy,
                "resolution_success": summary.resolution_success,
                "response_time_score": summary.response_time_score,
                "results_path": str(results_path.resolve()),
            },
        )
        logger.info("Benchmark completed with overall score %.2f", summary.overall_score)

        return BenchmarkResponse(summary=summary, results=case_results)

    def _append_learning(self, *, issue_type: str, raw_input: str, decision: str, success: bool) -> None:
        try:
            data_path = Path(self.settings.data_dir) / "incidents.json"
            incidents = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else []
            incidents.append(
                {
                    "issue": issue_type,
                    "pattern": _safe_pattern(raw_input),
                    "keywords": _keywords(raw_input),
                    "fix": decision,
                    "success_rate": 1.0 if success else 0.0,
                    "learned": True,
                }
            )
            data_path.write_text(json.dumps(incidents, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Learning loop append failed: %s", exc)


def _safe_pattern(raw_input: str) -> str:
    text = raw_input.lower().strip()
    return " ".join(text.split()[:4])[:80]


def _keywords(raw_input: str) -> list[str]:
    normalized = raw_input.lower()
    candidates = ("created", "stuck", "timeout", "validation", "paypal", "billing address", "delayed", "batch", "file", "spike")
    return [k for k in candidates if k in normalized]
