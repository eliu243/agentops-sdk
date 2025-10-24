from __future__ import annotations

from typing import Optional

from .config import Config, config
from .runtime import RunContext, ensure_run_started
from .guardrails import AgentTerminatedError


def init(
    server_url: str,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    max_llm_calls: int = 5,
    monitor_http: bool = True,
) -> None:
    config.server_url = server_url.rstrip("/")
    config.api_key = api_key
    config.project = project or "default"
    config.max_llm_calls = max(1, int(max_llm_calls))

    try:
        from .patches.openai_v1 import patch_openai
        patch_openai()
    except Exception:
        pass

    # Patch HTTP libraries for A2A monitoring
    if monitor_http:
        try:
            from .patches.http_monitor import patch_http_libraries
            patch_http_libraries()
        except Exception:
            pass


__all__ = [
    "Config",
    "config",
    "RunContext",
    "start_run",
    "ensure_run_started",
    "init",
    "AgentTerminatedError",
]

start_run = RunContext


