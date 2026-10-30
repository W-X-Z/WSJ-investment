import "server-only";
import { db } from "@/lib/supabase";

/** 투자 아이디어 (ADR-0028): ★1~5 · 제목 · 투자 아이디어 · 해석 · 기업 · 근거. 화면에는 결론만 — 방법론·노드 id 는 보이지 않는다. */
export type OppCompany = { company?: string | null; name: string; ticker?: string | null; exchange?: string | null; role?: string | null };
export type OppEvidence = { title: string; url: string; date?: string | null; publisher?: string | null };
export type Opportunity = {
  opportunity_key: string; title: string; stars: number; idea: string; interpretation?: string | null;
  companies: OppCompany[]; evidence: OppEvidence[]; nodes: string[]; clue_refs: OppEvidence[];
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
  };
}

/** 낸 아이디어(active) — ★ 높은 순, 같은 ★ 안에서는 최근 순. 뷰가 없으면(0031 전) 빈 목록. */
export async function loadOpportunities(): Promise<Opportunity[]> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const { data, error } = await db("public").from("v_opportunities").select("*").eq("status", "active").limit(500);
    if (error || !data) return [];
    return (data as Record<string, unknown>[]).map(normalize)
      .sort((a, b) => b.stars - a.stars || (b.published_at ?? b.updated_at).localeCompare(a.published_at ?? a.updated_at));
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

/** 같은 부품·병목을 지나는 다른 아이디어 (부모·자식이 아니라 공유하는 고리로 묶는다). */
export function relatedTo(o: Opportunity, all: Opportunity[]): Opportunity[] {
  const mine = new Set(o.nodes);
  if (!mine.size) return [];
  return all.filter((x) => x.opportunity_key !== o.opportunity_key && x.nodes.some((n) => mine.has(n)));
}

export const primaryOf = (o: Opportunity) => o.companies.find((c) => c.role === "primary") ?? o.companies[0];

/** 카드의 한 줄 요지 = 아이디어의 첫 문장. */
export function lead(o: Opportunity): string {
  const m = o.idea.match(/^(.+?[.다])(\s|$)/);
  return (m ? m[1] : o.idea).trim();
}
