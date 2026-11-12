# WSJ Investment F0/F1 implementation

This branch adds an isolated frontier investment research vertical slice. The existing scheduled pipeline and production database are not modified.

## F0: Stable contracts and evidence

- Contracts: frontier/contracts.py defines point-in-time Evidence, Signal, Thesis, EconomicHypothesis, ResearchResult, InvestmentView and verified US/KR Company.
- Store: frontier/storage.py persists runs and stage artifacts in local SQLite with idempotent resume.
- Calculation: frontier/economics.py computes value pool -> attributable incremental revenue -> incremental operating income -> illustrative discounted equity sensitivity. Missing assumptions stay UNKNOWN, not zero.
- Sources: frontier/sources.py reads existing Supabase ideas.clues and clue_texts in READ-ONLY mode, excluding the pipeline's previous research and future-dated evidence.
- Migration: supabase/migrations/0041_frontier_agent_poc.sql is an OPTIONAL PostgreSQL schema contract. It is NOT applied, and there is no PostgREST write adapter in F1.

## F1: Runnable AI workflow

Discovery LLM -> Opportunity LLM -> deterministic economic triage -> Research / critical objections LLM -> Investment review LLM -> SQLite and JSON.

The output is a research lead and view, not a trading instruction. A "candidate" is only a candidate for further human underwriting. References to non-existent evidence IDs are rejected; stale market data and single-source research cannot yield a candidate verdict. Candidate is downgraded to watch when the minimum conditions do not hold. No model output is allowed to assert a guaranteed upside.

### Setup and run from a JSON evidence pack

Use Python 3.11+, and configure the real API model ID rather than relying on an outdated hardcoded model.

    cd pipeline
    pip install -e ".[dev]"
    export ANTHROPIC_API_KEY="YOUR_KEY"
    export WSJ_FRONTIER_MODEL="YOUR_SUPPORTED_ANTHROPIC_MODEL"
    python -m wsj.frontier --input ../research/examples/frontier_f1_synthetic.json --db frontier.sqlite --output result.json

### Run against existing Supabase data (read only)

Provide companies.json as an array of Company objects with name, ticker, exchange (NASDAQ/NYSE/AMEX/KOSPI/KOSDAQ), market_cap_usd, optional price_usd, as_of. Market cap is a checked point-in-time snapshot; USD conversion is required for Korean companies.

    export SUPABASE_URL="..."
    export SUPABASE_SECRET_KEY="..."
    python -m wsj.frontier --from-clues --days 7 --max-docs 60 --companies companies.json --db frontier.sqlite --output result.json

The adapter supplies existing collected documents only. F1 does not perform autonomous web search or independently retrieve missing documents. If the data has no supported market cap or economics, the idea stays on the watchlist.

### Offline tests

    cd pipeline
    pytest -q tests/test_frontier_f1.py

Tests use injected fake LLM responses (no billable API calls). Coverage: full four-stage run; identical-run idempotency; unknown evidence IDs; future-dated papers / market data; missing economics; unverified tickers; independent citation gating; negative margins; existing-clues reader.

## Boundaries and explicit limitations

1. One source observation does not establish independent fact validation. In F1 research uses ONLY the supplied evidence; unsupported claims are unverified.
2. The economic bridge is an ILLUSTRATIVE scenario, not an official market estimate, business valuation, implied expectation, or target stock price. It does not model dilution or probability of technological success.
3. Investing requires verified corporate ownership, cash flow, customer revenue exposure, contract economics and price-implied expectations; these are expanded in F2-F5.
4. The PostgreSQL schema migration is not connected to the local SQLite store; deploy a separate service-role PostgREST backend only after schema review. Do not apply migration to production automatically.
5. No trading or portfolio execution is provided.
6. Current runtime executes within a single process, resumable from validated stage output; it is not a distributed task queue.
7. Source freshness is enforced via explicit timestamp and no look-ahead policy. AI is not allowed to invent citations, but evidence content can still be wrong and needs independent verification.

## Architecture evolution

Keep the contracts stable. Split the discovery prompt into Technology / Demand / Bottleneck / Discrepancy specialist agents. Add new economics calculators through a deterministic registry. Replace the initial single research role with an orchestrator calling technology, market, supply-chain, company and falsification roles. Add a separate valuation tool that compares base and change scenarios to current price-implied expectations. Connect thesis monitoring only after human-reviewable underwriting is reliable.
