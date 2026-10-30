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
    return (data as Clue[]).map((c) => ({ ...c, companies: tidyCompanies(Array.isArray(c.companies) ? c.companies : []) }));
  } catch {
    return [];
  }
}

const TAIL = /\s+\(([^()]*)\)\s*$/;
const TICKER = /^[A-Z0-9][A-Z0-9.\-]{0,9}$/;

/** 기업 표시를 정리한다: 그래프 라벨의 괄호 꼬리("(TPEx 3324, 비SEC)")를 떼고, 같은 회사(같은 티커·같은/포함되는 이름)는 한 번만. */
export function tidyCompanies(list: ClueCompany[]): ClueCompany[] {
  const out: ClueCompany[] = [];
  const names: string[] = [];
  const tickers = new Set<string>();
  for (const x of list) {
    const raw = (x?.name ?? "").trim();
    if (!raw) continue;
    const tail = raw.match(TAIL)?.[1]?.split(",")[0]?.trim().split(/\s+/).pop() ?? "";
    const name = raw.replace(TAIL, "") || raw;
    const own = (x.ticker ?? "").trim().replace(/^[A-Za-z]+:/, "").toUpperCase();
    const ticker = own || (TICKER.test(tail) ? tail : "");
    const key = name.toLowerCase();
    const dupName = names.some((n) => n === key || (Math.min(n.length, key.length) >= 2 && (n.includes(key) || key.includes(n))));
    if ((ticker && tickers.has(ticker)) || dupName) continue;
    if (ticker) tickers.add(ticker);
    names.push(key);
    out.push({ ...x, name, ticker: ticker || null });
  }
  return out;
}

export const KIND_KO: Record<string, string> = {
  trade_press: "업계지", company_newsroom: "기업 발표", disclosure: "공시", standards: "표준", conference: "학회", research: "논문",
  release_notes: "릴리스", market_data: "시장 자료", policy: "정책", company_feed: "기업 소식", issue: "공급망 이슈",
};

/** KST 날짜 (YYYY-MM-DD) — 묶음 제목용. */
export const kstDay = (iso: string) => new Date(new Date(iso).getTime() + 9 * 36e5).toISOString().slice(0, 10);
