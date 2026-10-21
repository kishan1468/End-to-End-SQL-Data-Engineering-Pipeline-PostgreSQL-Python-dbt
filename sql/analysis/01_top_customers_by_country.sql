-- Top 3 customers by lifetime revenue in every country.
-- Techniques: CTE, DENSE_RANK() window function with PARTITION BY.
WITH ranked AS (
    SELECT
        country,
        customer_id,
        full_name,
        lifetime_orders,
        lifetime_revenue,
        DENSE_RANK() OVER (
            PARTITION BY country
            ORDER BY lifetime_revenue DESC
        ) AS rank_in_country
    FROM marts.dim_customers
    WHERE lifetime_revenue > 0
)
SELECT *
FROM ranked
WHERE rank_in_country <= 3
ORDER BY country, rank_in_country;
