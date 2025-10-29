# AgentOps SDK (MVP)

DevSecOps guardrails and observability for autonomous agents.

## Install

```bash
# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install the SDK in development mode
cd ~/agentops-sdk
pip install -e .[openai]

# Demo deps (HTTP + FastAPI server)
pip install fastapi uvicorn requests
```

## Services (API + Dashboard)

```bash
docker compose up
```

- API: http://localhost:8000
- Web: http://localhost:5173

## Environment

- `OPENAI_API_KEY`: required for LLM-backed policy checks (optional otherwise)
- `AGENTOPS_URL`: backend base URL (default `http://localhost:8000`)
- `AGENTOPS_FORBIDDEN`: extra forbidden substrings (comma-separated), e.g. `token,private_key`

```bash
export OPENAI_API_KEY=sk-...
# optional
export AGENTOPS_URL=http://localhost:8000
export AGENTOPS_FORBIDDEN=token,private_key
```

## Demos

### 1) Runaway Guardrail (LLM call limit)

```bash
python examples/runaway_demo.py
```

What it shows: auto-instrumented OpenAI calls, token/cost tracking, and termination when `max_llm_calls` is exceeded.

### 2) HTTP A2A Monitoring (egress tracing)

Logs outbound HTTP calls (requests/httpx) as A2A events.

```bash
python examples/http_a2a_demo.py
```

What it shows: A2A events appear in the dashboard with method, URL, status, payload truncation, errors, and durations.

### 3) Two-Agent A2A Guardrails (egress + ingress + policy)

Starts a minimal FastAPI "Agent B" inbox and sends messages from "Agent A" over HTTP. The SDK enforces guardrails at:
- Egress (client send)
- Ingress (server receive)
- Tool/LLM calls (OpenAI patch)

```bash
# Ensure services are running (API + Web)
docker compose up

# Run the demo
python examples/crewai_a2a_demo.py
```

Policy configuration used in the demo (`agentops.init`):
- `forbidden=["password", "api_key", "secret key"]`: keyword/regex guardrail
- `enable_llm_policy=True`: enable LLM-backed policy
- `llm_policy_model="gpt-4o-mini"`: model used for analysis
- `llm_policy_after_keyword=True`: also run LLM when keyword violation is found (for audit)
- `block_on_violation=True`: block and log violations

Output tips:
- Ingress handler prints whether decision came from KEYWORD, LLM, or KEYWORD+LLM. If LLM fails, it prints LLM_SKIPPED with reason.
- Egress violations are sent as `a2a_guardrail_violation` events; check the Web dashboard.

## Features (MVP)
- Auto-instrument OpenAI Chat Completions
- Visual trace of prompts/responses
- Cost/tokens aggregation
- Guardrails: recursion limit, A2A HTTP monitoring, keyword/regex policy, optional LLM-backed policy

## Development
- SDK code: `src/agentops/`
- API service: `services/api/` (FastAPI + SQLite)
- Web dashboard: `services/web/` (Vite + React)
- Compose: `docker-compose.yml`
