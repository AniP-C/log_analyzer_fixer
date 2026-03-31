from __future__ import annotations

import random
import re

from app.utils.logger import log_flow_trace


class ActionExecutor:
    def execute(self, recovery_plan: list[str], raw_input: str, issue_type: str, decision: str) -> dict:
        target = self._extract_target(raw_input)
        plan = recovery_plan or ([decision] if decision not in ("no_action", "escalate") else [])

        log_flow_trace(
            "executor",
            "app.services.executor.ActionExecutor.execute",
            "execute_begin",
            {"decision": decision, "issue_type": issue_type, "target": target, "plan": plan},
        )

        steps: list[dict] = []
        if decision in ("no_action", "escalate"):
            status = "skipped" if decision == "no_action" else "success"
            if decision == "escalate":
                steps.append({"step": "escalate_to_oncall", "status": "success", "detail": f"Escalated incident for {target}."})
            log_flow_trace(
                "executor",
                "app.services.executor.ActionExecutor.execute",
                "execute_short_circuit",
                {"decision": decision, "status": status, "steps": [s["step"] for s in steps]},
            )
            return {
                "decision": decision,
                "target": target,
                "status": status,
                "issue_type": issue_type,
                "steps": steps,
            }

        # Deterministic-ish failure simulation: can be forced via input keywords.
        seed = sum(ord(c) for c in (raw_input + issue_type)) % 10_000
        rng = random.Random(seed)

        any_failed = False
        for step in plan:
            outcome = self._simulate_step(step, raw_input, rng)
            if outcome["status"] == "failed":
                any_failed = True
            steps.append(outcome)

        if not steps:
            exec_status = "skipped"
        elif any_failed and any(s["status"] == "success" for s in steps):
            exec_status = "partial"
        elif any_failed:
            exec_status = "failed"
        else:
            exec_status = "success"

        log_flow_trace(
            "executor",
            "app.services.executor.ActionExecutor.execute",
            "execute_end",
            {"final_status": exec_status, "target": target, "steps_run": len(steps)},
        )

        return {
            "decision": decision,
            "target": target,
            "status": exec_status,
            "issue_type": issue_type,
            "steps": steps,
        }

    def _extract_target(self, raw_input: str) -> str:
        match = re.search(r"(order|file|batch)[\s:_-]*(\d+)", raw_input, re.IGNORECASE)
        if match:
            return f"{match.group(1).lower()}_{match.group(2)}"
        return "unknown_target"

    def _simulate_step(self, step: str, raw_input: str, rng: random.Random) -> dict:
        normalized = raw_input.lower()
        # Forced failure hooks for demos/tests.
        if "simulate_fail" in normalized and step in ("check_downstream", "retry_workflow"):
            return {"step": step, "status": "failed", "detail": "Simulated failure triggered by input."}

        # Light stochastic failure for realism (bounded).
        failure_prob = 0.05
        if step in ("retry_workflow", "reprocess_file", "check_downstream"):
            failure_prob = 0.12

        if rng.random() < failure_prob:
            return {"step": step, "status": "failed", "detail": "Simulated transient failure."}

        return {"step": step, "status": "success", "detail": "Step completed."}
