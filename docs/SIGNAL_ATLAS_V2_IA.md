# Signal Atlas 2.0 — Decision-first UX & information architecture

## Product premise
The previous UI centered collector state, raw rows and data counts. The new entry point answers:
1. What materially changed?
2. Where in the technical supply chain does it propagate?
3. Which hypotheses or small listed companies could be affected?
4. What must be verified next?

**The homepage is a research decision surface, not an operations dashboard.** No market price momentum is required for discovery.

## IA / depth rules
| Depth | Navigation | User job | Density |
|---|---|---|---|
| 0 | `/` | Today's lead signal, active theses, industrial architecture, mixed feed | 1 main signal, 3 active theses, 3 industry switches, 6 feed rows |
| 1 | `/ecosystems`, `/feed`, `/ideas`, `/triggers`, `/search` | Filter, compare, inspect | Moderate |
| 2 | `/ecosystems/[slug]`, `/feed/[id]`, `/ideas/[id]` | Source-by-source reasoning, opposing evidence, measurements | Full depth |
| 2+ | `/data` → `/filings`, `/finra`, `/fda`, etc | Pipeline health and raw ingestion details | Expert / diagnostic |

The existing sidebar already keeps the legacy data workspace in nested disclosure, preserved in this release.

## New homepage behaviors
- Lead event links directly to its evidence-oriented detail page.
- Sector switch changes graph, metric and narrative together without a page reload.
- Mixed feed unifies evidence events and thesis cards, filters by materiality/type/sector.
- 6 items at first; secondary items behind “more”.
- Search is always one action away (topbar and homepage).
- Mobile: single-column lead, horizontal density reduced, full keyboard and semantic buttons.
- Distinguish historical curated seed from live corporate signal feeds; never call static seed “breaking news”.
- No fake stock returns, certainty scores or invented supplier relationships.

## Backend data contract
**Source-of-truth:** existing `0011_technology_intelligence.sql` tables for source revision, claim, graph node/edge, event, hypothesis and watch.
**New 0012:** `tech_event_publication` editorial selection, `tech_event_hypothesis_impacts` (event→thesis relation), immutable `tech_hypothesis_revisions` history; secure read views for feed and thesis.

### Entity flows
`raw.tech_sources -> raw.tech_claims -> core.tech_events -> core.tech_event_publication -> /feed`
`core.tech_nodes -> core.tech_edges -> ideas.tech_hypotheses -> ideas.tech_hypothesis_revisions -> /ideas`
`core.tech_events + ideas.tech_hypotheses -> ideas.tech_event_hypothesis_impacts -> home mixed feed`

### Future operational data pipeline
1. Monitor fetch + hash + source publication and first-seen timestamp.
2. Extract measured metrics and cite exact source revision.
3. Build deduplicated event; attach to technical graph.
4. Human/agent evaluate affected theses; preserve strengthened/weakened/invalidation and evidence.
5. Editorial rank and publish after reviewed_at; do not expose private unpublished analysis.
6. Read-only authenticated UI uses publication views; preserve public read-free data protection.

## Release constraints
- `0012` is **migration source only**; do not apply to production until `0011` is applied, RLS and publishing auth are configured, and service role is secured server-side.
- Frontend v2 deliberately reads the existing reviewed research seed + existing public `v_signals/v_briefs` for immediate deployability. It **does not yet** read `0012` views. These are backend contracts for the next integration phase.
- Static seed data are historical curated events and not a live real-time feed. Do not label as current-day findings.
- Do not put service role tokens into `NEXT_PUBLIC_*` variables.
- Future acceptance: query against new read models under a real authenticated session; source/claim links and event publication dates verified; feed rank controlled by editorial criteria, not merely price action.
