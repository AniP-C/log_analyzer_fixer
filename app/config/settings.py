from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    # Grok (xAI) - reasoning only. Uses OpenAI-compatible client in llm_utils.py.
    grok_api_key: str | None = None
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-3-mini"

    response_time_target_ms: float = 1500.0
    data_dir: str = str(Path(__file__).resolve().parents[1] / "data")
    logs_dir: str = str(Path(__file__).resolve().parents[2] / "logs")
    app_log_file: str = str(Path(__file__).resolve().parents[2] / "logs" / "app.log")
    event_log_file: str = str(Path(__file__).resolve().parents[2] / "logs" / "agent_events.jsonl")
    # One file: ordered step-by-step trace for a full analyze run (classification → RAG → reasoning/Grok → gates → execute → notify → learn).
    flow_trace_file: str = str(Path(__file__).resolve().parents[2] / "logs" / "flow_trace.jsonl")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
