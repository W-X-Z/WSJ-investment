-- 0004: raw.sec_* — EDGAR 공시 인덱스, Form 4. 소스 필드명 유지.

-- EFTS 검색 결과 기반 공시 인덱스 (8-K items, 10-K/Q, 13D 등)
create table if not exists raw.sec_filings (
  accession_no   text primary key,        -- adsh
  cik            bigint not null,         -- 주 발행인 CIK (ciks의 마지막 = 발행인 관례, 아닐 수 있음)
  ciks           bigint[] not null,
  form           text not null,
  root_form      text,
  file_date      date not null,
  period_ending  date,
  items          text[] not null default '{}',   -- 8-K 항목 ('1.01', '5.02' ...)
  display_names  text[],
  primary_doc    text,                    -- EFTS _id의 파일명
  sics           text[],
  biz_states     text[],
  inc_states     text[],
  file_url       text,
  payload        jsonb,
  ingested_at    timestamptz not null default now()
);
create index if not exists sec_filings_cik_date_idx  on raw.sec_filings (cik, file_date desc);
create index if not exists sec_filings_form_date_idx on raw.sec_filings (form, file_date desc);
create index if not exists sec_filings_items_idx     on raw.sec_filings using gin (items);

-- Form 3/4/5 헤더 (ownershipDocument)
create table if not exists raw.sec_form4_filings (
  accession_no          text primary key,
  document_type         text not null,          -- 3 | 4 | 5 | 4/A ...
  schema_version        text,
  issuer_cik            bigint not null,
  issuer_name           text,
  issuer_ticker         text,
  owner_cik             bigint,                 -- 첫 번째 reportingOwner (복수 보고자는 payload)
  owner_name            text,
  owner_count           integer not null default 1,
  is_director           boolean,
  is_officer            boolean,
  is_ten_percent_owner  boolean,
  is_other              boolean,
  officer_title         text,
  period_of_report      date,
  file_date             date,
  aff10b5one            boolean,
  remarks               text,
  file_url              text,
  payload               jsonb,                  -- 파싱 전체 (보고자 목록·각주 포함)
  ingested_at           timestamptz not null default now()
);
create index if not exists form4_filings_issuer_idx on raw.sec_form4_filings (issuer_cik, period_of_report desc);
create index if not exists form4_filings_owner_idx  on raw.sec_form4_filings (owner_cik);
create index if not exists form4_filings_date_idx   on raw.sec_form4_filings (file_date desc);

-- Form 4 거래·보유 행 (nonDerivative/derivative, transaction/holding)
create table if not exists raw.sec_form4_transactions (
  accession_no              text not null references raw.sec_form4_filings (accession_no) on delete cascade,
  seq                       integer not null,     -- 문서 내 순서
  table_type                text not null check (table_type in ('nonDerivative','derivative')),
  row_type                  text not null check (row_type in ('transaction','holding')),
  security_title            text,
  transaction_date          date,
  deemed_execution_date     date,
  transaction_form_type     text,
  transaction_code          text,               -- P S A M F G D J X ...
  equity_swap_involved      boolean,
  transaction_timeliness    text,
  shares                    numeric,
  price_per_share           numeric,
  acquired_disposed         text,               -- A | D
  shares_owned_following    numeric,
  ownership_nature          text,               -- D | I
  indirect_ownership_text   text,
  conversion_or_exercise_price numeric,
  exercise_date             date,
  expiration_date           date,
  underlying_title          text,
  underlying_shares         numeric,
  footnote_ids              text[],
  primary key (accession_no, seq)
);
create index if not exists form4_tx_date_idx on raw.sec_form4_transactions (transaction_date desc);
create index if not exists form4_tx_code_idx on raw.sec_form4_transactions (transaction_code);

alter table raw.sec_filings            enable row level security;
alter table raw.sec_form4_filings      enable row level security;
alter table raw.sec_form4_transactions enable row level security;
create policy "read raw" on raw.sec_filings            for select to anon, authenticated using (true);
create policy "read raw" on raw.sec_form4_filings      for select to anon, authenticated using (true);
create policy "read raw" on raw.sec_form4_transactions for select to anon, authenticated using (true);
