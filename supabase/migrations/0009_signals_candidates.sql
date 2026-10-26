-- 0009: 연결 레이어 — core.signals (종목×이벤트), core.candidates (교차 후보). ADR-0008 §3.
-- LLM 없이 규칙으로 만든다. 소스별 원문 키·링크를 들고 있어 브리프가 근거로 쓴다.

create table if not exists core.signals (
  id            bigint generated always as identity primary key,
  cik           bigint not null references core.companies (cik),
  signal_date   date   not null,                 -- 이벤트가 발생/공시된 날
  family        text   not null,                 -- insider | contract | clinical | fda | gov | flow | dilution | activist
  kind          text   not null,                 -- cluster_buy | officer_buy | material_agreement | status_change | ...
  direction     smallint not null default 1,     -- +1 긍정 / -1 부정(리스크) / 0 중립
  strength      numeric not null default 1,      -- 가족 내 상대 세기 (0~10 권장)
  summary       text   not null,                 -- 한 줄 설명 (사람이 읽는 용)
  source_table  text   not null,                 -- raw.sec_form4_filings 등
  source_key    text   not null,                 -- 원문 자연키 (accession_no, nct_id, generated_internal_id ...)
  url           text,
  payload       jsonb,
  detected_at   timestamptz not null default now(),
  unique (cik, family, kind, source_key)
);
create index if not exists signals_cik_date_idx on core.signals (cik, signal_date desc);
create index if not exists signals_date_idx     on core.signals (signal_date desc);
create index if not exists signals_family_idx   on core.signals (family, signal_date desc);

-- 후보: 90일 창에서 신호를 모아 매일 재계산. status/notes 는 사람이 바꾸고, 재계산이 보존한다.
create table if not exists core.candidates (
  cik                 bigint primary key references core.companies (cik),
  as_of               date not null,
  score               numeric not null default 0,
  families            text[] not null default '{}',     -- 독립 신호 계열 (긍정만)
  family_count        integer not null default 0,
  signal_count_90d    integer not null default 0,
  risk_count_90d      integer not null default 0,       -- direction = -1 인 신호 수
  first_signal_date   date,
  last_signal_date    date,
  top_signals         jsonb,                             -- [{family, kind, date, summary, url}] 상위 N
  risks               jsonb,                             -- 부정 신호 요약
  status              text not null default 'new' check (status in ('new','watch','briefed','dismissed')),
  notes               text,
  updated_at          timestamptz not null default now()
);
create index if not exists candidates_score_idx on core.candidates (score desc);
create index if not exists candidates_status_idx on core.candidates (status);

alter table core.signals    enable row level security;
alter table core.candidates enable row level security;
create policy "read core" on core.signals    for select to anon, authenticated using (true);
create policy "read core" on core.candidates for select to anon, authenticated using (true);

-- 조회 화면용: 후보 + 회사
create or replace view public.v_candidates
with (security_invoker = true) as
select c.cik, co.ticker, co.name, co.sector_bucket, co.public_float, co.exchange,
       c.as_of, c.score, c.families, c.family_count, c.signal_count_90d, c.risk_count_90d,
       c.first_signal_date, c.last_signal_date, c.top_signals, c.risks, c.status, c.notes, c.updated_at
from core.candidates c join core.companies co on co.cik = c.cik;

create or replace view public.v_signals
with (security_invoker = true) as
select s.id, s.cik, co.ticker, co.name, co.sector_bucket, s.signal_date, s.family, s.kind, s.direction,
       s.strength, s.summary, s.source_table, s.source_key, s.url, s.detected_at
from core.signals s join core.companies co on co.cik = s.cik;

grant select on public.v_candidates, public.v_signals to anon, authenticated;
