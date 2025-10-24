from __future__ import annotations

from .config import config
from .runtime import next_sequence, ensure_run_started
from .transport import post_event


class AgentTerminatedError(RuntimeError):
    pass


def enforce_max_calls() -> None:
    ensure_run_started()
    seq = next_sequence()
    if seq > config.max_llm_calls:
        post_event(
            {
                "type": "run_terminated",
                "run_id": config.run_id,
                "reason": "UNBOUNDED_RECURSION",
                "terminated_at": None,
            }
        )
        raise AgentTerminatedError("Unbounded Recursion: max LLM calls exceeded")


