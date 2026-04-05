# Operations Runbook

## Setup

Requires **Python 3.11+**.

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

Create local runtime env from template:

```bash
# macOS / Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Set secrets only in `.env` (never commit):

- `ORION_LLM_API_KEY=...`
- `ORION_AGENT_DEBUG_TRACE=true` (optional)

## Initialize data

`init_db.py` seeds the schema (including all three analytical views) and loads synthetic data in one step:

```bash
python data/init_db.py
```

To re-apply views only (without re-seeding data — useful after editing `sql/views.sql`):

```bash
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

### Trace interpretation quick-reference

- `phase=planner`: proposed action/tool and planner reasoning for the step.
- `phase=tool_execution`: executed tool, args, result preview or captured error.
- `phase=critique`: continue/stop decision and rationale.
- `phase=synthesis`: final answer composition from accumulated observations.
- `phase=final`: request-level summary including intent, execution mode, and fallback reason (if any).

### Fallback reason taxonomy (operational)

- `LLM mode requested but LLM is not configured`
- JSON parsing/validation failures after repair retries
- Downstream tool execution exceptions
- Deterministic safety fallback due to orchestration exception

Use these categories in incident notes to speed triage and trend analysis.

## Troubleshooting

- If imports fail, run commands from project root.
- If DB missing, re-run `python data/init_db.py`.
- If views missing or returning wrong columns, run `python data/init_db.py` (re-seeds from scratch) or use the `apply_views` one-liner above to re-apply `sql/views.sql` without re-seeding.
