import "server-only";
import seedIdeas from "@/data/ideas-seed.json";
import { db } from "@/lib/supabase";

/** AI 투자 아이디어 (ideas.investment_ideas → public.v_investment_ideas). ADR-0016. */
export type IdeaEvidence = { id: string; url: string; title: string; publisher?: string | null; date?: string | null; tier?: string | null; tier_ko?: string | null;
  rel?: string | null;    // 엔진이 붙인 층: direct(기업 직접) | related | industry | background
  note?: string | null }; // 확인된 사실·발췌
export type IdeaStep = { claim: string; evidence: IdeaEvidence[] };
export type Exposure = { share_pct: number; segment?: string; basis?: string; url?: string | null; as_of?: string | null };
export type IdeaCompany = { id: string; name: string; ticker?: string | null; exchange?: string | null; size_band?: string | null; role: string; why?: string;
  exposure?: Exposure | null };
/** 확인 일정 (ADR-0017): 날짜·기준이 있는 다음 확인. 예전 행은 문자열. */
export type WatchItem = { what: string; due?: string | null; metric?: string | null; threshold?: string | null; direction?: "strengthen" | "weaken" | null;
  status?: "pending" | "hit" | "miss" | "void" | "expired" | string; graded_at?: string | null; evidence_url?: string | null; grade_note?: string | null };
export type Tenbagger = { candidate: boolean | null; reason?: string };
export type PriceCtx = { key?: string; as_of?: string; close?: number | null; r1m?: number | null; r3m?: number | null; r12m?: number | null;
  from_high?: number | null; from_low?: number | null; vol_ratio?: number | null; market_cap_usd?: number | null; flags?: string[]; tenbagger?: Tenbagger | null };
/** 상장사 밸류에이션 맥락 (public.v_company_facts, 0022): 발행주식수 × 종가 × 환율. 주가가 갱신되면 시총도 따라간다. */
export type CompanyFacts = { company_id: string; ticker: string; currency: string; shares_outstanding: number; shares_as_of?: string | null;
  close?: number | null; price_as_of?: string | null; market_cap_local?: number | null; market_cap_usd?: number | null;
  r1m?: number | null; r3m?: number | null; r12m?: number | null; from_high?: number | null; from_low?: number | null };
/** 심층 분석 메모 (ideas.idea_notes → v_idea_notes): 왜 병목인가 → 시장 규모 → 공급 구조 → 다음 고리 → 밸류에이션 맥락 → 반대 근거 → 확인 일정. */
export type NoteSection = { id: string; title: string; body: string; sources: { title?: string; url: string; date?: string | null }[] };
export type IdeaNote = { idea_key: string; kind: string; content: { summary?: string; sections: NoteSection[]; computed_at?: string }; model?: string | null; updated_at: string };
/** 선행 추론 (ADR-0017 개정 2): 변화 → 경로 → 기업. 근거 점수(확신)와 별개의 기대값 — 경로·미반영·룸·발현. */
export type Anticipation = { score: number; parts: Record<string, { pts: number; max: number; note: string }>; trigger?: string | null;
  path: string[]; path_labels: string[]; hops: number; mechanism?: string; lead_quarters?: number | null;
  effect?: { pct_of_revenue: number; basis?: string; url?: string | null; as_of?: string | null } | null; priced_in?: "none" | "partial" | "full" | null };
/** 판단 (엔진이 계산한 10점 근거 점수와 내역). 주가 전망이 아니라 근거의 강도. */
export type Assessment = { score: number; parts: Record<string, { pts: number; max: number; note: string }>; exposure?: Exposure | null;
  price?: PriceCtx | null; bottlenecks?: { id: string; label: string }[]; observations?: { indicator_id: string; label?: string; unit?: string; as_of: string;
  value?: number | null; source_url?: string | null }[]; anticipation?: Anticipation | null; computed_at?: string };
export type InvestmentIdea = {
  idea_key: string; status?: string; trend?: string | null; type: "bottleneck" | "transition" | "confirmation" | "risk" | string;
  title: string; thesis: string; stars: number; stars_reason?: string | null; primary_company: string;
  companies: IdeaCompany[]; chain: IdeaStep[]; risks: IdeaStep[]; watch: (string | WatchItem)[]; what_changed?: string | null;
  nodes: string[]; ecosystems: string[]; signal_refs: string[]; evidence_count: number; last_signal_at?: string | null;
  first_seen?: string | null; updated_at: string; revision?: number; model?: string | null; method?: string | null; stale?: boolean;
  assessment?: Assessment | null;
};

export const WATCH_STATUS_KO: Record<string, string> = { pending: "확인 전", hit: "확인됨", miss: "빗나감", void: "의미 없어짐", expired: "기한 지남" };
export const PART_KO: Record<string, string> = { company: "기업 직접 근거", confirm: "숫자 확인", structure: "병목·전환 구조", exposure: "노출 순도", counter: "최근 반대 근거" };
export const ANT_PART_KO: Record<string, string> = { path: "변화 → 기업 경로", unpriced: "아직 미반영", room: "룸 (변화 규모 ÷ 매출)", lead: "발현 시점" };
export const PRICED_KO: Record<string, string> = { none: "시장 미반영", partial: "일부 반영", full: "이미 반영" };
export const watchItems = (x: Pick<InvestmentIdea, "watch">): WatchItem[] =>
  (x.watch ?? []).map((w) => (typeof w === "string" ? { what: w, status: "pending" } : { status: "pending", ...w }));
/** 가장 가까운 확인 일정 (기한 있는 것 먼저). */
export function nextWatch(x: Pick<InvestmentIdea, "watch">): WatchItem | null {
  const ws = watchItems(x).filter((w) => (w.status ?? "pending") === "pending");
  return ws.filter((w) => w.due).sort((a, b) => (a.due ?? "").localeCompare(b.due ?? ""))[0] ?? ws[0] ?? null;
}
export const pct = (v?: number | null, digits = 0) => (v == null ? null : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`);
/** 시가총액을 읽기 쉽게: $0.64B · $12.7B · $109B. */
export const usdB = (v?: number | null) => (v == null ? null : v >= 1e11 ? `$${Math.round(v / 1e9)}B` : v >= 1e10 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e8 ? `$${(v / 1e9).toFixed(2)}B` : `$${Math.round(v / 1e6)}M`);
/** 텐배거 출발 조건 (엔진과 같은 임시값): 시총 $3B 이하 · 1년 저점 대비 3배 미만. */
export const TENBAGGER_MCAP_USD = 3e9;
export const TENBAGGER_MAX_FROM_LOW = 200;
export function tenbaggerCheck(mcap?: number | null, fromLow?: number | null): Tenbagger {
  if (mcap == null) return { candidate: null, reason: "시가총액 미확인" };
  if (mcap > TENBAGGER_MCAP_USD) return { candidate: false, reason: `시총 ${usdB(mcap)} > $${TENBAGGER_MCAP_USD / 1e9}B` };
  if (fromLow != null && fromLow >= TENBAGGER_MAX_FROM_LOW) return { candidate: false, reason: `1년 저점 대비 ${pct(fromLow)} — 이미 ${(1 + fromLow / 100).toFixed(1)}배` };
  return { candidate: true, reason: `시총 ${usdB(mcap)}${fromLow != null ? ` · 저점 대비 ${pct(fromLow)}` : ""}` };
}

/** 상장사 밸류에이션 (0022 전에는 빈 Map). */
export async function loadFacts(): Promise<Map<string, CompanyFacts>> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return new Map();
  try {
    const { data, error } = await db("public").from("v_company_facts").select("*").limit(2000);
    if (error || !data) return new Map();
    const num = (v: unknown) => (v == null ? null : Number(v));
    return new Map((data as CompanyFacts[]).map((f) => [f.company_id, { ...f, shares_outstanding: Number(f.shares_outstanding), close: num(f.close),
      market_cap_local: num(f.market_cap_local), market_cap_usd: num(f.market_cap_usd), r1m: num(f.r1m), r3m: num(f.r3m), r12m: num(f.r12m),
      from_high: num(f.from_high), from_low: num(f.from_low) }]));
  } catch { return new Map(); }
}

/** 가치평가 (ADR-0019, ideas.valuations → v_valuations): 매일 아침 LLM 이 이슈 → 영향 경로 → 기업 숫자 → 시나리오별 내재 시총·주가와 기댓값.
 *  사람이 보는 결과는 이것이다. 근거·선행 점수는 계산기로 뒤에 남는다. 모형 산출이지 권유가 아니다. */
export type ValuationScenario = { name: "bear" | "base" | "bull"; prob: number; story?: string; revenue?: number | null; margin_pct?: number | null;
  metric?: "ps" | "pe" | null; multiple?: number | null; implied_mcap_local?: number | null; implied_price: number; upside_pct: number; evidence?: IdeaEvidence[] };
export type Valuation = { idea_key: string; as_of: string; company_id: string; currency: string; price: number; price_as_of?: string | null; shares?: number | null;
  market_cap_usd?: number | null; horizon_months: number; scenarios: ValuationScenario[]; expected_price: number; expected_upside_pct: number;
  confidence: "low" | "mid" | "high"; verdict: string; assumptions: IdeaStep[]; breaks: IdeaStep[]; path?: { labels?: string[]; mechanism?: string | null } | null;
  model?: string | null; method?: string | null; prev_expected_upside_pct?: number | null; prev_as_of?: string | null; n_valuations?: number | null };
export const SCENARIO_KO: Record<string, string> = { bear: "약세", base: "기본", bull: "강세" };
export const CONFIDENCE_KO: Record<string, string> = { low: "확신 낮음", mid: "확신 중간", high: "확신 높음" };
/** 통화 기호와 자릿수: 현지 통화 그대로 (NT$42.5 · ₩12,100 · $3.00 · ¥5,129). */
const CUR_SYM: Record<string, string> = { USD: "$", TWD: "NT$", KRW: "₩", JPY: "¥", CNY: "CN¥", HKD: "HK$", EUR: "€", GBP: "£" };
export function money(v: number | null | undefined, cur: string): string {
  if (v == null) return "";
  const sym = CUR_SYM[cur] ?? `${cur} `;
  const digits = v >= 1000 ? 0 : v >= 100 ? 1 : 2;
  return `${sym}${v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}
/** 오늘 종가로 다시 계산한 상승여력: 평가 뒤 주가가 움직여도 기대 주가는 그대로, 여력만 바뀐다. 종가가 없으면 평가 당시 값. */
export function liveUpside(v: Valuation, close?: number | null): { upside: number; price: number; live: boolean } {
  const p = close != null && close > 0 ? close : v.price;
  return { upside: Math.round(10 * (100 * (v.expected_price / p - 1))) / 10, price: p, live: close != null && close > 0 };
}

/** 활성 아이디어의 최신 가치평가 (0024 전에는 빈 Map). */
export async function loadValuations(): Promise<Map<string, Valuation>> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return new Map();
  try {
    const { data, error } = await db("public").from("v_valuations").select("*").limit(500);
    if (error || !data) return new Map();
    const num = (x: unknown) => (x == null ? null : Number(x));
    return new Map((data as Valuation[]).map((v) => [v.idea_key, { ...v, price: Number(v.price), expected_price: Number(v.expected_price),
      expected_upside_pct: Number(v.expected_upside_pct), shares: num(v.shares), market_cap_usd: num(v.market_cap_usd),
      prev_expected_upside_pct: num(v.prev_expected_upside_pct), horizon_months: Number(v.horizon_months ?? 12),
      scenarios: (v.scenarios ?? []).map((s) => ({ ...s, prob: Number(s.prob), implied_price: Number(s.implied_price), upside_pct: Number(s.upside_pct) })) }]));
  } catch { return new Map(); }
}

/** 한 아이디어의 평가 이력 (오래된 순). */
export async function loadValuationHistory(key: string): Promise<{ as_of: string; price: number; expected_price: number; expected_upside_pct: number; confidence: string }[]> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const { data, error } = await db("public").from("v_valuation_history").select("as_of,price,expected_price,expected_upside_pct,confidence").eq("idea_key", key).order("as_of", { ascending: true }).limit(120);
    if (error || !data) return [];
    return (data as { as_of: string; price: number; expected_price: number; expected_upside_pct: number; confidence: string }[])
      .map((r) => ({ ...r, price: Number(r.price), expected_price: Number(r.expected_price), expected_upside_pct: Number(r.expected_upside_pct) }));
  } catch { return []; }
}

/** 아이디어의 심층 분석 메모 (0022 전에는 null). */
export async function loadIdeaNote(key: string): Promise<IdeaNote | null> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return null;
  try {
    const { data, error } = await db("public").from("v_idea_notes").select("*").eq("idea_key", key).eq("kind", "deep").maybeSingle();
    return error || !data ? null : (data as IdeaNote);
  } catch { return null; }
}

export const IDEA_TYPE: Record<string, { label: string; tone: string }> = {
  bottleneck: { label: "병목 수혜", tone: "bottleneck" },
  transition: { label: "기술 전환", tone: "transition" },
  confirmation: { label: "실적·가격 확인", tone: "confirmation" },
  risk: { label: "리스크", tone: "risk" },
};
export const SIZE_KO: Record<string, string> = { micro: "초소형", small: "소형", mid: "중형", large: "대형", mega: "초대형", private: "비상장" };
export const ROLE_KO: Record<string, string> = { primary: "핵심", peer: "동종", customer: "고객", competitor: "경쟁", displaced: "피해 가능" };
export const ECO_KO: Record<string, string> = { hbm: "HBM·패키징", optics: "광통신", power: "전력·냉각" };
export const TREND_KO: Record<string, string> = { new: "새 아이디어", strengthened: "기업 근거로 강화", weakened: "근거 약화", industry: "업계 근거 갱신" };

/** 정렬: ★ → 최신 근거 날짜 → 갱신 시각. 같은 ★ 이면 근거가 새로운 아이디어가 위로. */
const order = (a: InvestmentIdea, b: InvestmentIdea) =>
  b.stars - a.stars || (b.last_signal_at ?? "").localeCompare(a.last_signal_at ?? "") || b.updated_at.localeCompare(a.updated_at);

/** DB 의 활성 아이디어. 테이블이 아직 없거나(마이그레이션 전) 비어 있으면 리포에 묶인 시드를 쓴다. */
export async function loadIdeas(): Promise<{ ideas: InvestmentIdea[]; source: "db" | "seed"; error?: string }> {
  const seed = () => [...(seedIdeas as unknown as InvestmentIdea[])].filter((x) => (x.status ?? "active") === "active").sort(order);
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return { ideas: seed(), source: "seed" };
  try {
    const { data, error } = await db("public").from("v_investment_ideas").select("*").order("stars", { ascending: false }).order("updated_at", { ascending: false }).limit(60);
    if (error || !data?.length) return { ideas: seed(), source: "seed", error: error?.message };
    return { ideas: (data as InvestmentIdea[]).sort(order), source: "db" };
  } catch (e) {
    return { ideas: seed(), source: "seed", error: e instanceof Error ? e.message : "연결 오류" };
  }
}

export async function loadIdea(key: string): Promise<InvestmentIdea | null> {
  const { ideas } = await loadIdeas();
  return ideas.find((x) => x.idea_key === key) ?? null;
}

/** 근거 날짜 → 며칠 전 (UTC 날짜 기준). 날짜 없으면 null. */
export function ageDays(iso?: string | null): number | null {
  if (!iso) return null;
  const t = new Date(iso.length <= 10 ? `${iso}T00:00:00Z` : iso).getTime();
  return Number.isNaN(t) ? null : Math.max(0, Math.floor((Date.now() - t) / 864e5));
}

/** 근거가 최근 사실(S…)인가, 그래프 배경(G…)인가. */
export const isBackground = (e: IdeaEvidence) => e.id.startsWith("G");
export const FRESH_DAYS = 14;

export type CompanyEvent = { event_id: string; company_id: string; kind: string; published_at: string; title: string; url: string; publisher?: string | null; importance: number;
  text?: string | null; verified?: boolean | null };
export const EVENT_KIND_KO: Record<string, string> = { filing: "공시", disclosure: "공시", revenue: "월매출", news: "뉴스" };

/** 아이디어 기업들의 최근 소식 (public.v_company_events, 0019). 뷰가 없으면 빈 배열. */
export async function loadCompanyEvents(ids: string[], limit = 24): Promise<CompanyEvent[]> {
  if (!ids.length || !process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const { data, error } = await db("public").from("v_company_events").select("event_id,company_id,kind,published_at,title,url,publisher,importance,text,verified")
      .in("company_id", ids).order("published_at", { ascending: false }).limit(120);
    if (error || !data) return [];
    // 원문 확인됐거나 중요도 2 이상만 — 확인된 것 먼저, 기업마다 최대 4건
    const per = new Map<string, number>();
    return (data as CompanyEvent[]).filter((e) => (e.verified || e.importance >= 2) && !e.text?.startsWith("관련 없음"))
      .sort((a, b) => Number(!!b.verified) - Number(!!a.verified) || b.importance - a.importance || b.published_at.localeCompare(a.published_at))
      .filter((e) => { const n = per.get(e.company_id) ?? 0; per.set(e.company_id, n + 1); return n < 4; })
      .slice(0, limit).sort((a, b) => b.published_at.localeCompare(a.published_at));
  } catch {
    return [];
  }
}

export function ago(iso?: string | null): string {
  if (!iso) return "";
  const d = (Date.now() - new Date(iso).getTime()) / 864e5;
  if (d < 1) return "오늘";
  if (d < 2) return "어제";
  if (d < 30) return `${Math.floor(d)}일 전`;
  return iso.slice(0, 10).replaceAll("-", ".");
}
