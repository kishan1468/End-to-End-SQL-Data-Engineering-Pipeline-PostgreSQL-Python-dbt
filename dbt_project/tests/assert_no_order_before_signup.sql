-- An order cannot be placed before the customer signed up. Returned rows = failures.
select
    o.order_id,
    o.order_date,
    c.signup_date
from {{ ref('fct_orders') }} o
join {{ ref('stg_customers') }} c using (customer_id)
where o.order_date < c.signup_date
