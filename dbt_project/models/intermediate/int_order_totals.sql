-- One row per order with item counts and the order total.
with items as (

    select * from {{ ref('stg_order_items') }}

),

totals as (

    select
        order_id,
        count(*)         as item_count,
        sum(quantity)    as units,
        sum(line_total)  as order_total
    from items
    group by order_id

)

select * from totals
