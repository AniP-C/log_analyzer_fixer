from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


_LOGGER_CONFIGURED = False
_EVENT_LOGGER_NAME = "flowfix.events"


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
