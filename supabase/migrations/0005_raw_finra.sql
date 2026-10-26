-- 0005: raw.finra_* — FINRA Data API (무인증). 파티션 키 그대로 PK.

-- regShoDaily: 일별 공매도 거래량 (시장·보고시설별 행)
create table if not exists raw.finra_short_daily (
  trade_report_date         date not null,
  symbol                    text not null,
  market_code               text not null,
  reporting_facility_code   text not null,
  short_par_quantity        numeric,
  short_exempt_par_quantity numeric,
  total_par_quantity        numeric,
  ingested_at               timestamptz not null default now(),
  primary key (trade_report_date, symbol, market_code, reporting_facility_code)
);
create index if not exists finra_short_daily_symbol_idx on raw.finra_short_daily (symbol, trade_report_date desc);

-- consolidatedShortInterest: 월 2회 공매도 잔고
create table if not exists raw.finra_short_interest (
  settlement_date                   date not null,
  symbol                            text not null,
  issue_name                        text,
  market_class_code                 text,
  current_short_position_quantity   numeric,
  previous_short_position_quantity  numeric,
  average_daily_volume_quantity     numeric,
  days_to_cover_quantity            numeric,
  change_percent                    numeric,
  change_previous_number            numeric,
  stock_split_flag                  text,
  revision_flag                     text,
  ingested_at                       timestamptz not null default now(),
  primary key (settlement_date, symbol)
);
create index if not exists finra_short_interest_symbol_idx on raw.finra_short_interest (symbol, settlement_date desc);

-- weeklySummary: ATS/OTC 주간 종목·MPID별 거래량
create table if not exists raw.finra_ats_weekly (
  week_start_date             date not null,
  tier_identifier             text not null,
  symbol                      text not null,
  mpid                        text not null,
  summary_type_code           text not null,     -- ATS_W_SMBL_FIRM | OTC_W_SMBL_FIRM ...
  issue_name                  text,
  market_participant_name     text,
  firm_crd_number             text,
  total_weekly_trade_count    numeric,
  total_weekly_share_quantity numeric,
  total_notional_sum          numeric,
  last_update_date            date,
  ingested_at                 timestamptz not null default now(),
  primary key (week_start_date, tier_identifier, symbol, mpid, summary_type_code)
);
create index if not exists finra_ats_weekly_symbol_idx on raw.finra_ats_weekly (symbol, week_start_date desc);

alter table raw.finra_short_daily    enable row level security;
alter table raw.finra_short_interest enable row level security;
alter table raw.finra_ats_weekly     enable row level security;
create policy "read raw" on raw.finra_short_daily    for select to anon, authenticated using (true);
create policy "read raw" on raw.finra_short_interest for select to anon, authenticated using (true);
create policy "read raw" on raw.finra_ats_weekly     for select to anon, authenticated using (true);
