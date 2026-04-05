## OrionPulse Technical Review (2026-04-05)

Scope reviewed: `src/orion_sales_agent/*`, `mcp_server/server.py`, `sql/views.sql`, `tests/`.

### Executive summary

The v1.2 hardening pass resolved all confirmed critical and high findings from a full codebase audit. The test suite expanded from 57 to 120 tests (added `test_security.py`, `test_reliability.py`, `test_quality.py`). Intent routing correctness was improved. The primary remaining risk areas are documentation of operational procedures (now updated) and a small set of medium-priority test coverage gaps.

---

## Findings, actions, and outcomes

### Confirmed and fixed

**1. `sql/views.sql` out of sync with `schema.sql` (HIGH)**
- `vw_region_performance` defined only 4 columns; `agent.py` queried for 7. `vw_product_margin_rank` missing `subcategory` and `units_sold`.
- The live database was correct (seeded from `schema.sql`), but a clean `init_db.py` run followed by `apply_views` would have produced broken views.
- **Fix:** `sql/views.sql` updated to include all columns referenced by agent code. Both files are now in sync.

**2. Admin auth checked after `agent.answer()` in `_chat_impl` (HIGH)**
- A non-admin user sending `with_analytics=true` would trigger a full agent execution before the auth exception fired — wasting compute and creating a fragile ordering dependency.
- **Fix:** `require_role(admin)` moved to before `agent.answer()`.

**3. Metric f-string interpolation in `forecast_metric` / `anomaly_detection` (MEDIUM)**
- `SUM({metric})` interpolated the caller-supplied metric name directly into SQL. The allowlist check was correct and positioned before use, but the pattern made the safety boundary non-obvious.
- **Fix:** `_METRIC_COLUMN` lookup dict introduced. Allowlist and SQL identifier now defined in one place; interpolation is structurally impossible for values outside the dict.

**4. PRAGMA string concatenation in MCP server (MEDIUM)**
- `"PRAGMA table_info(" + table_name + ")"` — allowlist guard was correct, but the concatenation pattern warranted documentation.
- **Fix:** Replaced with f-string. Added inline comment explaining why parameterized binding is not available for PRAGMA identifiers in SQLite.

**5. Intent routing: anomaly plurals not matched (LOW)**
- `"anomaly" in q` does not match `"anomalies"` or `"anomalous"`.
- **Fix:** Changed to `"anomal" in q`.

**6. Intent routing: product-by-revenue phrasing not matched (LOW)**
- `"Which product had the highest revenue?"` failed to route because `"highest"` was not in the product qualifier keyword set.
- **Fix:** Added `"highest"` and `"lowest"` to the set.

---

### Investigated and not fixed (false positives or acceptable)

| Finding | Conclusion |
|---------|------------|
| `vw_region_performance` runtime KeyError | False positive — live DB has all columns; SQL query succeeds at runtime |
| Division by zero at `agent.py:733` | `if margins:` guard on line 732 prevents it |
| MAPE negative clamp (unreachable code) | Harmless defensive code; not worth removing |
| JSON depth limit DoS | Not a realistic risk for this workload |
| X-Forwarded-For trust | Correctly documented in comments; not a production deployment |

---

## State at close of review

- 120 tests, all passing
- `sql/views.sql` and `schema.sql` in sync
- Auth check order correct in all endpoints
- Metric SQL uses lookup dict in both `forecast_metric` and `anomaly_detection`
- Intent router handles `anomaly`/`anomalies`/`anomalous` and product-revenue phrasing

## Remaining medium-priority gaps (not addressed in this pass)

- No direct unit tests for `anomaly_detection()` (threshold validation, z-score correctness)
- No unit tests for `analytics_exports.py` (CSV row counts, manifest structure)
- No structural test asserting admin auth precedes `agent.answer()` in `_chat_impl`
- `kpi_summary` quarter grain and empty-DB paths not tested

See `docs/TEST_STRATEGY.md` Recommended Next Tests for full list.
