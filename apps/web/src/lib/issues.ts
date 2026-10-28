import "server-only";
import seedJson from "@/data/ecosystem-seed.json";
import { db } from "@/lib/supabase";
import { type InvestmentIdea } from "@/lib/ideas";

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
