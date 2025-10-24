from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import config
from ..guardrails import enforce_max_calls
from ..runtime import ensure_run_started
from ..transport import post_event


_patched = False


def _extract_prompt(messages: List[Dict[str, Any]]) -> str:
    try:
        parts = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)[:8000]
    except Exception:
        return ""


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = {
        "gpt-4o-mini": (0.150 / 1_000_000, 0.600 / 1_000_000),
    }
    input_price, output_price = pricing.get(model, (0.0, 0.0))
    return prompt_tokens * input_price + completion_tokens * output_price


def patch_openai() -> None:
    global _patched
    if _patched:
        return
    try:
        from openai.resources.chat.completions import Completions
    except Exception:
        return

    original_create = Completions.create

    def wrapped_create(self, *args, **kwargs):  # type: ignore[no-redef]
        enforce_max_calls()
        ensure_run_started()

        model: Optional[str] = kwargs.get("model")
        messages: Optional[List[Dict[str, Any]]] = kwargs.get("messages")
        prompt_text = _extract_prompt(messages or [])

        resp = original_create(self, *args, **kwargs)

        try:
            usage = getattr(resp, "usage", None)
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
            content = ""
            try:
                content = resp.choices[0].message.content  # type: ignore[attr-defined]
            except Exception:
                content = ""

            cost_usd = _estimate_cost(model or "", prompt_tokens, completion_tokens)

            post_event(
                {
                    "type": "llm_call",
                    "run_id": config.run_id,
                    "seq": None,
                    "model": model,
                    "prompt": prompt_text,
                    "response": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "created_at": None,
                }
            )
        except Exception:
            pass

        return resp

    Completions.create = wrapped_create  # type: ignore[assignment]
    _patched = True


