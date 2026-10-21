-- Daily revenue with a 7-day moving average and a running total.
with daily as (

    select
        order_date,
        count(*)         as orders,
        sum(order_total) as revenue
    from {{ ref('fct_orders') }}
    where is_revenue_order
    group by order_date

)

select
    order_date,
    orders,
    revenue,
    round(avg(revenue) over (
        order by order_date
        rows between 6 preceding and current row
    ), 2) as revenue_7d_avg,
    sum(revenue) over (order by order_date) as cumulative_revenue
from daily
