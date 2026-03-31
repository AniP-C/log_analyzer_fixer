from __future__ import annotations


class Notifier:
    def send(self, *, severity: str, confidence: float, decision: str, execution_status: str, target: str, low_confidence_escalate: bool) -> dict:
        if low_confidence_escalate:
            channel = "escalate"
        elif severity == "high":
            channel = "slack+email"
        elif severity == "medium":
            channel = "email"
        else:
            channel = "none"

        message = (
            f"FlowFix decision={decision} status={execution_status} severity={severity} "
            f"confidence={confidence:.2f} target={target}"
        )

        status = "no_notification" if channel == "none" else f"{channel}_sent"
        return {"channel": channel, "message": message, "status": status}
