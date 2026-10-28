import "server-only";
import { db } from "@/lib/supabase";
import { seed, type GraphNode } from "@/lib/research";
import { loadIdeas, type InvestmentIdea, type PriceCtx } from "@/lib/ideas";

/** 병목 보드 (ADR-0017): 그래프의 병목마다 최근 이슈·상태 관측치·상장 공급사·가격 맥락·아이디어를 한 줄로.
 *  온톨로지를 사람이 볼 수 있게 — '어디가 조여지는지, 누가 그 길목에 있는지, 이미 아이디어가 있는지'. */

export type BoardSupplier = { id: string; name: string; ticker?: string | null; exchange?: string | null; size?: string | null; price?: PriceCtx | null;
  ideaKey?: string | null };
export type BoardState = { id: string; label: string; value: number; unit?: string | null; as_of: string; value_1m?: number | null; url?: string | null };
export type BoardIssue = { key: string; title: string; date: string; importance: number; url?: string | null };
export type BoardRow = { id: string; label: string; ecosystem?: string; activity: number; issues: BoardIssue[]; states: BoardState[];
  via: { id: string; label: string }[]; suppliers: BoardSupplier[]; ideas: { key: string; title: string; stars: number }[] };

const US = new Set(["Nasdaq", "NYSE", "NYSE American"]);
const KEYED = new Set(["TWSE", "TPEx", "KRX", "KOSDAQ", "SSE", "SZSE", "BJSE", "HKEX", "TSE"]);
export const pxKey = (n?: GraphNode | null): string | null => {
  const ex = (n?.listing as { exchange?: string | null } | undefined)?.exchange;
  const tk = n?.listing?.ticker;
  if (!ex || !tk) return null;
  if (US.has(ex)) return String(tk).toUpperCase();
  return KEYED.has(ex) ? `${ex}:${String(tk).toUpperCase()}` : null;
};
export const cleanName = (label: string) => label.split(/\s+\(/)[0];

async function safe<T>(q: PromiseLike<{ data: T[] | null; error: { message: string } | null }>): Promise<T[]> {
  try {
    const { data, error } = await q;
    return error ? [] : data ?? [];
  } catch {
    return [];
  }
}

export async function loadPrices(): Promise<Map<string, PriceCtx>> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) return new Map();
  const rows = await safe<PriceCtx & { ticker: string }>(db("public").from("v_price_context").select("*").limit(2000));
  return new Map(rows.map((r) => [r.ticker, { ...r, r1m: num(r.r1m), r3m: num(r.r3m), r12m: num(r.r12m), from_high: num(r.from_high), vol_ratio: num(r.vol_ratio) }]));
}
const num = (v: unknown) => (v == null ? null : Number(v));

export async function loadBoard(): Promise<{ rows: BoardRow[]; priceCount: number; obsCount: number }> {
  const nodes = new Map(seed.nodes.map((n) => [n.id, n]));
  const hasDb = !!process.env.NEXT_PUBLIC_SUPABASE_URL && !!process.env.NEXT_PUBLIC_SUPABASE_KEY;
  const since = new Date(Date.now() - 30 * 864e5).toISOString();
  const [issues, inds, prices, { ideas }] = await Promise.all([
    hasDb ? safe<{ issue_key: string; title: string; latest_published_at: string; importance: number; nodes: string[]; sources: { url: string }[] }>(
      db("public").from("v_supply_chain_issues").select("issue_key,title,latest_published_at,importance,nodes,sources").gte("latest_published_at", since).limit(400)) : [],
    hasDb ? safe<{ indicator_id: string; label: string; category: string; value: number; unit: string; as_of: string; value_1m: number | null; nodes: string[]; source_url: string }>(
      db("public").from("v_indicators").select("indicator_id,label,category,value,unit,as_of,value_1m,nodes,source_url").eq("category", "observation")) : [],
    hasDb ? loadPrices() : Promise.resolve(new Map<string, PriceCtx>()),
    loadIdeas(),
  ]);
  const mit = new Map<string, string[]>();
  const suppliers = new Map<string, string[]>();
  for (const e of seed.edges) {
    if (e.relation === "mitigated_by" && nodes.get(e.from)?.kind === "bottleneck") (mit.get(e.from) ?? mit.set(e.from, []).get(e.from)!).push(e.to);
    if (e.relation === "offered_by" && nodes.get(e.to)?.kind === "company") (suppliers.get(e.from) ?? suppliers.set(e.from, []).get(e.from)!).push(e.to);
  }
  const ideaOf = new Map<string, InvestmentIdea>();
  for (const x of ideas) for (const c of x.companies) if (!ideaOf.has(c.id) || x.primary_company === c.id) ideaOf.set(c.id, x);
  const rows: BoardRow[] = [];
  for (const b of seed.nodes.filter((n) => n.kind === "bottleneck")) {
    const via = mit.get(b.id) ?? [];
    const watch = new Set([b.id, ...via]);
    const iss = issues.filter((i) => (i.nodes ?? []).some((n) => watch.has(n)));
    const sts = inds.filter((i) => (i.nodes ?? []).some((n) => watch.has(n)));
    const sup = [...new Set(via.flatMap((v) => suppliers.get(v) ?? []))].map((id) => nodes.get(id)!).filter((n) => n?.listing?.ticker);
    const ids = new Set<string>();
    const bIdeas = ideas.filter((x) => (x.nodes ?? []).some((n) => watch.has(n)) || x.companies.some((c) => sup.some((s) => s.id === c.id && c.role === "primary")))
      .filter((x) => !ids.has(x.idea_key) && ids.add(x.idea_key));
    const activity = iss.reduce((a, i) => a + (i.importance ?? 1), 0) + 3 * sts.length;
    rows.push({
      id: b.id, label: b.label, ecosystem: b.ecosystem, activity,
      issues: iss.sort((a, b2) => b2.importance - a.importance).slice(0, 4).map((i) => ({ key: i.issue_key, title: i.title, date: i.latest_published_at?.slice(0, 10), importance: i.importance, url: i.sources?.[0]?.url })),
      states: sts.map((s) => ({ id: s.indicator_id, label: s.label, value: Number(s.value), unit: s.unit, as_of: s.as_of, value_1m: s.value_1m == null ? null : Number(s.value_1m), url: s.source_url })),
      via: via.map((v) => ({ id: v, label: nodes.get(v)?.label ?? v })),
      suppliers: sup.map((n) => ({ id: n.id, name: cleanName(n.label), ticker: n.listing?.ticker, exchange: (n.listing as { exchange?: string | null }).exchange, size: n.size_band,
        price: prices.get(pxKey(n) ?? "") ?? null, ideaKey: ideaOf.get(n.id)?.idea_key ?? null })),
      ideas: bIdeas.map((x) => ({ key: x.idea_key, title: x.title, stars: x.stars })),
    });
  }
  rows.sort((a, b) => b.activity - a.activity || b.ideas.length - a.ideas.length || a.label.localeCompare(b.label));
  return { rows, priceCount: prices.size, obsCount: inds.length };
}
