"""
Two-agent A2A guardrails demo using HTTP with egress and ingress checks.

Requirements (for CrewAI label only):
  pip install crewai fastapi uvicorn requests
"""
import os
import threading
import time
from typing import Optional

import agentops
from agentops import evaluate_policy
from agentops.transport import post_event

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import requests


def start_agent_b_server(host: str = "127.0.0.1", port: int = 9000) -> threading.Thread:
    app = FastAPI()

    @app.post("/agent-b/inbox")
    async def inbox(request: Request):
        payload = await request.json()
        message: str = payload.get("message", "")

        # Ingress guardrail evaluation
        result = evaluate_policy(message, direction="ingress")
        # Optional: print decision source (keyword vs LLM) or why LLM was skipped
        try:
            lbl = (result.label or "")
            rsn = (result.reason or "")
            if "|" in lbl:
                src = "KEYWORD+LLM"
            elif lbl.startswith("llm_"):
                src = "LLM" if "llm_policy" in rsn or lbl == "llm_clean" else "LLM_SKIPPED"
            else:
                src = "KEYWORD"
            extra = f" reason={rsn}" if src != "KEYWORD" else ""
            print(f"Ingress evaluation: {src} -> allowed={result.allowed}{extra}")
        except Exception:
            pass
        if not result.allowed:
            # Log the ingress violation as an A2A event
            post_event(
                {
                    "run_id": agentops.ensure_run_started(),
                    "type": "a2a_guardrail_violation",
                    "method": "INGRESS",
                    "url": f"http://{host}:{port}/agent-b/inbox",
                    "service_name": "guardrail",
                    "request_data": message[:500],
                    "response_data": None,
                    "status_code": 403,
                    "duration_ms": 0,
                    "error": f"{result.label}:{result.reason}:{','.join(result.matches)[:180]}",
                    "created_at": int(time.time() * 1000),
                }
            )
            return JSONResponse(status_code=403, content={"ok": False, "blocked": True})

        return {"ok": True, "received": True}

    def _run():
        uvicorn.run(app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # give the server a moment
    time.sleep(0.5)
    return t


def crewai_agent_a_send(message: str, to_url: str) -> Optional[requests.Response]:
    # This function simulates a CrewAI agent emitting a message over HTTP
    # Egress guardrail will be applied by agentops HTTP monitor
    try:
        resp = requests.post(to_url, json={"message": message}, timeout=5)
        return resp
    except Exception as e:
        print(f"Agent A send error: {e}")
        return None


def main() -> None:
    server = os.environ.get("AGENTOPS_URL", "http://localhost:8000")

    agentops.init(
        server_url=server,
        project="a2a-guardrails-demo",
        monitor_http=True,
        block_on_violation=True,
        forbidden=["password", "api_key", "secret key"],
        enable_llm_policy=True,
        llm_policy_model="gpt-4o-mini",
        llm_policy_after_keyword=True,
    )

    # Start Agent B (ingress-guarded) server
    start_agent_b_server()

    with agentops.start_run():
        # 1) Safe message (should pass both egress and ingress)
        safe = "Hello Agent B, here is a harmless status update."
        r1 = crewai_agent_a_send(safe, "http://127.0.0.1:9000/agent-b/inbox")
        print("Safe send:", getattr(r1, "status_code", "blocked"))

        # 2) Unauthorized content (should be blocked at egress by policy)
        bad = "Here is my password: hunter2"
        r2 = crewai_agent_a_send(bad, "http://127.0.0.1:9000/agent-b/inbox")
        print("Bad send (blocked at egress):", getattr(r2, "status_code", "blocked"))

        print("Check dashboard at http://localhost:5173 for A2A events and guardrail logs.")


if __name__ == "__main__":
    main()


