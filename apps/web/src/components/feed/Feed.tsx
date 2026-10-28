import Link from "next/link";
import { CONFIDENCE_KO, IDEA_TYPE, SCENARIO_KO, TREND_KO, liveUpside, money, pct, usdB, type CompanyFacts, type InvestmentIdea, type PriceCtx, type Valuation } from "@/lib/ideas";
import { REL_KO, ecoLabel, rel, shortName, type FeedIdea, type IdeaView } from "@/lib/feed";

/** ★ 를 글자로 (배지 없이). */
export function StarText({ n }: { n: number }) {
  return <span className="fd-stars" aria-label={`별 ${n}개 (3개 만점)`}>{"★".repeat(n)}<i>{"★".repeat(Math.max(0, 3 - n))}</i></span>;
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

/** 가치평가 결과 한 줄 (ADR-0019): 현재 → 기대 주가 (상승여력, 기간) · 확신. 오늘 종가가 있으면 여력을 다시 계산한다.
 *  평가가 없으면 '가치평가 전'. 점수는 그리지 않는다. */
export function ValueLine({ v, facts, detail }: { v: Valuation | null; facts: CompanyFacts | null; detail?: boolean }) {
  if (!v) return <p className="fd-value fd-value-none">가치평가 전{facts?.market_cap_usd != null ? ` · 시총 ${usdB(facts.market_cap_usd)}` : ""}</p>;
  const live = liveUpside(v, facts?.close);
  const up = live.upside;
  const tone = up >= 50 ? "hi" : up >= 15 ? "mid" : up > -15 ? "flat" : "lo";
  const sc = v.scenarios;
  return <p className={`fd-value fd-value-${tone}`}>
    <b className="fd-value-up">{pct(up)}</b>
    <span className="fd-value-px">{money(live.price, v.currency)} → {money(v.expected_price, v.currency)}<small> · {v.horizon_months}개월 기대</small></span>
    <span className="fd-value-conf">{CONFIDENCE_KO[v.confidence]}</span>
    {detail && sc.length ? <span className="fd-value-sc">{sc.map((s) => `${SCENARIO_KO[s.name]} ${pct(s.upside_pct)}`).join(" · ")}</span> : null}
    {!detail && sc.length ? <span className="fd-value-sc" title={sc.map((s) => `${SCENARIO_KO[s.name]} ${Math.round(s.prob * 100)}% → ${money(s.implied_price, v.currency)}`).join(" · ")}>
      {sc.map((s) => `${SCENARIO_KO[s.name]} ${pct(s.upside_pct)}`).join(" · ")}</span> : null}
    <time dateTime={v.as_of}>{v.as_of.slice(5).replace("-", "/")} 평가{live.live && facts?.price_as_of ? ` · ${facts.price_as_of.slice(5).replace("-", "/")} 종가` : ""}</time>
  </p>;
}

/** 피드 카드: ★·생태계·생성일 → 제목 → 가치평가 결과 → 관련 기업 → 관련 이슈. 논리·근거·시나리오는 상세에서. */
const CHANGE_KO: Record<string, string> = { new: "새로", strengthened: "강화", weakened: "약화" };
const md = (d?: string | null) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "");
const ROLE_ORDER: Record<string, number> = { primary: 0, peer: 1, competitor: 2, customer: 3, displaced: 4 };

export function IdeaCard({ idea, changed }: { idea: FeedIdea; changed: boolean }) {
  const href = `/ideas/${idea.idea_key}`;
  const tag = changed && idea.shownTrend ? CHANGE_KO[idea.shownTrend] : null;
  const cos = [...idea.companies].sort((a, b) => (a.id === idea.primary_company ? -1 : b.id === idea.primary_company ? 1 : 0)
    || (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9));
  const shown = cos.slice(0, 3);
  const eco = idea.ecosystems.map((e) => ecoLabel(e)).filter(Boolean).join(" · ");
  return <article className="fd-card">
    <div className="fd-card-top">
      <StarText n={idea.stars}/>{eco ? <span>{eco}</span> : null}{tag ? <b className={`fd-trend fd-trend-${idea.shownTrend}`}>{tag}</b> : null}
      {idea.first_seen ? <time dateTime={idea.first_seen.slice(0, 10)}>{md(idea.first_seen)} 생성</time> : null}
    </div>
    <h3><Link href={href}>{idea.title}</Link></h3>
    <ValueLine v={idea.valuation} facts={idea.facts}/>
    <dl className="fd-card-dl">
      <dt>관련 기업</dt>
      <dd><ul className="fd-chips">{shown.map((c) => <li key={c.id} className={c.id === idea.primary_company ? "on" : ""}>
        {shortName(c)}{c.ticker ? <small>{c.ticker}</small> : null}</li>)}
        {cos.length > shown.length ? <li className="more">외 {cos.length - shown.length}</li> : null}</ul></dd>
      {idea.issues.length ? <><dt>관련 이슈</dt>
        <dd><ul className="fd-card-iss">{idea.issues.map((i) => <li key={i.key}>
          <time>{md(i.date)}</time>{i.url ? <a href={i.url} target="_blank" rel="noreferrer">{i.title}</a> : <span>{i.title}</span>}</li>)}
          {idea.issueCount > idea.issues.length ? <li className="more"><Link href={href}>외 {idea.issueCount - idea.issues.length}건</Link></li> : null}</ul></dd></> : null}
    </dl>
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
