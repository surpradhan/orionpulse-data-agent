## OrionPulse Technical Review (2026-03-01)

Scope reviewed: `src/orion_sales_agent/*`, `mcp_server/server.py`, project docs and quality context from Memory Bank.

### Executive summary
- Core architecture and safety posture are solid (SQL policy centralization, auth profiles, role-guarded web endpoints, typed response envelopes).
- Primary readiness gap is maintainability/documentation depth in core orchestration and web surface modules.
- Secondary risk is delivery friction from lint/type-check environment drift (already tracked in memory-bank).

---

## Findings and prioritized improvement areas

### P0 (recommended before next push)

1. **Code-level documentation gaps across critical modules**
   - **Impact:** Slower onboarding, higher change-risk during hotfixes, unclear API/service invariants.
   - **Observed in:** `agent.py`, `webapp.py`, `analytics.py`, `sql_policy.py`, `mcp_server/server.py`.
   - **Action taken now:** Added/expanded docstrings on core public and shared implementation functions.

2. **Monolithic web layer file composition (`webapp.py`)**
   - **Impact:** Reduced readability/testability; difficult contract evolution.
   - **Recommendation:** Split into `api_models.py`, `auth.py`, route modules, and externalize large HTML/JS to static/template file.

3. **Concentrated orchestration responsibilities (`agent.py`)**
   - **Impact:** High cognitive load and elevated regression risk for feature edits.
   - **Recommendation:** Extract `llm_client`, `planner_contracts`, `tool_registry`, `memory_store`, and orchestration coordinator modules.

### P1 (next sprint)

4. **Error-contract consistency across channels**
   - **Impact:** Different failure semantics between MCP and web can surprise clients.
   - **Recommendation:** Introduce channel-specific but standardized error model documentation and mapping strategy.

5. **SQL object extraction edge-case hardening**
   - **Impact:** Regex extraction may under-handle complex nested SQL aliases/CTEs in future use.
   - **Recommendation:** Increase parser-first checks and add tests for nested joins/subqueries/aliasing.

6. **Operational observability documentation depth**
   - **Impact:** Harder production triage for fallback/trace analysis.
   - **Recommendation:** Add trace interpretation and incident triage guide in runbook.

### P2 (backlog)

7. **Forecast method extensibility**
   - **Impact:** Current Holt-family approach is pragmatic but limited for some series patterns.
   - **Recommendation:** Add explicit model-selection strategy and comparative diagnostics.

8. **Quality-gate ergonomics**
   - **Impact:** Local/CI parity issues (`mypy` availability, broad Ruff backlog) can slow developer loop.
   - **Recommendation:** Lock dev-tooling profile and progressively enforce lint scope.

---

## Documentation uplift completed in this cycle

- `src/orion_sales_agent/agent.py`
  - Added module docstring and method-level behavioral docstrings for orchestration, LLM contract validation, and entrypoints.
- `src/orion_sales_agent/webapp.py`
  - Added module docstring plus endpoint/shared-helper docstrings for auth, mode resolution, response envelope, and route implementations.
- `src/orion_sales_agent/analytics.py`
  - Added module docstring plus function docstrings for KPI summary, forecasting, diagnostics, and anomalies.
- `src/orion_sales_agent/sql_policy.py`
  - Added module and policy-function docstrings clarifying safety intent and constraints.
- `mcp_server/server.py`
  - Added module and MCP-tool docstrings explaining safety checks, input guards, and behavior.

---

## Recommended next refactor plan (post-push)

1. **Web layer modularization**
   - Move Pydantic models and auth utilities out of route module.
   - Move inline HTML/JS to separate static/template artifact.

2. **Agent orchestration decomposition**
   - Introduce interfaces for planner/critic/synthesis and tool execution abstraction.
   - Add unit tests around orchestration step transitions and failure states.

3. **Contract and operations docs expansion**
   - Publish endpoint-by-endpoint auth/response/error matrix.
   - Add trace artifacts quick-reference and fallback reason taxonomy.
