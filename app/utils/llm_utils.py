from __future__ import annotations

import json
import time
from typing import Any

from app.config.settings import get_settings
from app.utils.logger import get_logger, log_flow_trace


logger = get_logger(__name__)


def _get_grok_client():
    settings = get_settings()
    if not settings.grok_api_key:
        log_flow_trace(
            "grok",
            "app.utils.llm_utils._get_grok_client",
            "grok_skipped",
            {"reason": "grok_api_key_missing"},
        )
        return None, settings

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("OpenAI-compatible client is not installed; using fallback logic.")
        log_flow_trace(
            "grok",
            "app.utils.llm_utils._get_grok_client",
            "grok_skipped",
            {"reason": "openai_package_missing"},
        )
        return None, settings

    # xAI Grok provides an OpenAI-compatible API; we keep the integration light and optional.
    log_flow_trace(
        "grok",
        "app.utils.llm_utils._get_grok_client",
        "grok_client_ready",
        {"base_url_host": settings.grok_base_url, "model": settings.grok_model},
    )
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
        log_flow_trace(
            "grok",
            "app.utils.llm_utils.llm_reason_about_issue",
            "grok_request_start",
            {
                "model": settings.grok_model,
                "issue_type": issue_type,
                "similar_cases_count": len(similar_cases),
                "prompt_chars": len(prompt),
            },
        )
        t0 = time.perf_counter()
        response = client.responses.create(
            model=settings.grok_model,
            input=prompt,
            temperature=0.1,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        text = response.output_text
        parsed = json.loads(text)
        log_flow_trace(
            "grok",
            "app.utils.llm_utils.llm_reason_about_issue",
            "grok_request_success",
            {
                "latency_ms": elapsed_ms,
                "response_chars": len(text) if text else 0,
                "parsed_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
            },
        )
        return parsed
    except Exception as exc:
        logger.warning("LLM reasoning failed: %s", exc)
        log_flow_trace(
            "grok",
            "app.utils.llm_utils.llm_reason_about_issue",
            "grok_request_failed",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
        return None
