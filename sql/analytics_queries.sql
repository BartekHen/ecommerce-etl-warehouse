-- Example OLAP analytics queries (DQL - Data Query Language).
--
-- These show the kind of question the star schema is designed to answer
-- quickly. Every query only ever needs to JOIN fact_sales to one or two
-- dimension tables - no deep chains of joins like you would need on the
-- normalized OLTP source. Run them with the DuckDB CLI, e.g.:
--   duckdb warehouse.duckdb < sql/analytics_queries.sql
-- or paste one query at a time into a DuckDB / Python session.


-- 1. Revenue and margin per sales channel and month.
SELECT
    d.year,
    d.month,
    d.month_name,
    ch.name AS channel,
    SUM(f.net_amount) AS revenue,
    SUM(f.margin) AS margin
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_channel ch ON f.channel_key = ch.channel_key
GROUP BY d.year, d.month, d.month_name, ch.name
ORDER BY d.year, d.month, channel;


-- 2. Top 10 best-selling products by revenue.
SELECT
    p.name AS product_name,
    p.category,
    SUM(f.quantity) AS units_sold,
    SUM(f.net_amount) AS revenue
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.name, p.category
ORDER BY revenue DESC
LIMIT 10;


-- 3. Average order value (AOV) per country.
-- AOV = total revenue / number of distinct orders.
-- Here "order" is approximated by grouping on (customer_key, date_key)
-- since fact_sales is at the order_item grain.
SELECT
    c.country,
    ROUND(SUM(f.net_amount) / COUNT(DISTINCT (f.customer_key, f.date_key)), 2) AS avg_order_value
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.country
ORDER BY avg_order_value DESC;


-- 4. Quarterly revenue trend (all channels combined).
SELECT
    d.year,
    d.quarter,
    SUM(f.net_amount) AS revenue,
    SUM(f.margin) AS margin
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.quarter
ORDER BY d.year, d.quarter;


-- 5. Revenue and margin per product category.
SELECT
    p.category,
    SUM(f.net_amount) AS revenue,
    SUM(f.margin) AS margin,
    ROUND(100.0 * SUM(f.margin) / NULLIF(SUM(f.net_amount), 0), 1) AS margin_pct
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY revenue DESC;


-- 6. Top 5 customers by lifetime revenue.
SELECT
    c.name AS customer_name,
    c.country,
    SUM(f.net_amount) AS lifetime_revenue
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.name, c.country
ORDER BY lifetime_revenue DESC
LIMIT 5;
