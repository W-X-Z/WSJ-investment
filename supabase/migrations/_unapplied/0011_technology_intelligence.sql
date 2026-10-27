-- 0011: Technology Intelligence knowledge model (not yet applied to production).
-- Architectural split: raw evidence -> validated claims -> technology graph -> hypotheses -> watches.
-- IMPORTANT: historical observation timestamps must NEVER be inferred from contemporary API records.
-- IMPORTANT: research hypotheses / unpublished analyses remain private; do not copy existing anon read policies.

create table if not exists core.tech_ecosystems (
  slug text primary key check (slug ~ '^[a-z0-9][a-z0-9_-]{1,63}$'),
  title text not null,
  description text not null default '',
  wiki_path text,
  lifecycle text not null default 'research' check (lifecycle in ('research','active','archived')),
  ontology_version text not null default 'v1',
  source_of_truth text not null default 'repository',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists core.tech_nodes (
  id text primary key,
  ecosystem_slug text references core.tech_ecosystems(slug),
  kind text not null check (kind in (
    'ecosystem','product','product_generation','requirement','bottleneck',
    'technology','material','component','process','equipment','standard',
    'facility','customer','company','experiment'
  )),
  label text not null,
  canonical_key text,
  summary text,
  alias_terms text[] not null default '{}',
  attributes jsonb not null default '{}',
  disclosure_state text not null default 'research' check (
    disclosure_state in ('research','reviewed','published','deprecated')
  ),
  first_known_at timestamptz,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tech_nodes_ecosystem_kind_idx on core.tech_nodes(ecosystem_slug,kind);
create index if not exists tech_nodes_search_idx on core.tech_nodes using gin (to_tsvector('simple',label));
create index if not exists tech_nodes_attrs_idx on core.tech_nodes using gin (attributes);

-- Each revision / public release of a source is immutable (different content hash).
-- first_seen_at is *our collector's* observation timestamp, not a retroactive discovery date.
create table if not exists raw.tech_sources (
  id uuid primary key default gen_random_uuid(),
  source_group text not null,
  source_type text not null check (source_type in (
    'filing','regulator','standard','patent','paper','benchmark','product_spec',
    'customer_document','press_release','developer','archive','other'
  )),
  source_url text not null check (source_url ~ '^https://'),
  title text,
  author_or_publisher text,
  published_at timestamptz,
  published_precision text not null default 'unknown' check (published_precision in ('second','day','month','unknown')),
  published_at_basis text,
  first_seen_at timestamptz not null default now(),
  fetched_at timestamptz not null default now(),
  content_hash text not null check (length(content_hash)>=16),
  archive_url text,
  excerpt text,
  raw_pointer text,
  license_note text,
  crawl_status text not null default 'retrieved' check (crawl_status in ('retrieved','partial','blocked','removed')),
  historical_snapshot boolean not null default false,
  unique(source_url,content_hash)
);
create index if not exists tech_sources_published_idx on raw.tech_sources(published_at desc nulls last);
create index if not exists tech_sources_seen_idx on raw.tech_sources(first_seen_at desc);
create index if not exists tech_sources_group_idx on raw.tech_sources(source_group);
create index if not exists tech_sources_title_search_idx on raw.tech_sources using gin (to_tsvector('simple',coalesce(title,'')||' '||coalesce(excerpt,'')));

-- A claim is always linked to the exact revision of the source it was extracted from.
-- Measurement value by itself is not meaningful without unit and conditions.
create table if not exists raw.tech_claims (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references raw.tech_sources(id) on delete restrict,
  subject_node_id text references core.tech_nodes(id) on delete set null,
  claim_type text not null check (claim_type in (
    'measurement','requirement','technical_statement','customer_adoption',
    'commercial_order','risk','counterevidence','date_milestone'
  )),
  statement text not null,
  measured_name text,
  measured_value numeric,
  measured_unit text,
  measurement_conditions jsonb not null default '{}',
  passage_locator text,
  evidence_quote text,
  epistemic_level text not null default 'vendor_claim' check (epistemic_level in (
    'independent_measurement','official_record','vendor_claim','technical_inference','hypothesis'
  )),
  published_at timestamptz,
  first_seen_at timestamptz,
  verification_status text not null default 'unreviewed' check (
    verification_status in ('unreviewed','reviewed','disputed','retracted')
  ),
  extracted_at timestamptz not null default now(),
  verified_at timestamptz,
  normalized_fingerprint text unique
);
create index if not exists tech_claims_node_idx on raw.tech_claims(subject_node_id);
create index if not exists tech_claims_source_idx on raw.tech_claims(source_id);
create index if not exists tech_claims_metric_idx on raw.tech_claims(measured_name,published_at);

create table if not exists core.tech_edges (
  id text primary key,
  from_node text not null references core.tech_nodes(id) on delete restrict,
  to_node text not null references core.tech_nodes(id) on delete restrict,
  relation text not null check (relation in (
    'drives_requirement','creates_bottleneck','mitigated_by','offered_by',
    'substitutes_for','requires_component_or_material','uses_component_or_equipment',
    'depends_on','qualified_by','validated_by','supplied_to','produces','owns','invests_in'
  )),
  polarity text not null default 'conditional' check (polarity in ('positive','negative','conditional','neutral')),
  epistemic_state text not null default 'hypothesis' check (epistemic_state in (
    'documented','issuer_claim','independent_verified','technical_inference','hypothesis','disputed','retracted'
  )),
  reasoning_note text,
  confidence_band text not null default 'unverified' check (confidence_band in ('unverified','low','medium','high')),
  asserted_at timestamptz not null default now(),
  valid_from timestamptz,
  valid_until timestamptz,
  last_verified_at timestamptz,
  supersedes_edge_id text references core.tech_edges(id),
  created_at timestamptz not null default now(),
  check (from_node<>to_node)
);
create index if not exists tech_edges_from_idx on core.tech_edges(from_node,relation);
create index if not exists tech_edges_to_idx on core.tech_edges(to_node,relation);
create index if not exists tech_edges_state_idx on core.tech_edges(epistemic_state,created_at desc);

create table if not exists core.tech_edge_evidence (
  edge_id text not null references core.tech_edges(id) on delete cascade,
  claim_id uuid not null references raw.tech_claims(id) on delete cascade,
  stance text not null check (stance in ('supports','contradicts','context')),
  reviewed_at timestamptz,
  primary key (edge_id,claim_id)
);

-- Explicitly distinguish association from proven customer supply.
create table if not exists core.tech_company_exposures (
  node_id text not null references core.tech_nodes(id) on delete restrict,
  cik bigint not null references core.companies(cik) on delete restrict,
  role text not null check (role in ('designer','manufacturer','supplier','customer','integrator','potential_supplier')),
  relation_state text not null default 'candidate' check (relation_state in ('candidate','offered_by','qualified','contracted','shipped','revenue_verified','rejected')),
  observed_product text,
  estimated_unit_content numeric,
  estimated_unit_content_unit text,
  revenue_exposure_usd numeric,
  estimate_basis text,
  last_confirmed_claim_id uuid references raw.tech_claims(id),
  verified_at timestamptz,
  primary key(node_id,cik,role)
);
create index if not exists tech_company_by_cik_idx on core.tech_company_exposures(cik,relation_state);

create table if not exists core.tech_events (
  id uuid primary key default gen_random_uuid(),
  event_fingerprint text not null unique,
  ecosystem_slug text references core.tech_ecosystems(slug),
  target_node_id text references core.tech_nodes(id),
  source_id uuid references raw.tech_sources(id) on delete restrict,
  source_group text not null,
  event_type text not null,
  title text not null,
  summary text,
  old_value jsonb,
  new_value jsonb,
  event_occurred_at timestamptz,
  published_at timestamptz,
  first_seen_at timestamptz not null default now(),
  detected_at timestamptz not null default now(),
  status text not null default 'detected' check (status in ('detected','triaged','corroborated','under_review','promoted','retracted','dismissed')),
  importance text not null default 'unrated' check (importance in ('unrated','low','medium','high','critical')),
  novelty_reason text,
  human_reviewed_at timestamptz
);
create index if not exists tech_events_date_idx on core.tech_events(detected_at desc);
create index if not exists tech_events_eco_idx on core.tech_events(ecosystem_slug,published_at desc);
create index if not exists tech_events_node_idx on core.tech_events(target_node_id);

create table if not exists ideas.tech_hypotheses (
  id uuid primary key default gen_random_uuid(),
  ecosystem_slug text references core.tech_ecosystems(slug),
  anchor_node_id text references core.tech_nodes(id),
  owner_cik bigint references core.companies(cik),
  title text not null,
  thesis text not null,
  economic_mechanism text,
  counter_thesis text,
  falsifier text,
  next_milestone text,
  next_check_after date,
  confidence_band text not null default 'unverified' check (confidence_band in ('unverified','low','medium','high')),
  state text not null default 'proposed' check (state in ('proposed','monitoring','strengthened','weakened','invalidated','realized','archived')),
  version integer not null default 1 check(version>0),
  published_to_app boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tech_hypotheses_state_idx on ideas.tech_hypotheses(state,updated_at desc);
create index if not exists tech_hypotheses_eco_idx on ideas.tech_hypotheses(ecosystem_slug,updated_at desc);

create table if not exists ideas.tech_hypothesis_evidence (
  hypothesis_id uuid not null references ideas.tech_hypotheses(id) on delete cascade,
  claim_id uuid not null references raw.tech_claims(id) on delete restrict,
  stance text not null check (stance in ('supports','contradicts','neutral')),
  review_note text,
  created_at timestamptz not null default now(),
  primary key(hypothesis_id,claim_id)
);

create table if not exists ops.tech_watch_rules (
  id text primary key,
  ecosystem_slug text not null references core.tech_ecosystems(slug),
  target_node_id text not null references core.tech_nodes(id),
  detector_key text not null,
  trigger_spec jsonb not null,
  confirmation_requirement text,
  cadence text not null default 'weekly' check (cadence in ('hourly','daily','weekly','monthly')),
  is_enabled boolean not null default false,
  next_check_at timestamptz,
  last_check_at timestamptz,
  last_fingerprint text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tech_watch_due_idx on ops.tech_watch_rules(next_check_at) where is_enabled;

create table if not exists ops.tech_watch_runs (
  id bigint generated always as identity primary key,
  watch_id text not null references ops.tech_watch_rules(id),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','succeeded','empty','failed','blocked')),
  observation_count integer not null default 0 check (observation_count>=0),
  new_event_count integer not null default 0 check(new_event_count>=0),
  error_text text,
  snapshot_hash text
);
create index if not exists tech_watch_runs_recent_idx on ops.tech_watch_runs(watch_id,started_at desc);

create table if not exists ops.tech_watch_alerts (
  id uuid primary key default gen_random_uuid(),
  watch_id text not null references ops.tech_watch_rules(id),
  event_id uuid references core.tech_events(id),
  dedupe_key text not null unique,
  severity text not null check (severity in ('review','high','critical')),
  status text not null default 'candidate' check (status in ('candidate','reviewed','notified','dismissed','resolved')),
  reason text not null,
  reviewer_note text,
  created_at timestamptz not null default now(),
  notified_at timestamptz,
  resolved_at timestamptz
);
create index if not exists tech_alert_pending_idx on ops.tech_watch_alerts(created_at desc) where status in ('candidate','reviewed');

-- DO NOT put research claims on an unrestricted PostgREST endpoint.
-- These tables should not inherit the old anonymous read-only development console policy.
alter table core.tech_ecosystems enable row level security;
alter table core.tech_nodes enable row level security;
alter table core.tech_edges enable row level security;
alter table core.tech_edge_evidence enable row level security;
alter table core.tech_company_exposures enable row level security;
alter table core.tech_events enable row level security;
alter table raw.tech_sources enable row level security;
alter table raw.tech_claims enable row level security;
alter table ideas.tech_hypotheses enable row level security;
alter table ideas.tech_hypothesis_evidence enable row level security;
alter table ops.tech_watch_rules enable row level security;
alter table ops.tech_watch_runs enable row level security;
alter table ops.tech_watch_alerts enable row level security;

revoke all on core.tech_ecosystems,core.tech_nodes,core.tech_edges,core.tech_edge_evidence,core.tech_company_exposures,core.tech_events from anon,authenticated;
revoke all on raw.tech_sources,raw.tech_claims from anon,authenticated;
revoke all on ideas.tech_hypotheses,ideas.tech_hypothesis_evidence from anon,authenticated;
revoke all on ops.tech_watch_rules,ops.tech_watch_runs,ops.tech_watch_alerts from anon,authenticated;
grant all on core.tech_ecosystems,core.tech_nodes,core.tech_edges,core.tech_edge_evidence,core.tech_company_exposures,core.tech_events to service_role;
grant all on raw.tech_sources,raw.tech_claims to service_role;
grant all on ideas.tech_hypotheses,ideas.tech_hypothesis_evidence to service_role;
grant all on ops.tech_watch_rules,ops.tech_watch_runs,ops.tech_watch_alerts to service_role;
grant usage,select on all sequences in schema ops to service_role;

-- App publishing: make explicit, redacted SECURITY INVOKER public views only after
-- user authentication is designed.  Until then Next.js displays the reviewed
-- repository seed and existing v_signals/v_briefs. This migration is schema-only.
