from __future__ import annotations


class Notifier:
    def send(self, execution_result: dict, issue_type: str, confidence: float) -> dict:
        channel = "email" if confidence >= 0.8 else "slack"
        message = (
            f"FlowFix handled {issue_type} for {execution_result['target']} with action "
            f"{execution_result['action']} ({execution_result['status']})."
        )

        return {
            "channel": channel,
            "message": message,
            "status": f"{channel}_sent",
        }
