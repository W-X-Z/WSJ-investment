import Link from "next/link";
import { Icon } from "@/components/Icon";
import { Stars } from "@/components/Stars";
import { ECO_KO, IDEA_TYPE, ROLE_KO, SIZE_KO, TREND_KO, ago, type IdeaCompany, type IdeaEvidence, type InvestmentIdea } from "@/lib/ideas";

const SMALL = new Set(["micro", "small"]);

export function CompanyChip({ c, strong = false }: { c: IdeaCompany; strong?: boolean }) {
  const small = SMALL.has(c.size_band ?? "");
  return <span className={`ic-chip ${strong ? "ic-chip-primary" : ""} ${small ? "ic-chip-small" : ""}`} title={c.why}>
    {small ? "★ " : ""}<b>{c.name}</b>{c.ticker ? <em>{c.ticker}</em> : null}{c.size_band ? <small>{SIZE_KO[c.size_band] ?? c.size_band}</small> : null}
  </span>;
}

export function EvidenceLinks({ items }: { items: IdeaEvidence[] }) {
  return <span className="ic-ev">{items.map((e) => <a key={e.id + e.url} href={e.url} target="_blank" rel="noreferrer" title={e.title}>
    {e.publisher ?? hostOf(e.url)}{e.tier_ko ? <i>{e.tier_ko}</i> : null}<Icon name="external" size={11}/>
  </a>)}</span>;
}

const hostOf = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return "출처"; } };

/** 피드 카드: 결론(★·제목·두 문장·기업)을 먼저, 근거 사슬은 펼치면 보인다. */
export function IdeaCard({ idea, rank }: { idea: InvestmentIdea; rank?: number }) {
  const type = IDEA_TYPE[idea.type] ?? { label: idea.type, tone: "bottleneck" };
  const primary = idea.companies.find((c) => c.id === idea.primary_company) ?? idea.companies[0];
  const others = idea.companies.filter((c) => c !== primary && c.role !== "customer").slice(0, 3);
  return <article className={`ic ic-${type.tone} ${idea.stale ? "ic-stale" : ""}`}>
    <div className="ic-top">
      {rank ? <span className="ic-rank">{String(rank).padStart(2, "0")}</span> : null}
      <Stars n={idea.stars} why={idea.stars_reason ?? undefined} label/>
      <span className={`ic-type ic-type-${type.tone}`}>{type.label}</span>
      {idea.ecosystems.map((e) => <span key={e} className="ic-eco">{ECO_KO[e] ?? e}</span>)}
      {idea.trend && TREND_KO[idea.trend] ? <span className={`ic-trend ic-trend-${idea.trend}`}>{TREND_KO[idea.trend]}</span> : null}
      <small className="ic-when">{ago(idea.updated_at)} · 근거 {idea.evidence_count}</small>
    </div>
    <Link href={`/ideas/${idea.idea_key}`} className="ic-title">{idea.title}</Link>
    <p className="ic-thesis">{idea.thesis}</p>
    <div className="ic-companies">{primary ? <CompanyChip c={primary} strong/> : null}{others.map((c) => <CompanyChip key={c.id} c={c}/>)}</div>
    <details className="ic-why">
      <summary>왜 그런가 · 근거 {idea.chain.length}단계</summary>
      <ol>{idea.chain.map((s, i) => <li key={i}><span>{s.claim}</span><EvidenceLinks items={s.evidence}/></li>)}</ol>
      {idea.risks.length ? <div className="ic-risk"><b>반대 근거</b> {idea.risks[0].claim}</div> : null}
      <Link href={`/ideas/${idea.idea_key}`} className="ic-more">리스크·지켜볼 신호까지 보기 <Icon name="arrow-right" size={14}/></Link>
    </details>
  </article>;
}

export { ROLE_KO };
