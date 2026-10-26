-- 0002: 수집기 실행 로그와 워터마크. ADR-0003 참조.

create table if not exists ops.collector_runs (
  id            bigint generated always as identity primary key,
  collector     text        not null,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  status        text        not null check (status in ('running','succeeded','failed','skipped')),
  rows_upserted integer     not null default 0,
  params        jsonb,              -- CLI 인자 (--since, --limit 등)
  watermark     jsonb,              -- 이 실행이 끝났을 때의 워터마크
  error         text,
  runner_host   text
);
create index if not exists collector_runs_collector_started_idx on ops.collector_runs (collector, started_at desc);

-- 수집기별 현재 워터마크. 러너는 run 시작 시 읽고 성공 시 갱신한다.
create table if not exists ops.collector_state (
  collector   text primary key,
  watermark   jsonb       not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);

alter table ops.collector_runs  enable row level security;
alter table ops.collector_state enable row level security;
create policy "read ops" on ops.collector_runs  for select to anon, authenticated using (true);
create policy "read ops" on ops.collector_state for select to anon, authenticated using (true);
