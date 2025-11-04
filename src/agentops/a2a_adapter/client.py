from __future__ import annotations

import time
from typing import Any

from ..policy import evaluate
from ..config import config
from ..runtime import ensure_run_started, current_run_id
from ..transport import post_event


try:
    from python_a2a import A2AClient as _BaseA2AClient  # type: ignore
except Exception:  # pragma: no cover
    _BaseA2AClient = object  # type: ignore


class AgentOpsA2AClient(_BaseA2AClient):  # type: ignore[misc]
    """AgentOps-wrapped A2AClient enforcing egress policy and emitting events."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[no-redef]
        # Accept adapter-only logging URL and common alternatives
        self.base_url = kwargs.pop("base_url", None)
        self._alt_url = kwargs.get("url") or kwargs.get("server_url") or kwargs.get("endpoint_url")

        # Ensure underlying python_a2a receives required positional endpoint_url
        if args and len(args) >= 1:
            endpoint_url = args[0]
            if not endpoint_url and self.base_url:
                # Replace missing positional with base_url
                args = (self.base_url,) + args[1:]
        else:
            endpoint_url = kwargs.pop("endpoint_url", None) or self.base_url or self._alt_url
            if endpoint_url is None:
                raise TypeError("A2AClient.__init__() missing required 'endpoint_url'; provide endpoint_url or base_url")
            args = (endpoint_url,)

        super().__init__(*args, **kwargs)  # type: ignore[misc]

    def send_message(self, agent_id: str, message: str, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        # Egress policy evaluation
        result = evaluate(message, direction="egress", extra_forbidden=config.forbidden_patterns)
        if not result.allowed:
            ensure_run_started()
            try:
                post_event(
                    {
                        "run_id": current_run_id(),
                        "type": "a2a_guardrail_violation",
                        "method": "EGRESS",
                        "url": getattr(self, "base_url", ""),
                        "service_name": "guardrail",
                        "request_data": (message or "")[:500],
                        "response_data": None,
                        "status_code": 0,
                        "duration_ms": 0,
                        "error": f"{result.label}:{result.reason}:{','.join(result.matches)[:180]}",
                        "created_at": int(time.time() * 1000),
                    }
                )
            except Exception:
                pass
            if config.block_on_violation:
                raise RuntimeError("Egress blocked by policy: unauthorized content detected")

        # Trace send
        start = time.time()
        try:
            # Common python-a2a signature: send_message(agent_id, message, ...)
            resp = super().send_message(agent_id, message, *args, **kwargs)  # type: ignore[attr-defined]
        except TypeError:
            # Fallback signature: send_message(message, ...)
            msg_obj = message
            # If raw string is provided, wrap into a minimal shim with to_dict()
            if isinstance(message, str):
                class _A2AMessageShim:
                    def __init__(self, to_id: str, text: str) -> None:
                        self._to = to_id
                        self._text = text
                        # python_a2a may access message_id
                        self.message_id = None  # type: ignore[attr-defined]
                        # python_a2a may access conversation_id
                        self.conversation_id = None  # type: ignore[attr-defined]
                        # optional fields some versions access
                        self.parent_message_id = None  # type: ignore[attr-defined]
                        self.metadata = {}

                    def to_dict(self) -> dict:
                        return {"to": self._to, "message": self._text}

                    # Some python_a2a versions expect Google A2A formatted payload
                    def to_google_a2a(self) -> dict:  # type: ignore[override]
                        return {
                            "to": self._to,
                            "task": {
                                "input": [
                                    {"type": "text", "text": self._text}
                                ]
                            },
                            "parent_message_id": self.parent_message_id,
                            "conversation_id": self.conversation_id,
                            "metadata": self.metadata,
                        }

                msg_obj = _A2AMessageShim(agent_id, message)
            resp = super().send_message(msg_obj, *args, **kwargs)  # type: ignore[attr-defined]
        try:
            post_event(
                {
                    "run_id": current_run_id(),
                    "type": "a2a_message_send",
                    "method": "EGRESS",
                    "url": getattr(self, "base_url", None)
                    or getattr(self, "_alt_url", None)
                    or getattr(self, "url", None)
                    or getattr(self, "server_url", ""),
                    "service_name": "a2a_client",
                    "request_data": (message or "")[:500],
                    "response_data": None,
                    "status_code": getattr(resp, "status_code", None),
                    "duration_ms": round((time.time() - start) * 1000, 2),
                    "error": None,
                    "created_at": int(time.time() * 1000),
                }
            )
        except Exception:
            pass
        return resp


