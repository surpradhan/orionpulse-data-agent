# Operations Runbook

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create local runtime env from template:

```bash
copy .env.example .env
```

Set secrets only in `.env` (never commit):

- `ORION_LLM_API_KEY=...`
- `ORION_AGENT_DEBUG_TRACE=true` (optional)

## Initialize data

```bash
python data/init_db.py
python -c "from src.orion_sales_agent.views import apply_views; from src.orion_sales_agent.config import settings; apply_views(settings.db_path)"
```

## Start services

- MCP server: `python mcp_server/server.py`
- Web UI: `python -m uvicorn src.orion_sales_agent.webapp:app --reload`

## Validation

```bash
python scripts/preflight.py
pytest
```

## Debug Trace Mode (Planner/Tool/Critique Transparency)

Enable in `.env`:

```bash
ORION_AGENT_DEBUG_TRACE=true
ORION_AGENT_TRACE_PATH=artifacts/agent-traces
```

Then run:

```bash
python scripts/ask_agent.py --question "why did margin drop in APAC" --format json
```

Trace files are written under `artifacts/agent-traces/trace_*.json`.

## Troubleshooting

- If imports fail, run commands from project root.
- If DB missing, re-run `python data/init_db.py`.
- If views missing, apply `apply_views` command above.
