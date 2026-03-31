from __future__ import annotations

import json
from pathlib import Path

from app.config.settings import get_settings
from app.utils.logger import log_flow_trace


class RAGEngine:
    def __init__(self) -> None:
        settings = get_settings()
        data_path = Path(settings.data_dir) / "incidents.json"
        self.incidents = json.loads(data_path.read_text(encoding="utf-8"))

    def retrieve(self, issue_type: str, raw_input: str, top_k: int = 3) -> list[dict]:
        log_flow_trace(
            "rag",
            "app.services.rag_engine.RAGEngine.retrieve",
            "retrieve_begin",
            {"issue_type": issue_type, "top_k": top_k, "incident_pool_size": len(self.incidents)},
        )
        normalized = raw_input.lower()
        scored_cases: list[tuple[int, dict]] = []

        for incident in self.incidents:
            if incident["issue"] != issue_type:
                continue

            score = 0
            pattern = incident.get("pattern", "").lower()
            if pattern and pattern in normalized:
                score += 3

            for keyword in incident.get("keywords", []):
                if keyword.lower() in normalized:
                    score += 1

            scored_cases.append((score, incident))

        ranked = [case for _, case in sorted(scored_cases, key=lambda item: item[0], reverse=True)]
        out = ranked[:top_k]
        log_flow_trace(
            "rag",
            "app.services.rag_engine.RAGEngine.retrieve",
            "retrieve_end",
            {
                "candidates_scored": len(scored_cases),
                "returned": len(out),
                "top_fixes": [c.get("fix") for c in out],
            },
        )
        return out
