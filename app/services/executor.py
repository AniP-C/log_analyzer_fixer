from __future__ import annotations

import re


class ActionExecutor:
    def execute(self, action: str, raw_input: str, issue_type: str) -> dict:
        target = self._extract_target(raw_input)

        if action == "retry_workflow":
            steps = [
                "Validated workflow state.",
                f"Retried workflow for {target}.",
                "Confirmed job returned to active processing.",
            ]
        elif action == "remove_and_reprocess":
            steps = [
                f"Isolated invalid record for {target}.",
                "Removed unsupported characters from payload in simulation.",
                "Reprocessed the file batch.",
            ]
        elif action == "isolate_and_rerun_batch":
            steps = [
                f"Located failed item related to {target}.",
                "Isolated the affected order from the batch.",
                "Re-ran the remaining workload.",
            ]
        else:
            steps = [
                "Escalated for manual inspection.",
                f"Attached diagnostics for {target}.",
            ]

        return {
            "action": action,
            "target": target,
            "status": "success",
            "issue_type": issue_type,
            "steps": steps,
        }

    def _extract_target(self, raw_input: str) -> str:
        match = re.search(r"(order|file|batch)[\s:_-]*(\d+)", raw_input, re.IGNORECASE)
        if match:
            return f"{match.group(1).lower()}_{match.group(2)}"
        return "unknown_target"
