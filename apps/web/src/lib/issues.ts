import "server-only";
import seedJson from "@/data/ecosystem-seed.json";
import { db } from "@/lib/supabase";
import { type InvestmentIdea } from "@/lib/ideas";
import { shortName } from "@/lib/feed";

/**
 * 이슈 피드 (ADR-0023): 최근 공급망 이슈와 "그 이슈가 공급망에 갖는 의미".
 *  - 이슈 자체: public.v_supply_chain_issues (수집기가 쓴 요약·why_it_matters·중요도·태깅 노드)
 *  - 영향 경로: public.v_issue_hypotheses (1단계 가설 — 이슈마다 경로 ≤3, 기업이 붙은 경로는 리포트 후보; 0026 전에는 비어 있다)
 *  - 연결된 리포트: 그 이슈를 근거(signal_refs)로 쓴 활성 아이디어
 */
export type IssueSource = { url: string; title?: string; publisher?: string; published_at?: string; source_type?: string };
export type IssueCompany = { company_id: string; label?: string; direction?: "+" | "-" | "±" | string; size_band?: string | null; basis?: string | null };
export type Issue = {
  issue_key: string; ecosystem?: string | null; event_type?: string | null; title: string; summary?: string | null; why_it_matters?: string | null;
  importance: number; importance_rationale?: string | null; nodes: string[]; companies?: IssueCompany[] | null; sources?: IssueSource[] | null;
  source_count?: number | null; publisher_count?: number | null; first_seen: string; last_seen?: string | null; latest_published_at?: string | null; stars?: number | null;
};
/** 1단계 가설의 영향 경로 하나 (엔진 hypotheses.by_issue 가 저장한 그대로). */
export type IssuePath = {
  id: string; claim: string; path: string[]; path_labels?: string[]; company?: string | null; company_label?: string | null;
  effect_pct?: number | null; lead_quarters?: number | null; why_unpriced?: string | null; falsifier?: string | null; research?: string[];
  score?: number | null; criteria?: Record<string, number>; flags?: string[]; extends?: string | null; selected?: boolean; rank?: number | null;
};
export type IssueHypotheses = { issue_key: string; as_of: string; paths: IssuePath[]; model?: string | null; method?: string | null };

export const EVENT_TYPE_KO: Record<string, string> = {
  capacity: "증설·캐파", pricing: "가격", order: "수주·계약", earnings: "실적", technology: "기술", policy: "정책·규제", supply: "공급", demand: "수요",
  guidance: "가이던스", partnership: "협력", product: "제품", other: "기타",
};

type SeedNode = { id: string; kind?: string; label: string };
const NODES = new Map<string, SeedNode>(((seedJson as { nodes: SeedNode[] }).nodes ?? []).map((n) => [n.id, n]));
/** 그래프 노드 id → 짧은 한글 라벨 ("Group Up 群翊 (TPEx 6664, 비SEC)" 의 괄호 꼬리는 뗀다). */
export const nodeLabel = (id: string): string => (NODES.get(id)?.label ?? id).replace(/\s+\(.*$/, "");
export const nodeKind = (id: string): string | undefined => NODES.get(id)?.kind;

const ready = () => !!process.env.NEXT_PUBLIC_SUPABASE_URL && !!process.env.NEXT_PUBLIC_SUPABASE_KEY;

/** 최근 days 일의 이슈 (중요도 ≥ minImportance), 최신 순. */
export async function loadIssues(days = 14, minImportance = 5, limit = 80): Promise<Issue[]> {
  if (!ready()) return [];
  try {
    const since = new Date(Date.now() - days * 864e5).toISOString();
    const { data, error } = await db("public").from("v_supply_chain_issues").select("*")
      .gte("importance", minImportance).or(`latest_published_at.gte.${since},first_seen.gte.${since}`)
      .order("latest_published_at", { ascending: false, nullsFirst: false }).limit(limit);
    if (error || !data) return [];
    return (data as Issue[]).map((r) => ({ ...r, importance: Number(r.importance), nodes: r.nodes ?? [] }));
  } catch { return []; }
}

export async function loadIssue(key: string): Promise<Issue | null> {
  if (!ready()) return null;
  try {
    const { data, error } = await db("public").from("v_supply_chain_issues").select("*").eq("issue_key", key).maybeSingle();
    if (error || !data) return null;
    const r = data as Issue;
    return { ...r, importance: Number(r.importance), nodes: r.nodes ?? [] };
  } catch { return null; }
}

/** 이슈별 영향 경로 (0026 전·뷰 없음 → 빈 Map). */
export async function loadIssueHypotheses(keys?: string[]): Promise<Map<string, IssueHypotheses>> {
  if (!ready()) return new Map();
  try {
    let q = db("public").from("v_issue_hypotheses").select("issue_key,as_of,paths,model,method");
    if (keys?.length) q = q.in("issue_key", keys);
    const { data, error } = await q.limit(300);
    if (error || !data) return new Map();
    return new Map((data as IssueHypotheses[]).map((h) => [h.issue_key, { ...h, paths: Array.isArray(h.paths) ? h.paths : [] }]));
  } catch { return new Map(); }
}

/** 이슈 → 그 이슈를 근거로 쓴 활성 리포트(아이디어). signal_refs 에 issue_key 가 있으면 연결. */
export function ideasByIssue(ideas: InvestmentIdea[]): Map<string, InvestmentIdea[]> {
  const m = new Map<string, InvestmentIdea[]>();
  for (const x of ideas) for (const k of x.signal_refs ?? []) {
    if (k.startsWith("events:")) continue;
    m.set(k, [...(m.get(k) ?? []), x]);
  }
  return m;
}

/** 이슈의 짧은 날짜 (최신 보도일 → 처음 본 날). */
export const issueDate = (i: Issue): string | null => (i.latest_published_at ?? i.first_seen ?? null)?.slice(0, 10) ?? null;

/* ------------------------------------------------------------------ 이슈의 온톨로지 그래프 (ADR-0023 개정)
 * 이슈 상세에 그리는 국소 그래프: 변화(이슈가 태깅한 노드) → 병목·요구·기술 → 부품·소재·공정·장비 → 기업. 1단계 가설의 경로는 굵게.
 * 시드 그래프(ecosystem-seed.json)에서 태깅 노드로부터 2단계까지 BFS 로 모으고, 열마다 상한을 두어 읽을 수 있는 크기로 줄인다. */
type SeedEdge = { id: string; from: string; to: string; relation: string };
type SeedNodeFull = SeedNode & { ecosystem?: string; listing?: { exchange?: string; ticker?: string } | null; size_band?: string | null };
const EDGES = ((seedJson as unknown as { edges: SeedEdge[] }).edges ?? []);
const NODES_FULL = new Map<string, SeedNodeFull>(((seedJson as unknown as { nodes: SeedNodeFull[] }).nodes ?? []).map((n) => [n.id, n]));
const DRAW_RELS = new Set(["requires", "mitigated_by", "creates_bottleneck", "drives_requirement", "offered_by", "develops", "implements", "substitutes_for", "displaces", "adopts", "supplied_to", "holds_ip", "succeeds", "specified_by"]);
const SCOPE_EXCHANGES = new Set(["NYSE", "Nasdaq", "NYSE American", "KRX", "KOSDAQ"]);
export const inScope = (id: string) => SCOPE_EXCHANGES.has(NODES_FULL.get(id)?.listing?.exchange ?? "");
/** 열: 0 변화(태깅 노드) · 1 병목·요구·기술·세대 · 2 부품·소재·공정·장비·제품 · 3 기업 */
const COL_OF: Record<string, number> = { requirement: 1, bottleneck: 1, technology: 1, product_generation: 1, standard: 1, component: 2, material: 2, process: 2, equipment: 2, product: 2, company: 3 };
const KIND_PRIO: Record<string, number> = { bottleneck: 6, technology: 5, requirement: 4, product_generation: 3, process: 5, equipment: 5, component: 4, material: 4, product: 2, company: 3 };
export const COL_LABEL = ["변화", "병목·기술", "부품·공정·장비", "기업"];
export type GraphNode = { id: string; label: string; kind: string; col: number; onPath: boolean; tagged: boolean; company?: { inScope: boolean; ticker?: string | null; ideaKey?: string | null; selected?: boolean } };
export type GraphEdge = { from: string; to: string; relation: string; onPath: boolean; inferred?: boolean };
export type IssueGraph = { nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean };

export function issueGraph(issue: Issue, paths: IssuePath[], reportByCompany: Map<string, string>, caps = [4, 8, 9, 8]): IssueGraph {
  const tagged = (issue.nodes ?? []).filter((n) => NODES_FULL.has(n) && NODES_FULL.get(n)!.kind !== "ecosystem").slice(0, caps[0]);
  const onPath = new Set<string>();
  const pathPairs = new Set<string>();
  for (const p of paths) {
    const ids = (p.path ?? []).filter((n) => NODES_FULL.has(n));
    ids.forEach((n) => onPath.add(n));
    for (let i = 1; i < ids.length; i++) pathPairs.add(`${ids[i - 1]}>${ids[i]}`);
  }
  const adj = new Map<string, { other: string; e: SeedEdge }[]>();
  for (const e of EDGES) {
    if (!DRAW_RELS.has(e.relation)) continue;
    adj.set(e.from, [...(adj.get(e.from) ?? []), { other: e.to, e }]);
    adj.set(e.to, [...(adj.get(e.to) ?? []), { other: e.from, e }]);
  }
  // BFS: 태깅 노드 → 2단계. 부모를 기억해 두면 자식을 넣을 때 부모도 넣을 수 있다.
  const hop = new Map<string, number>(); const parent = new Map<string, string>();
  const queue: string[] = [];
  for (const t of tagged) { hop.set(t, 0); queue.push(t); }
  while (queue.length) {
    const cur = queue.shift()!;
    const h = hop.get(cur)!;
    if (h >= 2) continue;
    for (const { other } of adj.get(cur) ?? []) {
      if (hop.has(other)) continue;
      const n = NODES_FULL.get(other);
      if (!n || n.kind === "ecosystem") continue;
      if (n.kind === "company" && !inScope(other) && !onPath.has(other)) continue;  // 범위 밖 기업은 경로에 있을 때만
      hop.set(other, h + 1); parent.set(other, cur); queue.push(other);
    }
  }
  const score = (id: string) => {
    const n = NODES_FULL.get(id)!;
    return (onPath.has(id) ? 100 : 0) + (KIND_PRIO[n.kind ?? ""] ?? 1) + (reportByCompany.has(id) ? 30 : 0) + (n.kind === "company" && inScope(id) ? 5 : 0) - 6 * (hop.get(id) ?? 3);
  };
  const colOf = (id: string) => (tagged.includes(id) ? 0 : COL_OF[NODES_FULL.get(id)!.kind ?? ""] ?? 2);
  const chosen = new Set<string>(tagged);
  for (const id of onPath) if (NODES_FULL.has(id)) chosen.add(id);
  let truncated = false;
  for (const col of [1, 2, 3]) {
    const pool = [...hop.keys()].filter((id) => !chosen.has(id) && colOf(id) === col).sort((a, b) => score(b) - score(a));
    const room = Math.max(0, caps[col] - [...chosen].filter((id) => colOf(id) === col).length);
    pool.slice(0, room).forEach((id) => chosen.add(id));
    if (pool.length > room) truncated = true;
  }
  for (let guard = 0; guard < 4; guard++) for (const id of [...chosen]) { const p = parent.get(id); if (p && !chosen.has(p)) chosen.add(p); }  // 부모 사슬 보장
  const nodes: GraphNode[] = [...chosen].map((id) => {
    const n = NODES_FULL.get(id)!;
    const label = n.kind === "company" ? shortName({ id, name: nodeLabel(id), ticker: n.listing?.ticker ?? null }) : nodeLabel(id);
    const node: GraphNode = { id, label, kind: n.kind ?? "", col: colOf(id), onPath: onPath.has(id), tagged: tagged.includes(id) };
    if (n.kind === "company") node.company = { inScope: inScope(id), ticker: n.listing?.ticker ?? null, ideaKey: reportByCompany.get(id) ?? null, selected: paths.some((p) => p.company === id && p.selected) };
    return node;
  });
  const order = (a: GraphNode, b: GraphNode) => Number(b.onPath) - Number(a.onPath) || Number(!!b.company?.ideaKey) - Number(!!a.company?.ideaKey) || (KIND_PRIO[b.kind] ?? 0) - (KIND_PRIO[a.kind] ?? 0) || a.label.localeCompare(b.label);
  nodes.sort((a, b) => a.col - b.col || order(a, b));
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  for (const e of EDGES) {
    if (!DRAW_RELS.has(e.relation) || !chosen.has(e.from) || !chosen.has(e.to)) continue;
    const k = `${e.from}>${e.to}`;
    if (seen.has(k)) continue;
    seen.add(k);
    edges.push({ from: e.from, to: e.to, relation: e.relation, onPath: pathPairs.has(k) || pathPairs.has(`${e.to}>${e.from}`) });
  }
  for (const pair of pathPairs) {  // 경로가 그래프 간선 없이 건너뛴 고리는 점선(추론)
    const [a, b] = pair.split(">");
    if (chosen.has(a) && chosen.has(b) && !seen.has(pair) && !seen.has(`${b}>${a}`)) { edges.push({ from: a, to: b, relation: "inferred", onPath: true, inferred: true }); seen.add(pair); }
  }
  return { nodes, edges, truncated };
}
