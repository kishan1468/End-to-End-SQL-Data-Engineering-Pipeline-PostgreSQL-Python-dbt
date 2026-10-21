-- Order-level fact table: one row per order.
with orders as (

    select * from {{ ref('stg_orders') }}

),

totals as (

    select * from {{ ref('int_order_totals') }}

),

payments as (

    select * from {{ ref('stg_payments') }}

),

customers as (

    select * from {{ ref('stg_customers') }}

)

select
    o.order_id,
    o.customer_id,
    c.country,
    o.order_date,
    o.status,
    o.is_revenue_order,
    t.item_count,
    t.units,
    t.order_total,
    p.amount          as paid_amount,
    p.payment_method,
    p.paid_at
from orders o
join totals t        on t.order_id = o.order_id
join customers c     on c.customer_id = o.customer_id
left join payments p on p.order_id = o.order_id
