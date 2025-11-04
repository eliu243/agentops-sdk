from __future__ import annotations

"""
AgentOps drop-in adapter for python-a2a.

Re-export `run_server` and `A2AClient` but with governance:
- Ingress: wrap ASGI app with middleware to enforce policy on message bodies
- Egress: wrap client send_message to enforce policy before sending
"""

from typing import Any

from .middleware import AgentOpsA2AMiddleware
from .middleware_wsgi import AgentOpsA2AWSGIMiddleware
from .client import AgentOpsA2AClient


try:
    # Underlying python_a2a API
    from python_a2a import run_server as _pa2a_run_server  # type: ignore
except Exception:  # pragma: no cover
    _pa2a_run_server = None  # type: ignore


_setup_routes_patched = False


def _monkeypatch_python_a2a_setup_routes() -> None:
    global _setup_routes_patched
    if _setup_routes_patched:
        return
    try:
        from python_a2a import A2AServer  # type: ignore
        from flask import request, jsonify  # type: ignore
        import time
        from ..policy import evaluate as _evaluate
        from ..runtime import ensure_run_started as _ensure, current_run_id as _rid
        from ..transport import post_event as _post

        original_setup = A2AServer.setup_routes  # type: ignore[attr-defined]

        def wrapped_setup(self, app):  # type: ignore[no-redef]
            @app.before_request  # type: ignore[attr-defined]
            def _agentops_ingress_guard():  # type: ignore[unused-variable]
                if request.path in ["/", "/a2a", "/agent.json", "/a2a/agent.json"]:
                    return None

                payload = request.get_json(silent=True) or {}
                message_text = payload.get("message")

                try:
                    _ensure()
                    _post(
                        {
                            "run_id": _rid(),
                            "type": "a2a_message_receive",
                            "method": "INGRESS",
                            "url": request.base_url,
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
                    pass

                result = _evaluate(message_text, direction="ingress")
                if not result.allowed:
                    try:
                        _post(
                            {
                                "run_id": _rid(),
                                "type": "a2a_guardrail_violation",
                                "method": "INGRESS",
                                "url": request.base_url,
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
                    return jsonify({"ok": False, "blocked": True}), 403
                return None

            return original_setup(self, app)

        A2AServer.setup_routes = wrapped_setup  # type: ignore[assignment]
        _setup_routes_patched = True
    except Exception:
        pass


def run_server(app: Any, *args: Any, **kwargs: Any) -> Any:
    """Run A2A server with AgentOps ingress middleware installed.

    Matches python_a2a.run_server signature.
    """
    if _pa2a_run_server is None:
        raise RuntimeError("python_a2a is not installed; cannot run A2A server")

    # Ensure python_a2a servers get instrumentation via setup_routes
    _monkeypatch_python_a2a_setup_routes()

    # Install middleware (ASGI vs WSGI)
    wrapped_app = app
    try:
        # ASGI path (FastAPI/Starlette)
        if hasattr(app, "add_middleware"):
            app.add_middleware(AgentOpsA2AMiddleware)
        # Flask: expose wsgi_app
        elif hasattr(app, "wsgi_app"):
            try:
                app.wsgi_app = AgentOpsA2AWSGIMiddleware(app.wsgi_app)
            except Exception:
                app.wsgi_app = AgentOpsA2AWSGIMiddleware(app.wsgi_app)
        else:
            # Try ASGI generic wrap first; if it fails at runtime, rely on WSGI
            wrapped_app = AgentOpsA2AMiddleware(app)
    except Exception:
        # Fallback WSGI wrapper
        wrapped_app = AgentOpsA2AWSGIMiddleware(app)

    return _pa2a_run_server(wrapped_app, *args, **kwargs)


# Re-export A2AClient as wrapped client
A2AClient = AgentOpsA2AClient

__all__ = [
    "run_server",
    "A2AClient",
]


