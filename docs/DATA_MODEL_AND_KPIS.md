# Data Model and KPI Reference

## Tables

- `dim_product(product_id, product_name, category, subcategory, launch_date, base_price)`
- `dim_region(region_id, region_name, country, sales_channel)`
- `fact_sales(sale_id, order_date, product_id, region_id, units_sold, gross_revenue, discount_amount, net_revenue, cogs, margin)`

## Relationships

- `fact_sales.product_id -> dim_product.product_id`
- `fact_sales.region_id -> dim_region.region_id`

## Analytical Views

Views are defined in `sql/views.sql` and applied via `src/orion_sales_agent/views.py:apply_views()`. They are also created by `data/init_db.py` through `sql/schema.sql`.

| View | Columns | Purpose |
|------|---------|---------|
| `vw_monthly_sales` | `period, net_revenue, margin, units_sold, asp, margin_pct` | Monthly KPI time series |
| `vw_region_performance` | `region_name, country, sales_channel, net_revenue, margin, units_sold, margin_pct` | Region leaderboard with channel context |
| `vw_product_margin_rank` | `product_name, category, subcategory, net_revenue, margin, units_sold, margin_pct` | Product ranking by margin rate |

The `country` and `sales_channel` columns in `vw_region_performance` come from `dim_region`. The `subcategory` column in `vw_product_margin_rank` comes from `dim_product`.

## Core KPIs

- Net Revenue = `SUM(net_revenue)`
- Margin = `SUM(margin)`
- Margin % = `SUM(margin) / SUM(net_revenue)`
- ASP = `SUM(net_revenue) / SUM(units_sold)`
- Discount Rate = `SUM(discount_amount) / SUM(gross_revenue)`
