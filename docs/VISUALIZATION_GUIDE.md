# Visualization Guide — OrionPulse Data Agent

The agent can generate charts alongside any analytical answer.
Charts are produced by `src/orion_sales_agent/visualization.py` using
**matplotlib** and **seaborn**, and saved to `artifacts/charts/`.

---

## How to Request Charts

### Web API

Use `/ask_with_visuals` (or `POST /chat` with `"with_visuals": true`):

```bash
# GET endpoint
curl "http://localhost:8000/ask_with_visuals?q=Show+me+the+revenue+trend&fmt=png" \
  -H "X-Orion-Token: <analyst-token>"

# POST /chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Orion-Token: <analyst-token>" \
  -d '{"q": "Show me the revenue trend", "with_visuals": true, "fmt": "svg"}'
```

### MCP

Charts are not directly generated via MCP tools. Use the web endpoints above, or
call `visualization.generate_insight_pack()` programmatically.

### Chat UI

The browser UI at `http://localhost:8000` includes a **"Show charts"** toggle that
sets `with_visuals=true` automatically.

---

## Chart Types

The agent produces up to four chart types per request, depending on which analytics
are relevant to the question.

### 1. `kpi_trend` — Monthly KPI Trend

A line chart showing `net_revenue`, `margin`, and/or `units_sold` over time.

- **Data source:** `vw_monthly_sales`
- **X axis:** Month (`YYYY-MM`)
- **Y axis:** Currency (revenue/margin) or count (units)
- **When generated:** Questions about trends, revenue over time, growth

**Example filename:** `artifacts/charts/kpi_trend.png`

---

### 2. `region_performance` — Regional Performance Bar Chart

A horizontal bar chart comparing regions by `net_revenue` or `margin_pct`.

- **Data source:** `vw_region_performance`
- **X axis:** Metric value
- **Y axis:** Region name
- **When generated:** Questions about regional breakdown, best/worst performing regions

**Example filename:** `artifacts/charts/region_performance.png`

---

### 3. `forecast_band` — Forecast with Confidence Band

A line chart showing historical values plus forecast points with upper/lower
confidence bounds shaded.

- **Data source:** `analytics.forecast_metric()` output
- **Solid line:** Historical actuals (last 12 periods)
- **Dashed line + shaded band:** Forecast + approximate 95% confidence interval
- **When generated:** Questions about future revenue, forecasting, predictions

**Example filename:** `artifacts/charts/forecast_band.png`

> The shaded band is an approximate 95% CI derived from residual standard deviation.
> See [Forecast Methodology](FORECAST_METHODOLOGY.md) for details.

---

### 4. `anomaly_timeline` — Anomaly Timeline

A scatter-over-line chart marking anomalous periods with a distinct marker.

- **Data source:** `analytics.anomaly_detection()` output
- **Line:** Full monthly series
- **Markers:** Periods flagged as anomalies (|z-score| ≥ threshold)
- **When generated:** Questions about outliers, unusual periods, anomaly detection

**Example filename:** `artifacts/charts/anomaly_timeline.png`

---

## Output Format

| Format | Flag | Notes |
|--------|------|-------|
| PNG | `fmt=png` (default) | Raster, suitable for web display and reports |
| SVG | `fmt=svg` | Vector, suitable for high-resolution print and BI tools |

---

## Artifact Layout

All chart files are written under `artifacts/charts/` relative to the project root.
The directory is created automatically at startup.

```
artifacts/
└── charts/
    ├── kpi_trend.png
    ├── region_performance.png
    ├── forecast_band.png
    ├── anomaly_timeline.png
    └── manifest.json          ← chart registry (updated on each generation)
```

**`manifest.json`** tracks every chart generated in the current session:

```json
{
  "generated_at": "2026-03-29T12:00:00Z",
  "charts": [
    {
      "chart_type": "kpi_trend",
      "path": "artifacts/charts/kpi_trend.png",
      "url": "/artifacts/charts/kpi_trend.png",
      "fmt": "png"
    }
  ]
}
```

Charts are served as static files at `/artifacts/charts/<filename>`.

---

## Programmatic Usage

```python
from orion_sales_agent.visualization import generate_insight_pack

# Generate all applicable charts for an analytical context
charts = generate_insight_pack(
    db_path="data/orion_sales_agent.db",
    fmt="png",           # "png" or "svg"
    output_dir="artifacts/charts",
)
# Returns list of chart metadata dicts (chart_type, path, url, fmt)
```

Individual chart functions:

```python
from orion_sales_agent.visualization import (
    plot_kpi_trend,
    plot_region_performance,
    plot_forecast_with_band,
    plot_anomaly_timeline,
)
```

---

## Configuration

Charts are enabled at the request level (no global toggle). No additional environment
variables are required beyond `ORION_DB_PATH`.

Voice + chart combined mode is supported: the HTML UI reads chart URLs from the
response and renders them inline alongside the TTS audio response.

---

*See also: [API Reference](API_REFERENCE.md) · [Analytics Export Guide](ANALYTICS_EXPORT_GUIDE.md)*
