import "server-only";
import impactJson from "@/data/impact-index.json";
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
  research_result?: PathResearch | null;  // 조사 작업의 판정 (ADR-0024) — loadIssueHypotheses 가 붙인다
};
export type IssueHypotheses = { issue_key: string; as_of: string; paths: IssuePath[]; model?: string | null; method?: string | null };
export type PathResearch = { issue_key: string; path_id: string; as_of: string; verdict: "confirmed" | "partial" | "unconfirmed" | "no_data" | "refuted"; summary: string;
  event_ids?: string[]; sources?: { title?: string; url: string; date?: string; kind?: string }[]; created_at?: string };
export const VERDICT_KO: Record<PathResearch["verdict"], string> = { confirmed: "확인", partial: "일부 확인", unconfirmed: "미확인", no_data: "자료 없음", refuted: "반박" };
/** 출처 종류 (조사 작업이 sources[].kind 로 밝힌다 — 신뢰도는 표시하되 문턱이 아니다). */
export const SOURCE_KIND_KO: Record<string, string> = { official: "공식", customer: "고객", trade_press: "업계지", news: "언론", rumor: "소문·단서" };

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
    const hyps = (data as IssueHypotheses[]).map((h) => ({ ...h, paths: Array.isArray(h.paths) ? h.paths : [] }));
    // 조사 판정을 경로에 붙인다 (0027 전이면 뷰가 없어 조용히 넘어간다)
    try {
      let rq = db("public").from("v_path_research").select("issue_key,path_id,as_of,verdict,summary,sources,created_at");
      if (keys?.length) rq = rq.in("issue_key", keys);
      const { data: rs } = await rq.limit(1000);
      const byKey = new Map((rs as PathResearch[] | null ?? []).map((r) => [`${r.issue_key}|${r.path_id}|${r.as_of}`, r]));
      for (const h of hyps) for (const p of h.paths) p.research_result = byKey.get(`${h.issue_key}|${p.id}|${h.as_of}`) ?? null;
    } catch { /* 0027 전 */ }
    return new Map(hyps.map((h) => [h.issue_key, h]));
  } catch { return new Map(); }
}

/** 이슈 → 그 이슈를 근거로 쓴 활성 리포트(아이디어). signal_refs 에 issue_key 가 있으면 연결. */
export function ideasByIssue<T extends InvestmentIdea>(ideas: T[]): Map<string, T[]> {
  const m = new Map<string, T[]>();
  for (const x of ideas) for (const k of x.signal_refs ?? []) {
    if (k.startsWith("events:")) continue;
    m.set(k, [...(m.get(k) ?? []), x]);
  }
  return m;
}

/** 이슈의 짧은 날짜 (최신 보도일 → 처음 본 날). */
export const issueDate = (i: Issue): string | null => (i.latest_published_at ?? i.first_seen ?? null)?.slice(0, 10) ?? null;

/* ------------------------------------------------------------------ 이슈의 영향 그래프 (ADR-0023 개정 2)
 * 이슈 상세에 그리는 것은 '이웃 전부'가 아니라 **가중치가 높은 흐름**이다. 가중치 = 엔진의 경로 신뢰도(impact-index: 간선 근거 등급의 곱, 0~1) —
 * 이슈가 태깅한 노드에서 기업까지의 경로 중 상위 K 개만 그리고, 1단계 가설의 경로(LLM 이 세운 영향 경로)는 그 위에 굵게 얹는다.
 * 신뢰도는 '근거가 얼마나 단단한가'이지 '영향이 얼마나 큰가'가 아니다 — 크기는 가설 경로의 effect_pct 가 말한다. */
type ImpactEntry = { company_id: string; direction?: string; confidence: number; band?: string; path: string[]; size_band?: string | null; ticker?: string | null };
const IMPACT = (impactJson as unknown as { nodes: Record<string, { companies: ImpactEntry[] }> }).nodes ?? {};
type SeedNodeFull = SeedNode & { ecosystem?: string; listing?: { exchange?: string; ticker?: string } | null; size_band?: string | null };
const NODES_FULL = new Map<string, SeedNodeFull>(((seedJson as unknown as { nodes: SeedNodeFull[] }).nodes ?? []).map((n) => [n.id, n]));
const ID_BY_LABEL = new Map<string, string>([...NODES_FULL.values()].map((n) => [n.label, n.id]));
const SCOPE_EXCHANGES = new Set(["NYSE", "Nasdaq", "NYSE American", "KRX", "KOSDAQ"]);
export const inScope = (id: string) => SCOPE_EXCHANGES.has(NODES_FULL.get(id)?.listing?.exchange ?? "");
/** 열 = 흐름의 단계: 0 이슈가 태깅한 변화 → 1차 영향 → 2차 → … (경로에서의 자리 중 가장 깊은 것). 종류별 열이 아니라 단계별 열이라
 *  기업 → 공급사 같은 고리도 왼쪽에서 오른쪽으로 읽힌다. */
export const MAX_COL = 4;
export const colLabel = (i: number) => (i === 0 ? "변화" : `${i}차 영향`);
export type GraphNode = { id: string; label: string; kind: string; col: number; weight: number; onPath: boolean; tagged: boolean;
  company?: { inScope: boolean; ticker?: string | null; ideaKey?: string | null; direction?: string; confidence: number } };
export type GraphEdge = { from: string; to: string; weight: number; onPath: boolean; inferred?: boolean };
export type GraphPath = { ids: string[]; weight: number; kind: "index" | "hypothesis"; company: string | null; direction?: string; label?: string };
export type IssueGraph = { nodes: GraphNode[]; edges: GraphEdge[]; paths: GraphPath[]; dropped: number };

export function issueGraph(issue: Issue, hyPaths: IssuePath[], reportByCompany: Map<string, string>, k = 8): IssueGraph {
  const tagged = (issue.nodes ?? []).filter((n) => NODES_FULL.has(n) && NODES_FULL.get(n)!.kind !== "ecosystem").slice(0, 4);
  // 1) 엔진 경로: 태깅 노드마다 impact-index 의 기업 경로 (라벨 → id). 같은 기업은 가장 센 경로 하나만.
  const cand = new Map<string, GraphPath>();
  let total = 0;
  for (const t of tagged) {
    for (const e of IMPACT[t]?.companies ?? []) {
      const ids = e.path.map((l) => ID_BY_LABEL.get(l)).filter((x): x is string => !!x);
      if (ids.length < 2 || ids[ids.length - 1] !== e.company_id) continue;
      total++;
      const bonus = (inScope(e.company_id) ? 0.08 : 0) + (reportByCompany.has(e.company_id) ? 0.15 : 0);
      const w = Math.min(1, e.confidence + bonus);
      const cur = cand.get(e.company_id);
      if (!cur || w > cur.weight) cand.set(e.company_id, { ids, weight: w, kind: "index", company: e.company_id, direction: e.direction });
    }
  }
  const picked = [...cand.values()].sort((a, b) => b.weight - a.weight).slice(0, k);
  // 2) 가설 경로: 점수(12점) → 0~1. 기업이 없으면 끝 노드까지만.
  for (const p of hyPaths) {
    const ids = (p.path ?? []).filter((n) => NODES_FULL.has(n));
    if (ids.length < 2) continue;
    picked.push({ ids, weight: Math.min(1, ((p.score ?? 6) / 12)), kind: "hypothesis", company: p.company ?? null, label: p.claim,
      direction: p.effect_pct != null && p.effect_pct < 0 ? "negative" : undefined });  // 지는 쪽 경로 (effect_pct 음수) 는 기업 칸에 − 표시
  }
  // 3) 노드·간선 (가중치 = 그 간선을 지나는 경로 중 최대)
  const nodeW = new Map<string, number>(); const onPath = new Set<string>(); const depth = new Map<string, number>();
  const edges = new Map<string, GraphEdge>();
  for (const pth of picked) {
    pth.ids.forEach((id, i) => { nodeW.set(id, Math.max(nodeW.get(id) ?? 0, pth.weight)); depth.set(id, Math.min(MAX_COL, Math.max(depth.get(id) ?? 0, i))); });
    if (pth.kind === "hypothesis") pth.ids.forEach((id) => onPath.add(id));
    for (let i = 1; i < pth.ids.length; i++) {
      const a = pth.ids[i - 1], b = pth.ids[i];
      const cur = edges.get(`${a}>${b}`);
      edges.set(`${a}>${b}`, { from: a, to: b, weight: Math.max(cur?.weight ?? 0, pth.weight), onPath: (cur?.onPath ?? false) || pth.kind === "hypothesis",
        inferred: !hasEdge(a, b) });  // 그래프에 없는 고리 = 가설이 건너뛴 추론
    }
  }
  for (const t of tagged) if (!nodeW.has(t)) nodeW.set(t, 1);
  const bestFor = (id: string) => picked.find((p) => p.company === id);
  const nodes: GraphNode[] = [...nodeW.keys()].map((id) => {
    const n = NODES_FULL.get(id)!;
    const label = n.kind === "company" ? shortName({ id, name: nodeLabel(id), ticker: n.listing?.ticker ?? null }) : nodeLabel(id);
    const node: GraphNode = { id, label, kind: n.kind ?? "", col: depth.get(id) ?? 0, weight: nodeW.get(id) ?? 0, onPath: onPath.has(id), tagged: tagged.includes(id) };
    if (n.kind === "company") node.company = { inScope: inScope(id), ticker: n.listing?.ticker ?? null, ideaKey: reportByCompany.get(id) ?? null, direction: bestFor(id)?.direction, confidence: bestFor(id)?.weight ?? 0 };
    return node;
  });
  nodes.sort((a, b) => a.col - b.col || b.weight - a.weight || a.label.localeCompare(b.label));
  return { nodes, edges: [...edges.values()], paths: picked, dropped: Math.max(0, total - cand.size) + Math.max(0, cand.size - k) };
}

const EDGE_SET = new Set(((seedJson as unknown as { edges: { from: string; to: string }[] }).edges ?? []).flatMap((e) => [`${e.from}>${e.to}`, `${e.to}>${e.from}`]));
const hasEdge = (a: string, b: string) => EDGE_SET.has(`${a}>${b}`);
