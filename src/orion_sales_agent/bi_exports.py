from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .db import query_df


BI_DIR = Path("artifacts/bi_exports")
SPECS_DIR = Path("specs/bi")


def _ensure_dirs() -> None:
    BI_DIR.mkdir(parents=True, exist_ok=True)
    SPECS_DIR.mkdir(parents=True, exist_ok=True)


def export_canonical_datasets(fmt: str = "csv") -> dict[str, Any]:
    if fmt not in {"csv", "parquet"}:
        raise ValueError("fmt must be csv or parquet")

    _ensure_dirs()
    datasets = {
        "sales_monthly": "SELECT * FROM vw_monthly_sales ORDER BY period",
        "region_performance": "SELECT * FROM vw_region_performance ORDER BY net_revenue DESC",
        "product_margin": "SELECT * FROM vw_product_margin_rank ORDER BY margin_pct DESC",
        "forecast_output": "SELECT period, net_revenue, margin, units_sold FROM vw_monthly_sales ORDER BY period",
    }

    outputs: dict[str, str] = {}
    for name, sql in datasets.items():
        df = query_df(settings.db_path, sql)
        out = BI_DIR / f"{name}.{fmt}"
        if fmt == "csv":
            df.to_csv(out, index=False)
        else:
            df.to_parquet(out, index=False)
        outputs[name] = str(out).replace("\\", "/")
    return outputs


def build_semantic_packs() -> dict[str, str]:
    _ensure_dirs()

    kpi_dictionary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": [
            {"name": "net_revenue", "formula": "SUM(net_revenue)", "format": "currency"},
            {"name": "margin", "formula": "SUM(margin)", "format": "currency"},
            {"name": "margin_pct", "formula": "SUM(margin)/SUM(net_revenue)", "format": "percentage"},
            {"name": "asp", "formula": "SUM(net_revenue)/SUM(units_sold)", "format": "currency"},
        ],
    }
    relationship_map = {
        "entities": ["fact_sales", "dim_product", "dim_region"],
        "joins": [
            {"left": "fact_sales.product_id", "right": "dim_product.product_id", "type": "many_to_one"},
            {"left": "fact_sales.region_id", "right": "dim_region.region_id", "type": "many_to_one"},
        ],
        "grain": "transaction",
    }
    visual_mapping = {
        "net_revenue_trend": {"chart": "line", "dataset": "sales_monthly", "x": "period", "y": "net_revenue"},
        "region_comparison": {"chart": "bar", "dataset": "region_performance", "x": "region_name", "y": "net_revenue"},
        "margin_rank": {"chart": "bar", "dataset": "product_margin", "x": "product_name", "y": "margin_pct"},
    }
    powerbi_model_notes = {
        "measures": [
            "Net Revenue = SUM(fact_sales[net_revenue])",
            "Margin = SUM(fact_sales[margin])",
            "Margin % = DIVIDE([Margin],[Net Revenue])",
        ],
        "relationships": "Use relationship_map.json",
    }
    tableau_pack = {
        "recommended_data_sources": ["sales_monthly.csv", "region_performance.csv", "product_margin.csv"],
        "worksheet_templates": ["Revenue Trend", "Region Performance", "Product Margin Rank"],
    }
    oac_mapping = {
        "subject_areas": ["Sales Performance", "Regional Analysis", "Product Profitability"],
        "dataset_contracts": ["sales_monthly", "region_performance", "product_margin"],
    }

    files = {
        "kpi_dictionary.json": kpi_dictionary,
        "relationship_map.json": relationship_map,
        "visual_mapping.json": visual_mapping,
        "powerbi_model_notes.json": powerbi_model_notes,
        "tableau_workbook_template.json": tableau_pack,
        "oac_semantic_mapping.json": oac_mapping,
    }

    outputs: dict[str, str] = {}
    for name, content in files.items():
        out = SPECS_DIR / name
        out.write_text(json.dumps(content, indent=2), encoding="utf-8")
        outputs[name] = str(out).replace("\\", "/")
    return outputs


def export_bi_pack(fmt: str = "csv") -> dict[str, Any]:
    data_files = export_canonical_datasets(fmt=fmt)
    semantic_files = build_semantic_packs()
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "format": fmt,
        "datasets": data_files,
        "semantic_packs": semantic_files,
    }
    _ensure_dirs()
    manifest_path = BI_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest"] = str(manifest_path).replace("\\", "/")
    return manifest
