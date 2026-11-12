"""Read-only adapter for existing Supabase clue tables."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from wsj.db.postgrest import PostgrestStore
from wsj.frontier.contracts import Company, Evidence, InputPack

def load_recent_clues(as_of: datetime, days: int, companies: list[Company],
                      *, max_docs: int = 60, store: Any | None = None) -> InputPack:
    if days <= 0 or max_docs <= 0:
        raise ValueError("days and max_docs must be positive")
    own = store is None
    if own:
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY required")
        store = PostgrestStore(url, key)
    try:
        since = (as_of - timedelta(days=days)).isoformat()
        rows = store.select(
            "ideas.clues",
            ["clue_id", "title", "url", "summary", "published_at", "seen_at", "source_kind", "source_id"],
            {"relevant": True, "seen_at": ("gte", since)}, limit=max_docs * 2, order="seen_at.desc",
        )
        rows = [r for r in rows if r.get("source_id") not in ("agent_research", "chat_research")]
        urls = [r["url"] for r in rows[:max_docs] if r.get("url")]
        bodies: dict[str, str] = {}
        for offset in range(0, len(urls), 30):
            try:
                parts = store.select("ideas.clue_texts", ["url", "body"], {
                    "url": urls[offset:offset + 30], "status": "ok",
                })
                bodies.update({str(x["url"]): str(x["body"]) for x in parts if x.get("body")})
            except Exception:
                pass  # missing body must not be fabricated; summary fallback below
        documents: list[Evidence] = []
        seen_urls: set[str] = set()
        for row in rows:
            url = row.get("url")
            if not url or url in seen_urls:
                continue
            text = bodies.get(url) or row.get("summary") or ""
            if len(text.strip()) < 20:
                continue
            try:
                observed = datetime.fromisoformat(str(row["seen_at"]).replace("Z", "+00:00"))
                published = (datetime.fromisoformat(str(row["published_at"]).replace("Z", "+00:00"))
                             if row.get("published_at") else observed)
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if observed > as_of or published > as_of:
                    continue
                documents.append(Evidence(
                    id="clue:" + str(row["clue_id"]), title=str(row["title"]),
                    url=url, text=text[:8000], published_at=published, observed_at=observed,
                    source_kind=str(row.get("source_kind") or "unknown"),
                ))
                seen_urls.add(url)
            except (ValueError, TypeError, KeyError):
                continue
            if len(documents) >= max_docs:
                break
        if not documents:
            raise ValueError("No eligible evidence in window; check source timestamps and bodies")
        return InputPack(as_of=as_of, evidence=documents, companies=companies)
    finally:
        if own:
            store.close()
