# Prompt Templates — OrionPulse Data Agent

Reusable prompt patterns for consistent, high-quality agent responses.
Use these as starting points — fill in the `{placeholders}` for your context.

> **Channel note:** These templates work across all interaction channels (Web UI, CLI, MCP chat).
> For the Web API, pass the filled prompt as the `q` field in `/chat` or `/ask`.

---

## 1. KPI Summary

**Goal:** Summarize performance for a given region and period.

**Template:**
```
Summarize {region} sales performance for {period}.
Include net revenue, margin %, units sold, and ASP.
Flag any metrics that are significantly above or below the prior period.
```

**Filled example — EMEA Q1 review:**
```
Summarize EMEA sales performance for 2025-Q1.
Include net revenue, margin %, units sold, and ASP.
Flag any metrics that are significantly above or below the prior period.
```

**Expected output shape:**
- KPI table: net revenue, margin %, units sold, ASP with period-over-period delta
- 2–3 sentence interpretation of the overall trend
- Bulleted risks or highlights (e.g. "Margin % dropped 4 pp — driven by higher COGS in Electronics")

**Variations:**
```
# Company-wide summary
Summarize company-wide sales performance for 2025-Q4.
Include net revenue, margin %, units sold, and ASP.
Highlight any categories or regions that are outliers.

# Category drill-down
Summarize Electronics category performance for 2025-H1.
Include net revenue by region, margin %, and month-over-month trend.
```

---

## 2. Root Cause Analysis

**Goal:** Diagnose a decline (or spike) in a specific metric.

**Template:**
```
Why did {metric} {decline/increase} in {region/category} during {period}?
Identify the top 2–3 drivers, show supporting evidence, and suggest corrective actions.
```

**Filled example — margin drop in APAC:**
```
Why did margin % decline in APAC during 2025-Q3?
Identify the top 2–3 drivers, show supporting evidence, and suggest corrective actions.
```

**Expected output shape:**
- Root cause #1, #2, #3 with evidence (e.g. revenue vs COGS data, product mix shift)
- Recommended actions per driver
- Confidence level or data caveats if relevant

**Variations:**
```
# Revenue spike investigation
Why did net revenue spike in North America in 2025-11?
Was it driven by volume, pricing, or mix? Show the breakdown.

# Cross-region comparison
Why is margin % lower in Online channel vs Retail for the same product category?
Show the data and explain the structural drivers.

# Product-level drill-down
Why are margins for Accessories declining while Electronics margins are stable?
Compare COGS and ASP trends for both categories over the last 6 months.
```

---

## 3. Forecast

**Goal:** Generate a forward-looking forecast for a metric with uncertainty context.

**Template:**
```
Forecast {metric} for the next {n} months.
Show the forecast values, confidence bands, and the key assumptions behind the model.
Flag any warnings about data quality or model fit.
```

**Filled example — 6-month revenue forecast:**
```
Forecast net revenue for the next 6 months.
Show the forecast values, confidence bands, and the key assumptions behind the model.
Flag any warnings about data quality or model fit.
```

**Expected output shape:**
- Table or list of forecast periods with point estimate, lower bound, upper bound
- Model assumptions (e.g. "Holt-Winters additive seasonality applied")
- Diagnostics summary: MAPE, sMAPE, and backtest period count
- Warnings if insufficient history or wide confidence bands

**Variations:**
```
# Margin forecast
Forecast gross margin for the next 3 months.
Include confidence intervals and note any seasonality patterns the model has detected.

# Units forecast with anomaly context
Forecast units sold for the next 4 months for the Electronics category.
Also flag any anomalous months in the historical series that may affect the forecast.

# Short-term with explicit horizon
What is the expected net revenue for 2026-Q2?
Provide point estimate and uncertainty range.
```

---

## 4. Anomaly Detection

**Goal:** Identify unusual periods in a metric series and explain them.

**Template:**
```
Identify any anomalous months in {metric} over the full history.
Use a z-score threshold of {threshold} and explain what likely caused each anomaly.
```

**Filled example — revenue anomalies:**
```
Identify any anomalous months in net revenue over the full history.
Use a z-score threshold of 2.0 and explain what likely caused each anomaly.
```

**Expected output shape:**
- List of flagged periods with metric value, z-score, and direction (above/below mean)
- Brief hypothesis for each anomaly
- Recommendation: investigate further, accept as seasonal, or treat as data error

**Variations:**
```
# Stricter threshold
Are there any extreme outliers in margin over the past 2 years?
Use a z-score threshold of 2.5.

# Combine with forecast
Are there anomalous months in net revenue that might distort the next forecast?
Flag them and explain how they affect model reliability.
```

---

## 5. Regional Comparison

**Goal:** Compare performance across regions or sales channels.

**Template:**
```
Compare {metric} across all regions for {period}.
Rank regions from best to worst and explain the top gap driver between #1 and #2.
```

**Filled example — Q4 revenue ranking:**
```
Compare net revenue across all regions for 2025-Q4.
Rank regions from best to worst and explain the top gap driver between #1 and #2.
```

**Expected output shape:**
- Ranked table of regions with metric value and share of total
- Gap analysis between top two performers
- One action recommendation per underperforming region

**Variations:**
```
# Channel comparison
Compare margin % between Online and Retail channels for 2025.
What explains the difference? Is it pricing, volume, or product mix?

# Multi-metric regional view
For EMEA in 2025-H2, show net revenue, margin %, and units sold side by side.
Flag any region where margin % is below 20%.
```

---

## 6. Analytics Export + BI Handoff

**Goal:** Generate a structured export pack for downstream BI consumption.

**Template:**
```
Prepare an analytics export for {purpose}.
Include monthly sales trends, regional performance, and product margin rankings.
Export format: {csv/parquet}.
```

**Filled example — board reporting pack:**
```
Prepare an analytics export for the Q1 2026 board reporting pack.
Include monthly sales trends, regional performance, and product margin rankings.
Export format: csv.
```

> **Note:** This prompt requires admin-role access (`/ask_with_analytics_exports` endpoint or
> admin token). See [API Reference](API_REFERENCE.md) for auth details.

**Expected output shape:**
- Confirmation of exported dataset files (paths)
- Semantic pack files generated (KPI dictionary, relationship map, BI platform stubs)
- Manifest JSON path for downstream pipeline ingestion

---

## Tips for Best Results

| Goal | Tip |
|------|-----|
| More precise answers | Specify `region`, `period`, and `metric` explicitly rather than asking broadly |
| Faster responses | Use `deterministic` mode (`ORION_CLI_DEFAULT_MODE=deterministic`) for KPI/forecast questions |
| Richer narrative | Use `llm` or `auto` mode for root cause and comparison questions |
| Charts with answers | Append `"with_visuals": true` in the `/chat` payload or use `/ask_with_visuals` |
| Reproducibility | Save the `trace_id` from the response envelope to re-examine agent reasoning in trace files |
