import Link from "next/link";
import { notFound } from "next/navigation";
import { CompanyLine, EvidenceList, OppTime, Prose, Stars5 } from "@/components/opps/Opps";
import { IdeaChart } from "@/components/opps/IdeaChart";
import { changeNote, loadOpportunities, loadOpportunity, loadPrices, marketKo, primaryOf, relatedTo } from "@/lib/opportunities";
import { rel } from "@/lib/feed";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  return { title: o?.title ?? "투자 아이디어" };
}

/** 투자 아이디어 상세 (사용자 2026-11-04): 핵심 요약 콜아웃 → 주가 차트(이슈 번호, 누르면 해당 이슈로) → 날짜별 히스토리 → 관련 자료·링크.
 *  히스토리가 없는 옛 아이디어는 본문(투자 아이디어·해석)을 그대로 보인다. */
export default async function OpportunityPage({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  if (!o) notFound();
  const primary = primaryOf(o);
  const [all, prices] = await Promise.all([loadOpportunities(), loadPrices(primary)]);
  const related = relatedTo(o, all);
  const others = o.companies.filter((c) => c.role !== "primary");
  const hasHistory = o.history.length > 0;
  const note = changeNote(o);
  const summary = o.interpretation?.trim();
  return <article className="fd op op-detail">
    <p className="op-back"><Link href="/">← 투자 아이디어</Link></p>
    <header className="op-dhead">
      <div className="op-card-top"><Stars5 n={o.stars} large/><CompanyLine o={o}/><OppTime o={o}/></div>
      <h1>{o.title}</h1>
      {note && !hasHistory ? <p className="op-note"><b>고친 점</b> {note}{o.published_at ? <span> · 처음 낸 날 {rel(o.published_at)}</span> : null}</p> : null}
    </header>

    {hasHistory ? <>
      {summary ? <section className="op-callout" aria-label="핵심"><h2>핵심</h2><Prose text={summary}/></section> : null}
      {prices.length > 1 ? <IdeaChart prices={prices} history={o.history} name={primary?.name ?? o.title}/> : null}
      <section className="op-sec"><h2>히스토리</h2>
        <ol className="op-hist">{o.history.map((h, i) => <li key={`${h.date}-${i}`} id={`hist-${i}`}>
          <span className="op-hist-n">{i + 1}</span>
          <div className="op-hist-body">
            <time dateTime={h.date}>{h.date.replace(/-/g, ".")}</time>
            <h3>{h.url ? <a href={h.url} target="_blank" rel="noreferrer">{h.title}</a> : h.title}</h3>
            {h.body ? <Prose text={h.body}/> : null}
          </div>
        </li>)}</ol>
      </section>
      <details className="op-more"><summary>아이디어 전문</summary><Prose text={o.idea}/></details>
    </> : <>
      <section className="op-sec"><h2>투자 아이디어</h2><Prose text={o.idea}/></section>
      {summary ? <section className="op-sec"><h2>해석</h2><Prose text={summary}/></section> : null}
      {prices.length > 1 ? <IdeaChart prices={prices} history={[]} name={primary?.name ?? o.title}/> : null}
    </>}

    {others.length ? <section className="op-sec"><h2>관련 기업</h2>
      <ul className="op-cos">{others.map((c, i) => <li key={`${c.name}-${i}`}><b>{c.name}</b>{c.ticker ? <span>{[c.ticker, marketKo(c.exchange)].filter(Boolean).join(" · ")}</span> : null}</li>)}</ul>
    </section> : null}
    {related.length ? <section className="op-sec"><h2>같은 흐름의 아이디어</h2>
      <ul className="op-rel">{related.map((r) => <li key={r.opportunity_key}><Link href={`/opportunities/${r.opportunity_key}`}>{r.title}</Link></li>)}</ul>
    </section> : null}
    <section className="op-sec"><h2>관련 자료</h2><EvidenceList items={o.evidence}/></section>
  </article>;
}
