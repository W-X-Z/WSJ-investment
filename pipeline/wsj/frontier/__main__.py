"""CLI: python -m wsj.frontier --input point_in_time_pack.json --model MODEL."""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from wsj.frontier.agents import AnthropicJSONLLM
from wsj.frontier.contracts import Company, InputPack
from wsj.frontier.flow import FrontierPipeline
from wsj.frontier.sources import load_recent_clues
from wsj.frontier.storage import SQLiteRunStore

def main() -> None:
    p = argparse.ArgumentParser(description="WSJ F0/F1 frontier investment research")
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--input", help="JSON evidence + company market data pack")
    choice.add_argument("--from-clues", action="store_true", help="Read existing Supabase clues (read-only)")
    p.add_argument("--companies", help="JSON array with verified US/KR market-cap snapshots")
    p.add_argument("--as-of", help="Timezone-aware ISO timestamp used for recent clue extraction")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--max-docs", type=int, default=60)
    p.add_argument("--db", default="frontier.sqlite", help="Resumable local SQLite research state")
    p.add_argument("--output", help="Optional JSON output filename")
    p.add_argument("--model", default=os.environ.get("WSJ_FRONTIER_MODEL"))
    p.add_argument("--max-research", type=int, default=3)
    a = p.parse_args()
    if not a.model:
        p.error("Supply --model or WSJ_FRONTIER_MODEL; ANTHROPIC_API_KEY is required")
    if a.from_clues:
        if not a.companies:
            p.error("--companies required with --from-clues; unknown tickers must not be assumed")
        companies = [Company.model_validate(x) for x in json.loads(Path(a.companies).read_text(encoding="utf-8"))]
        as_of = datetime.fromisoformat(a.as_of.replace("Z", "+00:00")) if a.as_of else datetime.now(timezone.utc)
        pack = load_recent_clues(as_of, a.days, companies, max_docs=a.max_docs)
    else:
        pack = InputPack.model_validate_json(Path(a.input).read_text(encoding="utf-8"))
    with SQLiteRunStore(a.db) as store:
        result = FrontierPipeline(AnthropicJSONLLM(a.model), store,
                                  max_research=a.max_research).run(pack)
    result_json = json.dumps(result, indent=2, ensure_ascii=False)
    if a.output:
        Path(a.output).write_text(result_json + "\n", encoding="utf-8")
    print(result_json)

if __name__ == "__main__":
    main()
