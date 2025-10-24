# AgentOps SDK (MVP)

DevSecOps guardrails and observability for autonomous agents.

## Install

```bash
# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install the SDK in development mode
pip install -e agentops-sdk[openai]
```

## Quickstart (Local Demo)

1) Start local API and dashboard:

```bash
docker compose up
```

- API: http://localhost:8000
- Web: http://localhost:5173

2) Run demo with basic example:

```bash
export OPENAI_API_KEY=sk-test
python examples/runaway_demo.py
```

Open the dashboard to view the run trace, usage, cost, and termination.

## Features (MVP)
- Auto-instrument OpenAI Chat Completions
- Visual trace of prompts/responses
- Cost/tokens aggregation
- Guardrail to stop unbounded recursion

## Development
- SDK code: `agentops/`
- API service: `services/api/` (FastAPI + SQLite)
- Web dashboard: `services/web/` (Vite + React)
- Compose: `docker-compose.yml`
