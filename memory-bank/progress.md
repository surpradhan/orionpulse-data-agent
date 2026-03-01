# Progress

## What works
- Agent answers KPI/root-cause/forecast/anomaly/dashboard/storyboard queries.
- LLM orchestration now has schema checks + JSON repair/retry.
- Visualization and BI export generation are integrated.
- Voice-enabled chat UI supports browser STT/TTS controls.
- SQL policy centralized and parser-backed validation added.
- Role-based API auth implemented with strict-mode option via `ORION_AUTH_REQUIRED`.
- `/kpi` and `/forecast` now follow analyst token checks for policy consistency.
- Startup guard now fails fast when auth is required but tokens are missing.
- Core HTTP JSON endpoints now use a standard response envelope (`status`, `trace_id`, `timestamp`, `warnings`, `data`).
- Tests expanded and passing.
- MCP integration-level tests now cover tool metadata, SQL safety, analytics, spec generation, and export flows.
- Targeted MCP integration suite and full pytest suite are both passing.

## What remains
- Optional hardening: decide final production profile defaults and rollout strategy for strict auth across environments.
- Optional contract step: evaluate typed response models (Pydantic) to formalize envelope + payload schemas.
- Optional forecasting upgrades: richer diagnostics and model selection.
- Add performance/load tests and scenario breadth beyond current MCP integration functional coverage.

## Known issues / caveats
- Statsmodels may emit convergence warnings on some series.
- Browser speech APIs vary by browser/platform support.
- If auth is not required and tokens are unset, API allows dev-mode access.