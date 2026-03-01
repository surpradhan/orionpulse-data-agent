# OrionPulse Agent - Real-time UI Test Cases (Review Draft)

## Scope

These test cases cover real-time validation of the minimal web UI and core API endpoints:

- Home page render
- KPI endpoint behavior
- Forecast endpoint behavior
- Error and safety behaviors for hardened logic
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

### AUTH-001: Unauthenticated access policy check (current-state)
**Objective:** Validate whether app enforces authentication for UI routes.  
**Steps:**
1. Open `http://127.0.0.1:8010/` in a fresh browser session
2. Open `http://127.0.0.1:8010/kpi`
3. Open `http://127.0.0.1:8010/forecast`

**Expected (current implementation):**
- Routes are accessible without login (HTTP 200)

**Security note:**
- This is expected for current v1 (no auth module yet), and should be tracked as a hardening backlog item.

**Evidence to save:** screenshots of all 3 endpoints

---

### AUTH-002: Protected-route expectation test (future target)
**Objective:** Define target behavior after auth is added.  
**Steps:**
1. Access protected endpoint without token/session
2. Access with invalid token/session
3. Access with valid token/session

**Expected (future):**
- No token/session => HTTP 401/403
- Invalid token/session => HTTP 401/403
- Valid token/session => HTTP 200

**Status:**
- Not applicable in current build; included as planned security regression test.

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
- JSON array with objects containing: `period`, `net_revenue`, `margin`, `units_sold`, `asp`, `margin_pct`
- Array length > 0

**Evidence to save:** screenshot of response body

---

### UI-003: Forecast endpoint returns valid JSON
**Objective:** Verify `/forecast` returns forecast payload.  
**Steps:**
1. Open `http://127.0.0.1:8010/forecast`
2. Inspect payload

**Expected:**
- HTTP 200
- JSON object with keys: `metric`, `horizon`, `history`, `forecast`, `assumptions`
- `horizon` equals configured default (3)
- `forecast` list length = 3

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
- AUTH-001 executed and documented for current state
- All security/validation tests API-SEC-001..API-VAL-002 pass
- Evidence artifacts generated for each case
