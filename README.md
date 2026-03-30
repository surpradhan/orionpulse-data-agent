# OrionPulse Data Agent (MCP + SQLite + FastAPI)

OrionPulse is a sales analytics agent that combines deterministic data tooling with optional LLM orchestration.

It supports:
- Sales KPI analysis over a curated SQLite model
- Forecasting and anomaly detection
- Dashboard/storyboard spec generation
- Analytics export package generation for BI tools
- MCP tool access, CLI usage, and a WEB UI/API

## Core capabilities

- Data model: `dim_product`, `dim_region`, `fact_sales`
- MCP tools: metadata, readonly SQL, KPI summary, forecast, anomaly, view creation (admin-gated), spec generation
- Agent orchestration modes: deterministic, llm, auto (with safe fallback)
- Web API: standardized envelope + execution provenance fields
- Voice-enabled UI: browser speech-to-text and text-to-speech controls

## Quick start

1) Create and activate environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Configure environment variables

```bash
cp .env.example .env
# Edit .env — at minimum set ORION_LLM_API_KEY if using LLM mode
```

3) Initialize data and views

```bash
python data/init_db.py
python -c "from src.orion_sales_agent.views import apply_views; from src.orion_sales_agent.config import settings; apply_views(settings.db_path); print('views applied')"
```

4) Run services

```bash
python mcp_server/server.py
python -m uvicorn src.orion_sales_agent.webapp:app --reload
```

5) Try CLI

```bash
python scripts/ask_agent.py --question "forecast next months revenue" --format json
python scripts/ask_agent.py --question "why did margin drop" --mode auto --format json
python scripts/ask_agent.py --question "show performance with charts" --with-charts --format json
python scripts/ask_agent.py --question "prepare analytics exports" --with-analytics-exports --format json
```

## Interaction channels and mode policy

- MCP: deterministic contract behavior by default
- Web/API: default `auto` (configurable via `ORION_WEB_DEFAULT_MODE`)
- CLI: default `deterministic` (configurable via `ORION_CLI_DEFAULT_MODE`)

See:
- `docs/ENGINEERING_EXECUTION_MODE_POLICY.md`
- `docs/INTERACTION_MODES.md`

## LLM orchestration (optional)

Configure:

```bash
ORION_LLM_API_KEY=your_key_here
ORION_LLM_BASE_URL=https://api.openai.com/v1
ORION_LLM_MODEL=gpt-4o-mini
ORION_LLM_MAX_STEPS=4
```

If unavailable or failing, the agent falls back to deterministic logic.

## API response contract

Core JSON endpoints use:

```json
{
  "status": "ok",
  "trace_id": "orion-...",
  "timestamp": "2026-...Z",
  "warnings": [],
  "data": {}
}
```

Also includes provenance:
- `execution_mode`: `deterministic` | `llm_orchestrated` | `fallback_rule_based`
- `fallback_reason` (optional)

Routes:
- Primary: `/chat`, `/kpi`, `/forecast`, `/ask`, `/ask_with_visuals`, `/ask_with_analytics_exports`
- Versioned aliases: `/v1/...` for the same endpoints

## Auth and security posture

Key variables:
- `ORION_ENV`
- `ORION_AUTH_REQUIRED`
- `ORION_AUTH_PROFILE` (`DEV_OPEN`, `DEV_GUARDED`, `PROD_STRICT`)
- `ORION_ANALYST_TOKEN`
- `ORION_ADMIN_TOKEN`

When auth is required and tokens are missing, startup fails fast.

Safety highlights:
- SQL constrained to single-statement readonly `SELECT`/`WITH`
- Allowlist validation for queryable objects
- SQL row limits bounded by config
- Admin-only operations gated and policy-checked

## Validation

```bash
python scripts/preflight.py
pytest
```

## Documentation map

| Topic | Document |
|-------|----------|
| Architecture and strategy | `docs/MASTER_PLAN.md` |
| Implementation roadmap | `docs/IMPLEMENTATION_ROADMAP.md` |
| Data model and KPIs | `docs/DATA_MODEL_AND_KPIS.md` |
| **API endpoint reference** | `docs/API_REFERENCE.md` |
| Interaction modes (MCP / CLI / Web) | `docs/INTERACTION_MODES.md` |
| Execution mode policy | `docs/ENGINEERING_EXECUTION_MODE_POLICY.md` |
| Auth profiles and security | `SECURITY.md` |
| Ops runbook | `docs/OPERATIONS_RUNBOOK.md` |
| Channel error semantics | `docs/CHANNEL_ERROR_CONTRACTS.md` |
| MCP response contract decision | `docs/MCP_RESPONSE_CONTRACT_DECISION.md` |
| Analytics exports | `docs/ANALYTICS_EXPORT_GUIDE.md` |
| **Visualization and charts** | `docs/VISUALIZATION_GUIDE.md` |
| **Forecast methodology** | `docs/FORECAST_METHODOLOGY.md` |
| Full doc index and governance | `docs/INDEX.md` |

## Project layout

- `src/orion_sales_agent/` core package
- `mcp_server/` MCP server entrypoint
- `data/` DB initialization and seed utilities
- `sql/` schema and views
- `skills/` business reasoning knowledge files
- `specs/` generated dashboard/storyboard/analytics spec files
- `docs/` architecture, policy, and operational guidance
