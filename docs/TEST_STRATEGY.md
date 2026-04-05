# Test Strategy — OrionPulse Data Agent

This document describes the test architecture, coverage matrix, and guidance for
adding or extending tests. Run the full suite with `pytest` from the project root.

---

## Running Tests

```bash
# Full suite
pytest

# Specific file
pytest tests/test_sql_policy_edge_cases.py

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print output
pytest -s
```

**CI:** Tests run in GitHub Actions on every push and pull request to `main`.
The CI workflow seeds the database (`python data/init_db.py`) before running `pytest`.
See `.github/workflows/ci.yml`.

---

## Suite Overview

| File | Category | Tests | What it covers |
|------|----------|-------|----------------|
| `test_sql_policy_edge_cases.py` | Unit | 23 | SQL policy: allowlist, mutation blocking, CTE/alias extraction, nested subqueries, JOIN extraction |
| `test_security.py` | Unit | 22 | XSS sanitization, constant-time token comparison, `require_role` enforcement, auth structural invariants |
| `test_reliability.py` | Unit | 23 | Crash guards for forecast/dashboard/storyboard/anomaly synthesis, LLM circuit-breaker, visualization lock, artifact TTL purge |
| `test_quality.py` | Unit | 18 | Rate limiter correctness, memory bloat guard, health endpoint, API model strictness, max-length consistency |
| `test_forecast_quality.py` | Unit | 4 | Forecast analytics: diagnostics structure, short-series warnings, method selection, candidate exposure |
| `test_auth_profile_defaults.py` | Unit | 7 | Auth config: profile resolution, token requirements, invalid profile rejection |
| `test_critical_paths.py` | Integration | 9 | End-to-end: SQL policy, forecast output, chart contract, LLM fallback, web auth, v1 routes |
| `test_web_contracts_performance.py` | Integration | 4 | Web API: envelope shape, HTML template, KPI/forecast contracts, latency budget |
| `test_performance_load.py` | Load | 2 | Concurrency: 16-request burst on `/forecast`, 25-request sustained load on `/kpi` |
| **Total** | | **112 + parametrized = 120** | |

---

## Coverage Matrix

### SQL Policy (`src/orion_sales_agent/sql_policy.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Single-statement enforcement | `test_single_statement_strips_trailing_semicolon`, `test_single_statement_rejects_multi_statement`, `test_single_statement_rejects_empty` | edge_cases |
| Allowlist enforcement — base tables | `test_sql_policy_allowlist`, `test_view_name_in_allowlist_passes` | critical_paths, edge_cases |
| Allowlist enforcement — nested subqueries | `test_nested_subquery_in_where_allowed_objects`, `test_nested_subquery_blocked_when_inner_object_disallowed`, `test_deeply_nested_subquery_all_allowed` | edge_cases |
| Allowlist enforcement — CTEs | `test_multi_cte_names_excluded_from_refs`, `test_multi_cte_validate_passes_with_allowed_objects`, `test_cte_referencing_disallowed_base_table_blocked` | edge_cases |
| Allowlist enforcement — JOINs | `test_multiple_join_types_extract_correctly`, `test_self_join_same_table_counts_once`, `test_cross_join_objects_extracted`, `test_four_way_join_all_allowed_passes`, `test_join_with_one_disallowed_table_blocked` | edge_cases |
| Mutation keyword blocking | `test_forbidden_tokens_rejected` (9 tokens: INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/REPLACE/ATTACH) | edge_cases |
| PRAGMA blocking | `test_pragma_blocked` | edge_cases |
| SELECT without FROM rejected | `test_query_with_no_from_clause_rejected` | edge_cases |
| Case-insensitive table matching | `test_case_insensitive_table_matching` | edge_cases |
| CTE and alias extraction | `test_extract_referenced_objects_handles_cte_and_aliases` | edge_cases |
| Quoted / schema-qualified names | `test_extract_referenced_objects_handles_quoted_and_schema_names` | edge_cases |
| Unknown nested object rejected | `test_validate_readonly_select_rejects_unknown_nested_object` | edge_cases |
| Multi-statement in critical path | `test_sql_policy_blocks_multi_statement` | critical_paths |

**Gap:** No tests for `EXPLAIN` / `EXPLAIN QUERY PLAN` handling; no tests for very long queries (>10 KB).

---

### Analytics — Forecast (`src/orion_sales_agent/analytics.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Forecast returns intervals and diagnostics | `test_forecast_has_intervals_and_diagnostics`, `test_forecast_diagnostics_present_and_bounded` | critical_paths, forecast_quality |
| Short series returns warning, null metrics | `test_short_series_returns_nullable_metrics_with_warning` | forecast_quality |
| Candidate methods exposed in diagnostics | `test_forecast_diagnostics_exposes_candidate_methods` | forecast_quality |
| Method selection returns valid method name | `test_select_forecast_method_returns_supported_method` | forecast_quality |

**Gap:** No tests for `kpi_summary` with `grain="quarter"`; no tests for `anomaly_detection` with non-default thresholds; no negative test for `horizon > 24`.

---

### Analytics — Anomaly Detection (`src/orion_sales_agent/analytics.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Anomaly synthesis: empty list returns safe message | `test_synthesize_anomaly_empty_list`, `test_synthesize_anomaly_none_input` | reliability |
| Anomaly synthesis: single flagged period formatted correctly | `test_synthesize_anomaly_single_flagged_period` | reliability |

**Gap:** No dedicated unit tests for `anomaly_detection()` itself (threshold range, invalid threshold rejection, z-score correctness, empty DB). Currently covered indirectly via `/ask` integration only.

---

### Authentication (`src/orion_sales_agent/auth.py`)

| Behaviour | Test | File |
|-----------|------|------|
| DEV_OPEN profile: no token required | `test_dev_open_with_no_tokens_is_allowed`, `test_resolve_auth_profile_defaults_for_dev_open` | auth_profile_defaults |
| DEV_GUARDED profile default | `test_resolve_auth_profile_defaults_for_dev_guarded` | auth_profile_defaults |
| PROD_STRICT profile default for non-dev | `test_resolve_auth_profile_defaults_for_non_dev_strict` | auth_profile_defaults |
| Invalid profile raises ValueError | `test_explicit_invalid_profile_raises` | auth_profile_defaults |
| PROD_STRICT requires `auth_required=True` | `test_prod_strict_requires_auth_required_true` | auth_profile_defaults |
| Non-dev env requires tokens | `test_non_dev_requires_token_configuration` | auth_profile_defaults |
| Analyst vs admin role enforcement | `test_web_auth_roles` | critical_paths |
| Missing token blocks access | `test_auth_required_without_tokens_blocks_access` | critical_paths |

**Gap:** No test for HMAC timing-safe comparison behaviour; no test for token rotation mid-session.

---

### Security (`src/orion_sales_agent/auth.py`, `agent.py`)

| Behaviour | Test | File |
|-----------|------|------|
| HTML/script tag stripping from LLM output | `TestSanitizeText` (8 cases) | security |
| Constant-time token comparison prevents timing attacks | `TestCtEq` (7 cases) | security |
| `require_role`: analyst/admin enforcement, missing token, wrong role | `TestRequireRole` (5 cases) | security |
| Auth structural invariants (DEV_OPEN, PROD_STRICT properties) | `TestAuthStructural` (2 cases) | security |

**Gap:** No test confirming admin `require_role` fires before `agent.answer()` in `_chat_impl` (structural regression guard).

---

### Web API (`src/orion_sales_agent/webapp.py`)

| Behaviour | Test | File |
|-----------|------|------|
| `/chat`, `/ask`, `/ask_with_visuals`, `/ask_with_analytics_exports` envelope shape | `test_web_contract_chat_and_ask_family` | web_contracts_performance |
| `/` serves HTML template | `test_home_route_serves_externalized_template` | web_contracts_performance |
| `/kpi` and `/forecast` envelope shape | `test_web_contract_kpi_and_forecast` | web_contracts_performance |
| `/v1/*` aliases available | `test_v1_routes_available` | critical_paths |
| Latency budget (< 30s per endpoint) | `test_endpoint_smoke_latency_by_mode` | web_contracts_performance |

**Gap:** No tests for 422 validation errors (bad `fmt` value, `q` too short/long); no test for `with_visuals=true` with bad DB path.

---

### Visualization (`src/orion_sales_agent/visualization.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Chart generation contract (returns metadata) | `test_visualization_contract_chart_output` | critical_paths |

**Gap:** No tests for SVG format output; no tests for each individual chart type (`plot_kpi_trend`, `plot_region_performance`, `plot_forecast_with_band`, `plot_anomaly_timeline`); no test for manifest JSON structure.

---

### LLM Client (`src/orion_sales_agent/llm_client.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Fallback triggered on bad JSON from LLM | `test_llm_fallback_on_bad_json` | critical_paths |
| LLM mode without API key reports fallback | `test_llm_requested_without_configuration_reports_fallback` | critical_paths |

**Gap:** No test for timeout behaviour; no test for retry logic (`ORION_LLM_JSON_RETRIES`).

---

### Performance & Load

| Behaviour | Test | File |
|-----------|------|------|
| `/forecast` burst: 16 concurrent requests < 10s max latency | `test_forecast_burst_concurrency` | performance_load |
| `/kpi` sustained: 25 sequential requests < 20s total | `test_kpi_sustained_load` | performance_load |

**Gap:** No load test for `/chat` in LLM mode; no memory leak / connection pool exhaustion test.

---

### Reliability (`src/orion_sales_agent/agent.py`, `visualization.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Forecast synthesis handles empty/None data without crash | `TestSynthesizeForecastCrashGuard` (4 cases) | reliability |
| Dashboard synthesis handles empty/invalid spec | `TestSynthesizeDashboard` (3 cases) | reliability |
| Storyboard synthesis handles edge inputs | `TestSynthesizeStoryboard` (2 cases) | reliability |
| LLM circuit-breaker: fallback after repeated tool failures | `TestLlmCircuitBreaker` (7 cases) | reliability |
| Visualization manifest lock prevents concurrent corruption | `TestVisualizationLock` (2 cases) | reliability |
| Artifact TTL purge removes stale charts | `TestArtifactTTLPurge` (3 cases) | reliability |

### Quality / Operational (`src/orion_sales_agent/webapp.py`, `memory_store.py`)

| Behaviour | Test | File |
|-----------|------|------|
| Rate limiter: per-IP bucketing, window expiry, burst enforcement | `TestRateLimiter` (4 cases) | quality |
| Memory bloat guard: 50 KB cap enforced on write | `TestMemoryBloatGuard` (4 cases) | quality |
| `/health` endpoint returns status and DB connectivity | `TestHealthEndpoint` (4 cases) | quality |
| API model field strictness (no extra fields accepted) | `TestApiModelStrictness` (3 cases) | quality |
| Max-length consistency across response fields | `TestMaxLengthConsistency` (3 cases) | quality |

---

### Not Yet Covered

| Module | Gap |
|--------|-----|
| `analytics_exports.py` | No unit tests for CSV/Parquet export, semantic pack file contents, manifest structure |
| `analytics.py` (anomaly) | No unit tests for `anomaly_detection()` threshold validation, z-score correctness, empty series |
| `specs.py` | No tests for `dashboard_spec()` with filters, `storyboard_spec()` with non-default audience |
| `memory_store.py` | No tests for 20-item cap eviction, persistence across restarts |
| `agent.py` | No unit tests for planner/critic/synthesis step validation (covered only via integration) |
| `db.py` | No tests for connection pool behaviour under concurrent load |
| `config.py` | No tests for all 26 env var defaults (partial coverage via auth profile tests) |

---

## Fixtures and Setup

### `conftest.py`

Sets matplotlib to a non-GUI backend at session start to prevent display errors in CI:

```python
from src.orion_sales_agent.visualization import set_test_safe_matplotlib_backend
set_test_safe_matplotlib_backend()
```

### Database

Tests that hit the database expect a seeded SQLite file at `ORION_DB_PATH`
(default: `data/orion_sales_agent.db`). Run `python data/init_db.py` before
the suite if the file does not exist. CI does this automatically.

### Monkeypatching

Tests in `test_critical_paths.py`, `test_auth_profile_defaults.py`, and
`test_web_contracts_performance.py` use pytest's built-in `monkeypatch` fixture
to override environment variables and settings without touching the real environment.

---

## Adding New Tests

1. **Unit tests** for a module → add to an existing `test_<module>.py` or create one.
2. **Integration tests** that touch the DB or web layer → add to `test_critical_paths.py`
   or `test_web_contracts_performance.py`.
3. **Load / concurrency tests** → add to `test_performance_load.py`.
4. If your test requires a new setup step, add a **fixture to `conftest.py`** — do not
   inline setup inside individual test functions.
5. Mark slow tests with `@pytest.mark.slow` (add the marker to `pyproject.toml`
   `[tool.pytest.ini_options]` markers list) so they can be skipped in fast feedback loops.

---

## Recommended Next Tests (by priority)

| Priority | Module | Test to add |
|----------|--------|-------------|
| P1 | `anomaly_detection` | Direct unit tests: threshold range validation, invalid threshold rejection, z-score correctness, empty series |
| P1 | `analytics_exports` | CSV row counts match DB, parquet schema, manifest keys |
| P1 | `webapp.py` | 422 on bad `fmt`/`q` values; structural test that admin `require_role` precedes `agent.answer()` |
| P2 | `specs.py` | `dashboard_spec` with filters, `storyboard_spec` audience variations |
| P2 | `memory_store.py` | 20-item eviction, file persistence round-trip |
| P2 | `kpi_summary` | Quarter grain, period_filter, empty DB |
| P3 | `llm_client.py` | Timeout, retry exhaustion |
| P3 | `visualization.py` | SVG output, individual chart function contracts, manifest JSON structure |

---

*Owner: QA/Release Engineer. Update this file when new tests are added or coverage gaps are closed.*
