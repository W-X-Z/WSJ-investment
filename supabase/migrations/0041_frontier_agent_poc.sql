-- F0/F1 optional durable Supabase persistence, not applied automatically.
-- Existing ideas.clues, core.graph_* and research.reports remain untouched.
-- Apply with Supabase SQL editor after review; service_role only.

create schema if not exists research;

create table if not exists research.frontier_runs (
    run_id text primary key,
    as_of timestamptz not null,
    input_hash text not null,
    status text not null check (status in ('running', 'completed', 'failed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists research.frontier_artifacts (
    run_id text not null references research.frontier_runs(run_id) on delete cascade,
    stage text not null,
    content jsonb not null,
    recorded_at timestamptz not null default now(),
    primary key (run_id, stage)
);

create index if not exists frontier_artifacts_stage_idx
    on research.frontier_artifacts (stage, recorded_at desc);

alter table research.frontier_runs enable row level security;
alter table research.frontier_artifacts enable row level security;

revoke all on research.frontier_runs, research.frontier_artifacts from public, anon, authenticated;
grant all on research.frontier_runs, research.frontier_artifacts to service_role;

-- Do not expose this schema to anon or authenticated clients.
-- The F1 CLI uses SQLiteRunStore by default; the migration is a persistence contract
-- for a subsequent service-role adapter and is not required for local execution.
