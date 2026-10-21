-- Product dimension with sales metrics and rank inside its category.
with products as (

    select * from {{ ref('stg_products') }}

),

sales as (

    select
        i.product_id,
        sum(i.quantity)   as units_sold,
        sum(i.line_total) as revenue
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_orders') }} o on o.order_id = i.order_id
    where o.is_revenue_order
    group by i.product_id

)

select
    p.product_id,
    p.product_name,
    p.category,
    p.unit_price,
    coalesce(s.units_sold, 0) as units_sold,
    coalesce(s.revenue, 0)    as revenue,
    rank() over (
        partition by p.category
        order by coalesce(s.revenue, 0) desc
    ) as revenue_rank_in_category
from products p
left join sales s on s.product_id = p.product_id
