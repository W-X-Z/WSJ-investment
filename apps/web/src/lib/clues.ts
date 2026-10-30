import "server-only";
import { db } from "@/lib/supabase";

/** 단서 (ADR-0028): 출처 목록에서 들어온 작은 소식 — 시세 기사는 수집 단계에서 빠진다. 화면에는 제목·출처·날짜·한 줄·기업만. */
export type ClueCompany = { company?: string | null; name: string; ticker?: string | null; exchange?: string | null };
export type Clue = {
  clue_id: number; url: string; title: string; summary?: string | null; published_at?: string | null; seen_at: string;
  source_name?: string | null; source_kind?: string | null; region?: string | null; companies: ClueCompany[]; note?: string | null;
};

export async function loadClues(days = 7, limit = 300): Promise<Clue[]> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const since = new Date(Date.now() - days * 864e5).toISOString();
    const { data, error } = await db("public").from("v_clues")
      .select("clue_id,url,title,summary,published_at,seen_at,source_name,source_kind,region,companies,note")
      .gte("seen_at", since).order("seen_at", { ascending: false }).limit(limit);
    if (error || !data) return [];
    return (data as Clue[]).map((c) => ({ ...c, companies: Array.isArray(c.companies) ? c.companies : [] }));
  } catch {
    return [];
  }
}

export const KIND_KO: Record<string, string> = {
  trade_press: "업계지", company_newsroom: "기업 발표", disclosure: "공시", standards: "표준", conference: "학회", research: "논문",
  release_notes: "릴리스", market_data: "시장 자료", policy: "정책", company_feed: "기업 소식", issue: "공급망 이슈",
};

/** KST 날짜 (YYYY-MM-DD) — 묶음 제목용. */
export const kstDay = (iso: string) => new Date(new Date(iso).getTime() + 9 * 36e5).toISOString().slice(0, 10);
