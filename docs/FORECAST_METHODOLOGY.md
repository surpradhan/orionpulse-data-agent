# Forecast Methodology — OrionPulse Data Agent

This document explains how the agent selects, trains, and evaluates forecast models,
and how to interpret the diagnostics returned by `/forecast` and the `run_forecast` MCP tool.

---

## Supported Metrics

| Metric | Description |
|--------|-------------|
| `net_revenue` | Monthly net revenue (default) |
| `margin` | Monthly gross margin |
| `units_sold` | Monthly units sold |

---

## Data Preparation

1. Sales data is aggregated to **monthly grain** (`YYYY-MM`) from `fact_sales`.
2. Months with `NULL` period or value are dropped.
3. A minimum of **8 historical months** is required; fewer returns a warning payload
   with no forecast.

---

## Candidate Models

Two model families are evaluated automatically on every request:

### 1. Holt-Linear (`holt_linear_v1`)

**Statsmodels:** `ExponentialSmoothing(trend="add", seasonal=None)`

- Captures level + linear trend.
- Always a candidate regardless of series length.
- Suitable for series with trend but no strong recurring seasonality.

### 2. Holt-Winters Additive (`holt_winters_v1`)

**Statsmodels:** `ExponentialSmoothing(trend="add", seasonal="add", seasonal_periods=12)`

- Captures level + trend + additive annual seasonality.
- **Only evaluated when training data ≥ 24 months** (two full seasonal cycles required
  for stable parameter estimation).
- Preferred when monthly seasonality is detected in the data.

---

## Model Selection (Holdout RMSE)

Method selection uses a **time-series holdout backtest**:

```
Full series:  [──────── train ────────] [── test ──]
                n - backtest_points       backtest_points
```

1. `backtest_points = min(3, n // 4)`, floored so training segment has ≥ 6 points.
2. Each candidate is fit on `train`, then forecasts `len(test)` steps ahead.
3. RMSE is computed between the forecast and actual `test` values.
4. The candidate with the **lowest RMSE** is selected for the final forecast.

If only one candidate qualifies (< 24 months of data), Holt-Linear wins by default.

---

## Confidence Intervals

After selecting the best model, it is re-fit on the **full series** and used to
generate `horizon` future periods.

**Interval construction:**

```
spread = 1.96 × residual_std × √steps
```

- `residual_std` — standard deviation of in-sample model residuals.
- `steps` — forecast step index (1, 2, 3, … horizon), widening the band over time.
- **Fallback** (when `residual_std = 0`): `spread = max(|forecast_value| × 0.05, 1.0)`.
  This is a heuristic interval — not a statistical one — and is flagged in
  `diagnostics.interval_method`.

| `interval_method` value | Meaning |
|-------------------------|---------|
| `approx_95pct_from_residual_std` | Standard residual-based CI (preferred) |
| `heuristic_5pct_fallback` | 5% of forecast value; model had zero residuals |

---

## Reading the Diagnostics Object

Every forecast response includes a `diagnostics` block:

```json
{
  "method": "holt_linear_v1",
  "train_points": 21,
  "backtest_points": 3,
  "mape": 4.7,
  "smape": 4.5,
  "rmse": 12340.0,
  "residual_std": 8200.0,
  "interval_method": "approx_95pct_from_residual_std",
  "warnings": [],
  "candidates": [
    { "method": "holt_linear_v1", "train_points": 21, "backtest_points": 3, "rmse": 12340.0 },
    { "method": "holt_winters_v1", "train_points": 21, "backtest_points": 3, "rmse": null, "error": "..." }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `method` | string | Model selected for the final forecast |
| `train_points` | int | Number of months used for training |
| `backtest_points` | int | Number of months held out for evaluation |
| `mape` | float\|null | Mean Absolute Percentage Error on the backtest window (%) |
| `smape` | float\|null | Symmetric MAPE on the backtest window (%) |
| `rmse` | float\|null | Root Mean Squared Error on the backtest window |
| `residual_std` | float | Std of in-sample residuals (used for CI width) |
| `interval_method` | string | How confidence bands were computed |
| `warnings` | array | Non-fatal issues (e.g. short training window) |
| `candidates` | array | All evaluated models with their backtest RMSE |

### Interpreting MAPE / sMAPE

| MAPE | Rough interpretation |
|------|---------------------|
| < 5% | Excellent |
| 5–10% | Good |
| 10–20% | Acceptable |
| > 20% | Poor — treat forecast with caution |

sMAPE is provided as a complement to MAPE; it is less sensitive to near-zero actuals.
Prefer sMAPE when revenue or margin contains months close to zero.

### Warnings

Common warnings and their meaning:

| Warning | Meaning |
|---------|---------|
| `Insufficient history: need at least 8 periods` | Series too short; no forecast generated |
| `Insufficient series length for diagnostics` | Series < 8 points; diagnostics skipped |
| `Training segment too short for robust backtest` | Training < 6 points after holdout split |
| `Backtest model failed for all candidate methods` | Model fitting error; check data quality |
| `Backtest window resolved to zero; metrics unavailable` | Edge case; diagnostics unavailable |

---

## Configuring the Forecast

| Setting | Default | How to change |
|---------|---------|---------------|
| Forecast horizon | 3 months | `ORION_DEFAULT_FORECAST_HORIZON` env var, or `horizon` param on MCP tool |
| Metric | `net_revenue` | `metric` param (`net_revenue` \| `margin` \| `units_sold`) |
| Minimum history | 8 periods | Hard-coded; determined by backtest requirements |

---

## Limitations & Known Constraints

1. **Monthly grain only.** Daily or weekly granularity is not currently supported.
2. **Additive seasonality only.** Multiplicative seasonality (common in fast-growing
   series) is not modelled.
3. **No external regressors.** The model uses only the historical metric series;
   promotions, seasonality events, or macroeconomic inputs are not incorporated.
4. **Short series.** With 8–12 months of data, Holt-Linear is the only candidate
   and confidence intervals will be wide.
5. **Confidence bands are approximate.** The interval formula is a heuristic based
   on residual spread, not a formal Bayesian posterior.

---

## Planned Improvements (v2)

- ARIMA / SARIMA as a third candidate model
- Configurable evaluation metric (RMSE vs sMAPE)
- Multiplicative seasonality option for faster-growing series
- Forecast accuracy tracking against actuals over time

---

*See also: [Analytics Export Guide](ANALYTICS_EXPORT_GUIDE.md) · [API Reference](API_REFERENCE.md)*
