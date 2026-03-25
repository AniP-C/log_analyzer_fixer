from __future__ import annotations

import json
from typing import Any

from app.config.settings import get_settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _get_openai_client():
    settings = get_settings()
    if not settings.openai_api_key:
        return None, settings

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("OpenAI package is not installed; using fallback logic.")
        return None, settings

    return OpenAI(api_key=settings.openai_api_key), settings


def llm_classify_issue(raw_input: str, issue_types: tuple[str, ...]) -> dict[str, Any] | None:
    client, settings = _get_openai_client()
    if not client:
        return None

    prompt = (
        "Classify the operational issue into exactly one issue type.\n"
        f"Issue types: {', '.join(issue_types)}\n"
        "Return JSON with keys issue_type, confidence, rationale.\n"
        f"Input: {raw_input}"
    )

    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=prompt,
            temperature=0,
        )
        text = response.output_text
        parsed = json.loads(text)
        if parsed["issue_type"] in issue_types:
            return parsed
    except Exception as exc:
        logger.warning("LLM classification failed: %s", exc)

    return None


def llm_reason_about_issue(
    raw_input: str,
    issue_type: str,
    similar_cases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    client, settings = _get_openai_client()
    if not client:
        return None

    prompt = (
        "You are an SRE automation agent.\n"
        "Given an issue, infer the most likely root cause and best remediation.\n"
        "Return strict JSON with keys root_cause, possible_actions, final_action, confidence.\n"
        f"Issue type: {issue_type}\n"
        f"Raw input: {raw_input}\n"
        f"Retrieved cases: {json.dumps(similar_cases)}"
    )

    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=prompt,
            temperature=0.1,
        )
        return json.loads(response.output_text)
    except Exception as exc:
        logger.warning("LLM reasoning failed: %s", exc)
        return None
