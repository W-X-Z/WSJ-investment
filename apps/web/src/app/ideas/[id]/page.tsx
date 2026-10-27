import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { CompanyChip, EvidenceLinks, Freshness } from "@/components/IdeaCard";
import { Stars } from "@/components/Stars";
import { ECO_KO, EVENT_KIND_KO, IDEA_TYPE, ROLE_KO, SIZE_KO, ago, loadCompanyEvents, loadIdea } from "@/lib/ideas";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const idea = await loadIdea((await params).id);
  return { title: idea?.title ?? "투자 아이디어" };
}

/** 아이디어 상세: 결론 → 논리 단계(단계마다 출처) → 반대 근거 → 지켜볼 신호 → 관련 기업. */
export default async function IdeaDetail({ params }: { params: Promise<{ id: string }> }) {
  const idea = await loadIdea((await params).id);
  if (!idea) notFound();
  const events = await loadCompanyEvents(idea.companies.filter((c) => c.role !== "customer").map((c) => c.id));
  const nameOf = new Map(idea.companies.map((c) => [c.id, c.name]));
  const type = IDEA_TYPE[idea.type] ?? { label: idea.type, tone: "bottleneck" };
  return <div className="idetail">
    <div className="breadcrumb"><Link href="/">투자 아이디어</Link><Icon name="chevron-right" size={13}/><span>{idea.title}</span></div>
    <section className={`idetail-verdict ic-${type.tone}`}>
      <div className="ic-top">
        <Stars n={idea.stars} label/>
        <span className={`ic-type ic-type-${type.tone}`}>{type.label}</span>
        {idea.ecosystems.map((e) => <span key={e} className="ic-eco">{ECO_KO[e] ?? e}</span>)}
        <small className="ic-when"><Freshness date={idea.last_signal_at}/> · 갱신 {ago(idea.updated_at)}</small>
      </div>
      <h1>{idea.title}</h1>
      <p>{idea.thesis}</p>
      {idea.stars_reason ? <div className="idetail-why-stars">★ {idea.stars_reason}</div> : null}
      {idea.what_changed ? <div className="idetail-changed">이번에 바뀐 점 · {idea.what_changed}</div> : null}
    </section>

    <div className="idetail-grid">
      <div>
        <h2>논리</h2>
        <ol className="idetail-chain">{idea.chain.map((s, i) => <li key={i}><div className="idetail-claim">{s.claim}</div><EvidenceLinks items={s.evidence}/></li>)}</ol>

        <h2>반대 근거</h2>
        <ul className="idetail-risks">{idea.risks.length ? idea.risks.map((r, i) => <li key={i}><div>{r.claim}</div>{r.evidence.length ? <EvidenceLinks items={r.evidence}/> : null}</li>) : <li>기록된 반대 근거 없음</li>}</ul>

        <h2>지켜볼 신호</h2>
        <ul className="idetail-watch">{idea.watch.map((w, i) => <li key={i}><Icon name="target" size={14}/>{w}</li>)}</ul>

        {events.length ? <>
          <h2>관련 기업 최근 소식 <small className="idetail-sub">공시·월매출·뉴스, 최근 30일</small></h2>
          <ul className="idetail-events">{events.map((e) => <li key={e.event_id} className={e.importance >= 2 ? "ev-imp" : ""}>
            <span className="idetail-ev-date">{e.published_at.slice(5, 10).replace("-", "/")}</span>
            <span className="idetail-ev-kind">{EVENT_KIND_KO[e.kind] ?? e.kind}</span>
            <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a>
            <small>{nameOf.get(e.company_id)} · {e.publisher}</small>
          </li>)}</ul>
        </> : null}
      </div>
      <aside>
        <h2>관련 기업</h2>
        <div className="idetail-companies">{idea.companies.map((c) => <div key={c.id} className="idetail-company">
          <div className="idetail-company-top"><CompanyChip c={c} strong={c.id === idea.primary_company}/><span className="idetail-role">{ROLE_KO[c.role] ?? c.role}</span></div>
          {c.why ? <p>{c.why}</p> : null}
          <small>{[c.exchange, c.ticker, c.size_band ? SIZE_KO[c.size_band] : null].filter(Boolean).join(" · ")} · <Link href={`/map?focus=${encodeURIComponent(c.id)}`}>공급망에서 보기</Link></small>
        </div>)}</div>
        <div className="idetail-meta">
          {idea.first_seen ? <div>처음 등장 {idea.first_seen.slice(0, 10)}</div> : null}
          {idea.revision ? <div>개정 {idea.revision}회</div> : null}
          <div>{idea.method === "session" ? "세션 분석" : "자동 분석"}{idea.model ? ` · ${idea.model}` : ""}</div>
          <div>근거 {idea.evidence_count}건 · 투자 권유 아님</div>
        </div>
      </aside>
    </div>
  </div>;
}
