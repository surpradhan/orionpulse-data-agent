from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seed_orion_data import SeedConfig, build_dimensions, build_fact_sales  # noqa: E402

from src.orion_sales_agent.config import settings  # noqa: E402
from src.orion_sales_agent.db import execute_script, get_connection  # noqa: E402


def main() -> None:
    schema_path = Path("sql/schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")
    execute_script(settings.db_path, schema_sql)

    products_df, regions_df = build_dimensions()
    sales_df = build_fact_sales(products_df, regions_df, SeedConfig())

    with get_connection(settings.db_path) as conn:
        products_df.to_sql("dim_product", conn, if_exists="append", index=False)
        regions_df.to_sql("dim_region", conn, if_exists="append", index=False)
        sales_df.to_sql("fact_sales", conn, if_exists="append", index=False)
        conn.commit()

    print(f"Database initialized at: {settings.db_path}")
    print(f"dim_product rows: {len(products_df)}")
    print(f"dim_region rows: {len(regions_df)}")
    print(f"fact_sales rows: {len(sales_df)}")


if __name__ == "__main__":
    main()
