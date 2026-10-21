select
    customer_id,
    initcap(first_name) || ' ' || initcap(last_name) as full_name,
    lower(email)                                     as email,
    country,
    signup_date
from {{ source('raw', 'customers') }}
