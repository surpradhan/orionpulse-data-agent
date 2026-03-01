# Engineering Execution Mode Policy (MCP vs Web UI vs CLI)

## Purpose

Define consistent execution behavior across channels so OrionPulse keeps deterministic correctness for system-of-record outputs while enabling LLM-assisted reasoning for exploratory flows.

## Mode Definitions

- `deterministic`: rule-based orchestration only.
- `llm`: require LLM orchestration when configured; fallback with explicit reason if unavailable.
- `auto`: use LLM orchestration when configured, else deterministic.

## Channel Policy

### MCP
- Default: deterministic contract behavior.
- Rationale: tool contracts must remain stable for integrations.
- Notes: orchestration intelligence can sit above MCP clients, but MCP tool semantics remain deterministic.

### Web UI/API
- Default: `auto` (`ORION_WEB_DEFAULT_MODE`, default `auto`).
- Deterministic-only endpoints:
  - `/kpi`, `/forecast`
  - `/ask_with_analytics_exports`
- Auto/LLM-eligible endpoints:
  - `/ask`, `/chat`, `/ask_with_visuals`
- All core endpoints expose `execution_mode`; fallback paths may include `fallback_reason`.

### CLI
- Default: deterministic (`ORION_CLI_DEFAULT_MODE`, default `deterministic`).
- Supports `--mode auto|deterministic|llm`.
- JSON output exposes `execution_mode`; fallback paths may include `fallback_reason`.

## API Versioning

v1 aliases were added for core routes to enable forward-compatible contract evolution:

- `POST /v1/chat`
- `GET /v1/kpi`
- `GET /v1/forecast`
- `GET /v1/ask`
- `GET /v1/ask_with_visuals`
- `GET /v1/ask_with_analytics_exports`

Legacy routes remain available for backward compatibility.

## Engineering Guardrails

- Deterministic fallback must exist for any LLM failure.
- Business-critical numeric outputs and export artifacts remain deterministic.
- Execution mode metadata is part of response observability and debugging.

## Next Iterations

- Add endpoint-level typed response models (Pydantic) with explicit `execution_mode` and `fallback_reason` fields.
- Add performance/load tests for heavy endpoints (`/chat`, `/ask_with_visuals`, `/ask_with_analytics_exports`).
- Add UI mode indicator and provenance display.