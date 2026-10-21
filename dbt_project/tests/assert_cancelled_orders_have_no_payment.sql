-- Cancelled and pending orders must not carry a payment. Returned rows = failures.
select order_id, status, paid_amount
from {{ ref('fct_orders') }}
where status in ('cancelled', 'pending')
  and paid_amount is not null
