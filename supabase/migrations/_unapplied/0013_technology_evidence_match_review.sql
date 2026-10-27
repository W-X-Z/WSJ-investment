-- 0013: Raw bibliographic matches and measurement candidates for human-reviewed technology intelligence.
-- This is schema-only. DO NOT apply before migrations 0011/0012 and RLS/service-role review.
-- A co-mention or abstract numeric token NEVER becomes a verified tech edge or claim automatically.

create table if not exists raw.tech_source_node_matches (
  source_id uuid not null references raw.tech_sources(id) on delete cascade,
  node_id text not null references core.tech_nodes(id) on delete restrict,
  matcher_version text not null,
  match_score smallint not null check (match_score between 0 and 100),
  matched_aliases text[] not null default '{}',
  matched_in text not null check (matched_in in ('title','abstract','title_and_abstract','body')),
  source_published_precision text not null default 'unknown'
    check(source_published_precision in ('day','month','year','unknown')),
  linkage_status text not null default 'unreviewed'
    check (linkage_status in ('unreviewed','relevant','false_positive','needs_full_text')),
  rationale text,
  linked_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewer text,
  primary key (source_id,node_id,matcher_version),
  check ((linkage_status='unreviewed' and reviewed_at is null)
    or (linkage_status<>'unreviewed'))
);
create index if not exists tech_source_match_node_idx
  on raw.tech_source_node_matches(node_id,linkage_status,linked_at desc);
create index if not exists tech_source_match_recheck_idx
  on raw.tech_source_node_matches(matcher_version,linkage_status);

create table if not exists raw.tech_numeric_mention_candidates (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references raw.tech_sources(id) on delete restrict,
  node_id text not null references core.tech_nodes(id) on delete restrict,
  matched_literal text not null,
  value_numeric numeric,
  value_unit text,
  operator text not null default 'unspecified'
    check (operator in ('unspecified','less_than','less_or_equal','greater_than',
                       'greater_or_equal','approximate')),
  passage text not null,
  passage_locator text,
  source_published_precision text not null default 'unknown'
    check (source_published_precision in ('day','month','year','unknown')),
  matcher_version text not null,
  verification_status text not null default 'unreviewed'
    check (verification_status in ('unreviewed','needs_primary_fulltext','verified','rejected')),
  test_conditions jsonb not null default '{}',
  experiment_subject text,
  primary_claim_id uuid references raw.tech_claims(id),
  extracted_at timestamptz not null default now(),
  reviewed_at timestamptz,
  check (verification_status<>'verified' or (primary_claim_id is not null and reviewed_at is not null))
);
create index if not exists tech_numeric_candidate_node_idx
  on raw.tech_numeric_mention_candidates(node_id,verification_status);
create index if not exists tech_numeric_candidate_source_idx
  on raw.tech_numeric_mention_candidates(source_id);

create table if not exists core.tech_edge_review_queue (
  id uuid primary key default gen_random_uuid(),
  from_node_id text not null references core.tech_nodes(id) on delete restrict,
  to_node_id text not null references core.tech_nodes(id) on delete restrict,
  proposal_kind text not null
    check (proposal_kind in ('document_co_mention','candidate_caused_by','candidate_supplier_link')),
  underlying_source_ids uuid[] not null default '{}',
  same_source_group_count integer not null default 0 check (same_source_group_count >= 0),
  independent_confirmation_count integer not null default 0
    check (independent_confirmation_count >= 0),
  review_state text not null default 'queued'
    check (review_state in ('queued','researching','confirmed','rejected','obsolete')),
  uncertainty_note text not null default
    'Shared bibliographic mention does not establish a causal supply relationship.',
  reviewed_by text,
  reviewed_at timestamptz,
  promoted_edge_id text references core.tech_edges(id) on delete set null,
  opened_at timestamptz not null default now(),
  check (from_node_id<>to_node_id),
  check (promoted_edge_id is null or (review_state='confirmed' and reviewed_at is not null)),
  unique(from_node_id,to_node_id,proposal_kind)
);
create index if not exists tech_edge_review_queue_state_idx
  on core.tech_edge_review_queue(review_state,opened_at desc);

alter table raw.tech_source_node_matches enable row level security;
alter table raw.tech_numeric_mention_candidates enable row level security;
alter table core.tech_edge_review_queue enable row level security;

revoke all on raw.tech_source_node_matches,raw.tech_numeric_mention_candidates,
  core.tech_edge_review_queue from anon,authenticated;
grant all on raw.tech_source_node_matches,raw.tech_numeric_mention_candidates,
  core.tech_edge_review_queue to service_role;

-- No public read view is created. Publishing requires reviewed source+claim and
-- explicit editorial selection; do not expose the raw match table directly.
