import Link from "next/link";
import { rel } from "@/lib/feed";
import { changedAfterPublish, lead, marketKo, primaryOf, touchedAt, type OppEvidence, type Opportunity } from "@/lib/opportunities";

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

/** 낸 때, 또는 낸 뒤 고쳤으면 '… 고침'. */
export function OppTime({ o }: { o: Opportunity }) {
  const changed = changedAfterPublish(o);
  return <time className={changed ? "op-changed" : undefined} dateTime={touchedAt(o)}>{rel(touchedAt(o))}{changed ? " 고침" : ""}</time>;
}

/** 목록 카드: ★ · 기업 · 제목 · 한 줄 요지. 카드 전체가 상세로 가는 링크. */
export function OppCard({ o }: { o: Opportunity }) {
  return <Link href={`/opportunities/${o.opportunity_key}`} className="op-card">
    <div className="op-card-top"><Stars5 n={o.stars}/><CompanyLine o={o}/><OppTime o={o}/></div>
    <h3>{o.title}</h3>
    <p>{lead(o)}</p>
  </Link>;
}

/** 문단 머리의 짧은 표지 — "단서:", "시장이 믿는 것과 우리:", "가장 약한 고리:". 에이전트가 쓴 구조를 그대로 보이게 굵게만 한다. */
const LABEL = /^([^:：\n.]{1,18})[:：]\s+/;
const SENTENCE_END = /(?<=[.!?])\s+(?=[가-힣A-Z0-9"'(])/;

/** 긴 본문을 문단으로. 줄바꿈이 있으면 그대로, 없으면(옛 글) 세 문장씩 끊는다 — 한 덩어리로 찍히지 않게. */
export function paragraphs(text: string): string[] {
  const byLine = text.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  if (byLine.length > 1 || text.length < 450) return byLine;
  const sents = text.split(SENTENCE_END).map((s) => s.trim()).filter(Boolean);
  const out: string[] = [];
  for (let i = 0; i < sents.length; i += 3) out.push(sents.slice(i, i + 3).join(" "));
  return out;
}

export function Prose({ text }: { text: string }) {
  return <div className="op-prose">{paragraphs(text).map((p, i) => {
    const m = p.match(LABEL);
    return <p key={i}>{m ? <><b>{m[1]}</b>{p.slice(m[0].length)}</> : p}</p>;
  })}</div>;
}

export function EvidenceList({ items }: { items: OppEvidence[] }) {
  return <ol className="op-ev">{items.map((e, i) => <li key={`${e.url}-${i}`}>
    <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a>
    <span>{[e.publisher, e.date ? e.date.slice(0, 10) : null].filter(Boolean).join(" · ")}</span>
  </li>)}</ol>;
}
