-- Which products make up the first 80% of revenue inside each category?
-- Techniques: SUM() OVER running total, share of partition total, CASE.
WITH product_rev AS (
    SELECT category, product_id, product_name, revenue
    FROM marts.dim_products
    WHERE revenue > 0
),
running AS (
    SELECT
        *,
        SUM(revenue) OVER (PARTITION BY category ORDER BY revenue DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / SUM(revenue) OVER (PARTITION BY category) AS cumulative_share
    FROM product_rev
)
SELECT
    category,
    product_name,
    revenue,
    ROUND(100 * cumulative_share, 1) AS cumulative_share_pct,
    CASE WHEN cumulative_share <= 0.8 THEN 'core (top 80%)' ELSE 'long tail' END AS bucket
FROM running
ORDER BY category, revenue DESC;
