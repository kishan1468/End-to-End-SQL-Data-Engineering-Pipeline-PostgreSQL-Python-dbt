-- Every completed/shipped/refunded order must have a payment equal to the order total.
-- Returned rows = failures.
select
    order_id,
    status,
    order_total,
    paid_amount
from {{ ref('fct_orders') }}
where status in ('completed', 'shipped', 'refunded')
  and (paid_amount is null or abs(paid_amount - order_total) > 0.01)
