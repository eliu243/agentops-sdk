from __future__ import annotations

import json
import time
from typing import Any, Callable, Awaitable

from ..policy import evaluate
from ..config import config
from ..runtime import ensure_run_started, current_run_id
from ..transport import post_event


class AgentOpsA2AMiddleware:
    """ASGI middleware enforcing ingress policy on A2A message bodies.

    Expects JSON payloads with a `message` field. If blocked, returns 403 and logs an
    `a2a_guardrail_violation` event. Otherwise forwards to the downstream app.
    """

    def __init__(self, app: Callable[..., Awaitable[Any]]):
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Skip metadata/health probes and non-POST requests
        path = scope.get("raw_path") or scope.get("path") or b"/"
        if isinstance(path, bytes):
            path = path.decode("utf-8", "ignore")
        method = (scope.get("method") or "").upper()
        if path in ["/", "/a2a", "/agent.json", "/a2a/agent.json", "/.well-known/agent.json", "/a2a/.well-known/agent.json"] or method != "POST":
            await self.app(scope, receive, send)
            return

        body_bytes = b""

        async def _recv() -> dict:
            nonlocal body_bytes
            msg = await receive()
            if msg.get("type") == "http.request":
                body_bytes += msg.get("body", b"") or b""
            return msg

        # Read request body fully
        more = True
        while more:
            msg = await _recv()
            more = msg.get("more_body", False)

        message_text = None
        try:
            if body_bytes:
                payload = json.loads(body_bytes.decode("utf-8", "ignore"))
                message_text = payload.get("message")
        except Exception:
            message_text = None

        # Emit generic ingress receive event for observability
        try:
            existing_run = current_run_id()
            ensure_run_started()
            transient_run = existing_run is None
            post_event(
                {
                    "run_id": current_run_id(),
                    "type": "a2a_message_receive",
                    "method": "INGRESS",
                    "url": self._scope_url(scope),
                    "service_name": "a2a_server",
                    "request_data": (message_text or "")[:500],
                    "response_data": None,
                    "status_code": None,
                    "duration_ms": 0,
                    "error": None,
                    "created_at": int(time.time() * 1000),
                }
            )
        except Exception:
            transient_run = False

        # Evaluate ingress policy
        result = evaluate(message_text, direction="ingress", extra_forbidden=config.forbidden_patterns)
        if not result.allowed:
            ensure_run_started()
            try:
                post_event(
                    {
                        "run_id": current_run_id(),
                        "type": "a2a_guardrail_violation",
                        "method": "INGRESS",
                        "url": self._scope_url(scope),
                        "service_name": "guardrail",
                        "request_data": (message_text or "")[:500],
                        "response_data": None,
                        "status_code": 403,
                        "duration_ms": 0,
                        "error": f"{result.label}:{result.reason}:{','.join(result.matches)[:180]}",
                        "created_at": int(time.time() * 1000),
                    }
                )
            except Exception:
                pass

            # Return 403
            content = json.dumps({"ok": False, "blocked": True}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": content,
            })
            # Close transient run to avoid dangling traces
            try:
                if transient_run:
                    post_event({"type": "run_completed", "run_id": current_run_id(), "ended_at": int(time.time() * 1000)})
            except Exception:
                pass
            return

        # Re-inject the original body and continue
        async def _receive_again() -> dict:
            nonlocal body_bytes
            b = body_bytes
            body_bytes = b""
            return {"type": "http.request", "body": b, "more_body": False}

        await self.app(scope, _receive_again, send)
        # Close transient run after successful handling
        try:
            if transient_run:
                post_event({"type": "run_completed", "run_id": current_run_id(), "ended_at": int(time.time() * 1000)})
        except Exception:
            pass

    @staticmethod
    def _scope_url(scope: dict) -> str:
        try:
            scheme = scope.get("scheme", "http")
            server = scope.get("server", ("localhost", 80))
            host, port = server[0], server[1]
            path = scope.get("raw_path") or scope.get("path") or b"/"
            if isinstance(path, bytes):
                path = path.decode("utf-8", "ignore")
            return f"{scheme}://{host}:{port}{path}"
        except Exception:
            return ""


