PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_product_margin_rank;
DROP VIEW IF EXISTS vw_region_performance;
DROP VIEW IF EXISTS vw_monthly_sales;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_region;

CREATE TABLE dim_product (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    launch_date TEXT NOT NULL,
    base_price REAL NOT NULL CHECK (base_price >= 0),
    CHECK (length(launch_date) = 10)
);

CREATE TABLE dim_region (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL,
    country TEXT NOT NULL,
    sales_channel TEXT NOT NULL
);

CREATE TABLE fact_sales (
    sale_id INTEGER PRIMARY KEY,
    order_date TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    units_sold INTEGER NOT NULL CHECK (units_sold >= 0),
    gross_revenue REAL NOT NULL CHECK (gross_revenue >= 0),
    discount_amount REAL NOT NULL CHECK (discount_amount >= 0),
    net_revenue REAL NOT NULL CHECK (net_revenue >= 0),
    cogs REAL NOT NULL CHECK (cogs >= 0),
    margin REAL NOT NULL,
    CHECK (length(order_date) = 10),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
);

CREATE INDEX idx_fact_sales_order_date ON fact_sales(order_date);
CREATE INDEX idx_fact_sales_product_id ON fact_sales(product_id);
CREATE INDEX idx_fact_sales_region_id ON fact_sales(region_id);
CREATE INDEX idx_fact_sales_order_prod_region ON fact_sales(order_date, product_id, region_id);

-- ── Analytical views ──────────────────────────────────────────────────────────

CREATE VIEW vw_monthly_sales AS
SELECT
    substr(order_date, 1, 7)                                          AS period,
    SUM(net_revenue)                                                   AS net_revenue,
    SUM(margin)                                                        AS margin,
    SUM(units_sold)                                                    AS units_sold,
    CASE WHEN SUM(units_sold) = 0 THEN 0
         ELSE SUM(net_revenue) / SUM(units_sold) END                  AS asp,
    CASE WHEN SUM(net_revenue) = 0 THEN 0
         ELSE SUM(margin) / SUM(net_revenue) END                      AS margin_pct
FROM fact_sales
GROUP BY 1;

CREATE VIEW vw_region_performance AS
SELECT
    r.region_name,
    r.country,
    r.sales_channel,
    SUM(f.net_revenue)                                                 AS net_revenue,
    SUM(f.margin)                                                      AS margin,
    SUM(f.units_sold)                                                  AS units_sold,
    CASE WHEN SUM(f.net_revenue) = 0 THEN 0
         ELSE SUM(f.margin) / SUM(f.net_revenue) END                  AS margin_pct
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
GROUP BY r.region_id, r.region_name, r.country, r.sales_channel;

CREATE VIEW vw_product_margin_rank AS
SELECT
    p.product_name,
    p.category,
    p.subcategory,
    SUM(f.net_revenue)                                                 AS net_revenue,
    SUM(f.margin)                                                      AS margin,
    SUM(f.units_sold)                                                  AS units_sold,
    CASE WHEN SUM(f.net_revenue) = 0 THEN 0
         ELSE SUM(f.margin) / SUM(f.net_revenue) END                  AS margin_pct
FROM fact_sales f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category, p.subcategory;
