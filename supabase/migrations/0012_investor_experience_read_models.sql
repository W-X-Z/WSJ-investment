-- 0012: Decision-first UI read model, designed for authenticated publishing.
-- REQUIRES 0011; intentionally does not grant access to anon/authenticated.
-- Never run on production without authentication/RLS review and backfill.
create table if not exists ideas.tech_hypothesis_revisions (
  id bigint generated always as identity primary key,
  hypothesis_id uuid not null references ideas.tech_hypotheses(id) on delete restrict,
  revision integer not null check(revision>0),
  old_state text,
  new_state text not null check(new_state in ('proposed','monitoring','strengthened','weakened','invalidated','realized','archived')),
  reason text not null,
  supporting_claim_ids uuid[] not null default '{}',
  contradicting_claim_ids uuid[] not null default '{}',
  changed_at timestamptz not null default now(),
  changed_by text not null default 'system',
  unique(hypothesis_id,revision)
);
create index if not exists tech_hypothesis_revisions_latest_idx on ideas.tech_hypothesis_revisions(hypothesis_id,changed_at desc);

create table if not exists ideas.tech_event_hypothesis_impacts (
  event_id uuid not null references core.tech_events(id) on delete restrict,
  hypothesis_id uuid not null references ideas.tech_hypotheses(id) on delete restrict,
  impact text not null check(impact in ('new','strengthened','weakened','invalidated','neutral','unreviewed')),
  impact_explanation text not null,
  path_edge_ids text[] not null default '{}',
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  primary key(event_id,hypothesis_id)
);
create index if not exists tech_impact_hypothesis_idx on ideas.tech_event_hypothesis_impacts(hypothesis_id,created_at desc);

create table if not exists core.tech_event_publication (
  event_id uuid primary key references core.tech_events(id) on delete restrict,
  display_title text not null,
  executive_summary text not null,
  impact_summary text,
  editorial_rank integer check(editorial_rank between 1 and 100),
  reviewed_at timestamptz,
  published_at timestamptz,
  is_published boolean not null default false,
  check(not is_published or (reviewed_at is not null and published_at is not null))
);
create index if not exists tech_publication_priority_idx on core.tech_event_publication(is_published,editorial_rank,published_at desc);

-- Server-only read projections. No grants to browser role: all joins retain RLS.
-- Do not use SECURITY DEFINER views to bypass underlying permissions.
create or replace view core.v_technology_intelligence_feed
with (security_invoker = true)
as
select e.id::text as id,
       p.display_title as title,
       p.executive_summary as summary,
       p.impact_summary,
       e.ecosystem_slug,
       e.event_type,
       e.importance,
       e.status,
       e.published_at as source_published_at,
       e.first_seen_at,
       p.published_at as editorial_published_at,
       p.editorial_rank,
       s.source_url,
       s.source_group,
       s.source_type,
       e.target_node_id,
       count(distinct i.hypothesis_id) as linked_hypotheses
from core.tech_events e
join core.tech_event_publication p on p.event_id=e.id
left join raw.tech_sources s on s.id=e.source_id
left join ideas.tech_event_hypothesis_impacts i on i.event_id=e.id
where p.is_published and e.status not in ('dismissed','retracted')
group by e.id,p.event_id,s.id;

create or replace view ideas.v_technology_thesis_feed
with (security_invoker = true)
as
select h.id::text as id,
       h.title,
       h.thesis,
       h.economic_mechanism,
       h.counter_thesis,
       h.falsifier,
       h.next_milestone,
       h.next_check_after,
       h.state,
       h.confidence_band,
       h.ecosystem_slug,
       h.owner_cik,
       h.anchor_node_id,
       h.updated_at,
       (select max(r.changed_at) from ideas.tech_hypothesis_revisions r where r.hypothesis_id=h.id) as last_thesis_change_at,
       (select count(*) from ideas.tech_hypothesis_evidence he where he.hypothesis_id=h.id and he.stance='supports') as supporting_claims,
       (select count(*) from ideas.tech_hypothesis_evidence he where he.hypothesis_id=h.id and he.stance='contradicts') as contradictory_claims
from ideas.tech_hypotheses h
where h.published_to_app and h.state <> 'archived';

alter table ideas.tech_hypothesis_revisions enable row level security;
alter table ideas.tech_event_hypothesis_impacts enable row level security;
alter table core.tech_event_publication enable row level security;
revoke all on ideas.tech_hypothesis_revisions,ideas.tech_event_hypothesis_impacts,core.tech_event_publication from anon,authenticated;
revoke all on core.v_technology_intelligence_feed,ideas.v_technology_thesis_feed from anon,authenticated;
grant all on ideas.tech_hypothesis_revisions,ideas.tech_event_hypothesis_impacts,core.tech_event_publication to service_role;
grant select on core.v_technology_intelligence_feed,ideas.v_technology_thesis_feed to service_role;
grant usage,select on all sequences in schema ideas to service_role;
