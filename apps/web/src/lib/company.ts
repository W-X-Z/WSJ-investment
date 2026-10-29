import "server-only";
import impactJson from "@/data/impact-index.json";
import seedJson from "@/data/ecosystem-seed.json";
import { db } from "@/lib/supabase";
import { shortName } from "@/lib/feed";
import { type InvestmentIdea } from "@/lib/ideas";
import { type Issue, nodeLabel } from "@/lib/issues";

/** 기업 위키 (ADR-0023 개정 2): 한 기업의 공급망 위치 · 시세·재무 · 이 기업에 닿는 변화 · 리포트 · 소식 · 이슈를 한 곳에. 이슈 상세의 '관련 기업'은 여기로 온다. */
type Node = { id: string; kind?: string; label: string; ecosystem?: string; also_in?: string[]; listing?: { ticker?: string; exchange?: string } | null; size_band?: string | null; role?: string };
type Edge = { from: string; to: string; relation: string };
const NODES = new Map<string, Node>(((seedJson as unknown as { nodes: Node[] }).nodes ?? []).map((n) => [n.id, n]));
const EDGES = ((seedJson as unknown as { edges: Edge[] }).edges ?? []);
const IMPACT = (impactJson as unknown as { nodes: Record<string, { companies: { company_id: string; confidence: number; direction?: string; path: string[] }[] }> }).nodes ?? {};

export type CompanyWiki = {
  id: string; name: string; label: string; ticker?: string | null; exchange?: string | null; size_band?: string | null; ecosystems: string[]; role?: string;
  supplies: { id: string; label: string; kind: string }[];                   // 공급·개발하는 부품·기술
  bottlenecks: { id: string; label: string }[];                              // 그 부품이 푸는 병목
  peers: { id: string; name: string; ticker?: string | null; inScope: boolean }[];
  customers: { id: string; name: string }[];
  reaches: { node: string; label: string; confidence: number; direction?: string; path: string[] }[];  // 이 기업에 닿는 변화 (impact-index)
};
const SCOPE = new Set(["NYSE", "Nasdaq", "NYSE American", "KRX", "KOSDAQ"]);
const short = (id: string) => { const n = NODES.get(id); return n ? shortName({ id, name: nodeLabel(id), ticker: n.listing?.ticker ?? null }) : id; };

export function companySlug(id: string): string { return id.replace(/^company:/, ""); }
export function companyId(slug: string): string { return slug.startsWith("company:") ? slug : `company:${slug}`; }

export function companyWiki(id: string): CompanyWiki | null {
  const n = NODES.get(id);
  if (!n || n.kind !== "company") return null;
  const supplyIds = new Set<string>();
  for (const e of EDGES) {
    if (e.relation === "offered_by" && e.to === id) supplyIds.add(e.from);
    if ((e.relation === "develops" || e.relation === "holds_ip") && e.from === id) supplyIds.add(e.to);
  }
  const supplies = [...supplyIds].map((s) => NODES.get(s)).filter((x): x is Node => !!x).map((x) => ({ id: x.id, label: nodeLabel(x.id), kind: x.kind ?? "" }));
  const bn = new Map<string, string>();
  for (const e of EDGES) if (e.relation === "mitigated_by" && supplyIds.has(e.to) && NODES.get(e.from)?.kind === "bottleneck") bn.set(e.from, nodeLabel(e.from));
  const peerIds = new Map<string, number>();
  for (const e of EDGES) {
    if (e.relation === "offered_by" && supplyIds.has(e.from) && e.to !== id && NODES.get(e.to)?.kind === "company") peerIds.set(e.to, (peerIds.get(e.to) ?? 0) + 1);
    if ((e.relation === "develops") && supplyIds.has(e.to) && e.from !== id && NODES.get(e.from)?.kind === "company") peerIds.set(e.from, (peerIds.get(e.from) ?? 0) + 1);
  }
  const peers = [...peerIds.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([pid]) => ({ id: pid, name: short(pid), ticker: NODES.get(pid)?.listing?.ticker ?? null, inScope: SCOPE.has(NODES.get(pid)?.listing?.exchange ?? "") }));
  const customers = EDGES.filter((e) => e.relation === "supplied_to" && e.from === id && NODES.get(e.to)?.kind === "company").slice(0, 6).map((e) => ({ id: e.to, name: short(e.to) }));
  const reaches: CompanyWiki["reaches"] = [];
  for (const [node, v] of Object.entries(IMPACT)) {
    const hit = v.companies.find((c) => c.company_id === id);
    if (hit && NODES.get(node)?.kind !== "company") reaches.push({ node, label: nodeLabel(node), confidence: hit.confidence, direction: hit.direction, path: hit.path });
  }
  reaches.sort((a, b) => b.confidence - a.confidence);
  return { id, name: short(id), label: n.label, ticker: n.listing?.ticker ?? null, exchange: n.listing?.exchange ?? null, size_band: n.size_band ?? null,
    ecosystems: [n.ecosystem, ...(n.also_in ?? [])].filter((x): x is string => !!x), role: n.role,
    supplies, bottlenecks: [...bn.entries()].map(([bid, label]) => ({ id: bid, label })), peers, customers, reaches: reaches.slice(0, 8) };
}

export type Fundamentals = { company_id: string; period: string; period_end?: string | null; revenue?: number | null; op_margin_pct?: number | null; net_margin_pct?: number | null;
  revenue_yoy_pct?: number | null; ps?: number | null; pe?: number | null; currency?: string | null; note?: string | null };
export async function loadFundamentals(id: string): Promise<Fundamentals | null> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return null;
  try {
    const { data, error } = await db("public").from("v_company_fundamentals").select("*").eq("company_id", id).order("period_end", { ascending: false }).limit(3);
    if (error || !data?.length) return null;
    const rows = data as Fundamentals[];
    const r = rows.find((x) => x.period === "ttm") ?? rows[0];
    const num = (v: unknown) => (v == null ? null : Number(v));
    return { ...r, revenue: num(r.revenue), op_margin_pct: num(r.op_margin_pct), net_margin_pct: num(r.net_margin_pct), revenue_yoy_pct: num(r.revenue_yoy_pct), ps: num(r.ps), pe: num(r.pe) };
  } catch { return null; }
}

/** 이 기업이 이름으로 나온 최근 이슈. */
export async function loadIssuesMentioning(id: string, limit = 8): Promise<Issue[]> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return [];
  try {
    const { data, error } = await db("public").from("v_supply_chain_issues").select("issue_key,title,ecosystem,event_type,importance,why_it_matters,nodes,companies,first_seen,latest_published_at,stars")
      .contains("companies", JSON.stringify([{ company_id: id }])).order("latest_published_at", { ascending: false, nullsFirst: false }).limit(limit);
    if (error || !data) return [];
    return (data as Issue[]).map((r) => ({ ...r, importance: Number(r.importance), nodes: r.nodes ?? [] }));
  } catch { return []; }
}

/** 이 기업이 주 기업인 리포트와, 관련 기업으로 들어간 리포트. */
export function reportsOf<T extends InvestmentIdea>(id: string, ideas: T[]): { primary: T[]; related: T[] } {
  return { primary: ideas.filter((x) => x.primary_company === id), related: ideas.filter((x) => x.primary_company !== id && x.companies.some((c) => c.id === id)) };
}
