# Implementation Roadmap

## Phase 1 - Foundation

- Scaffold project
- Add environment/config files
- Define SQL schema

## Phase 2 - Data

- Generate synthetic dimensions and facts
- Initialize SQLite DB
- Validate row counts and referential integrity

## Phase 3 - MCP Server

- Table metadata and SQL tools
- KPI summaries
- View creation and spec generation tools
- Forecast and anomaly tools

## Phase 4 - Knowledge + Output Artifacts

- Skills markdown files
- SQL reusable views
- JSON dashboard/storyboard specs

## Phase 5 - User Interaction + Quality

- CLI interaction mode
- Minimal web UI
- Tests, preflight, docs and quickstart

## Acceptance Criteria

- Agent can read all 3 tables via MCP
- Agent can answer KPI and deeper analysis questions
- Agent can produce forecast output
- Agent can produce view + dashboard/storyboard artifacts
