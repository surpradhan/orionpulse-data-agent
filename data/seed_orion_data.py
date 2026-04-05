from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class SeedConfig:
    start_month: str = "2023-01-01"
    end_month: str = "2025-12-01"
    seed: int = 42


def build_dimensions() -> tuple[pd.DataFrame, pd.DataFrame]:
    products = pd.DataFrame(
        [
            (1, "Cloud Basic", "Cloud", "SMB", "2021-06-01", 120.0),
            (2, "Cloud Pro", "Cloud", "Mid-Market", "2021-09-01", 260.0),
            (3, "Cloud Enterprise", "Cloud", "Enterprise", "2022-03-01", 540.0),
            (4, "Security Suite", "Security", "Enterprise", "2021-11-01", 430.0),
            (5, "Data Integrator", "Data", "Mid-Market", "2022-05-01", 310.0),
            (6, "Insight AI", "Analytics", "Enterprise", "2023-02-01", 620.0),
        ],
        columns=[
            "product_id",
            "product_name",
            "category",
            "subcategory",
            "launch_date",
            "base_price",
        ],
    )

    regions = pd.DataFrame(
        [
            (1, "NA", "USA", "Direct"),
            (2, "EMEA", "Germany", "Partner"),
            (3, "APAC", "India", "Direct"),
            (4, "LATAM", "Brazil", "Partner"),
        ],
        columns=["region_id", "region_name", "country", "sales_channel"],
    )
    return products, regions


def build_fact_sales(
    products: pd.DataFrame, regions: pd.DataFrame, cfg: SeedConfig
) -> pd.DataFrame:
    random.seed(cfg.seed)
    months = pd.date_range(cfg.start_month, cfg.end_month, freq="MS")
    rows: list[tuple] = []
    sale_id = 1

    for m in months:
        seasonality = 1.15 if m.month in (10, 11, 12) else (0.92 if m.month in (6, 7) else 1.0)
        trend = 1.0 + (m.year - 2023) * 0.07
        for _, p in products.iterrows():
            for _, r in regions.iterrows():
                base_units = random.randint(40, 180)
                units = max(10, int(base_units * seasonality * trend * random.uniform(0.85, 1.2)))
                gross = units * float(p.base_price) * random.uniform(0.95, 1.08)
                discount = gross * random.uniform(0.04, 0.18)
                net = gross - discount
                cogs = net * random.uniform(0.52, 0.76)
                margin = net - cogs
                order_day = random.randint(1, 27)
                order_date = date(m.year, m.month, order_day).isoformat()
                rows.append(
                    (
                        sale_id,
                        order_date,
                        int(p.product_id),
                        int(r.region_id),
                        units,
                        round(gross, 2),
                        round(discount, 2),
                        round(net, 2),
                        round(cogs, 2),
                        round(margin, 2),
                    )
                )
                sale_id += 1

    return pd.DataFrame(
        rows,
        columns=[
            "sale_id",
            "order_date",
            "product_id",
            "region_id",
            "units_sold",
            "gross_revenue",
            "discount_amount",
            "net_revenue",
            "cogs",
            "margin",
        ],
    )
