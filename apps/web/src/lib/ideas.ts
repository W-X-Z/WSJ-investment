import "server-only";
import seedIdeas from "@/data/ideas-seed.json";
import { db } from "@/lib/supabase";

/** AI 투자 아이디어 (ideas.investment_ideas → public.v_investment_ideas). ADR-0016. */
export type IdeaEvidence = { id: string; url: string; title: string; publisher?: string | null; date?: string | null; tier?: string | null; tier_ko?: string | null };
export type IdeaStep = { claim: string; evidence: IdeaEvidence[] };
export type IdeaCompany = { id: string; name: string; ticker?: string | null; exchange?: string | null; size_band?: string | null; role: string; why?: string };
export type InvestmentIdea = {
  idea_key: string; status?: string; trend?: string | null; type: "bottleneck" | "transition" | "confirmation" | "risk" | string;
  title: string; thesis: string; stars: number; stars_reason?: string | null; primary_company: string;
  companies: IdeaCompany[]; chain: IdeaStep[]; risks: IdeaStep[]; watch: string[]; what_changed?: string | null;
  nodes: string[]; ecosystems: string[]; signal_refs: string[]; evidence_count: number; last_signal_at?: string | null;
  first_seen?: string | null; updated_at: string; revision?: number; model?: string | null; method?: string | null; stale?: boolean;
};

export const IDEA_TYPE: Record<string, { label: string; tone: string }> = {
  bottleneck: { label: "병목 수혜", tone: "bottleneck" },
  transition: { label: "기술 전환", tone: "transition" },
  confirmation: { label: "실적·가격 확인", tone: "confirmation" },
  risk: { label: "리스크", tone: "risk" },
};
export const SIZE_KO: Record<string, string> = { micro: "초소형", small: "소형", mid: "중형", large: "대형", mega: "초대형", private: "비상장" };
export const ROLE_KO: Record<string, string> = { primary: "핵심", peer: "동종", customer: "고객", competitor: "경쟁", displaced: "피해 가능" };
export const ECO_KO: Record<string, string> = { hbm: "HBM·패키징", optics: "광통신", power: "전력·냉각" };
export const TREND_KO: Record<string, string> = { new: "새 아이디어", strengthened: "근거 강화", weakened: "근거 약화" };

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

export type CompanyEvent = { event_id: string; company_id: string; kind: string; published_at: string; title: string; url: string; publisher?: string | null; importance: number };
export const EVENT_KIND_KO: Record<string, string> = { filing: "공시", disclosure: "공시", revenue: "월매출", news: "뉴스" };

/** 아이디어 기업들의 최근 소식 (public.v_company_events, 0019). 뷰가 없으면 빈 배열. */
export async function loadCompanyEvents(ids: string[], limit = 24): Promise<CompanyEvent[]> {
  if (!ids.length || !process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const { data, error } = await db("public").from("v_company_events").select("event_id,company_id,kind,published_at,title,url,publisher,importance")
      .in("company_id", ids).order("published_at", { ascending: false }).limit(120);
    if (error || !data) return [];
    // 중요도 2 이상을 먼저, 기업마다 최대 4건
    const per = new Map<string, number>();
    return (data as CompanyEvent[]).sort((a, b) => b.importance - a.importance || b.published_at.localeCompare(a.published_at))
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
