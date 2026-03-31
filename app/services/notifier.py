from __future__ import annotations

from app.utils.logger import log_flow_trace


class Notifier:
    def send(self, *, severity: str, confidence: float, decision: str, execution_status: str, target: str, low_confidence_escalate: bool) -> dict:
        log_flow_trace(
            "notifier",
            "app.services.notifier.Notifier.send",
            "route_begin",
            {
                "severity": severity,
                "confidence": confidence,
                "decision": decision,
                "execution_status": execution_status,
                "target": target,
                "low_confidence_escalate": low_confidence_escalate,
            },
        )

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

        log_flow_trace(
            "notifier",
            "app.services.notifier.Notifier.send",
            "route_decided",
            {
                "channel": channel,
                "notify_status": status,
                "rules": "low_conf_escalate; high_slack_email; medium_email; low_none",
            },
        )

        return {"channel": channel, "message": message, "status": status}
