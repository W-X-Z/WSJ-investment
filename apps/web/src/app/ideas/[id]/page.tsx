import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { Cites, Freshness, MetaLine, References } from "@/components/feed/Feed";
import { EVENT_KIND_KO, ROLE_KO, SIZE_KO, loadCompanyEvents, loadIdea } from "@/lib/ideas";
import { REL_KO, rel, viewIdea } from "@/lib/feed";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const idea = await loadIdea((await params).id);
  return { title: idea?.title ?? "투자 아이디어" };
}

/**
 * 아이디어 상세 (Semafor 식으로 사실·해석·반대 근거를 나눈다):
 * 왜 지금 → 확인된 사실(기업 직접·관련 기업 근거) → 논리(각주) → 반대 근거 → 지켜볼 것 → 관련 기업 최근 소식 → 출처.
 */
export default async function IdeaDetail({ params }: { params: Promise<{ id: string }> }) {
  const raw = await loadIdea((await params).id);
  if (!raw) notFound();
  const idea = viewIdea(raw);
  const events = await loadCompanyEvents(idea.companies.filter((c) => c.role !== "customer").map((c) => c.id));
  const nameOf = new Map(idea.companies.map((c) => [c.id, c.name]));
  // 같은 URL 의 기업 소식에 원문을 확인한 요약이 있으면 그것을 쓴다 (근거의 원문 발췌보다 읽기 쉽다)
  const checked = new Map(events.filter((e) => e.text && e.verified).map((e) => [e.url, e.text as string]));
  for (const r of idea.refs) if (checked.has(r.url)) r.note = checked.get(r.url);
  const facts = idea.refs.filter((r) => r.id.startsWith("S") && (r.rel === "direct" || r.rel === "related"))
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")).slice(0, 6);
  const w = idea.whyNow;
  return <div className="fd fd-detail">
    <div className="breadcrumb"><Link href="/">오늘의 피드</Link><Icon name="chevron-right" size={13}/><span>{idea.title}</span></div>
    <header className="fd-dhead">
      <MetaLine idea={idea}/>
      <h1>{idea.title}</h1>
      <p className="fd-thesis">{idea.thesis}</p>
      <div className="fd-foot"><Freshness idea={idea}/><span>갱신 {rel(idea.updated_at)}</span></div>
    </header>

    <div className="fd-dgrid">
      <div>
        <section className="fd-dsec">
          <h2>왜 지금</h2>
          {w ? <p className="fd-lead">{w.date ? <span className="fd-date">{w.date.slice(5).replace("-", "/")}</span> : null}{w.text}<Cites ns={w.refs}/></p> : null}
          {!idea.companyAt ? <p className="fd-note-warn">주 기업({idea.primary?.name}) 자신의 최근 공시·실적·수주로 확인된 근거는 아직 없습니다. 업계 신호와 공급망 구조로 세운 아이디어입니다.</p> : null}
          {idea.what_changed ? <p className="fd-changed"><b>바뀐 점</b>{idea.what_changed}</p> : null}
          {idea.stars_reason ? <p className="fd-starsreason"><b>★ 판단</b>{idea.stars_reason}</p> : null}
        </section>

        {facts.length ? <section className="fd-dsec">
          <h2>확인된 사실<small>주 기업·관련 기업 자신의 소식</small></h2>
          <ul className="fd-facts">{facts.map((r) => <li key={r.n}>
            <div className="fd-ref-meta">{[r.date?.slice(0, 10), r.publisher, REL_KO[r.rel]].filter(Boolean).join(" · ")}</div>
            <p>{checked.has(r.url) ? r.note : r.title}<Cites ns={[r.n]}/></p>
          </li>)}</ul>
        </section> : null}

        <section className="fd-dsec">
          <h2>논리</h2>
          <ol className="fd-chain">{idea.chain.map((s, i) => <li key={i}>{s.claim}<Cites ns={s.evidence.map((e) => idea.refs.find((r) => r.url === e.url && r.title === e.title)?.n ?? 0).filter(Boolean)}/></li>)}</ol>
        </section>

        <section className="fd-dsec">
          <h2>반대 근거</h2>
          <ul className="fd-risks">{idea.risks.length ? idea.risks.map((r, i) => <li key={i}>{r.claim}
            <Cites ns={r.evidence.map((e) => idea.refs.find((x) => x.url === e.url && x.title === e.title)?.n ?? 0).filter(Boolean)}/></li>) : <li>기록된 반대 근거 없음</li>}</ul>
        </section>

        {idea.watch.length ? <section className="fd-dsec">
          <h2>지켜볼 것</h2>
          <ul className="fd-watch">{idea.watch.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </section> : null}

        {events.length ? <section className="fd-dsec">
          <h2>관련 기업 최근 소식<small>공시·월매출·뉴스 · 최근 30일</small></h2>
          <ul className="fd-events">{events.map((e) => <li key={e.event_id}>
            <div className="fd-ref-meta">{[e.published_at.slice(0, 10), nameOf.get(e.company_id), EVENT_KIND_KO[e.kind] ?? e.kind, e.publisher, e.verified ? "원문 확인" : null].filter(Boolean).join(" · ")}</div>
            {e.text && e.verified ? <p className="fd-ref-note">{e.text}</p> : null}
            <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a>
          </li>)}</ul>
        </section> : null}

        <section className="fd-dsec">
          <h2>출처<small>기업 직접 · 관련 기업 · 업계 · 그래프 배경</small></h2>
          <References idea={idea}/>
        </section>
      </div>

      <aside className="fd-aside">
        <h2>관련 기업</h2>
        <ul>{idea.companies.map((c) => <li key={c.id}>
          <div><b>{c.name}</b><span>{ROLE_KO[c.role] ?? c.role}</span></div>
          <small>{[c.exchange, c.ticker, c.size_band ? SIZE_KO[c.size_band] : null].filter(Boolean).join(" · ")} · <Link href={`/map?focus=${encodeURIComponent(c.id)}`}>공급망에서 보기</Link></small>
          {c.why ? <p>{c.why}</p> : null}
        </li>)}</ul>
        <div className="fd-aside-meta">
          {idea.first_seen ? <div>처음 등장 {idea.first_seen.slice(0, 10)}</div> : null}
          {idea.revision ? <div>개정 {idea.revision}회</div> : null}
          <div>{idea.method === "session" ? "Claude 예약작업" : "자동 분석"}{idea.model ? ` · ${idea.model}` : ""}</div>
          <div>투자 권유 아님</div>
        </div>
      </aside>
    </div>
  </div>;
}
