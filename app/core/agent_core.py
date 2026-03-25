from __future__ import annotations

import json
import time
from pathlib import Path

from app.config.settings import get_settings
from app.core.classifier import IssueClassifier
from app.core.reasoning import ReasoningEngine
from app.models.schemas import AnalyzeResponse, BenchmarkResponse, BenchmarkSummary, CaseResult
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
        classification = self.classifier.classify(raw_input)
        similar_cases = self.rag_engine.retrieve(classification.issue_type, raw_input)
        reasoning = self.reasoning_engine.reason(raw_input, classification.issue_type, similar_cases)
        execution = self.executor.execute(reasoning.final_action, raw_input, classification.issue_type)
        notification = self.notifier.send(execution, classification.issue_type, reasoning.confidence)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

        response = AnalyzeResponse(
            issue_type=classification.issue_type,
            root_cause=reasoning.root_cause,
            action_taken=reasoning.final_action,
            execution_status=execution["status"],
            notification=notification["status"],
            confidence=reasoning.confidence,
            reasoning=reasoning.possible_actions,
            similar_cases=similar_cases,
            execution_log=execution["steps"],
            target=execution["target"],
            response_time_ms=duration_ms,
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
                "action_taken": reasoning.final_action,
                "execution_status": execution["status"],
                "execution_log": execution["steps"],
                "notification": notification["status"],
                "target": execution["target"],
                "response_time_ms": duration_ms,
                "similar_cases": similar_cases,
            },
        )
        logger.info("Completed analysis for input '%s' with action '%s'", raw_input, reasoning.final_action)
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
