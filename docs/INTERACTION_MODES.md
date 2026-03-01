# User Interaction Modes

This document describes how OrionPulse is used across channels and how execution mode is controlled.

For engineering policy details, see `docs/ENGINEERING_EXECUTION_MODE_POLICY.md`.

## 1) MCP Chat (integration-first)

Primary use case for programmatic integrations through MCP tools.

- MCP tool contracts are intentionally deterministic and tool-shaped.
- Responses are raw tool payloads (not HTTP envelopes).
- Best for stable, automatable data workflows.

Example asks:
- "Show Q4 net revenue and margin % by region"
- "Why did APAC margin decline last month?"
- "Forecast next 3 months net revenue"

## 2) CLI mode (`scripts/ask_agent.py`)

Convenient local/operator interface for analytics and orchestration testing.

Examples:

```bash
python scripts/ask_agent.py --question "forecast next months revenue" --format json
python scripts/ask_agent.py --question "why did margin drop" --mode auto --format json
python scripts/ask_agent.py --question "show kpi summary" --mode deterministic --format json
```

Mode controls:
- `--mode auto|deterministic|llm`
- Default from `ORION_CLI_DEFAULT_MODE` (default `deterministic`)

## 3) Web UI / HTTP API mode

Launch:

```bash
python -m uvicorn src.orion_sales_agent.webapp:app --reload
```

Default: `auto` via `ORION_WEB_DEFAULT_MODE`.

Deterministic-only endpoints:
- `/kpi`
- `/forecast`
- `/ask_with_analytics_exports`

Auto/LLM-eligible endpoints:
- `/chat`
- `/ask`
- `/ask_with_visuals`

Versioned aliases also exist under `/v1/...`.

## 4) Structured prompt mode (cross-channel technique)

Use explicit templates for repeatable outputs:
- Goal
- Scope (time/region/product)
- Desired output format (table, narrative, actions)

See `docs/prompt_templates.md`.

## Response guidance

Answers should include:
- Scope and filters used
- Formula assumptions (especially KPI and forecast context)
- Evidence/driver breakdown where applicable
- Recommended actions and expected business effect
