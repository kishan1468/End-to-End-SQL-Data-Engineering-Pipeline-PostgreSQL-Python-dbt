-- Monthly revenue with month-over-month and year-over-year growth.
-- Techniques: DATE_TRUNC aggregation, LAG() window function.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', order_date)::date AS month,
        COUNT(*)                              AS orders,
        SUM(order_total)                      AS revenue
    FROM marts.fct_orders
    WHERE is_revenue_order
    GROUP BY 1
)
SELECT
    month,
    orders,
    revenue,
    ROUND(100.0 * (revenue - LAG(revenue, 1)  OVER w) / NULLIF(LAG(revenue, 1)  OVER w, 0), 1) AS mom_growth_pct,
    ROUND(100.0 * (revenue - LAG(revenue, 12) OVER w) / NULLIF(LAG(revenue, 12) OVER w, 0), 1) AS yoy_growth_pct
FROM monthly
WINDOW w AS (ORDER BY month)
ORDER BY month;
