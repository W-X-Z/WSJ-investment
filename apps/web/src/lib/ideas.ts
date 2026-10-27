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

const order = (a: InvestmentIdea, b: InvestmentIdea) => b.stars - a.stars || b.updated_at.localeCompare(a.updated_at);

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

export function ago(iso?: string | null): string {
  if (!iso) return "";
  const d = (Date.now() - new Date(iso).getTime()) / 864e5;
  if (d < 1) return "오늘";
  if (d < 2) return "어제";
  if (d < 30) return `${Math.floor(d)}일 전`;
  return iso.slice(0, 10).replaceAll("-", ".");
}
