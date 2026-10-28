import "server-only";
import improvementLog from "@/data/improvement-log.json";
import { db } from "@/lib/supabase";
import { seed } from "@/lib/research";
import { loadIdeas, watchItems } from "@/lib/ideas";
import { loadPrices, pxKey } from "@/lib/board";

/** 시스템 점검 (ADR-0017) — 데이터가 제대로 들어오는지, 판단이 쌓이는지, 스스로 무엇을 고쳤는지. pipeline/wsj/ecosystems/health.py 와 같은 기준. */

export type Run = { id: number; collector: string; status: string; started_at: string; finished_at?: string | null; rows_upserted: number; error?: string | null };
export type LogEntry = { date: string; kind: string; by: string; title: string; detail?: string; pr?: number };
export type Problem = { severity: 1 | 2 | 3; area: string; what: string };

const DAILY = ["issues", "company_feed", "prices", "ideas"];
const STALE_DAYS: Record<string, number> = { daily: 5, weekly: 14, monthly: 75, irregular: 120 };
const US = new Set(["Nasdaq", "NYSE", "NYSE American"]);
const MARKET: Record<string, string> = { TWSE: "대만", TPEx: "대만", KRX: "한국", KOSDAQ: "한국", SSE: "중국", SZSE: "중국", BJSE: "중국", HKEX: "홍콩", TSE: "일본" };

export function deadEndBottlenecks(): string[] {
  const nodes = new Map(seed.nodes.map((n) => [n.id, n]));
  const nxt = new Map<string, string[]>();
  const add = (a: string, b: string) => (nxt.get(a) ?? nxt.set(a, []).get(a)!).push(b);
  for (const e of seed.edges) {
    if (e.relation === "mitigated_by" || e.relation === "offered_by") add(e.from, e.to);
    else if (e.relation === "develops" || e.relation === "holds_ip") add(e.to, e.from);
  }
  const listed = (id: string) => { const n = nodes.get(id); return n?.kind === "company" && !!n.listing?.ticker && !!(n.listing as { exchange?: string }).exchange; };
  return seed.nodes.filter((n) => n.kind === "bottleneck").filter((b) => {
    let frontier = [b.id]; const seen = new Set(frontier);
    for (let h = 0; h < 2; h++) {
      const nf: string[] = [];
      for (const x of frontier) for (const y of nxt.get(x) ?? []) { if (seen.has(y)) continue; seen.add(y); if (listed(y)) return false; nf.push(y); }
      frontier = nf;
    }
    return true;
  }).map((b) => b.label);
}

async function safe<T>(q: PromiseLike<{ data: T[] | null; error: { message: string } | null }>): Promise<{ rows: T[]; missing: boolean }> {
  try { const { data, error } = await q; return { rows: error ? [] : data ?? [], missing: !!error }; } catch { return { rows: [], missing: true }; }
}

export async function loadSystem() {
  const hasDb = !!process.env.NEXT_PUBLIC_SUPABASE_URL && !!process.env.NEXT_PUBLIC_SUPABASE_KEY;
  const today = new Date();
  const [runsQ, indQ, regQ, prices, { ideas }] = await Promise.all([
    hasDb ? safe<Run>(db("public").from("v_collector_runs").select("*").order("started_at", { ascending: false }).limit(400)) : Promise.resolve({ rows: [] as Run[], missing: true }),
    hasDb ? safe<{ indicator_id: string; label: string; category: string; frequency: string; as_of: string }>(db("public").from("v_indicators").select("indicator_id,label,category,frequency,as_of")) : Promise.resolve({ rows: [], missing: true }),
    hasDb ? safe<{ indicator_id: string; label: string; category: string }>(db("public").from("v_indicator_registry").select("indicator_id,label,category")) : Promise.resolve({ rows: [], missing: true }),
    hasDb ? loadPrices() : Promise.resolve(new Map()),
    loadIdeas(),
  ]);
  const problems: Problem[] = [];
  // 수집기
  const byCollector = new Map<string, Run[]>();
  for (const r of runsQ.rows) (byCollector.get(r.collector) ?? byCollector.set(r.collector, []).get(r.collector)!).push(r);
  const collectors = [...byCollector.entries()].map(([name, rs]) => {
    const ok = rs.find((r) => r.status === "succeeded");
    const fails7 = rs.filter((r) => r.status === "failed" && Date.now() - new Date(r.started_at).getTime() < 7 * 864e5);
    return { name, lastOk: ok?.started_at ?? null, lastRows: ok?.rows_upserted ?? null, runs: rs.length, fails7: fails7.length, lastError: fails7[0]?.error ?? null, daily: DAILY.includes(name) };
  }).sort((a, b) => Number(b.daily) - Number(a.daily) || a.name.localeCompare(b.name));
  for (const c of collectors) {
    if (c.daily && (!c.lastOk || Date.now() - new Date(c.lastOk).getTime() > 2 * 864e5)) problems.push({ severity: 3, area: "데이터", what: `${c.name} 이 2일 넘게 성공하지 못함` });
    else if (c.fails7 && c.lastError) problems.push({ severity: 2, area: "데이터", what: `${c.name} 최근 7일 실패 ${c.fails7}번` });
  }
  if (runsQ.missing) problems.push({ severity: 1, area: "데이터", what: "수집 기록 뷰가 아직 없습니다 (마이그레이션 0021 적용 필요)" });
  // 지표
  const stale = indQ.rows.filter((i) => i.as_of && (today.getTime() - new Date(i.as_of).getTime()) / 864e5 > (STALE_DAYS[i.frequency] ?? 60));
  const haveVals = new Set(indQ.rows.map((i) => i.indicator_id));
  const empty = regQ.rows.filter((r) => !haveVals.has(r.indicator_id));
  const byCat = new Map<string, number>();
  for (const i of indQ.rows) byCat.set(i.category, (byCat.get(i.category) ?? 0) + 1);
  if (empty.length) problems.push({ severity: 2, area: "데이터", what: `값이 없는 지표 ${empty.length}개: ${empty.slice(0, 4).map((e) => e.label).join(", ")}` });
  if (!byCat.get("observation")) problems.push({ severity: 2, area: "온톨로지", what: "병목 상태 관측치가 아직 없습니다 — 병목이 조여지는지 숫자로 볼 수 없음" });
  // 가격
  const allListed = seed.nodes.filter((n) => n.kind === "company" && n.listing?.ticker && (n.listing as { exchange?: string }).exchange);
  const listed = allListed.filter((n) => pxKey(n));  // 가격 출처가 있는 거래소만 (유럽·인도 등은 따로 센다)
  const noSource = allListed.length - listed.length;
  const cov = new Map<string, [number, number]>();
  let covered = 0;
  for (const n of listed) {
    const ex = (n.listing as { exchange?: string }).exchange!;
    const m = US.has(ex) ? "미국" : MARKET[ex] ?? "그 밖";
    const p = prices.get(pxKey(n) ?? "");
    const fresh = !!p?.as_of && (today.getTime() - new Date(p.as_of).getTime()) / 864e5 <= 7;
    const v = cov.get(m) ?? [0, 0]; v[1]++; if (fresh) { v[0]++; covered++; } cov.set(m, v);
  }
  if (covered < listed.length * 0.6) problems.push({ severity: 2, area: "데이터", what: `최근 7일 가격이 있는 상장사 ${covered}/${listed.length}` });
  if (noSource) problems.push({ severity: 1, area: "데이터", what: `가격 출처가 없는 거래소의 상장사 ${noSource}곳 (유럽·인도·캐나다 등)` });
  // 그래프·판단
  const dead = deadEndBottlenecks();
  if (dead.length) problems.push({ severity: 3, area: "온톨로지", what: `상장사로 이어지지 않는 병목 ${dead.length}개` });
  const scores = ideas.map((x) => x.assessment?.score).filter((s): s is number => s != null);
  const record: Record<string, number> = {};
  for (const x of ideas) for (const w of watchItems(x)) record[w.status ?? "pending"] = (record[w.status ?? "pending"] ?? 0) + 1;
  const undated = ideas.reduce((a, x) => a + watchItems(x).filter((w) => !w.due).length, 0);
  if (ideas.length && scores.length < ideas.length) problems.push({ severity: 1, area: "판단", what: `점수 없는 아이디어 ${ideas.length - scores.length}건 (다음 실행에서 계산)` });
  if (undated) problems.push({ severity: 1, area: "판단", what: `날짜 없는 확인 일정 ${undated}개 — 채점할 수 없음` });
  problems.sort((a, b) => b.severity - a.severity);
  return {
    problems, collectors, runsMissing: runsQ.missing,
    indicators: { total: indQ.rows.length, registered: regQ.rows.length, stale: stale.length, empty: empty.length, byCat: [...byCat.entries()] },
    prices: { covered, listed: listed.length, noSource, byMarket: [...cov.entries()] },
    graph: { nodes: seed.nodes.length, edges: seed.edges.length, bottlenecks: seed.nodes.filter((n) => n.kind === "bottleneck").length, dead },
    judgment: { ideas: ideas.length, scores, record },
    log: (improvementLog as LogEntry[]).slice().sort((a, b) => b.date.localeCompare(a.date)),
  };
}
