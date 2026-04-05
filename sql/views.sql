DROP VIEW IF EXISTS vw_monthly_sales;
CREATE VIEW vw_monthly_sales AS
SELECT
    substr(order_date, 1, 7) AS period,
    SUM(net_revenue) AS net_revenue,
    SUM(margin) AS margin,
    SUM(units_sold) AS units_sold,
    CASE WHEN SUM(net_revenue)=0 THEN 0 ELSE SUM(margin)/SUM(net_revenue) END AS margin_pct
FROM fact_sales
GROUP BY 1
ORDER BY 1;

DROP VIEW IF EXISTS vw_region_performance;
CREATE VIEW vw_region_performance AS
SELECT
    r.region_name,
    r.country,
    r.sales_channel,
    SUM(f.net_revenue) AS net_revenue,
    SUM(f.margin) AS margin,
    SUM(f.units_sold) AS units_sold,
    CASE WHEN SUM(f.net_revenue)=0 THEN 0 ELSE SUM(f.margin)/SUM(f.net_revenue) END AS margin_pct
FROM fact_sales f
JOIN dim_region r ON r.region_id = f.region_id
GROUP BY r.region_name, r.country, r.sales_channel
ORDER BY net_revenue DESC;

DROP VIEW IF EXISTS vw_product_margin_rank;
CREATE VIEW vw_product_margin_rank AS
SELECT
    p.product_name,
    p.category,
    p.subcategory,
    SUM(f.net_revenue) AS net_revenue,
    SUM(f.margin) AS margin,
    SUM(f.units_sold) AS units_sold,
    CASE WHEN SUM(f.net_revenue)=0 THEN 0 ELSE SUM(f.margin)/SUM(f.net_revenue) END AS margin_pct
FROM fact_sales f
JOIN dim_product p ON p.product_id = f.product_id
GROUP BY p.product_name, p.category, p.subcategory
ORDER BY margin_pct DESC;
