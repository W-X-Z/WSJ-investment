import Link from "next/link";
import { rel } from "@/lib/feed";
import { lead, marketKo, primaryOf, type OppEvidence, type Opportunity } from "@/lib/opportunities";

/** ★1~5 — 나에게 얼마나 큰 투자 기회인가. 글자로만. */
export function Stars5({ n, large }: { n: number; large?: boolean }) {
  const k = Math.max(1, Math.min(5, Math.round(n)));
  return <span className={`op-stars${large ? " op-stars-lg" : ""}`} aria-label={`투자 기회 별 ${k}개 (5개 만점)`}>
    <span aria-hidden="true">{"★".repeat(k)}<i>{"★".repeat(5 - k)}</i></span>
  </span>;
}

export function CompanyLine({ o }: { o: Opportunity }) {
  const p = primaryOf(o);
  if (!p) return null;
  return <span className="op-co"><b>{p.name}</b>{p.ticker ? <span>{[p.ticker, marketKo(p.exchange)].filter(Boolean).join(" · ")}</span> : null}</span>;
}

/** 목록 카드: ★ · 기업 · 제목 · 한 줄 요지. 카드 전체가 상세로 가는 링크. */
export function OppCard({ o }: { o: Opportunity }) {
  return <Link href={`/opportunities/${o.opportunity_key}`} className="op-card">
    <div className="op-card-top"><Stars5 n={o.stars}/><CompanyLine o={o}/><time>{rel(o.published_at ?? o.updated_at)}</time></div>
    <h3>{o.title}</h3>
    <p>{lead(o)}</p>
  </Link>;
}

export function EvidenceList({ items }: { items: OppEvidence[] }) {
  return <ol className="op-ev">{items.map((e, i) => <li key={`${e.url}-${i}`}>
    <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a>
    <span>{[e.publisher, e.date ? e.date.slice(0, 10) : null].filter(Boolean).join(" · ")}</span>
  </li>)}</ol>;
}
