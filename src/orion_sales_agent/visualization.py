from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

from .analytics import anomaly_detection, forecast_metric, kpi_summary
from .config import settings
from .db import query_df

CHART_DIR = Path("artifacts/charts")
MANIFEST = CHART_DIR / "manifest.json"


def set_test_safe_matplotlib_backend() -> None:
    backend = matplotlib.get_backend().lower()
    if backend != "agg":
        matplotlib.use("Agg", force=True)


def _safe_slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_") or "chart"


def _init_chart_dir() -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)


def _register_chart(meta: dict[str, Any]) -> None:
    _init_chart_dir()
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            manifest = []
    else:
        manifest = []
    manifest.append(meta)
    MANIFEST.write_text(json.dumps(manifest[-200:], indent=2), encoding="utf-8")


def _save_plot(fig, base_name: str, fmt: str = "png") -> str:
    _init_chart_dir()
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    file_name = f"{_safe_slug(base_name)}_{ts}.{fmt}"
    out = CHART_DIR / file_name
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return str(out).replace("\\", "/")


def plot_kpi_trend(fmt: str = "png") -> dict[str, Any]:
    rows = kpi_summary(settings.db_path, grain="month")
    if not rows:
        return {"status": "empty", "reason": "No KPI rows available"}
    periods = [r["period"] for r in rows]
    values = [r["net_revenue"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.lineplot(x=periods, y=values, marker="o", ax=ax)
    ax.set_title("Net Revenue Trend (Monthly)")
    ax.set_xlabel("Period")
    ax.set_ylabel("Net Revenue")
    ax.tick_params(axis="x", rotation=45)
    path = _save_plot(fig, "kpi_trend", fmt)
    meta = {"chart_type": "kpi_trend", "path": path, "points": len(rows), "format": fmt}
    _register_chart(meta)
    return meta


def plot_region_performance(fmt: str = "png") -> dict[str, Any]:
    df = query_df(
        settings.db_path,
        "SELECT region_name, net_revenue FROM vw_region_performance ORDER BY net_revenue DESC",
    )
    if df.empty:
        return {"status": "empty", "reason": "No region performance rows available"}
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=df, x="region_name", y="net_revenue", ax=ax)
    ax.set_title("Region Performance by Net Revenue")
    ax.set_xlabel("Region")
    ax.set_ylabel("Net Revenue")
    path = _save_plot(fig, "region_performance", fmt)
    meta = {"chart_type": "region_performance", "path": path, "points": int(len(df)), "format": fmt}
    _register_chart(meta)
    return meta


def plot_forecast_with_band(
    metric: str = "net_revenue", horizon: int = 3, fmt: str = "png"
) -> dict[str, Any]:
    fc = forecast_metric(settings.db_path, metric=metric, horizon=horizon)
    history = fc.get("history", [])
    pred = fc.get("forecast", [])
    if not history or not pred:
        return {"status": "empty", "reason": fc.get("warning", "No forecast data available")}

    x_hist = [r["period"] for r in history]
    y_hist = [r["value"] for r in history]
    x_pred = [r["period"] for r in pred]
    y_pred = [r["value"] for r in pred]
    lower = [r.get("lower", r["value"] * 0.95) for r in pred]
    upper = [r.get("upper", r["value"] * 1.05) for r in pred]

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.lineplot(x=x_hist, y=y_hist, marker="o", label="History", ax=ax)
    sns.lineplot(x=x_pred, y=y_pred, marker="o", label="Forecast", ax=ax)
    ax.fill_between(
        range(len(x_hist), len(x_hist) + len(x_pred)), lower, upper, alpha=0.2,
        label="Confidence Band",
    )
    all_x = x_hist + x_pred
    ax.set_xticks(range(len(all_x)))
    ax.set_xticklabels(all_x, rotation=45)
    ax.set_title(f"Forecast: {metric}")
    ax.set_xlabel("Period")
    ax.set_ylabel(metric)
    ax.legend()

    path = _save_plot(fig, f"forecast_{metric}", fmt)
    meta = {
        "chart_type": "forecast_with_band", "path": path, "points": len(all_x), "format": fmt
    }
    _register_chart(meta)
    return meta


def plot_anomaly_timeline(
    metric: str = "net_revenue", threshold: float = 2.0, fmt: str = "png"
) -> dict[str, Any]:
    base = query_df(
        settings.db_path,
        f"SELECT substr(order_date,1,7) AS period, SUM({metric}) AS value"
        " FROM fact_sales GROUP BY 1 ORDER BY 1",
    )
    anomalies = anomaly_detection(settings.db_path, metric=metric, threshold=threshold)
    if base.empty:
        return {"status": "empty", "reason": "No base series for anomaly timeline"}

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.lineplot(data=base, x="period", y="value", marker="o", ax=ax)
    if anomalies:
        ax.scatter(
            [a["period"] for a in anomalies],
            [a["value"] for a in anomalies],
            color="red",
            label="Anomaly",
        )
    ax.set_title(f"Anomaly Timeline ({metric})")
    ax.set_xlabel("Period")
    ax.set_ylabel(metric)
    ax.tick_params(axis="x", rotation=45)
    if anomalies:
        ax.legend()
    path = _save_plot(fig, f"anomaly_{metric}", fmt)
    meta = {
        "chart_type": "anomaly_timeline",
        "path": path,
        "anomaly_count": len(anomalies),
        "format": fmt,
    }
    _register_chart(meta)
    return meta


def generate_chart(
    chart_type: str,
    metric: str = "net_revenue",
    horizon: int = 3,
    threshold: float = 2.0,
    fmt: str = "png",
) -> dict[str, Any]:
    if fmt not in {"png", "svg"}:
        raise ValueError("fmt must be png or svg")
    if chart_type == "kpi_trend":
        return plot_kpi_trend(fmt=fmt)
    if chart_type == "region_performance":
        return plot_region_performance(fmt=fmt)
    if chart_type == "forecast_with_band":
        return plot_forecast_with_band(metric=metric, horizon=horizon, fmt=fmt)
    if chart_type == "anomaly_timeline":
        return plot_anomaly_timeline(metric=metric, threshold=threshold, fmt=fmt)
    raise ValueError("Unsupported chart_type")


def generate_insight_pack(question: str, fmt: str = "png") -> dict[str, Any]:
    q = question.lower()
    visuals: list[dict[str, Any]] = []
    visuals.append(plot_kpi_trend(fmt=fmt))
    visuals.append(plot_region_performance(fmt=fmt))
    if "forecast" in q or "predict" in q:
        visuals.append(plot_forecast_with_band(fmt=fmt))
    if "anomaly" in q or "drop" in q or "spike" in q:
        visuals.append(plot_anomaly_timeline(fmt=fmt))
    return {
        "question": question,
        "visuals": visuals,
        "manifest": str(MANIFEST).replace("\\", "/"),
    }
