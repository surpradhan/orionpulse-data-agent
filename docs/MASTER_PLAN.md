# Master Plan - OrionPulse Data Agent v1

## Objective

Build a self-sufficient data agent that reads sales data from three tables through MCP tools, understands business context via skills files, and can generate analytical outputs (views, dashboard/storyboard specs, deeper reasoning and predictions).

## Architecture

1. **Data Layer**: SQLite (`dim_product`, `dim_region`, `fact_sales`)
2. **Tool Layer**: MCP tools for discovery/query/KPI/forecast/spec generation
3. **Knowledge Layer**: `skills/*.md`
4. **Output Layer**: SQL views + JSON specs + analytics results
5. **Interaction Layer**: MCP chat, CLI wrapper, minimal web UI

## Why this design

- Fast implementation with low setup burden
- Strong modularity for future migration (Postgres/Oracle)
- Reproducible local setup and straightforward operations

## Scope Delivered in v1

- Synthetic data generation and DB initialization
- MCP server with core and advanced tools
- KPI formulas and business playbooks
- Dashboard/storyboard artifacts
- Forecast/anomaly analytics
- Dev setup files, tests, and runbook docs

---

## Consolidated implementation roadmap (living summary)

This section supersedes earlier fragmented planning notes and keeps roadmap intent in one canonical location.

### Foundation
- Project scaffolding and configuration
- SQL schema and data bootstrap flows

### Data and modeling
- Synthetic dimension/fact generation
- SQLite initialization and integrity validation

### MCP and analytics core
- Metadata and safe SQL tools
- KPI summaries, forecasting, anomaly detection
- Admin-gated view creation and spec generation

### Knowledge and outputs
- Skills-based business context + KPI logic
- Reusable SQL views and JSON dashboard/storyboard specs
- Analytics export packs for downstream BI consumption

### Interaction and operational hardening
- MCP client workflows, CLI mode, web UI/API
- Typed response envelopes in web channel
- Auth profile-based hardening and role checks
- CI quality gates (lint/type/tests), expanded test coverage, runbook guidance

### Ongoing priorities
- Continue reducing lint backlog for repo-wide gate stability
- Expand forecasting method candidates and model-selection documentation
- Strengthen load/performance SLO-aligned test gates over time
