select
    product_id,
    product_name,
    category,
    unit_price
from {{ source('raw', 'products') }}
