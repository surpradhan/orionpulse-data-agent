# Data Model & Relationships

## Tables

1. `dim_product(product_id)`
2. `dim_region(region_id)`
3. `fact_sales(sale_id, product_id, region_id, order_date, measures...)`

## Join rules

- `fact_sales.product_id = dim_product.product_id`
- `fact_sales.region_id = dim_region.region_id`

## Grain

- `fact_sales` is transaction-level (one row per generated order event).
- Time aggregation should use `substr(order_date, 1, 7)` for month grain.
