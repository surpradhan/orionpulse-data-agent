PRAGMA foreign_keys = ON;

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
