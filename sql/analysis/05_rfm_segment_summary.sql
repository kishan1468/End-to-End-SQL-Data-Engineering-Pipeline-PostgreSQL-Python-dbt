-- Size and value of every RFM segment.
-- Techniques: aggregation over a dbt mart, share-of-total with a window function.
SELECT
    segment,
    COUNT(*)                                        AS customers,
    ROUND(AVG(recency_days), 1)                     AS avg_recency_days,
    ROUND(AVG(frequency), 1)                        AS avg_orders,
    ROUND(SUM(monetary), 2)                         AS total_revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1) AS pct_of_revenue
FROM marts.customer_rfm
GROUP BY segment
ORDER BY total_revenue DESC;
