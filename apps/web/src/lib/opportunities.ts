import "server-only";
import { db } from "@/lib/supabase";

/** 투자 아이디어 (ADR-0028): ★1~5 · 제목 · 투자 아이디어 · 해석 · 기업 · 근거. 화면에는 결론만 — 방법론·노드 id 는 보이지 않는다. */
export type OppCompany = { company?: string | null; name: string; ticker?: string | null; exchange?: string | null; role?: string | null };
export type OppEvidence = { title: string; url: string; date?: string | null; publisher?: string | null };
/** 날짜별 이슈 — 차트의 점 하나. body 는 자세히 써도 된다(사용자 2026-11-04: 구조가 보이면 디테일은 괜찮다). */
export type OppHistoryKind = "earnings" | "deal" | "filing" | "flow" | "external" | "ours";
export type OppHistory = { date: string; title: string; body?: string | null; url?: string | null; kind?: OppHistoryKind | null };
/** 상세 화면 상단 — 핵심 4칸과 판단 스트립 (사용자 2026-11-04). 비어 있으면 interpretation 을 그대로 보인다. */
export type OppFact = { label: string; value: string; note?: string | null };
/** idea(투자 아이디어: 무엇이 바뀌고 왜 이 회사인가) · outlook(주가 전망: 이 회사의 몫과 지금 가격, 2배에 필요한 것) · risk(리스크).
 *  change·position·price 는 첫 판의 칸 — 남아 있으면 셋으로 합쳐 보인다. */
export type OppBrief = { idea?: string; outlook?: string; risk?: string; change?: string; position?: string; price?: string; facts?: OppFact[]; next?: string };
export type PricePoint = { d: string; c: number };
export type Opportunity = {
  opportunity_key: string; title: string; stars: number; idea: string; interpretation?: string | null;
  companies: OppCompany[]; evidence: OppEvidence[]; nodes: string[]; clue_refs: OppEvidence[]; history: OppHistory[]; brief: OppBrief;
  status: string; status_note?: string | null; created_at: string; updated_at: string; published_at?: string | null;
};

const MARKET_KO: Record<string, string> = { KRX: "KOSPI", KOSDAQ: "KOSDAQ", NYSE: "NYSE", Nasdaq: "Nasdaq", "NYSE American": "NYSE", TWSE: "대만", TPEx: "대만", TSE: "일본" };
export const marketKo = (x?: string | null) => (x ? MARKET_KO[x] ?? x : "");

function arr<T>(x: unknown): T[] { return Array.isArray(x) ? (x as T[]) : []; }

function normalize(r: Record<string, unknown>): Opportunity {
  return {
    ...(r as unknown as Opportunity),
    companies: arr<OppCompany>(r.companies), evidence: arr<OppEvidence>(r.evidence),
    nodes: arr<string>(r.nodes), clue_refs: arr<OppEvidence>(r.clue_refs), stars: Number(r.stars) || 1,
    history: arr<OppHistory>(r.history).filter((h) => h && typeof h.date === "string" && typeof h.title === "string")
      .sort((a, b) => a.date.localeCompare(b.date)),
    brief: r.brief && typeof r.brief === "object" && !Array.isArray(r.brief) ? (r.brief as OppBrief) : {},
  };
}

/** 낸 아이디어(active) — ★ 높은 순, 같은 ★ 안에서는 최근 순. 뷰가 없으면(0031 전) 빈 목록. */
export async function loadOpportunities(): Promise<Opportunity[]> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const { data, error } = await db("public").from("v_opportunities").select("*").eq("status", "active").limit(500);
    if (error || !data) return [];
    return (data as Record<string, unknown>[]).map(normalize)
      .sort((a, b) => b.stars - a.stars || touchedAt(b).localeCompare(touchedAt(a)));
  } catch {
    return [];
  }
}

export async function loadOpportunity(key: string): Promise<Opportunity | null> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return null;
  try {
    const { data, error } = await db("public").from("v_opportunities").select("*").eq("opportunity_key", key).maybeSingle();
    return error || !data ? null : normalize(data as Record<string, unknown>);
  } catch {
    return null;
  }
}

/** 주 기업의 일봉(최근 400일). px_daily 의 티커 표기가 시장마다 달라(미국 "FPS", 한국 "KRX:007660") 후보를 함께 묻는다. */
export async function loadPrices(c?: OppCompany | null): Promise<PricePoint[]> {
  const t = (c?.ticker ?? "").trim();
  if (!t || !process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  const ex = (c?.exchange ?? "").trim();
  const cands = [...new Set([t, `KRX:${t}`, ex ? `${ex}:${t}` : "", `${ex.toUpperCase()}:${t}`].filter(Boolean))];
  try {
    const { data, error } = await db("public").from("v_px_daily").select("ticker,trade_date,close").in("ticker", cands).order("trade_date").limit(1000);
    if (error || !data?.length) return [];
    const rows = data as { ticker: string; trade_date: string; close: number }[];
    const best = cands.find((k) => rows.some((r) => r.ticker === k)) ?? rows[0].ticker;
    return rows.filter((r) => r.ticker === best).map((r) => ({ d: r.trade_date, c: Number(r.close) }));
  } catch {
    return [];
  }
}

/** 같은 부품·병목을 지나는 다른 아이디어 (부모·자식이 아니라 공유하는 고리로 묶는다). */
export function relatedTo(o: Opportunity, all: Opportunity[]): Opportunity[] {
  const mine = new Set(o.nodes);
  if (!mine.size) return [];
  return all.filter((x) => x.opportunity_key !== o.opportunity_key && x.nodes.some((n) => mine.has(n)));
}

/** 낸 뒤에 고쳤나 (리포트·검토가 근거·★ 를 바꾸면 updated_at 만 움직인다). 한 시간 안의 차이는 내는 과정의 일부로 본다. */
export function changedAfterPublish(o: Opportunity): boolean {
  if (!o.published_at) return false;
  return Date.parse(o.updated_at) - Date.parse(o.published_at) > 36e5;
}

/** 목록 정렬·'갱신' 표시에 쓰는 시각: 고쳤으면 고친 때, 아니면 낸 때. */
export const touchedAt = (o: Opportunity) => (changedAfterPublish(o) ? o.updated_at : o.published_at ?? o.updated_at);

/** 고친 점 — status_note 의 '2026-11-03 report:' 같은 머리를 떼고 본문만. 낸 뒤에 고친 아이디어에만. */
export function changeNote(o: Opportunity): string | null {
  if (!changedAfterPublish(o) || !o.status_note) return null;
  return o.status_note.replace(/^\s*\d{4}-\d{2}-\d{2}\s+[\w가-힣]+\s*:\s*/, "").trim() || null;
}

export const primaryOf = (o: Opportunity) => o.companies.find((c) => c.role === "primary") ?? o.companies[0];

/** 카드의 한 줄 요지 = 아이디어의 첫 문장. */
export function lead(o: Opportunity): string {
  const m = o.idea.match(/^(.+?[.다])(\s|$)/);
  return (m ? m[1] : o.idea).trim();
}
