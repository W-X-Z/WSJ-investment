import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { Cites, Freshness, MetaLine, References, ScoreText } from "@/components/feed/Feed";
import { EVENT_KIND_KO, PART_KO, ROLE_KO, SIZE_KO, WATCH_STATUS_KO, loadCompanyEvents, loadIdea, pct, watchItems } from "@/lib/ideas";
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

        <Judgment idea={idea}/>

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
          <h2>지켜볼 것<small>날짜가 오면 다음 실행이 결과를 채점합니다</small></h2>
          <ul className="fd-watch">{watchItems(idea).map((w, i) => <li key={i} className={`fd-w-${w.status ?? "pending"}`}>
            <span className="fd-w-status">{WATCH_STATUS_KO[w.status ?? "pending"] ?? w.status}</span>
            <div>
              <p>{w.due ? <span className="fd-date">{w.due}</span> : null}{w.what}
                {w.threshold ? <em> — {w.metric ? `${w.metric} ` : ""}{w.threshold}</em> : null}
                {w.direction ? <small> ({w.direction === "strengthen" ? "나오면 강화" : "나오면 약화"})</small> : null}</p>
              {w.grade_note || w.evidence_url ? <p className="fd-ref-meta">{w.grade_note}{w.evidence_url ? <> · <a href={w.evidence_url} target="_blank" rel="noreferrer">근거</a></> : null}</p> : null}
            </div>
          </li>)}</ul>
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

/** 판단: 10점 근거 점수의 내역, 노출 순도, 병목 상태 관측치, 이미 움직인 폭. 주가 전망이 아니다. */
function Judgment({ idea }: { idea: Awaited<ReturnType<typeof loadIdea>> & object }) {
  const a = idea.assessment;
  if (!a) return null;
  const order = ["company", "confirm", "structure", "exposure", "counter"];
  const p = a.price;
  return <section className="fd-dsec">
    <h2>판단<small>근거 점수 · {a.computed_at ? a.computed_at.slice(0, 10) : ""} 계산 · 주가 전망 아님</small></h2>
    <div className="fd-judge-head"><ScoreText idea={idea}/><span>★{idea.stars} — ★3 은 7점 이상, 2점 이하는 ★1</span></div>
    <ul className="fd-parts">{order.filter((k) => a.parts?.[k]).map((k) => {
      const v = a.parts[k];
      const w = v.max > 0 ? Math.max(0, v.pts) / v.max : 0;
      return <li key={k}>
        <span className="fd-part-name">{PART_KO[k] ?? k}</span>
        <span className="fd-part-bar" aria-hidden><i style={{ width: `${Math.round(w * 100)}%` }} className={v.pts < 0 ? "neg" : ""}/></span>
        <span className="fd-part-pts">{v.pts > 0 && k === "counter" ? "+" : ""}{v.pts}{v.max ? `/${v.max}` : ""}</span>
        <span className="fd-part-note">{v.note}</span>
      </li>;
    })}</ul>
    {a.exposure ? <p className="fd-judge-line"><b>노출 순도</b>{a.exposure.segment ? `${a.exposure.segment} ` : ""}매출 비중 {a.exposure.share_pct}%
      {a.exposure.basis ? ` — ${a.exposure.basis}` : ""}{a.exposure.url ? <> · <a href={a.exposure.url} target="_blank" rel="noreferrer">출처</a></> : null}</p> : null}
    {a.observations?.length ? <div className="fd-judge-line"><b>병목 상태</b><ul className="fd-obs">{a.observations.map((o) => <li key={o.indicator_id}>
      {o.label}: <strong>{o.value}{o.unit ? ` ${o.unit}` : ""}</strong> ({o.as_of}){o.source_url ? <> · <a href={o.source_url} target="_blank" rel="noreferrer">출처</a></> : null}
    </li>)}</ul></div> : null}
    {p ? <p className="fd-judge-line"><b>이미 움직인 폭</b>{[p.r1m != null ? `1개월 ${pct(p.r1m)}` : null, p.r3m != null ? `3개월 ${pct(p.r3m)}` : null,
      p.r12m != null ? `12개월 ${pct(p.r12m)}` : null, p.from_high != null ? `1년 고점 대비 ${pct(p.from_high)}` : null].filter(Boolean).join(" · ")}
      {p.as_of ? ` (${p.as_of})` : ""}{p.flags?.length ? <em> — {p.flags.join(" · ")}</em> : null}</p> : null}
    {a.bottlenecks?.length ? <p className="fd-judge-line"><b>걸린 병목</b>{a.bottlenecks.map((b, i) => <span key={b.id}>{i ? ", " : ""}
      <Link href={`/bottlenecks#${encodeURIComponent(b.id)}`}>{b.label}</Link></span>)}</p> : null}
  </section>;
}
