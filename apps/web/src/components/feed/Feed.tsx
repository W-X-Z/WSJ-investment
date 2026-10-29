import Link from "next/link";
import { CONFIDENCE_KO, IDEA_TYPE, TREND_KO, liveUpside, money, pct, usdB, type CompanyFacts, type PriceCtx, type Valuation } from "@/lib/ideas";
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

/** 값의 띠 (ADR-0023 개정): 목표주가·여력을 숫자로, 약세~강세 범위와 현재·목표의 위치를 막대로. 말은 없다 — 읽는 법은 ? 에.
 *  막대는 로그 눈금: 양 끝이 약세·강세 내재 주가, 속이 빈 점이 현재, 찬 점이 목표, 둘 사이를 여력 색으로 잇는다. */
export function ValueBand({ v, facts, large, stale }: { v: Valuation | null; facts: CompanyFacts | null; large?: boolean; stale?: Valuation | null }) {
  if (!v) return <div className="fd-vb fd-vb-none">
    <span>{stale ? "목표주가 재산출 대기" : "목표주가 산출 전"}</span>
    {stale ? <small>이전 {money(stale.expected_price, stale.currency)} ({stale.as_of.slice(5).replace("-", "/")})</small> : facts?.market_cap_usd != null ? <small>시총 {usdB(facts.market_cap_usd)}</small> : null}
  </div>;
  const live = liveUpside(v, facts?.close);
  const up = live.upside;
  const dir = up >= 0 ? "up" : "down";
  const bear = v.scenarios.find((s) => s.name === "bear"), bull = v.scenarios.find((s) => s.name === "bull");
  const pts = [bear?.implied_price, bull?.implied_price, live.price, v.expected_price].filter((x): x is number => x != null && x > 0);
  const lo = Math.min(...pts) / 1.08, hi = Math.max(...pts) * 1.08;
  const x = (val: number) => (Math.log(val) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * 100;
  const cur = x(live.price), tgt = x(v.expected_price);
  return <div className={`fd-vb fd-vb-${dir}${large ? " fd-vb-lg" : ""}`}>
    <div className="fd-vb-num">
      <b className="fd-vb-price">{money(v.expected_price, v.currency)}</b>
      <b className="fd-vb-up">{pct(up)}</b>
      <span className="fd-vb-now">현재 {money(live.price, v.currency)}</span>
    </div>
    {bear && bull ? <div className="fd-vb-bar" aria-label={`약세 ${money(bear.implied_price, v.currency)} · 강세 ${money(bull.implied_price, v.currency)}`}>
      <svg viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
        <line x1="1" y1="5" x2="99" y2="5" className="fd-vb-track"/>
        <line x1={x(bear.implied_price)} y1="5" x2={x(bull.implied_price)} y2="5" className="fd-vb-range"/>
        <line x1={cur} y1="5" x2={tgt} y2="5" className="fd-vb-move"/>
      </svg>
      <i className="fd-vb-cur" style={{ left: `${cur}%` }}/>
      <i className="fd-vb-tgt" style={{ left: `${tgt}%` }}/>
      <span className="fd-vb-lo">{money(bear.implied_price, v.currency)}</span>
      <span className="fd-vb-hi">{money(bull.implied_price, v.currency)}</span>
    </div> : null}
    {large ? <div className="fd-vb-meta"><span>{CONFIDENCE_KO[v.confidence]}</span><span>{v.horizon_months}개월</span><time dateTime={v.as_of}>{v.as_of.slice(5).replace("-", "/")} 산출</time>{live.live && facts?.price_as_of ? <time dateTime={facts.price_as_of}>{facts.price_as_of.slice(5).replace("-", "/")} 종가</time> : null}</div> : null}
  </div>;
}

/** 리포트 카드 (ADR-0023 개정 2): 기업 → 아이디어 제목·요지 → 값의 띠. 카드 전체가 상세로 가는 하나의 링크. 변화·확신 같은 꼬리표는 없다. */
const EXCHANGE_KO: Record<string, string> = { KRX: "KOSPI", KOSDAQ: "KOSDAQ", NYSE: "NYSE", Nasdaq: "Nasdaq", "NYSE American": "NYSE" };

export function ReportCard({ idea }: { idea: FeedIdea }) {
  const p = idea.primary;
  const eco = idea.ecosystems.map((e) => ecoLabel(e)).filter(Boolean).join(" ");
  return <Link href={`/ideas/${idea.idea_key}`} className="fd-rc">
    <div className="fd-rc-row">
      <span className="fd-rc-name">{p ? shortName(p) : idea.title}</span>
      <span className="fd-rc-tk">{[p?.ticker, p?.exchange ? EXCHANGE_KO[p.exchange] ?? p.exchange : null, eco].filter(Boolean).join(" ")}</span>
      <StarText n={idea.stars}/>
      <span className="fd-rc-go" aria-hidden="true">›</span>
    </div>
    <h3>{idea.title}</h3>
    <p className="fd-rc-thesis">{idea.thesis}</p>
    <ValueBand v={idea.valuation} facts={idea.facts} stale={idea.staleValuation}/>
  </Link>;
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
