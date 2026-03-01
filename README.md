# OrionPulse Data Agent (MCP + SQLite)

End-to-end sales analytics agent with:

- 3-table sales model and synthetic data generation
- MCP server tools for querying, KPI summaries, view creation, forecasting, anomalies
- Skills markdown knowledge files for business context and KPI logic
- SQL views and JSON dashboard/storyboard specs
- 3 interaction modes: MCP chat client, CLI wrapper, minimal web UI
- Agent orchestration layer: intent classification, multi-step tool routing, memory, and follow-up suggestions

## Quick Start

1. Create virtual environment:

```bash
python -m venv .venv
```

2. Activate and install dependencies:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Initialize database:

```bash
python data/init_db.py
```

4. Apply standard views:

```bash
python -c "from src.orion_sales_agent.views import apply_views; from src.orion_sales_agent.config import settings; apply_views(settings.db_path); print('views applied')"
```

5. Run MCP server:

```bash
python mcp_server/server.py
```

6. Try CLI mode:

```bash
python scripts/ask_agent.py --question "forecast next months revenue" --format json
```

Generate visual analytics artifacts from CLI:

```bash
python scripts/ask_agent.py --question "show performance with charts" --with-charts --format json
```

Agentic behavior now includes: intent detection, reasoning summary, contextual follow-up prompts, and short memory in `data/agent_memory.json`.

### LLM Orchestration (Planner + Tool-Calling + Critique Loop)

To enable dynamic multi-hop analysis (instead of only rule-based routing), set:

```bash
ORION_LLM_API_KEY=your_key_here
ORION_LLM_BASE_URL=https://api.openai.com/v1
ORION_LLM_MODEL=gpt-4o-mini
ORION_LLM_MAX_STEPS=4
```

When configured, the agent uses:
- planner loop (decides next tool dynamically)
- tool execution loop (kpi/forecast/anomaly/dashboard/storyboard/driver tools)
- critique loop (decides whether more evidence is needed)
- final synthesis step

If LLM is unavailable or fails, the agent safely falls back to deterministic orchestration.

7. Run minimal web UI:

```bash
python -m uvicorn src.orion_sales_agent.webapp:app --reload
```

Visit `http://127.0.0.1:8000`.

Try: `http://127.0.0.1:8000/ask?q=why%20did%20margin%20drop`

Visual endpoint:

`http://127.0.0.1:8000/ask_with_visuals?q=show%20kpi%20trend&fmt=png`

Generated charts are saved under `artifacts/charts/` and exposed via `/artifacts/charts/...`.

### API Response Envelope

Core JSON endpoints now return a standard envelope:

```json
{
  "status": "ok",
  "trace_id": "orion-...",
  "timestamp": "2026-...Z",
  "warnings": [],
  "data": { }
}
```

This applies to `/chat`, `/kpi`, `/forecast`, `/ask`, `/ask_with_visuals`, and `/ask_with_bi_exports`.

### Auth configuration

Auth behavior is controlled by:

- `ORION_ENV` (default: `dev`)
- `ORION_AUTH_REQUIRED` (defaults to `true` when `ORION_ENV != dev`, else `false`)
- `ORION_ANALYST_TOKEN`
- `ORION_ADMIN_TOKEN`

When auth is required and tokens are missing, the app fails fast at startup.

## Phase 2 BI Exports (Power BI / Tableau / OAC)

Generate BI-ready datasets + semantic packs:

```bash
python scripts/ask_agent.py --question "prepare bi export for power bi" --with-bi-exports --format json
```

API endpoint:

`http://127.0.0.1:8000/ask_with_bi_exports?q=prepare%20bi%20exports&fmt=csv`

See `docs/BI_EXPORT_GUIDE.md` for full details.

## Voice-enabled Chat UI

Open:

- `http://127.0.0.1:8000/`

Voice controls in UI:

- 🎤 Start/Stop Listening (speech-to-text)
- Auto speak answer (text-to-speech)
- Voice selector + speech rate slider

Environment scaffolding:

- `ORION_VOICE_PROVIDER=browser`
- `ORION_VOICE_LANG=en-US`
- `ORION_TTS_VOICE=`

## Validation

```bash
python scripts/preflight.py
pytest
```

## Security / Safety Notes

- `run_sql` accepts only single-statement `SELECT`/`WITH` queries.
- Queryable objects are restricted to an internal allowlist of approved tables/views.
- SQL limit is capped by `ORION_MAX_SQL_LIMIT`.
- `create_sql_view` is gated and requires `ORION_ADMIN_MODE=true` (and is blocked in readonly mode unless admin mode is enabled).
- Forecast/anomaly tools enforce input ranges and return graceful warning payloads for empty/insufficient data.

## Project Layout

- `data/`: seed + DB init
- `src/orion_sales_agent/`: core package
- `mcp_server/`: MCP server entrypoint
- `skills/`: business knowledge files
- `sql/`: schema and views
- `specs/`: dashboard/storyboard JSON
- `docs/`: full architecture and implementation plan docs
