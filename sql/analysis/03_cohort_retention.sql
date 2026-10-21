-- Monthly signup cohorts: share of each cohort that placed a revenue order N months after signup.
-- Techniques: multiple CTEs, date arithmetic, join back to cohort size.
WITH cohorts AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', signup_date)::date AS cohort_month
    FROM marts.dim_customers
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS customers_in_cohort
    FROM cohorts
    GROUP BY cohort_month
),
activity AS (
    SELECT DISTINCT
        o.customer_id,
        c.cohort_month,
        (EXTRACT(YEAR  FROM AGE(DATE_TRUNC('month', o.order_date), c.cohort_month)) * 12
       + EXTRACT(MONTH FROM AGE(DATE_TRUNC('month', o.order_date), c.cohort_month)))::int AS months_since_signup
    FROM marts.fct_orders o
    JOIN cohorts c USING (customer_id)
    WHERE o.is_revenue_order
),
cohort_activity AS (
    SELECT cohort_month, months_since_signup, COUNT(DISTINCT customer_id) AS active_customers
    FROM activity
    GROUP BY 1, 2
)
SELECT
    a.cohort_month,
    s.customers_in_cohort,
    a.months_since_signup,
    a.active_customers,
    ROUND(100.0 * a.active_customers / s.customers_in_cohort, 1) AS retention_pct
FROM cohort_activity a
JOIN cohort_size s USING (cohort_month)
WHERE a.months_since_signup BETWEEN 0 AND 6
ORDER BY a.cohort_month, a.months_since_signup;
