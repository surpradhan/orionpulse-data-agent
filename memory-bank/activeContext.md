# Active Context

## Current focus
- Hardened core platform after feature expansion (voice/UI/BI/LLM orchestration).

## Recent changes
- Added LLM JSON schema validation + repair/retry flow.
- Added token role checks (analyst/admin) on key web endpoints.
- Added `ORION_AUTH_REQUIRED` config with non-dev strict-default behavior and startup guard when tokens are missing.
- Enforced analyst role checks on `/kpi` and `/forecast` for consistent endpoint policy.
- Migrated FastAPI startup hook to lifespan to avoid deprecated `on_event` usage.
- Standardized API response envelope across key endpoints with `status`, `trace_id`, `timestamp`, `warnings`, `data`.
- Added centralized SQL policy module with parser-backed validation.
- Improved forecast outputs with interval bands + diagnostics.
- Added DB constraints/indexes and expanded critical-path tests.
- Added MCP integration-level tests covering tool contracts, SQL safety enforcement, analytics/spec/export flows.
- Verified targeted MCP integration suite and full pytest suite passing.

## Next steps
- Keep dev-mode bypass only for `ORION_ENV=dev` unless explicitly overridden by `ORION_AUTH_REQUIRED`.
- Consider extending response envelope standardization to MCP tool outputs (or document why MCP remains raw contract).
- Add richer model diagnostics and optional advanced forecasting methods.
- Add performance/load-oriented integration coverage beyond functional MCP validations.
- Add typed response models (Pydantic) for standardized API envelope + payload schemas.
- Decide and document MCP response contract direction (raw tool contract vs envelope convention).
- Add forecast quality scaffolding (backtesting + MAPE/SMAPE diagnostics).
- Add performance/load smoke tests for `/chat`, `/ask_with_visuals`, and `/ask_with_bi_exports`.
- Add CI follow-up gates for lint/type checks if pending.

## Active decisions
- Dev-mode auth bypass remains only when auth is not required and no tokens are configured.
- Forecast intervals are approximate residual-based (v1 practical approach).

## Key learnings
- Structured LLM output handling significantly improves orchestration resilience.
- Role-scoped endpoint protection is required before production exposure.