-- Payment-method mix per country with average order value.
-- Techniques: GROUP BY, window share per partition.
SELECT
    country,
    payment_method,
    COUNT(*)                                      AS payments,
    ROUND(AVG(paid_amount), 2)                    AS avg_order_value,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY country), 1) AS pct_of_country_payments
FROM marts.fct_orders
WHERE paid_amount IS NOT NULL
GROUP BY country, payment_method
ORDER BY country, payments DESC;
