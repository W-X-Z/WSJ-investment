import Link from "next/link";
import { notFound } from "next/navigation";
import { CompanyLine, EvidenceList, Stars5 } from "@/components/opps/Opps";
import { loadOpportunities, loadOpportunity, marketKo, relatedTo } from "@/lib/opportunities";
import { rel } from "@/lib/feed";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  return { title: o?.title ?? "투자 아이디어" };
}

/** 투자 아이디어 상세 (ADR-0028): ★ · 제목 · 투자 아이디어 · 해석 · 관련 기업 · 같은 고리의 다른 아이디어 · 근거. 결론만. */
export default async function OpportunityPage({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  if (!o) notFound();
  const related = relatedTo(o, await loadOpportunities());
  const others = o.companies.filter((c) => c.role !== "primary");
  return <article className="fd op op-detail">
    <p className="op-back"><Link href="/">← 투자 아이디어</Link></p>
    <header className="op-dhead">
      <div className="op-card-top"><Stars5 n={o.stars} large/><CompanyLine o={o}/><time>{rel(o.published_at ?? o.updated_at)}</time></div>
      <h1>{o.title}</h1>
    </header>
    <section className="op-sec"><h2>투자 아이디어</h2><p className="op-text">{o.idea}</p></section>
    {o.interpretation ? <section className="op-sec"><h2>해석</h2><p className="op-text">{o.interpretation}</p></section> : null}
    {others.length ? <section className="op-sec"><h2>관련 기업</h2>
      <ul className="op-cos">{others.map((c, i) => <li key={`${c.name}-${i}`}><b>{c.name}</b>{c.ticker ? <span>{[c.ticker, marketKo(c.exchange)].filter(Boolean).join(" · ")}</span> : null}</li>)}</ul>
    </section> : null}
    {related.length ? <section className="op-sec"><h2>같은 흐름의 아이디어</h2>
      <ul className="op-rel">{related.map((r) => <li key={r.opportunity_key}><Link href={`/opportunities/${r.opportunity_key}`}>{r.title}</Link></li>)}</ul>
    </section> : null}
    <section className="op-sec"><h2>근거</h2><EvidenceList items={o.evidence}/></section>
  </article>;
}
