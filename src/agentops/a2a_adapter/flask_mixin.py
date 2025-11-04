from __future__ import annotations

import time
from typing import Any

try:
    from flask import request, jsonify  # type: ignore
except Exception:  # pragma: no cover
    request = None  # type: ignore
    jsonify = None  # type: ignore

from .. import evaluate_policy
from ..runtime import ensure_run_started, current_run_id
from ..transport import post_event


class AgentOpsFlaskMixin:
    """Mixin for python-a2a A2AServer subclasses to add governance on ingress.

    Usage:
        from python_a2a import A2AServer
        class GovernedServer(AgentOpsFlaskMixin, A2AServer):
            pass
    """

    def setup_routes(self, app: Any):  # type: ignore[override]
        if request is not None and hasattr(app, "before_request"):
            @app.before_request  # type: ignore[attr-defined]
            def _agentops_governance():  # type: ignore[unused-variable]
                # Skip agent metadata endpoints and non-POST
                path = getattr(request, "path", "/")
                method = getattr(request, "method", "").upper()
                if path in ["/", "/a2a", "/agent.json", "/a2a/agent.json", "/.well-known/agent.json", "/a2a/.well-known/agent.json"] or method != "POST":
                    return None

                # Extract message text
                try:
                    payload = request.get_json(silent=True) or {}
                except Exception:
                    payload = {}
                message_text = payload.get("message")

                # Emit receive event
                try:
                    existing_run = current_run_id()
                    ensure_run_started()
                    transient_run = existing_run is None
                    post_event(
                        {
                            "run_id": current_run_id(),
                            "type": "a2a_message_receive",
                            "method": "INGRESS",
                            "url": getattr(request, "base_url", ""),
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

                # Policy evaluation
                result = evaluate_policy(message_text, direction="ingress")
                if not result.allowed:
                    try:
                        post_event(
                            {
                                "run_id": current_run_id(),
                                "type": "a2a_guardrail_violation",
                                "method": "INGRESS",
                                "url": getattr(request, "base_url", ""),
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
                    # Close transient run
                    try:
                        if transient_run:
                            post_event({"type": "run_completed", "run_id": current_run_id(), "ended_at": int(time.time() * 1000)})
                    except Exception:
                        pass
                    if jsonify is not None:
                        return jsonify({"ok": False, "blocked": True}), 403
                    return ("Blocked", 403)

                # For allowed requests, close transient run immediately (minimal change)
                try:
                    if transient_run:
                        post_event({"type": "run_completed", "run_id": current_run_id(), "ended_at": int(time.time() * 1000)})
                except Exception:
                    pass

        # Continue with python-a2a routes
        return super().setup_routes(app)  # type: ignore[misc]


