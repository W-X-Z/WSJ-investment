-- 0010: 브리프 레이어 — ideas.briefs / ideas.predictions, 원문·주가 캐시. ADR-0009 참조.

-- ideas 스키마를 PostgREST 에 노출 (파이프라인 write, 화면 read)
alter role authenticator set pgrst.db_schemas = 'public, graphql_public, raw, core, ops, ideas';
notify pgrst, 'reload config';
grant usage on schema ideas to anon, authenticated, service_role;
alter default privileges in schema ideas grant select on tables to anon, authenticated;
alter default privileges in schema ideas grant all on tables to service_role;
alter default privileges in schema ideas grant all on sequences to service_role;

-- 10-K / 8-K 추출 텍스트 캐시 (재실행 시 재다운로드 없음). 섹션 단위로 한 행.
create table if not exists raw.sec_documents (
  accession_no   text not null,
  cik            bigint not null,
  form           text not null,                 -- 10-K | 10-Q | 8-K | S-1 ...
  section        text not null,                 -- item_1 | item_1a | item_7 | full | ...
  file_date      date,
  period_ending  date,
  source_url     text not null,
  char_count     integer not null,
  text           text not null,                 -- 추출·캡 적용 후 본문
  extracted_by   text not null,                 -- anchor | regex | full
  fetched_at     timestamptz not null default now(),
  primary key (accession_no, section)
);
create index if not exists sec_documents_cik_idx on raw.sec_documents (cik, form, file_date desc);

-- 일봉 캐시 (Nasdaq historical API). 조정 없음 — 소형주 분할은 payload 로 추적하지 않는다.
create table if not exists raw.px_daily (
  ticker     text not null,
  trade_date date not null,
  open       numeric,
  high       numeric,
  low        numeric,
  close      numeric not null,
  volume     bigint,
  source     text not null default 'nasdaq',
  fetched_at timestamptz not null default now(),
  primary key (ticker, trade_date)
);

-- 브리프: 실행마다 새 행 (버전 누적). 사람이 읽는 본문은 brief jsonb, 비평은 critique jsonb.
create table if not exists ideas.briefs (
  id               bigint generated always as identity primary key,
  cik              bigint not null references core.companies (cik),
  ticker           text,
  as_of            date not null,
  version          integer not null default 1,           -- 같은 CIK 내 순번
  status           text not null default 'draft' check (status in ('draft','final','superseded','failed')),
  title            text,                                 -- 한 줄 논제
  brief            jsonb,                                 -- ADR-0009 §3 스키마
  research         jsonb,                                 -- 리서치 단계 결과 (출처 URL 포함)
  critique         jsonb,                                 -- 비평 단계 결과
  datapack_summary jsonb,                                 -- 데이터팩 요약 (수치·링크), 전문은 저장하지 않음
  scores           jsonb,                                 -- {conviction, asymmetry, data_quality, time_horizon_months, final_conviction}
  model            text,                                  -- 종합 단계 모델 ID
  prompt_version   text,
  usage            jsonb,                                 -- 단계별 토큰·검색 수·추정 비용(USD)
  error            text,
  created_at       timestamptz not null default now()
);
create index if not exists briefs_cik_idx on ideas.briefs (cik, created_at desc);
create index if not exists briefs_asof_idx on ideas.briefs (as_of desc);

-- 포워드 채점용 예측. outcome 은 사람이 분기마다 채운다 (나중에 Audit 자동화).
create table if not exists ideas.predictions (
  id          bigint generated always as identity primary key,
  brief_id    bigint not null references ideas.briefs (id) on delete cascade,
  cik         bigint not null,
  claim       text not null,
  measurable  text,                                     -- 무엇으로 판정하는가
  due_date    date not null,
  scenario    text,                                      -- bull | base | bear | falsifier
  outcome     text not null default 'pending' check (outcome in ('pending','hit','miss','unclear')),
  graded_at   timestamptz,
  grade_note  text,
  created_at  timestamptz not null default now()
);
create index if not exists predictions_due_idx on ideas.predictions (due_date) where outcome = 'pending';
create index if not exists predictions_cik_idx on ideas.predictions (cik);

alter table raw.sec_documents  enable row level security;
alter table raw.px_daily       enable row level security;
alter table ideas.briefs       enable row level security;
alter table ideas.predictions  enable row level security;
create policy "read raw"   on raw.sec_documents for select to anon, authenticated using (true);
create policy "read raw"   on raw.px_daily      for select to anon, authenticated using (true);
create policy "read ideas" on ideas.briefs      for select to anon, authenticated using (true);
create policy "read ideas" on ideas.predictions for select to anon, authenticated using (true);
grant select on raw.sec_documents, raw.px_daily to anon, authenticated;
grant select on ideas.briefs, ideas.predictions to anon, authenticated;
grant all on raw.sec_documents, raw.px_daily, ideas.briefs, ideas.predictions to service_role;
grant usage, select on all sequences in schema ideas to service_role;

-- 조회 화면용
create or replace view public.v_briefs
with (security_invoker = true) as
select b.id, b.cik, co.ticker, co.name, co.sector_bucket, b.as_of, b.version, b.status, b.title,
       b.scores, b.model, b.prompt_version, b.usage, b.error, b.created_at,
       (select count(*) from ideas.predictions p where p.brief_id = b.id) as prediction_count
from ideas.briefs b join core.companies co on co.cik = b.cik;

create or replace view public.v_predictions
with (security_invoker = true) as
select p.id, p.brief_id, p.cik, co.ticker, co.name, p.claim, p.measurable, p.due_date, p.scenario,
       p.outcome, p.graded_at, p.grade_note, p.created_at
from ideas.predictions p join core.companies co on co.cik = p.cik;

grant select on public.v_briefs, public.v_predictions to anon, authenticated;
