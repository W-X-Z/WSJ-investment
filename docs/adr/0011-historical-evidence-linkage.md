# ADR 0011 — Historical primary-source evidence ↔ supply-chain knowledge graph

Status: implemented as **review-only repository-backed indexing** on PR #8; database schema designed, not deployed.

## Decision

Preserve four distinct representations. Never conflate them:

1. **Bibliographic record** — a paper/SEC/Federal Register document exists. Historical `published_at` and actual `first_seen_at` are distinct. Imprecise publication time must retain `published_precision`.
2. **Node–source lexical match** — a passage potentially concerns a technology/material/process. This is a research discovery hint, not scientific corroboration.
3. **Quantitative mention candidate** — a number and ontology-allowed unit appear near a relevant passage. The claim subject, conditions, experimental vs simulation status, comparator (`<`, `>`) and methodology remain unverified.
4. **Reviewed technical claim / supply relationship** — only after primary full text, independent verification where possible, and reviewer sign-off does a candidate become a verified claim or tech graph edge. Never infer `supplied_to` or customer adoption from shared document title words.

## Current data flow

```
2020–2026 5,444 historical source records
  ├─ 3 ecosystem JSONL archives (OpenAlex/Crossref/SEC/Federal Register)
  ├─ canonical DOI dedupe, future-date exclusion, publication precision
  ↓
research/ecosystems/node_aliases.json (curated non-exhaustive bilingual labels)
  ↓
pipeline/wsj/ecosystems/enrich_graph.py (deterministic, no model inference)
  ├─ apps/web/src/data/graph-evidence-index.json
  │    node_id → yearly counts + bibliography + unit-gated mentions
  ├─ research/enriched/summary.json
  └─ research/enriched/relation-candidates.json
       co-mentioned technical terms ONLY; reviewer queue, no tech_edges mutation
  ↓
SupplyNetworkCanvas > NodeEvidencePanel
  ├─ source publication year histogram (bibliographic interest, NOT market adoption)
  ├─ candidate numeric phrases with unverified test conditions
  └─ original source URLs + exact phrase matching
```

This is complemented by a **curated, dated primary-source milestone ledger**:
`apps/web/src/data/industry-milestones.json`. It records HBM issuer technical disclosure, IEEE P802.3dj Standards Association ballot status and OCP 800VDC requirements development with explicit next verification triggers; it never asserts that standardization equals monetization.

## Repository vs proposed normalized DB

- Implemented: versioned research files + GitHub Actions automated offline read projection.
- Planned schema: `supabase/migrations/_unapplied/0013_technology_evidence_match_review.sql (미적용, ADR-0015 로 대체)`, adds unreviewed source-node match, numeric mention candidate, relationship review queue; enforces protected access and reviewer-gated promotion.
- **Production Supabase DB not yet modified.** Migrations 0011–0013 depend on a decision on authentication, RLS, and server-side publishing API. Service role credentials must stay server-side only.

## Agent review sequence for a high-value quantitative change

1. Locate source publication timestamp with precision; distinguish publication from ingestion.
2. Fetch full authoritative source/paper and pinpoint figure/table/page and experimental context.
3. Extract measurement name, subject, units, comparator and baseline; do not compare metrics with incompatible test conditions.
4. Determine which technology requirement, yield/reliability process, material or component it bears on.
5. Test against alternative architecture, independent source family and disconfirming evidence.
6. Trace supplier/manufacturer/customers only through company and third-party evidence. Distinguish technical product from customer qualification, capacity ramp, actual orders and realized revenue.
7. Promote event and change investment hypothesis state **only after review**, with evidence IDs, source group independence and explicit falsifier.

## Next collection gaps

- Full-text open-access technical publications, and primary test methodology/figures.
- Patent applications and claim-level mapping (do not count patent abstracts as validated technology).
- Primary historical SEC filing content (not just filing metadata).
- Source-by-source entity resolution for supplier product SKUs, manufacturing nodes, actual contracts, production volumes and BOM economic capture.
- Historical publication point-in-time access remains unverified; no fictitious pre-2026 collector sightings.

## Acceptance checks

- Date-only vs year-only records displayed honestly; no source dated after as-of.
- Crossref/OpenAlex duplicate DOI counts as one canonical source.
- Same abstract referencing two concepts creates **review candidate** only, no supply edge.
- Company, broad industry nodes do not inherit unrelated numerical expressions.
- Actual source quote candidates retain `<`/`>` qualifier; declared ontology units act as filter.
- Graph inspector uses the same reviewed ontology seed as backend; sync script checks it.
- CI unit tests and Next.js full build pass before merging.
