-- Customer dimension enriched with lifetime metrics and a revenue quartile.
with customers as (

    select * from {{ ref('stg_customers') }}

),

order_stats as (

    select
        customer_id,
        count(*)         filter (where is_revenue_order) as lifetime_orders,
        sum(order_total) filter (where is_revenue_order) as lifetime_revenue,
        min(order_date)                                  as first_order_date,
        max(order_date)                                  as last_order_date
    from {{ ref('fct_orders') }}
    group by customer_id

)

select
    c.customer_id,
    c.full_name,
    c.email,
    c.country,
    c.signup_date,
    coalesce(s.lifetime_orders, 0)  as lifetime_orders,
    coalesce(s.lifetime_revenue, 0) as lifetime_revenue,
    s.first_order_date,
    s.last_order_date,
    ntile(4) over (order by coalesce(s.lifetime_revenue, 0) desc) as revenue_quartile
from customers c
left join order_stats s on s.customer_id = c.customer_id
