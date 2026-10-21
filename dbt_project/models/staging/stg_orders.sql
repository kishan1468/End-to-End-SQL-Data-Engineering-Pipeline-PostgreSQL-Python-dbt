select
    order_id,
    customer_id,
    order_date,
    status,
    status in ('completed', 'shipped') as is_revenue_order
from {{ source('raw', 'orders') }}
