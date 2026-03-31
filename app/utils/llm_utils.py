from __future__ import annotations

import json
from typing import Any

from app.config.settings import get_settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _get_grok_client():
    settings = get_settings()
    if not settings.grok_api_key:
        return None, settings

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("OpenAI-compatible client is not installed; using fallback logic.")
        return None, settings

    # xAI Grok provides an OpenAI-compatible API; we keep the integration light and optional.
    return (
        OpenAI(api_key=settings.grok_api_key, base_url=settings.grok_base_url),
        settings,
    )


def llm_reason_about_issue(
    raw_input: str,
    issue_type: str,
    similar_cases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    client, settings = _get_grok_client()
    if not client:
        return None

    prompt = (
        "You are FlowFix Agent, an AI-native SRE automation agent focused on reducing MTTR.\n"
        "Given an incident and retrieved similar cases, decide the best next action.\n"
        "Return STRICT JSON ONLY (no markdown) with keys:\n"
        "- decision: one of retry_workflow, remove_and_reprocess, isolate_and_rerun_batch, escalate, no_action\n"
        "- confidence: number 0..1\n"
        "- recovery_plan: list of steps (strings)\n"
        "- why: list of short justifications (strings)\n"
        "- severity: low|medium|high\n"
        "- impact: {orders_affected:int, scope:'single'|'batch', notes?:string}\n"
        "- root_cause: string\n"
        "- correlated_incidents: boolean\n"
        "- common_root_cause: string|null\n"
        f"Issue type: {issue_type}\n"
        f"Raw input: {raw_input}\n"
        f"Retrieved cases: {json.dumps(similar_cases)}"
    )

    try:
        response = client.responses.create(
            model=settings.grok_model,
            input=prompt,
            temperature=0.1,
        )
        return json.loads(response.output_text)
    except Exception as exc:
        logger.warning("LLM reasoning failed: %s", exc)
        return None
