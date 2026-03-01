# User Interaction Modes

## 1) MCP Chat (Primary)

User asks natural language questions in an MCP-compatible chat client.

Examples:

- "Show Q4 net revenue and margin % by region"
- "Why did APAC margin decline last month?"
- "Forecast next 3 months net revenue"

## 2) Structured Prompt Mode

Use templates with explicit goal, scope, and output format for repeatability.

## 3) CLI Mode

`python scripts/ask_agent.py --question "forecast next months revenue" --format json`

## 4) Minimal Web UI

Launch with Uvicorn and use `/kpi` and `/forecast` endpoints.

## Answer Format Guidelines

Responses should include scope, formulas, assumptions, and recommended actions.
