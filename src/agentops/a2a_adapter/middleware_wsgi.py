from __future__ import annotations

import io
import json
import time
from typing import Callable, Iterable, Tuple

from ..config import config
from ..policy import evaluate
from ..runtime import ensure_run_started, current_run_id
from ..transport import post_event


class AgentOpsA2AWSGIMiddleware:
    """WSGI middleware enforcing ingress policy on JSON bodies with `message`.

    Works with Flask-style WSGI apps. If the message is blocked, returns 403 JSON
    and logs an `a2a_guardrail_violation` event. Otherwise forwards the request
    and re-injects the original body into `wsgi.input` for downstream handlers.
    """

    def __init__(self, app: Callable):
        self.app = app

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        try:
            content_length = int(environ.get("CONTENT_LENGTH", "0") or 0)
        except ValueError:
            content_length = 0

        body = b""
        if content_length > 0:
            body = environ.get("wsgi.input").read(content_length)  # type: ignore[operator]

        message_text = None
        if body:
            try:
                payload = json.loads(body.decode("utf-8", "ignore"))
                message_text = payload.get("message")
            except Exception:
                message_text = None

        # Emit generic ingress receive event
        try:
            existing_run = current_run_id()
            ensure_run_started()
            transient_run = existing_run is None
            post_event(
                {
                    "run_id": current_run_id(),
                    "type": "a2a_message_receive",
                    "method": "INGRESS",
                    "url": self._wsgi_url(environ),
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

        result = evaluate(message_text, direction="ingress", extra_forbidden=config.forbidden_patterns)
        if not result.allowed:
            ensure_run_started()
            try:
                post_event(
                    {
                        "run_id": current_run_id(),
                        "type": "a2a_guardrail_violation",
                        "method": "INGRESS",
                        "url": self._wsgi_url(environ),
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

            status = "403 FORBIDDEN"
            headers = [("Content-Type", "application/json")]
            start_response(status, headers)
            # Close transient run
            try:
                if transient_run:
                    post_event({"type": "run_completed", "run_id": current_run_id(), "ended_at": int(time.time() * 1000)})
            except Exception:
                pass
            return [json.dumps({"ok": False, "blocked": True}).encode("utf-8")]

        # Reinject original body for downstream app
        environ["wsgi.input"] = io.BytesIO(body)
        environ["CONTENT_LENGTH"] = str(len(body))
        result_iter = self.app(environ, start_response)
        # Close transient run after pass-through
        try:
            if transient_run:
                post_event({"type": "run_completed", "run_id": current_run_id(), "ended_at": int(time.time() * 1000)})
        except Exception:
            pass
        return result_iter

    @staticmethod
    def _wsgi_url(environ: dict) -> str:
        try:
            scheme = environ.get("wsgi.url_scheme", "http")
            host = environ.get("HTTP_HOST") or (environ.get("SERVER_NAME") or "localhost")
            path = environ.get("PATH_INFO", "/")
            return f"{scheme}://{host}{path}"
        except Exception:
            return ""


