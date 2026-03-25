from __future__ import annotations

from app.models.schemas import BenchmarkSummary, CaseResult


def score_benchmark(results: list[CaseResult], response_time_target_ms: float) -> BenchmarkSummary:
    total = len(results)
    detection_accuracy = _ratio(sum(result.passed_issue_type for result in results), total)
    action_accuracy = _ratio(sum(result.passed_action for result in results), total)
    resolution_success = _ratio(sum(result.execution_status == "success" for result in results), total)

    avg_response_time = sum(result.response_time_ms for result in results) / total if total else response_time_target_ms
    response_time_score = max(0.0, min(1.0, response_time_target_ms / max(avg_response_time, 1)))

    overall_score = round(
        (detection_accuracy * 0.3)
        + (action_accuracy * 0.3)
        + (resolution_success * 0.2)
        + (response_time_score * 0.2),
        4,
    )

    return BenchmarkSummary(
        total_cases=total,
        detection_accuracy=round(detection_accuracy, 4),
        action_accuracy=round(action_accuracy, 4),
        resolution_success=round(resolution_success, 4),
        response_time_score=round(response_time_score, 4),
        overall_score=overall_score,
    )


def _ratio(count: int, total: int) -> float:
    if not total:
        return 0.0
    return count / total
