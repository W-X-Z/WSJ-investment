-- 0007: 조회 화면용 뷰 (public 스키마에 두어 PostgREST 기본 노출로 접근)

-- 수집 현황 개요: 수집기별 최근 실행·행 수
create or replace view public.v_collector_overview as
select
  s.collector,
  s.watermark,
  s.updated_at as watermark_updated_at,
  r.status      as last_status,
  r.started_at  as last_started_at,
  r.finished_at as last_finished_at,
  r.rows_upserted as last_rows,
  r.error       as last_error
from ops.collector_state s
left join lateral (
  select * from ops.collector_runs cr
  where cr.collector = s.collector
  order by cr.started_at desc limit 1
) r on true;

-- 테이블 행 수 (근사치: pg_class.reltuples는 ANALYZE 기준). 정확한 count는 화면에서 head 요청으로.
create or replace view public.v_table_counts as
select n.nspname as schema_name, c.relname as table_name, c.reltuples::bigint as approx_rows
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'r' and n.nspname in ('raw','core','ops')
order by 1, 2;

-- 내부자 거래: 거래 행 + 헤더 + 유니버스 조인
create or replace view public.v_insider_transactions as
select
  t.accession_no, t.seq, t.table_type, t.row_type,
  f.issuer_cik, f.issuer_name, f.issuer_ticker,
  f.owner_cik, f.owner_name, f.officer_title,
  f.is_director, f.is_officer, f.is_ten_percent_owner,
  f.file_date, f.period_of_report,
  t.transaction_date, t.transaction_code, t.acquired_disposed,
  t.shares, t.price_per_share,
  (t.shares * t.price_per_share) as value_usd,
  t.shares_owned_following, t.ownership_nature, t.security_title,
  c.in_universe, c.sector_bucket, c.public_float,
  f.file_url
from raw.sec_form4_transactions t
join raw.sec_form4_filings f using (accession_no)
left join core.companies c on c.cik = f.issuer_cik;

grant select on public.v_collector_overview, public.v_table_counts, public.v_insider_transactions to anon, authenticated;
