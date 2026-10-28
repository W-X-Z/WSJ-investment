import Link from "next/link";
import { IDEA_TYPE, TREND_KO, pct, tenbaggerCheck, usdB, type CompanyFacts, type InvestmentIdea, type PriceCtx } from "@/lib/ideas";
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

/** 근거 점수 (10점) — 숫자와 막대. 점수가 아직 없으면(0021 전·첫 계산 전) 아무것도 안 그린다. */
export function ScoreText({ idea }: { idea: Pick<InvestmentIdea, "assessment"> }) {
  const s = idea.assessment?.score;
  if (s == null) return null;
  return <span className={`fd-score fd-score-${s >= 7 ? "hi" : s >= 4 ? "mid" : "lo"}`} title="근거 점수: 기업 직접 근거·숫자 확인·병목 구조·노출 순도·반대 근거 (주가 전망 아님)">
    근거 {s}/10</span>;
}

/** 피드 카드: ★·생태계·생성일 → 제목 → 관련 기업 → 관련 이슈. 논리·근거·판단은 상세에서. */
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
    <Valuation facts={idea.facts} price={idea.assessment?.price ?? null}/>
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

/** 주가·시가총액 한 줄 (주 기업): 시총 · 12개월 · 고점 대비 · 저점 대비, 그리고 텐배거 출발 조건 판정.
 *  v_company_facts(실시간)가 있으면 그것을, 없으면 판단에 저장된 가격 맥락을 쓴다. 전망이 아니라 '이미 움직인 폭'. */
export function Valuation({ facts, price, detail }: { facts: CompanyFacts | null; price: PriceCtx | null; detail?: boolean }) {
  const p = price ?? null;
  const mcap = facts?.market_cap_usd ?? p?.market_cap_usd ?? null;
  const r12 = facts?.r12m ?? p?.r12m ?? null, hi = facts?.from_high ?? p?.from_high ?? null, lo = facts?.from_low ?? p?.from_low ?? null, r3 = facts?.r3m ?? p?.r3m ?? null;
  if (mcap == null && r12 == null && hi == null && p?.close == null) return <p className="fd-val fd-val-none">주가·시총 수집 전</p>;
  const tb = p?.tenbagger && p.tenbagger.candidate !== null && mcap == null ? p.tenbagger : tenbaggerCheck(mcap, lo);
  const parts = [mcap != null ? `시총 ${usdB(mcap)}` : null, r12 != null ? `12개월 ${pct(r12)}` : null, detail && r3 != null ? `3개월 ${pct(r3)}` : null,
    hi != null ? `고점 ${pct(hi)}` : null, lo != null ? `저점 ${pct(lo)}` : null].filter(Boolean);
  return <p className="fd-val">
    {tb.candidate === true ? <b className="fd-tb on" title={tb.reason}>텐배거 후보</b> : tb.candidate === false ? <b className="fd-tb off" title={tb.reason}>{lo != null && lo >= 200 ? "이미 간 종목" : "큰 회사"}</b> : null}
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
