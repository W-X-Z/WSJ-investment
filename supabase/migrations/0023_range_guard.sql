-- 0023: 고점·저점 대비는 거래일 이력이 120일 이상일 때만 (며칠치 이력으로 '저점 대비 +2%' 가 나오지 않게). 열 순서는 그대로.
create or replace view public.v_price_context
with (security_invoker = true) as
with p as (
  select ticker, trade_date, close, volume, row_number() over (partition by ticker order by trade_date desc) as rn
  from raw.px_daily
  where trade_date > current_date - 400 and close is not null
)
select ticker,
       max(trade_date) filter (where rn = 1) as as_of,
       max(close) filter (where rn = 1) as close,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn = 22), 0) - 1), 1) as r1m,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn = 64), 0) - 1), 1) as r3m,
       round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn = 248), 0) - 1), 1) as r12m,
       case when count(*) >= 120 then round(100 * (max(close) filter (where rn = 1) / nullif(max(close) filter (where rn <= 250), 0) - 1), 1) end as from_high,
       round(avg(volume) filter (where rn <= 5) / nullif(avg(volume) filter (where rn between 6 and 65), 0), 2) as vol_ratio,
       count(*) as points,
       case when count(*) >= 120 then round(100 * (max(close) filter (where rn = 1) / nullif(min(close) filter (where rn <= 250), 0) - 1), 1) end as from_low
from p
group by ticker;
