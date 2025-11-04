# Python A2A Governance Demo

This document explains how `examples/python_a2a_demo.py` works, how the A2A server middleware is added, and how the A2A client send function is wrapped by the AgentOps SDK.

## What this demo shows
- Two agents communicating over HTTP using the `python-a2a` package
- AgentOps governance applied at two points:
  - Egress: before the client sends a message
  - Ingress: when the server receives a message
- Optional LLM-backed policy analysis (in addition to keyword/regex)
- A2A observability events (send/receive and guardrail violations) recorded to the AgentOps backend

## Prerequisites
- Backend services: `docker compose up`
  - API: `http://localhost:8000`
  - Web: `http://localhost:5173`
- Install libs:
  ```bash
  pip install -e .[openai]
  pip install python-a2a requests flask
  export OPENAI_API_KEY=sk-...
  ```

## Run the demo
```bash
python examples/python_a2a_demo.py
```
What you should see in the dashboard:
- `a2a_message_receive` on inbound requests (INGRESS)
- `a2a_message_send` for successful outbound sends (EGRESS)
- `a2a_guardrail_violation` when content is blocked (EGRESS or INGRESS)

Note: If a “bad” message is blocked at egress, it won’t reach the server. To see an ingress violation for it, set `block_on_violation=False` in `agentops.init` temporarily.

---

## How ingress governance is added (server middleware)
The demo uses a subclass of `python_a2a.A2AServer` that mixes in `AgentOpsFlaskMixin`:

```python
from agentops.a2a_adapter.flask_mixin import AgentOpsFlaskMixin
from python_a2a import A2AServer

class GovernedServer(AgentOpsFlaskMixin, A2AServer):
    pass

server = GovernedServer(url=f"http://{host}:{port}")
```

The mixin injects a Flask `before_request` hook inside `setup_routes(app)` (the exact point `python-a2a` wires up its routes):
- Skips metadata endpoints and non-POST requests (e.g., `/.well-known/agent.json`)
- Emits a generic receive event:
  - `a2a_message_receive` with `method=INGRESS`
- Evaluates ingress policy: `evaluate_policy(message_text, direction="ingress")`
- On violation:
  - Logs an `a2a_guardrail_violation` (INGRESS)
  - Returns `403` with `{ "ok": false, "blocked": true }`
- For non-violations, it lets the request proceed
- Minimal-run behavior: if the server had to create a transient run to log the event, it immediately posts `run_completed` so you don’t get dangling traces

Where to read the code:
- `src/agentops/a2a_adapter/flask_mixin.py`

Alternative entry points (also available):
- ASGI middleware: `src/agentops/a2a_adapter/middleware.py`
- WSGI middleware: `src/agentops/a2a_adapter/middleware_wsgi.py`

The mixin approach guarantees the hook runs on the actual Flask app that `python-a2a` constructs.

---

## How egress governance is applied (client wrapper)
The demo constructs the client using the AgentOps-wrapped adapter:

```python
from agentops.a2a_adapter import A2AClient
client = A2AClient(base_url="http://127.0.0.1:9100")

# Egress evaluation runs inside send_message
client.send_message("agent-b", "Hello Agent B from python-a2a demo")
```

The adapter extends `python_a2a.A2AClient` and overrides `send_message`:
1) Policy evaluation
   - Calls `evaluate(message, direction="egress")`
   - On violation:
     - Emits `a2a_guardrail_violation` (EGRESS)
     - Raises if `block_on_violation=True`
2) Send and trace
   - Calls the underlying client’s `send_message`
   - Emits `a2a_message_send` with duration and status

Compatibility notes:
- Different `python-a2a` versions expect different message shapes. The wrapper:
  - Tries `(agent_id, message)` signature first
  - Falls back to `(message)` signature and, if needed, wraps string messages into a small shim object implementing `to_dict()` and `to_google_a2a()`

Where to read the code:
- `src/agentops/a2a_adapter/client.py`

---

## AgentOps configuration used in the demo
Inside `examples/python_a2a_demo.py`:
```python
agentops.init(
    server_url="http://localhost:8000",
    project="python-a2a-guardrails-demo",
    monitor_http=False,   # adapter provides A2A governance; HTTP tracing not needed here
    block_on_violation=True,
    forbidden=["password", "api_key", "secret key"],
    enable_llm_policy=True,
    llm_policy_model="gpt-4o-mini",
    llm_policy_after_keyword=True,  # run LLM even if keyword matched (audit)
)
```
Tips:
- To force ingress violations to appear for a bad message, set `block_on_violation=False` so the message reaches the server and is blocked there.
- To add extra forbidden phrases without code changes, set `AGENTOPS_FORBIDDEN=token,private_key` in the environment.

---

## Event glossary
- `a2a_message_send` (EGRESS): outbound send traces from the client wrapper
- `a2a_message_receive` (INGRESS): inbound receive traces from the server mixin/middlewares
- `a2a_guardrail_violation` (EGRESS/INGRESS): policy failure with details in `error = label:reason:matches`
- `llm_call`: a model-based policy analysis entry if LLM checks are enabled

You can inspect these events per run in the dashboard (`http://localhost:5173`).
