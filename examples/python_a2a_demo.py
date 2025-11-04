"""
Two-agent A2A governance demo using python-a2a adapter.

Prereqs:
  pip install python-a2a requests flask
Services:
  docker compose up  # backend API + dashboard
"""
import os
import threading
import time

import agentops
from agentops.a2a_adapter import A2AClient
from agentops.a2a_adapter.flask_mixin import AgentOpsFlaskMixin

try:
    from python_a2a import A2AServer, run_server as pa2a_run_server
except Exception:
    A2AServer = None  # type: ignore


def start_agent_b_server(host: str = "127.0.0.1", port: int = 9100) -> threading.Thread:
    if A2AServer is None:
        raise RuntimeError("python-a2a not installed; run `pip install python-a2a`")

    class GovernedServer(AgentOpsFlaskMixin, A2AServer):
        pass

    # python-a2a requires an agent URL for the agent card
    server = GovernedServer(url=f"http://{host}:{port}")

    def _run():
        # Run via python-a2a helper so it constructs Flask app and registers routes
        pa2a_run_server(server, host=host, port=port)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.5)
    return t


def main() -> None:
    server = os.environ.get("AGENTOPS_URL", "http://localhost:8000")

    agentops.init(
        server_url=server,
        project="python-a2a-guardrails-demo",
        monitor_http=False,  # we use adapter hooks instead of generic HTTP patch here
        block_on_violation=True,
        forbidden=["password", "api_key", "secret key"],
        enable_llm_policy=True,
        llm_policy_model="gpt-4o-mini",
        llm_policy_after_keyword=True,
    )

    # Start Agent B server (with middleware via run_server)
    start_agent_b_server()

    # Create AgentOps-wrapped A2A client
    base_url = "http://127.0.0.1:9100"
    # Initialize wrapped client; adapter uses base_url for logging, underlying client may use defaults
    client = A2AClient(base_url=base_url)

    with agentops.start_run():
        # Safe message
        r1 = client.send_message("agent-b", "Hello Agent B from python-a2a demo")
        print("Safe send status:", getattr(r1, "status_code", 200))

        # Policy-violating message (egress should block and log)
        try:
            client.send_message("agent-b", "Here is my password: hunter2")
        except Exception as e:
            print("Blocked send:", e)

        print("Open dashboard: http://localhost:5173 and view A2A events/violations")


if __name__ == "__main__":
    main()


