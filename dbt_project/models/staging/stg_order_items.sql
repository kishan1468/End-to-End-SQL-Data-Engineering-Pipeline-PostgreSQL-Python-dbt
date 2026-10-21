select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    round(quantity * unit_price, 2) as line_total
from {{ source('raw', 'order_items') }}
