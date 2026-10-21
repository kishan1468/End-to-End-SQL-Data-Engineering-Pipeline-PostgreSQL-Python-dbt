-- RFM scoring (1 = worst, 4 = best) and a simple segment label.
with as_of as (

    select max(order_date) as as_of_date from {{ ref('fct_orders') }}

),

base as (

    select
        o.customer_id,
        (select as_of_date from as_of) - max(o.order_date) as recency_days,
        count(*)                                           as frequency,
        sum(o.order_total)                                 as monetary
    from {{ ref('fct_orders') }} o
    where o.is_revenue_order
    group by o.customer_id

),

scored as (

    select
        *,
        ntile(4) over (order by recency_days desc) as r_score,
        ntile(4) over (order by frequency asc)     as f_score,
        ntile(4) over (order by monetary asc)      as m_score
    from base

)

select
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    case
        when r_score >= 3 and f_score >= 3 and m_score >= 3 then 'Champion'
        when r_score >= 3 and f_score >= 2                  then 'Loyal'
        when r_score >= 3                                   then 'Recent'
        when r_score <= 2 and f_score >= 3                  then 'At risk'
        else 'Hibernating'
    end as segment
from scored
