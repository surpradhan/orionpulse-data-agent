# OrionPulse Agent - Real-time UI/API Test Cases

## Scope

These test cases cover real-time validation of the web UI and core API endpoints:

- Home page render
- KPI endpoint behavior
- Forecast endpoint behavior
- Auth, error, and safety behaviors for hardened logic
- Evidence capture for each test (screenshots + response payload logs)

## Preconditions

1. Dependencies installed
2. Database initialized and views applied
3. Web app running:

```bash
python -m uvicorn src.orion_sales_agent.webapp:app --host 127.0.0.1 --port 8010
```

4. Browser resolution baseline: 900x600 (for automated visual checks)

---

## Test Data Assumptions

- DB: `data/orion_sales_agent.db`
- Seeded rows expected:
  - `dim_product = 6`
  - `dim_region = 4`
  - `fact_sales = 864`

---

## Test Cases

### AUTH-001: Unauthenticated access policy check (profile-aware)
**Objective:** Validate behavior by auth profile and token configuration.  
**Steps:**
1. Start app with `ORION_AUTH_PROFILE=DEV_OPEN` and no tokens
2. Open `http://127.0.0.1:8010/`, `/kpi`, `/forecast`
3. Restart app with required auth (`DEV_GUARDED` or `PROD_STRICT`) and no token in request headers
4. Re-run `/kpi` and `/forecast`

**Expected:**
- `DEV_OPEN` (no required auth): routes may be reachable without token (HTTP 200)
- guarded/strict modes: protected routes require token (401/403 when missing/invalid)

**Security note:**
- Auth behavior is intentionally environment/profile-driven.

**Evidence to save:** screenshots of all 3 endpoints

---

### AUTH-002: Protected-route expectation test (future target)
**Objective:** Validate role-based route protection with configured tokens.  
**Steps:**
1. Access protected endpoint without token/session
2. Access with invalid token/session
3. Access with valid token/session

**Expected:**
- No token/session => HTTP 401/403
- Invalid token/session => HTTP 401/403
- Valid token/session => HTTP 200

**Status:**
- Applicable in current build when auth is required/configured.

---

### UI-001: Home page loads
**Objective:** Verify the root page is reachable and displays expected links.  
**Steps:**
1. Open `http://127.0.0.1:8010/`
2. Validate title/header contains "OrionPulse Agent"
3. Validate links for `/kpi` and `/forecast`

**Expected:**
- HTTP 200
- Visible heading and both links
- No console/runtime errors

**Evidence to save:** screenshot + console logs

---

### UI-002: KPI endpoint returns valid JSON
**Objective:** Verify `/kpi` returns aggregated KPI records.  
**Steps:**
1. Open `http://127.0.0.1:8010/kpi`
2. Inspect response shape

**Expected:**
- HTTP 200
- JSON envelope with `status`, `trace_id`, `timestamp`, `warnings`, `data`
- `data` contains KPI records with fields including: `period`, `net_revenue`, `margin`, `units_sold`, `asp`, `margin_pct`
- Result set length > 0

**Evidence to save:** screenshot of response body

---

### UI-003: Forecast endpoint returns valid JSON
**Objective:** Verify `/forecast` returns forecast payload.  
**Steps:**
1. Open `http://127.0.0.1:8010/forecast`
2. Inspect payload

**Expected:**
- HTTP 200
- JSON envelope with `status`, `trace_id`, `timestamp`, `warnings`, `data`
- `data` includes `metric`, `horizon`, `history`, `forecast`, `assumptions`
- `data.horizon` equals configured default (3)
- `data.forecast` list length = 3
- Optional additive diagnostics may be present in `data.diagnostics`

**Evidence to save:** screenshot of response body

---

### UI-004: Service stability under repeated refresh
**Objective:** Ensure no crash on repeated endpoint hits.  
**Steps:**
1. Refresh `/kpi` 5 times
2. Refresh `/forecast` 5 times

**Expected:**
- All responses return HTTP 200
- No server crash/restart

**Evidence to save:** screenshots + terminal logs

---

### API-SEC-001: SQL multi-statement rejection (backend safety)
**Objective:** Validate hardening rejects multi-statement SQL.  
**Method:** run server tool path via python snippet.

**Expected:**
- Error raised: multi-statement not allowed

---

### API-SEC-002: Disallowed object rejection
**Objective:** Validate non-allowlisted objects are blocked.  
**Expected:**
- Error raised for disallowed object reference

---

### API-SEC-003: create_sql_view blocked without admin mode
**Objective:** Ensure readonly/admin gating is enforced.  
**Expected:**
- Permission error when `ORION_ADMIN_MODE=false`

---

### API-VAL-001: Invalid forecast horizon rejected
**Objective:** Validate range checks.  
**Input:** horizon > 24  
**Expected:** validation error

---

### API-VAL-002: Invalid anomaly threshold rejected
**Objective:** Validate threshold bounds.  
**Input:** threshold < 1.0 or > 5.0  
**Expected:** validation error

---

## Output Capture Plan

For each test, store:

- `artifacts/ui-tests/<TEST_ID>.png` (screenshots)
- `artifacts/ui-tests/<TEST_ID>.log` (response/errors)
- `artifacts/ui-tests/summary.md` (pass/fail matrix)

---

## Pass/Fail Exit Criteria

- All UI tests UI-001..UI-004 pass
- AUTH-001 executed and documented for active auth profile
- All security/validation tests API-SEC-001..API-VAL-002 pass
- Evidence artifacts generated for each case
