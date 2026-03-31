from __future__ import annotations

import contextvars
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


_LOGGER_CONFIGURED = False
_EVENT_LOGGER_NAME = "flowfix.events"

# Per-request flow trace (set by FlowFixAgent.analyze_issue).
_flow_trace_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("flow_trace_ctx", default=None)
_flow_trace_lock = threading.Lock()


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event_payload = getattr(record, "event_payload", None)
        if event_payload:
            payload.update(event_payload)

        return json.dumps(payload, ensure_ascii=True)


def _configure_logging() -> None:
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return

    settings = get_settings()
    logs_dir = Path(settings.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        root_logger.addHandler(console_handler)

    app_file_handler = RotatingFileHandler(
        settings.app_log_file,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    app_file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root_logger.addHandler(app_file_handler)

    event_logger = logging.getLogger(_EVENT_LOGGER_NAME)
    event_logger.setLevel(logging.INFO)
    event_logger.propagate = False

    if not event_logger.handlers:
        event_handler = RotatingFileHandler(
            settings.event_log_file,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        event_handler.setFormatter(JsonLineFormatter())
        event_logger.addHandler(event_handler)

    _LOGGER_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_logging()
    return logging.getLogger(name)


def log_event(event_type: str, payload: dict[str, Any]) -> None:
    _configure_logging()
    event_logger = logging.getLogger(_EVENT_LOGGER_NAME)
    event_logger.info(event_type, extra={"event_payload": {"event_type": event_type, **payload}})


def flow_trace_start() -> str:
    """Begin a traced run; returns run_id. Pair with flow_trace_end()."""
    _configure_logging()
    run_id = str(uuid.uuid4())
    _flow_trace_ctx.set({"run_id": run_id, "seq": 0})
    return run_id


def flow_trace_end() -> None:
    _flow_trace_ctx.set(None)


def log_flow_trace(
    phase: str,
    location: str,
    event: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Append one JSON line to flow_trace_file (full pipeline visibility)."""
    ctx = _flow_trace_ctx.get()
    if ctx is None:
        return

    ctx["seq"] = int(ctx.get("seq", 0)) + 1
    settings = get_settings()
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": ctx["run_id"],
        "seq": ctx["seq"],
        "phase": phase,
        "location": location,
        "event": event,
        "data": data or {},
    }

    path = Path(settings.flow_trace_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _flow_trace_lock:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def flow_trace_run_id() -> str | None:
    ctx = _flow_trace_ctx.get()
    return str(ctx["run_id"]) if ctx else None
