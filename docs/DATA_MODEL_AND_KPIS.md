# Data Model and KPI Reference

## Tables

- `dim_product(product_id, product_name, category, subcategory, launch_date, base_price)`
- `dim_region(region_id, region_name, country, sales_channel)`
- `fact_sales(sale_id, order_date, product_id, region_id, units_sold, gross_revenue, discount_amount, net_revenue, cogs, margin)`

## Relationships

- `fact_sales.product_id -> dim_product.product_id`
- `fact_sales.region_id -> dim_region.region_id`

## Core KPIs

- Net Revenue = `SUM(net_revenue)`
- Margin = `SUM(margin)`
- Margin % = `SUM(margin) / SUM(net_revenue)`
- ASP = `SUM(net_revenue) / SUM(units_sold)`
- Discount Rate = `SUM(discount_amount) / SUM(gross_revenue)`
