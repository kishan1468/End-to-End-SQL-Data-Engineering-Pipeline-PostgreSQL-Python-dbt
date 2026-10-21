select
    payment_id,
    order_id,
    payment_method,
    amount,
    paid_at
from {{ source('raw', 'payments') }}
