import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { Cites, Freshness, MetaLine, PriceLine, References, TargetPrice } from "@/components/feed/Feed";
import { EVENT_KIND_KO, ROLE_KO, SCENARIO_KO, SIZE_KO, WATCH_STATUS_KO, liveUpside, loadCompanyEvents, loadFacts, loadIdea, loadIdeaNote, loadValuationHistory, loadValuations, money, pct, usdB, verification, verificationText, watchItems, type CompanyFacts, type IdeaEvidence, type IdeaNote, type Valuation } from "@/lib/ideas";
import { REL_KO, rel, relOf, viewIdea, type IdeaView } from "@/lib/feed";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const idea = await loadIdea((await params).id);
  return { title: idea?.title ?? "리서치 리포트" };
}

/**
 * 리서치 리포트 상세 (ADR-0023; 사실·해석·반대 근거를 나눈다):
 * 기업 · 목표주가 → 투자 아이디어(왜 지금) → 목표주가와 시나리오(추론 요약·시나리오 표·가정·깨지는 조건, ADR-0019) → 데이터 근거 → 가설의 논리(각주) → 반대 근거 → 예측·검증 → 관련 기업 최근 소식 → 출처.
 * 근거·선행 점수는 계산기로 뒤에 남고 화면에 올리지 않는다.
 */
export default async function IdeaDetail({ params }: { params: Promise<{ id: string }> }) {
  const raw = await loadIdea((await params).id);
  if (!raw) notFound();
  const idea = viewIdea(raw);
  const [events, factsMap, note, valuations, history] = await Promise.all([loadCompanyEvents(idea.companies.filter((c) => c.role !== "customer").map((c) => c.id)), loadFacts(),
    loadIdeaNote(idea.idea_key), loadValuations(), loadValuationHistory(idea.idea_key)]);
  const valuation = valuations.get(idea.idea_key) ?? null;
  // 가치평가의 근거(가정·시나리오·깨지는 조건)도 같은 각주 번호 체계에 넣는다 → 출처 목록에 함께 나온다
  const cite = (e: IdeaEvidence) => {
    const found = idea.refs.find((r) => r.url === e.url && r.title === e.title);
    if (found) return found.n;
    idea.refs.push({ ...e, rel: relOf(e, idea), n: idea.refs.length + 1 });
    return idea.refs.length;
  };
  const nameOf = new Map(idea.companies.map((c) => [c.id, c.name]));
  // 같은 URL 의 기업 소식에 원문을 확인한 요약이 있으면 그것을 쓴다 (근거의 원문 발췌보다 읽기 쉽다)
  const checked = new Map(events.filter((e) => e.text && e.verified).map((e) => [e.url, e.text as string]));
  for (const r of idea.refs) if (checked.has(r.url)) r.note = checked.get(r.url);
  const facts = idea.refs.filter((r) => r.id.startsWith("S") && (r.rel === "direct" || r.rel === "related"))
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")).slice(0, 6);
  const w = idea.whyNow;
  return <div className="fd fd-detail">
    <div className="breadcrumb"><Link href="/">리서치</Link><Icon name="chevron-right" size={13}/><span>{idea.primary?.name ?? idea.title}</span></div>
    <header className="fd-dhead">
      <p className="fd-dco"><b>{idea.primary?.name}</b>{idea.primary ? <span>{[idea.primary.ticker, idea.primary.exchange, idea.primary.size_band ? SIZE_KO[idea.primary.size_band] : null].filter(Boolean).join(" · ")}</span> : null}</p>
      <MetaLine idea={idea}/>
      <h1>{idea.title}</h1>
      <p className="fd-thesis">{idea.thesis}</p>
      <TargetPrice v={valuation} facts={factsMap.get(idea.primary_company) ?? null}/>
      <div className="fd-foot"><Freshness idea={idea}/><span>갱신 {rel(idea.updated_at)}</span></div>
    </header>

    <div className="fd-dgrid">
      <div>
        <section className="fd-dsec">
          <h2>투자 아이디어<small>왜 지금 이 기업인가</small></h2>
          {w ? <p className="fd-lead">{w.date ? <span className="fd-date">{w.date.slice(5).replace("-", "/")}</span> : null}{w.text}<Cites ns={w.refs}/></p> : null}
          {!idea.companyAt ? <p className="fd-note-warn">주 기업({idea.primary?.name}) 자신의 최근 공시·실적·수주로 확인된 근거는 아직 없습니다. 업계 신호와 공급망 구조로 세운 아이디어입니다.</p> : null}
          {idea.what_changed ? <p className="fd-changed"><b>바뀐 점</b>{idea.what_changed}</p> : null}
          {idea.stars_reason ? <p className="fd-starsreason"><b>★ 판단</b>{idea.stars_reason}</p> : null}
        </section>

        <Value idea={idea} v={valuation} facts={factsMap.get(idea.primary_company) ?? null} history={history} cite={cite}/>

        <DeepDive note={note}/>

        {facts.length ? <section className="fd-dsec">
          <h2>데이터 근거<small>주 기업·관련 기업 자신의 공시·실적·수주 — 원문에서 확인한 숫자</small></h2>
          <ul className="fd-facts">{facts.map((r) => <li key={r.n}>
            <div className="fd-ref-meta">{[r.date?.slice(0, 10), r.publisher, REL_KO[r.rel]].filter(Boolean).join(" · ")}</div>
            <p>{checked.has(r.url) ? r.note : r.title}<Cites ns={[r.n]}/></p>
          </li>)}</ul>
        </section> : null}

        <section className="fd-dsec">
          <h2>가설의 논리<small>사실은 각주, 추론은 (추론)</small></h2>
          <ol className="fd-chain">{idea.chain.map((s, i) => <li key={i} className={s.inference ? "inf" : ""}>{s.claim}<Cites ns={s.evidence.map((e) => idea.refs.find((r) => r.url === e.url && r.title === e.title)?.n ?? 0).filter(Boolean)}/></li>)}</ol>
        </section>

        <section className="fd-dsec">
          <h2>반대 근거</h2>
          <ul className="fd-risks">{idea.risks.length ? idea.risks.map((r, i) => <li key={i}>{r.claim}
            <Cites ns={r.evidence.map((e) => idea.refs.find((x) => x.url === e.url && x.title === e.title)?.n ?? 0).filter(Boolean)}/></li>) : <li>기록된 반대 근거 없음</li>}</ul>
        </section>

        {idea.watch.length ? <section className="fd-dsec">
          <h2>예측과 검증<small>가설이 맞으면 이 날짜에 이 숫자가 나온다 — 다음 실행이 채점하고, 적중 1건이면 ★2 · 2건이면 ★3 · 반증이 성립하면 가설을 버립니다 · {verificationText(verification(idea))}</small></h2>
          <ul className="fd-watch">{watchItems(idea).map((w, i) => <li key={i} className={`fd-w-${w.status ?? "pending"}`}>
            <span className="fd-w-status">{w.status === "hit" && w.direction === "weaken" ? "반증 성립" : w.status === "hit" ? "적중" : WATCH_STATUS_KO[w.status ?? "pending"] ?? w.status}</span>
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
          <div>목표주가는 모형 산출 · 투자 권유 아님</div>
        </div>
      </aside>
    </div>
  </div>;
}

/** 목표주가와 시나리오 (ADR-0019·0023): 사람이 보는 결과. 추론 요약(verdict), 시나리오 표(확률·매출·마진·배수 → 내재 시총·주가), 영향 경로, 가정(각주), 깨지는 조건,
 *  산출 이력. 그 아래에 '이미 움직인 폭'(시총·수익률)과 병목 상태 관측치. 근거·선행 점수는 그리지 않는다. */
function Value({ idea, v, facts, history, cite }: { idea: IdeaView; v: Valuation | null; facts: CompanyFacts | null;
  history: Awaited<ReturnType<typeof loadValuationHistory>>; cite: (e: IdeaEvidence) => number }) {
  const a = idea.assessment;
  const p = a?.price ?? null;
  const ctx = <>
    <PriceLine facts={facts} price={p}/>
    {facts?.market_cap_usd != null ? <p className="fd-judge-line"><b>시가총액</b>{usdB(facts.market_cap_usd)} — 발행주식 {Math.round(facts.shares_outstanding / 1e6).toLocaleString()}M주 × {facts.close?.toLocaleString()} {facts.currency}
      {facts.shares_as_of ? ` (주식수 ${facts.shares_as_of})` : ""}</p> : null}
    {a?.observations?.length ? <div className="fd-judge-line"><b>병목 상태</b><ul className="fd-obs">{a.observations.map((o) => <li key={o.indicator_id}>
      {o.label}: <strong>{o.value}{o.unit ? ` ${o.unit}` : ""}</strong> ({o.as_of}){o.source_url ? <> · <a href={o.source_url} target="_blank" rel="noreferrer">출처</a></> : null}
    </li>)}</ul></div> : null}
    {a?.bottlenecks?.length ? <p className="fd-judge-line"><b>걸린 병목</b>{a.bottlenecks.map((b, i) => <span key={b.id}>{i ? ", " : ""}
      <Link href={`/bottlenecks#${encodeURIComponent(b.id)}`}>{b.label}</Link></span>)}</p> : null}
  </>;
  if (!v) {
    return <section className="fd-dsec fd-value-sec">
      <h2>목표주가와 시나리오<small>주가·재무가 모이면 다음 아침 실행이 산출합니다 · 모형 산출이지 권유가 아님</small></h2>
      {ctx}
    </section>;
  }
  const live = liveUpside(v, facts?.close);
  const fmtBig = (x?: number | null) => (x == null ? "—" : x >= 1e12 ? `${(x / 1e12).toFixed(2)}조` : x >= 1e8 ? `${(x / 1e8).toFixed(1)}억` : x >= 1e6 ? `${(x / 1e6).toFixed(1)}M` : x.toLocaleString());
  const mult = (s: Valuation["scenarios"][number]) => (s.multiple != null && s.metric ? `${s.metric === "ps" ? "P/S" : "P/E"} ${s.multiple}` : "—");
  return <section className="fd-dsec fd-value-sec">
    <h2>목표주가와 시나리오<small>{v.as_of} 산출 · {v.horizon_months}개월 · {v.model ?? ""} · 모형 산출이지 권유가 아님</small></h2>
    <p className="fd-judge-line"><b>추론 요약</b></p>
    <p className="fd-lead">{v.verdict}</p>
    <table className="fd-sc-table">
      <thead><tr><th>시나리오</th><th>확률</th><th>매출 ({v.currency})</th><th>마진</th><th>배수</th><th>내재 시총</th><th>내재 주가</th><th>여력</th></tr></thead>
      <tbody>{v.scenarios.map((s) => <tr key={s.name} className={`fd-sc-${s.name}`}>
        <td><b>{SCENARIO_KO[s.name]}</b>{s.story ? <small>{s.story}<Cites ns={(s.evidence ?? []).map(cite)}/></small> : null}</td>
        <td>{Math.round(s.prob * 100)}%</td><td>{fmtBig(s.revenue)}</td><td>{s.margin_pct != null ? `${s.margin_pct}%` : "—"}</td><td>{mult(s)}</td>
        <td>{fmtBig(s.implied_mcap_local)}</td><td>{money(s.implied_price, v.currency)}</td>
        <td className={s.upside_pct >= 0 ? "up" : "down"}>{pct(s.upside_pct)}</td>
      </tr>)}</tbody>
      <tfoot><tr><td colSpan={6}>목표주가 = 확률 가중 기대 주가</td><td>{money(v.expected_price, v.currency)}</td><td className={live.upside >= 0 ? "up" : "down"}>{pct(live.upside)}</td></tr></tfoot>
    </table>
    {v.path?.labels?.length ? <p className="fd-ant-path">{v.path.labels.map((l, i) => <span key={i}>{i ? <i> → </i> : null}{l}</span>)}</p> : null}
    {v.path?.mechanism ? <p className="fd-judge-line"><b>왜 번지나</b>{v.path.mechanism}</p> : null}
    {v.assumptions?.length ? <div className="fd-judge-line"><b>가정</b><ul className="fd-assume">{v.assumptions.map((x, i) => <li key={i} className={x.kind === "estimate" ? "est" : ""}>
      {x.kind === "estimate" ? <em>추정</em> : null}{x.claim}<Cites ns={(x.evidence ?? []).map(cite)}/>
      {x.kind === "estimate" && x.basis ? <small> — {x.basis}</small> : null}</li>)}</ul></div> : null}
    {v.breaks?.length ? <div className="fd-judge-line"><b>깨지는 조건</b><ul className="fd-assume">{v.breaks.map((x, i) => <li key={i}>{x.claim}<Cites ns={x.evidence.map(cite)}/></li>)}</ul></div> : null}
    {history.length > 1 ? <p className="fd-judge-line"><b>산출 이력</b>{history.map((h, i) => <span key={h.as_of}>{i ? " → " : ""}{h.as_of.slice(5).replace("-", "/")} {pct(h.expected_upside_pct)}</span>)}
      {live.live && live.upside !== v.expected_upside_pct ? ` (오늘 종가 기준 ${pct(live.upside)})` : ""}</p> : null}
    {ctx}
  </section>;
}


/** 심층 분석 (ADR-0017 개정 1): 왜 병목인가(기술) → 시장 규모 → 공급 구조 → 다음 고리 → 밸류에이션 맥락 → 반대 근거 → 확인 일정.
 *  문단마다 날짜 있는 출처. 예약작업이 ★3·텐배거 후보 아이디어에 쓴다. */
function DeepDive({ note }: { note: IdeaNote | null }) {
  if (!note?.content?.sections?.length) return null;
  return <section className="fd-dsec fd-deep">
    <h2>심층 분석<small>{note.updated_at.slice(0, 10)} · {note.model ?? ""} · 숫자는 출처에 있는 것만</small></h2>
    {note.content.summary ? <p className="fd-lead">{note.content.summary}</p> : null}
    {note.content.sections.map((s) => <div key={s.id} className="fd-deep-sec">
      <h3>{s.title}</h3>
      {s.body.split(/\n{2,}/).map((para, i) => <p key={i}>{para}</p>)}
      {s.sources?.length ? <ul className="fd-deep-src">{s.sources.map((r, i) => <li key={i}>
        <a href={r.url} target="_blank" rel="noreferrer">{r.title ?? r.url}</a>{r.date ? <span> · {r.date.slice(0, 10)}</span> : null}</li>)}</ul> : null}
    </div>)}
  </section>;
}
