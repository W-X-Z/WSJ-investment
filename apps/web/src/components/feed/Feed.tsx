import Link from "next/link";
import { CONFIDENCE_KO, IDEA_TYPE, ROLE_KO, SCENARIO_KO, TREND_KO, liveUpside, money, pct, usdB, verification, verificationText, watchItems, type CompanyFacts, type PriceCtx, type Valuation } from "@/lib/ideas";
import { REL_KO, ecoLabel, rel, shortName, type FeedIdea, type IdeaView } from "@/lib/feed";

/** ★ 를 글자로 (배지 없이). ★ 는 확신이 아니라 검증 단계 — ★1 가설 · ★2 부분 확인 · ★3 확인 (ADR-0020). */
export const STAR_KO: Record<number, string> = { 1: "가설", 2: "부분 확인", 3: "확인" };
export function StarText({ n }: { n: number }) {
  return <span className="fd-stars" title={`검증 단계: ${STAR_KO[n] ?? n} (★1 가설 · ★2 부분 확인 · ★3 확인)`} aria-label={`검증 단계 ${STAR_KO[n] ?? n}`}>{"★".repeat(n)}<i>{"★".repeat(Math.max(0, 3 - n))}</i></span>;
}

/** 각주 번호 — 칩 대신 [1][2]. href 가 있으면 상세 화면의 출처로 간다. */
export function Cites({ ns, href }: { ns: number[]; href?: string }) {
  if (!ns.length) return null;
  return <sup className="fd-cite">{ns.map((n) => <a key={n} href={`${href ?? ""}#ref-${n}`}>{n}</a>)}</sup>;
}

/** 한 줄 메타: ★ · 변화 · 유형 · 생태계 — 모두 텍스트. */
export function MetaLine({ idea }: { idea: IdeaView }) {
  const t = idea.shownTrend;
  const trend = t && TREND_KO[t] ? <b className={`fd-trend fd-trend-${t}`}>{TREND_KO[t]}</b> : null;
  const parts = [IDEA_TYPE[idea.type]?.label ?? idea.type, ...idea.ecosystems.map((e) => ecoLabel(e))].filter(Boolean);
  return <div className="fd-meta"><StarText n={idea.stars}/>{trend ? <> · {trend}</> : null} · {parts.join(" · ")}</div>;
}

/** 근거의 나이 — 기업 직접 근거가 없으면 그 사실을 먼저 말한다. */
export function Freshness({ idea }: { idea: IdeaView }) {
  return <span className="fd-fresh">
    {idea.companyAt ? <span className={rel(idea.companyAt) === "오늘" || rel(idea.companyAt) === "어제" ? "fd-hot" : ""}>기업 근거 {rel(idea.companyAt)}</span>
      : <span className="fd-warn">기업 직접 근거 없음</span>}
    {idea.industryAt ? <> · 업계 근거 {rel(idea.industryAt)}</> : null}
  </span>;
}

/** 목표주가 블록 (ADR-0023): 목표주가 = 12개월 확률가중 기대 주가, 범위 = 약세~강세 내재 주가. 오늘 종가가 있으면 여력을 다시 계산한다.
 *  모형 산출이지 권유가 아니다 — 카드 하단 문구로 밝힌다. 평가가 없으면 '목표주가 산출 전'. */
export function TargetPrice({ v, facts, compact }: { v: Valuation | null; facts: CompanyFacts | null; compact?: boolean }) {
  if (!v) return <p className="fd-tp fd-tp-none"><span className="fd-tp-label">목표주가</span><span>산출 전{facts?.market_cap_usd != null ? ` · 시총 ${usdB(facts.market_cap_usd)}` : ""}</span>
    <small>주가·재무가 모이면 다음 실행에서 산출합니다</small></p>;
  const live = liveUpside(v, facts?.close);
  const up = live.upside;
  const tone = up >= 50 ? "hi" : up >= 15 ? "mid" : up > -15 ? "flat" : "lo";
  const bear = v.scenarios.find((s) => s.name === "bear"), bull = v.scenarios.find((s) => s.name === "bull");
  return <div className={`fd-tp fd-tp-${tone}`}>
    <span className="fd-tp-label">목표주가 <small>{v.horizon_months}개월</small></span>
    <b className="fd-tp-price">{money(v.expected_price, v.currency)}</b>
    <b className="fd-tp-up">{pct(up)}</b>
    <span className="fd-tp-now">현재 {money(live.price, v.currency)}{live.live && facts?.price_as_of ? <small> {facts.price_as_of.slice(5).replace("-", "/")}</small> : null}</span>
    <span className="fd-tp-conf">{CONFIDENCE_KO[v.confidence]}</span>
    {bear && bull ? <span className="fd-tp-range" title={v.scenarios.map((s) => `${SCENARIO_KO[s.name]} ${Math.round(s.prob * 100)}% → ${money(s.implied_price, v.currency)}`).join(" · ")}>
      약세 {money(bear.implied_price, v.currency)} <i>~</i> 강세 {money(bull.implied_price, v.currency)}</span> : null}
    {!compact ? <time dateTime={v.as_of}>{v.as_of.slice(5).replace("-", "/")} 산출</time> : null}
  </div>;
}

/** 리서치 리포트 카드 (ADR-0023): 기업 → 목표주가 → 투자 아이디어(제목·요지) → 데이터 근거 2개 → 예측 상태. 상세는 클릭. */
const CHANGE_KO: Record<string, string> = { new: "새 리포트", strengthened: "강화", weakened: "약화" };
const md = (d?: string | null) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "");
const ROLE_ORDER: Record<string, number> = { primary: 0, peer: 1, competitor: 2, customer: 3, displaced: 4 };
const EXCHANGE_KO: Record<string, string> = { KRX: "KOSPI", KOSDAQ: "KOSDAQ", NYSE: "NYSE", Nasdaq: "Nasdaq", "NYSE American": "NYSE Am." };

/** 카드에 올릴 근거 2개: 주 기업 직접 근거가 있는 단계 → 최근 사실 단계. 날짜 접두는 떼고 각주 날짜를 앞에 둔다. */
function keyFacts(idea: FeedIdea, n = 2): { date: string | null; text: string; n: number }[] {
  const steps = idea.chain.map((st) => {
    const refs = st.evidence.map((e) => idea.refs.find((r) => r.url === e.url && r.title === e.title)).filter((r): r is NonNullable<typeof r> => !!r);
    const s = refs.filter((r) => r.id.startsWith("S"));
    const direct = s.some((r) => r.rel === "direct");
    const date = s.map((r) => r.date?.slice(0, 10) ?? "").filter(Boolean).sort().at(-1) ?? null;
    return { st, direct, date, n: refs[0]?.n ?? 0, fact: s.length > 0 };
  }).filter((x) => x.fact);
  steps.sort((a, b) => Number(b.direct) - Number(a.direct) || (b.date ?? "").localeCompare(a.date ?? ""));
  return steps.slice(0, n).map((x) => ({ date: x.date, text: x.st.claim.replace(/^\d{1,2}\/\d{1,2}\s*(일\s*)?/, "").replace(/\s*\(추론\)$/, ""), n: x.n }));
}

export function ReportCard({ idea, changed }: { idea: FeedIdea; changed: boolean }) {
  const href = `/ideas/${idea.idea_key}`;
  const tag = changed && idea.shownTrend ? CHANGE_KO[idea.shownTrend] : null;
  const p = idea.primary;
  const others = [...idea.companies].filter((c) => c.id !== idea.primary_company).sort((a, b) => (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9)).slice(0, 3);
  const eco = idea.ecosystems.map((e) => ecoLabel(e)).filter(Boolean).join(" · ");
  const facts = keyFacts(idea);
  const ver = verification(idea);
  const nPred = watchItems(idea).length;
  const mcap = idea.facts?.market_cap_usd ?? idea.valuation?.market_cap_usd ?? null;
  return <article className="fd-rc">
    <header className="fd-rc-head">
      <div className="fd-rc-co">
        <Link href={href} className="fd-rc-name">{p ? shortName(p) : idea.title}</Link>
        <span className="fd-rc-tk">{[p?.ticker, p?.exchange ? EXCHANGE_KO[p.exchange] ?? p.exchange : null, mcap != null ? `시총 ${usdB(mcap)}` : null, eco].filter(Boolean).join(" · ")}</span>
      </div>
      <div className="fd-rc-meta"><StarText n={idea.stars}/><span>{STAR_KO[idea.stars]}</span>{tag ? <b className={`fd-trend fd-trend-${idea.shownTrend}`}>{tag}</b> : null}</div>
    </header>
    <TargetPrice v={idea.valuation} facts={idea.facts} compact/>
    <h3><Link href={href}>{idea.title}</Link></h3>
    <p className="fd-rc-thesis">{idea.thesis}</p>
    {facts.length ? <ul className="fd-rc-facts">{facts.map((f, i) => <li key={i}><time>{md(f.date)}</time><span>{f.text}</span><Cites ns={f.n ? [f.n] : []} href={href}/></li>)}</ul> : null}
    <footer className="fd-rc-foot">
      <span>{nPred ? `예측 ${nPred}건 · ${verificationText(ver)}` : "예측 없음"}</span>
      <span>근거 {idea.evidence_count}건</span>
      {others.length ? <span className="fd-rc-others">{others.map((c) => `${shortName(c)}(${ROLE_KO[c.role] ?? c.role})`).join(" · ")}</span> : null}
      {idea.first_seen ? <time dateTime={idea.first_seen.slice(0, 10)}>{md(idea.first_seen)} 첫 리포트</time> : null}
    </footer>
  </article>;
}

/** 주가·시가총액 한 줄 (주 기업, 상세 화면): 시총 · 12개월 · 3개월 · 고점 대비 · 저점 대비 — 전망이 아니라 '이미 움직인 폭'.
 *  v_company_facts(실시간)가 있으면 그것을, 없으면 판단에 저장된 가격 맥락을 쓴다. 판정 꼬리표(룸 큼 등)는 붙이지 않는다 (ADR-0019). */
export function PriceLine({ facts, price }: { facts: CompanyFacts | null; price: PriceCtx | null }) {
  const p = price ?? null;
  const mcap = facts?.market_cap_usd ?? p?.market_cap_usd ?? null;
  const r12 = facts?.r12m ?? p?.r12m ?? null, hi = facts?.from_high ?? p?.from_high ?? null, lo = facts?.from_low ?? p?.from_low ?? null, r3 = facts?.r3m ?? p?.r3m ?? null;
  if (mcap == null && r12 == null && hi == null && p?.close == null) return <p className="fd-val fd-val-none">주가·시총 수집 전</p>;
  const parts = [mcap != null ? `시총 ${usdB(mcap)}` : null, r12 != null ? `12개월 ${pct(r12)}` : null, r3 != null ? `3개월 ${pct(r3)}` : null,
    hi != null ? `고점 ${pct(hi)}` : null, lo != null ? `저점 ${pct(lo)}` : null].filter(Boolean);
  return <p className="fd-val">
    <span>{parts.join(" · ")}</span>
    {facts?.price_as_of ?? p?.as_of ? <time>{(facts?.price_as_of ?? p?.as_of ?? "").slice(5).replace("-", "/")}</time> : null}
  </p>;
}

/** 상세 화면 출처 목록 (각주 대상). 층(기업 직접·관련·업계·그래프 배경)을 글자로. */
export function References({ idea }: { idea: IdeaView }) {
  return <ol className="fd-refs">{idea.refs.map((r) => <li key={r.n} id={`ref-${r.n}`}>
    <span className="fd-ref-n">{r.n}</span>
    <div>
      <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
      <div className="fd-ref-meta">{[r.date ? r.date.slice(0, 10) : null, r.publisher, REL_KO[r.rel], r.tier_ko].filter(Boolean).join(" · ")}</div>
      {r.note ? <p className="fd-ref-note">{r.note}</p> : null}
    </div>
  </li>)}</ol>;
}
