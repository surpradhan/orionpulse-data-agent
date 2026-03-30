# Implementation Roadmap — OrionPulse Data Agent

> **Status as of 2026-03-29.**
> This document tracks what has shipped in v1, what is in progress, and what is planned for v2+.
> Update this file when a milestone ships or priorities shift. See `INDEX.md` for governance.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Shipped / complete |
| 🔄 | In progress |
| 📋 | Planned — prioritised |
| 💡 | Idea — not yet scheduled |

---

## Phase 1 — Foundation (v1, complete)

| # | Item | Status |
|---|------|--------|
| 1.1 | Project scaffolding, `pyproject.toml`, `requirements.txt` | ✅ |
| 1.2 | SQLite schema: `dim_product`, `dim_region`, `fact_sales` | ✅ |
| 1.3 | Three analytical views: `vw_monthly_sales`, `vw_region_performance`, `vw_product_margin_rank` | ✅ |
| 1.4 | Synthetic data generation (`data/generate_data.py`) | ✅ |
| 1.5 | `data/init_db.py` DB initialisation and integrity checks | ✅ |
| 1.6 | `scripts/preflight.py` startup validation | ✅ |
| 1.7 | `src/orion_sales_agent/config.py` — 26-variable settings layer | ✅ |

---

## Phase 2 — MCP & Analytics Core (v1, complete)

| # | Item | Status |
|---|------|--------|
| 2.1 | MCP server with 11 tools (list, describe, SQL, KPI, forecast, anomaly, spec, view creation) | ✅ |
| 2.2 | Read-only SQL policy with allowlist, parser validation, keyword blacklist | ✅ |
| 2.3 | `analytics.py`: KPI summary (monthly/quarterly), forecast, anomaly detection | ✅ |
| 2.4 | Forecast method selection: Holt-Linear vs Holt-Winters holdout RMSE comparison | ✅ |
| 2.5 | Backtest diagnostics: MAPE, sMAPE, RMSE, candidate comparison | ✅ |
| 2.6 | `analytics_exports.py`: CSV/Parquet export + semantic packs (KPI dict, BI stubs) | ✅ |
| 2.7 | `visualization.py`: chart generation (KPI trend, region bar, forecast band, anomaly timeline) | ✅ |

---

## Phase 3 — Knowledge Layer (v1, complete)

| # | Item | Status |
|---|------|--------|
| 3.1 | `skills/` Markdown files: business context, data model, KPI formulae, playbooks | ✅ |
| 3.2 | `specs.py`: dashboard spec (exec_overview template) and storyboard spec | ✅ |
| 3.3 | `tool_registry.py`: dynamic tool list for agent orchestration | ✅ |

---

## Phase 4 — Interaction & Hardening (v1, complete)

| # | Item | Status |
|---|------|--------|
| 4.1 | FastAPI web layer with 6 endpoints + `/v1/*` aliases | ✅ |
| 4.2 | Typed Pydantic response envelopes with `trace_id`, `warnings`, `execution_mode` | ✅ |
| 4.3 | Token-based auth with `analyst` / `admin` roles | ✅ |
| 4.4 | Three auth profiles: `DEV_OPEN`, `DEV_GUARDED`, `PROD_STRICT` | ✅ |
| 4.5 | `agent.py`: orchestration with deterministic / LLM / auto modes | ✅ |
| 4.6 | Planner / critic / synthesis pipeline with JSON schema validation | ✅ |
| 4.7 | `memory_store.py`: lightweight JSON memory persistence (20-item cap) | ✅ |
| 4.8 | HTML chat UI with voice-enabled TTS (`ORION_VOICE_PROVIDER`) | ✅ |
| 4.9 | CI pipeline: lint (ruff), type check (mypy), seed DB, pytest | ✅ |
| 4.10 | Comprehensive test suite (57 tests, unit + integration) | ✅ |

---

## Phase 5 — Documentation & Observability (v1, in progress)

| # | Item | Status |
|---|------|--------|
| 5.1 | `README.md`, `CONTRIBUTING.md`, `SECURITY.md` | ✅ |
| 5.2 | `docs/OPERATIONS_RUNBOOK.md`, `CHANNEL_ERROR_CONTRACTS.md`, `ANALYTICS_EXPORT_GUIDE.md` | ✅ |
| 5.3 | `docs/ENGINEERING_EXECUTION_MODE_POLICY.md`, `INTERACTION_MODES.md` | ✅ |
| 5.4 | `.env.example` with all 26 variables documented | ✅ |
| 5.5 | `docs/API_REFERENCE.md` — endpoint-by-endpoint contract (auth, params, response) | ✅ |
| 5.6 | `docs/VISUALIZATION_GUIDE.md` — chart generation and artifact layout | ✅ |
| 5.7 | `docs/FORECAST_METHODOLOGY.md` — method selection, diagnostics, confidence bands | ✅ |
| 5.8 | Expand `prompt_templates.md` with filled examples | 📋 |
| 5.9 | `docs/TEST_STRATEGY.md` — coverage matrix by module | 📋 |

---

## Phase 6 — v2 Candidates (planned / ideas)

### Analytics & Forecasting

| # | Item | Priority |
|---|------|----------|
| 6.1 | Add ARIMA/SARIMA as a third forecast candidate | 📋 |
| 6.2 | Configurable forecast evaluation metric (default: RMSE; option: sMAPE) | 📋 |
| 6.3 | Weekly/daily grain support in KPI summary | 📋 |
| 6.4 | Composite anomaly scoring across multiple metrics simultaneously | 💡 |

### Data & Infrastructure

| # | Item | Priority |
|---|------|----------|
| 6.5 | PostgreSQL / Oracle adapter alongside SQLite (connection-string driven) | 📋 |
| 6.6 | Incremental data load (append fact rows, don't re-seed) | 📋 |
| 6.7 | Schema migration tooling (Alembic or equivalent) | 💡 |

### MCP & API

| # | Item | Priority |
|---|------|----------|
| 6.8 | OpenAPI/Swagger auto-generated spec served at `/docs` | 📋 |
| 6.9 | Streaming responses for long-running LLM orchestration | 💡 |
| 6.10 | MCP tool versioning (`v1.*` namespacing) | 💡 |
| 6.11 | Additional dashboard templates beyond `exec_overview` | 📋 |

### Observability & Operations

| # | Item | Priority |
|---|------|----------|
| 6.12 | Structured JSON logging (replace print-based traces) | 📋 |
| 6.13 | Prometheus metrics endpoint (`/metrics`) | 💡 |
| 6.14 | Performance / load test gate in CI | 📋 |
| 6.15 | Health-check endpoint (`/health`) with DB ping | 📋 |

### Security & Auth

| # | Item | Priority |
|---|------|----------|
| 6.16 | JWT-based auth as an alternative to static tokens | 💡 |
| 6.17 | Per-route RBAC matrix (currently role-level only) | 💡 |

---

## Milestones

| Milestone | Target | Contents |
|-----------|--------|----------|
| **v1.0** | Shipped | Phases 1–4 complete, CI green, 57 tests passing |
| **v1.1** | In progress | Phase 5 documentation, `.env.example`, API reference, viz/forecast guides |
| **v2.0** | TBD | Phase 6 items prioritised as needed |

---

*Owner: see `INDEX.md`. Update this file when items ship or priorities change.*
