# API Reference — OrionPulse Data Agent

All endpoints are served by the FastAPI application (`src/orion_sales_agent/webapp.py`).
Every mutating endpoint and most read endpoints require an `X-Orion-Token` header.

> **Versioning:** Each route is available at both the canonical path (e.g. `/chat`) and a
> `/v1/*` alias (e.g. `/v1/chat`). They are identical; the alias exists for clients that
> require a versioned prefix. Future breaking changes will be introduced under `/v2/*`.

---

## Authentication

| Header | Value | Notes |
|--------|-------|-------|
| `X-Orion-Token` | `<token>` | Set via `ORION_ANALYST_TOKEN` or `ORION_ADMIN_TOKEN` env var |

**Roles:**

| Role | Required for | Token env var |
|------|-------------|---------------|
| `analyst` | `/chat`, `/kpi`, `/forecast`, `/ask`, `/ask_with_visuals` | `ORION_ANALYST_TOKEN` |
| `admin` | `/ask_with_analytics_exports` | `ORION_ADMIN_TOKEN` |

**Auth profiles** (set via `ORION_AUTH_PROFILE`):

| Profile | Behaviour |
|---------|-----------|
| `DEV_OPEN` | No token required. All routes accessible. **Local dev only.** |
| `DEV_GUARDED` | Token validated when provided; missing token still allowed. |
| `PROD_STRICT` | Token required on every guarded route. Missing/invalid = 401. |

---

## Response Envelope

All endpoints return a shared JSON envelope:

```json
{
  "trace_id": "uuid4-string",
  "timestamp": "2026-03-29T12:00:00Z",
  "execution_mode": "deterministic",
  "fallback_reason": null,
  "warnings": [],
  "data": { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `trace_id` | string | Unique ID for this request (correlates with trace files) |
| `timestamp` | string | ISO-8601 UTC timestamp |
| `execution_mode` | string | `deterministic`, `llm`, or `auto` (whichever ran) |
| `fallback_reason` | string\|null | Non-null when auto-mode fell back from deterministic to LLM |
| `warnings` | array | Non-fatal warnings (e.g. insufficient forecast history) |
| `data` | object | Endpoint-specific payload (see per-endpoint docs below) |

**Error responses** follow FastAPI's default structure:
```json
{ "detail": "human-readable error message" }
```
HTTP status codes: `400` bad input, `401` unauthorized, `403` forbidden, `422` validation error, `500` internal error.

---

## Endpoints

---

### `GET /`

Serves the HTML chat UI.

- **Auth:** None
- **Response:** `text/html` (Jinja2 template from `templates/home.html`)

---

### `POST /chat` · `POST /v1/chat`

Send a natural-language question to the agent. Returns a full answer with optional
visualizations and/or analytics exports.

- **Auth:** `analyst`
- **Content-Type:** `application/json`

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | ✅ | — | Question (3–400 characters) |
| `with_visuals` | boolean | — | `false` | Generate and attach chart files |
| `with_analytics` | boolean | — | `false` | Generate and attach analytics export pack |
| `fmt` | string | — | `"png"` | Chart format when `with_visuals=true`. Values: `png` \| `svg` |

**Example request:**
```json
{
  "q": "What is our net revenue trend over the last 6 months?",
  "with_visuals": true,
  "fmt": "png"
}
```

**`data` payload:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Agent's natural-language response |
| `charts` | array\|null | List of chart metadata objects (when `with_visuals=true`) |
| `analytics` | object\|null | Analytics export manifest (when `with_analytics=true`) |

---

### `GET /kpi` · `GET /v1/kpi`

Return aggregated KPI summary across all periods.

- **Auth:** `analyst`
- **Query parameters:** None (grain and period controlled via `ORION_DEFAULT_GRAIN` env var)

**`data` payload:**

Array of period objects:

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | `YYYY-MM` (month) or `YYYY-Qn` (quarter) |
| `net_revenue` | number | Sum of net revenue |
| `margin` | number | Sum of margin |
| `units_sold` | number | Sum of units sold |
| `asp` | number | Average selling price (`net_revenue / units_sold`) |
| `margin_pct` | number | Margin percentage (`margin / net_revenue`) |

---

### `GET /forecast` · `GET /v1/forecast`

Return a 3-period ahead forecast for `net_revenue` (default).

- **Auth:** `analyst`
- **Query parameters:** None (horizon controlled via `ORION_DEFAULT_FORECAST_HORIZON`)

**`data` payload:**

| Field | Type | Description |
|-------|------|-------------|
| `metric` | string | Metric being forecast |
| `horizon` | integer | Number of forecast periods |
| `history` | array | Last 12 historical data points (`period`, `value`) |
| `forecast` | array | Forecast points (`period`, `value`, `lower`, `upper`) |
| `assumptions` | array | Human-readable modelling assumptions |
| `diagnostics` | object | Backtest metrics — see [Forecast Methodology](FORECAST_METHODOLOGY.md) |
| `warning` | string\|null | Non-null when insufficient history or model failure |

---

### `GET /ask` · `GET /v1/ask`

Ask a single natural-language question. Lighter-weight than `/chat` — no visual or export options.

- **Auth:** `analyst`
- **Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | ✅ | Question (3–400 characters) |

**`data` payload:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Agent's natural-language response |

---

### `GET /ask_with_visuals` · `GET /v1/ask_with_visuals`

Ask a question and receive an answer with generated chart files.

- **Auth:** `analyst`
- **Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | ✅ | — | Question (3–400 characters) |
| `fmt` | string | — | `"png"` | Chart format: `png` \| `svg` |

**`data` payload:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Agent's natural-language response |
| `charts` | array | List of chart objects (see below) |

**Chart object:**

| Field | Type | Description |
|-------|------|-------------|
| `chart_type` | string | `kpi_trend`, `region_performance`, `forecast_band`, or `anomaly_timeline` |
| `path` | string | Relative path to the generated file under `artifacts/charts/` |
| `url` | string | URL path for browser access (e.g. `/artifacts/charts/kpi_trend.png`) |
| `fmt` | string | `png` or `svg` |

See [Visualization Guide](VISUALIZATION_GUIDE.md) for full chart type documentation.

---

### `GET /ask_with_analytics_exports` · `GET /v1/ask_with_analytics_exports`

Ask a question and trigger a full analytics export pack (datasets + semantic packs).

- **Auth:** `admin`
- **Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | string | ✅ | — | Question (3–400 characters) |
| `fmt` | string | — | `"csv"` | Export format: `csv` \| `parquet` |

**`data` payload:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Agent's natural-language response |
| `analytics` | object | Export manifest — see [Analytics Export Guide](ANALYTICS_EXPORT_GUIDE.md) |

---

## MCP Tools

The MCP server (`mcp_server/server.py`) exposes 11 tools. See [Interaction Modes](INTERACTION_MODES.md)
for channel setup. Tools and their parameters:

| Tool | Key Parameters | Auth | Description |
|------|---------------|------|-------------|
| `list_tables` | — | — | List all tables and views in the database |
| `describe_table` | `table_name` | — | Column schema for an allowlisted object |
| `run_sql` | `query`, `limit=200` | — | Execute safe read-only SQL |
| `get_kpi_summary` | `period_filter=""`, `grain="month"` | — | KPI summary, optionally filtered |
| `create_sql_view` | `view_name`, `definition` | admin | Create or replace a SQL view |
| `generate_dashboard_spec` | `template_name="exec_overview"`, `filters_json="{}"` | — | Dashboard spec JSON |
| `generate_storyboard_spec` | `goal`, `audience="exec"`, `period="latest_quarter"` | — | Storyboard narrative spec JSON |
| `run_forecast` | `metric="net_revenue"`, `horizon=3` | — | Forecast with diagnostics |
| `run_anomaly_detection` | `metric="net_revenue"`, `threshold=2.0` | — | Z-score anomaly detection |
| `apply_standard_views` | — | — | Apply canonical SQL views from `sql/views.sql` |
| `export_specs` | `output_dir="specs"` | — | Write default dashboard + storyboard specs to disk |

**SQL allowlist** (objects queryable via `run_sql` and `describe_table`):

```
fact_sales  ·  dim_product  ·  dim_region
vw_monthly_sales  ·  vw_region_performance  ·  vw_product_margin_rank
```

Queries referencing any other table or view are rejected with a policy error.

---

*See also: [Operations Runbook](OPERATIONS_RUNBOOK.md) · [Channel Error Contracts](CHANNEL_ERROR_CONTRACTS.md) · [Interaction Modes](INTERACTION_MODES.md)*
