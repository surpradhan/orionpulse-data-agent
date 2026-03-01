# Active Context

## Current focus
- Closing production-readiness gaps from execution plan: auth profile hardening, forecast quality diagnostics, load coverage, and CI gates.

## Recent changes
- Completed documentation consolidation and quality uplift across workspace Markdown files:
  - Rewrote `README.md` into a clearer single-entry guide (setup, channels, mode policy, auth posture, contracts, doc map).
  - Expanded `CONTRIBUTING.md` with lint/type expectations, documentation update policy, and area-specific testing guidance.
  - Expanded `SECURITY.md` with runtime hardening baseline, richer vuln-reporting requirements, and secure-dev checklist.
  - Updated `docs/INTERACTION_MODES.md` to align with execution mode policy and current channel behavior.
  - Updated `docs/UI_REALTIME_TEST_CASES.md` to reflect auth-profile-aware behavior and envelope-based endpoint responses.
  - Consolidated overlapping planning docs by enhancing `docs/MASTER_PLAN.md` with a living roadmap section.
  - Removed redundant planning files after consolidation:
    - `implementation_plan.md`
    - `docs/IMPLEMENTATION_ROADMAP.md`
- Implemented technical review refactor recommendations for modularity and maintainability:
  - Extracted web request/response models to `src/orion_sales_agent/api_models.py`.
  - Extracted auth helpers to `src/orion_sales_agent/auth.py` and switched web routes to shared `require_role`.
  - Extracted web inline UI HTML/JS into `src/orion_sales_agent/templates/home.html` and simplified `webapp.py` home route.
  - Extracted orchestration helper modules: `llm_client.py`, `planner_contracts.py`, `tool_registry.py`, `memory_store.py`; rewired `agent.py` to consume them.
- Implemented forecast method selection extensibility baseline:
  - Added `select_forecast_method` and candidate-model diagnostics (`diagnostics.candidates`) in `analytics.py`.
- Implemented SQL extraction edge-case hardening:
  - Upgraded object extraction to handle schema-qualified and quoted identifiers and exclude CTE aliases.
  - Added SQL policy edge-case tests in `tests/test_sql_policy_edge_cases.py`.
- Expanded contract/operations documentation:
  - Added `docs/CHANNEL_ERROR_CONTRACTS.md` with web-vs-MCP failure mapping.
  - Extended `docs/OPERATIONS_RUNBOOK.md` with trace interpretation and fallback taxonomy.
- Improved dev-tooling ergonomics:
  - Added `mypy==1.11.2` to `requirements.txt`.
  - Added baseline mypy config in `pyproject.toml`.
- Expanded/updated tests for this cycle:
  - `tests/test_forecast_quality.py` now validates candidate diagnostics and method selection.
  - `tests/test_web_contracts_performance.py` now verifies home template externalization.
  - `tests/test_critical_paths.py` now asserts forecast diagnostics include candidates.
- Verified targeted regression suite after changes:
  - `python -m pytest tests/test_sql_policy_edge_cases.py tests/test_forecast_quality.py tests/test_critical_paths.py tests/test_web_contracts_performance.py -q` -> `20 passed`.
- Added explicit auth profile system in config (`AuthProfile`: `DEV_OPEN`/`DEV_GUARDED`/`PROD_STRICT`) with resolvers and startup validation (`resolve_auth_profile`, `validate_auth_configuration`).
- Wired startup auth validation in FastAPI lifespan to enforce profile-aware auth safety checks before serving.
- Expanded forecast diagnostics with backtesting metrics (`mape`, `smape`, `rmse`, train/backtest points, method, warnings) while preserving additive API contract compatibility.
- Added dedicated auth profile matrix tests (`tests/test_auth_profile_defaults.py`).
- Added dedicated forecast quality tests for metric bounds and short-series nullable behavior (`tests/test_forecast_quality.py`).
- Added broader performance/load tests for burst concurrency and sustained requests (`tests/test_performance_load.py`).
- Added Matplotlib non-GUI backend helper (`set_test_safe_matplotlib_backend`) and enabled it in test bootstrap (`tests/conftest.py`).
- Extended CI workflow with lint and type-check stages before tests (`.github/workflows/ci.yml`).
- Expanded FastAPI typed response contracts to endpoint-specific envelope payloads (`ChatEnvelope`, `KpiEnvelope`, `ForecastEnvelope`, `AskEnvelope`, `AskWithVisualsEnvelope`, `AskWithAnalyticsExportsEnvelope`).
- Added frontend provenance UX hints for chat responses (`Mode`, `Fallback`, and `Warnings` labels).
- Added new web contract/performance smoke test module (`tests/test_web_contracts_performance.py`) for `/chat`, `/ask_with_visuals`, `/ask_with_analytics_exports`, `/kpi`, and `/forecast` including deterministic vs auto timing checks.
- Added MCP response contract decision doc: keep MCP outputs raw and use versioned tools for future evolution (`docs/MCP_RESPONSE_CONTRACT_DECISION.md`).
- Added initial typed API response/input models in FastAPI layer (`ApiEnvelope`, `ChatPayload`) for stronger HTTP contract validation.
- Added web UI provenance indicator showing `execution_mode` and optional `fallback_reason` in the home page chat interface.
- Updated web UI speech playback binding to read answer from standardized envelope path (`data.answer`).
- Added channel-by-channel execution mode policy implementation (MCP/Web UI/CLI).
- Added response-level execution provenance metadata (`execution_mode`, optional `fallback_reason`).
- Added CLI `--mode` support with configurable default (`ORION_CLI_DEFAULT_MODE`).
- Added configurable web default orchestration mode (`ORION_WEB_DEFAULT_MODE`).
- Added `/v1` aliases for core web endpoints for contract evolution.
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
- Run full repository validation (all tests + lint/type gates) and resolve any broader baseline debt outside targeted scope.
- Kick-off UI modernization initiative: extract CSS/JS into static assets, introduce Vite build tooling, progressive UX improvements (spinner, live streaming), rich markdown/chart rendering, accessibility conformance, dark-mode support, and front-end automation tests (Playwright, Lighthouse CI).
- Decide whether to enforce repo-wide Ruff clean-up now or scope CI lint target to critical modules until backlog cleanup is done.
- Consider richer forecasting candidates (e.g., damped trend/ARIMA family) and expose explicit selection strategy in API docs.
- Consider promoting load tests into stricter SLI/SLO gates as baseline stabilizes.

## Active decisions
- `docs/MASTER_PLAN.md` is now the canonical retained planning/roadmap summary document.
- Historical planning details from deleted roadmap files were preserved through consolidation into retained docs (primarily `README.md` + `docs/MASTER_PLAN.md`).
- Dev-mode auth bypass remains only when auth is not required and no tokens are configured.
- Forecast intervals are approximate residual-based (v1 practical approach).
- Forecast diagnostics are additive and backward compatible in existing forecast payload envelope.
- CI stage order remains: preflight -> lint -> type check -> tests.

## Key learnings
- Structured LLM output handling significantly improves orchestration resilience.
- Role-scoped endpoint protection is required before production exposure.