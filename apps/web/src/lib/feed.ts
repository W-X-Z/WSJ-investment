import "server-only";
import { db } from "@/lib/supabase";
import nativeNames from "@/data/company-names.json";
import { ECO_KO, liveUpside, loadFacts, loadIdeas, loadValuations, type CompanyFacts, type IdeaEvidence, type InvestmentIdea, type Valuation } from "@/lib/ideas";

const NATIVE = nativeNames as Record<string, string>;

/**
 * 홈 피드 = 아이디어 카드(제목 · 관련 기업 · 생성일 · 관련 이슈). 논리·근거·판단은 아이디어 상세에서 본다.
 * 상세의 형식: Semafor(사실 / 해석 / 반대 근거 분리), 각주식 인용(칩 대신 [1]).
 */

export type EvidenceRel = "direct" | "related" | "industry" | "background";
export const REL_KO: Record<EvidenceRel, string> = { direct: "기업 직접", related: "관련 기업", industry: "업계", background: "그래프 배경" };

/** 근거가 아이디어 주 기업에 대해 무엇인가. 엔진이 붙인 rel 을 쓰고, 예전 행은 제목에 주 기업 이름이 있는지로 본다. */
export function relOf(e: IdeaEvidence, idea: InvestmentIdea): EvidenceRel {
  if (e.rel === "direct" || e.rel === "related" || e.rel === "industry" || e.rel === "background") return e.rel;
  if (e.id.startsWith("G")) return "background";
  const p = idea.companies.find((c) => c.id === idea.primary_company);
  // 영어 이름·티커·현지어 이름(유니테스트·三井金属…) 중 하나라도 제목에 있으면 그 기업 이야기
  const names = [p?.name, p?.ticker, p?.name?.split(/[ /]/)[0], NATIVE[idea.primary_company]]
    .filter((x): x is string => !!x && (x.length >= 3 || (x.length >= 2 && /[^\x00-\x7F]/.test(x)))).map((x) => x.toLowerCase());
  const t = (e.title ?? "").toLowerCase();
  return names.some((n) => t.includes(n)) ? "direct" : "industry";
}

const day = (d?: string | null) => (d ? d.slice(0, 10) : null);
const maxDate = (xs: (string | null | undefined)[]) => xs.map(day).filter((x): x is string => !!x).sort().at(-1) ?? null;

export type IdeaView = InvestmentIdea & {
  shownTrend: string | null;  // 화면에 쓰는 변화: 새 기업 직접 근거 없이 '강화'된 행은 'industry'(업계 근거 갱신)로
  companyAt: string | null;   // 주 기업 직접 근거의 최신 날짜
  industryAt: string | null;  // 그 밖의 최근 근거 날짜
  whyNow: { text: string; rel: EvidenceRel; date: string | null; refs: number[] } | null;
  refs: (IdeaEvidence & { rel: EvidenceRel; n: number })[];   // 각주 순서대로
  primary?: InvestmentIdea["companies"][number];
};

/** 아이디어 → 화면용: 각주 번호, 기업·업계 근거 날짜, '왜 지금' 한 줄. */
export function viewIdea(idea: InvestmentIdea): IdeaView {
  const refs: IdeaView["refs"] = [];
  const num = (e: IdeaEvidence) => {
    const found = refs.find((r) => r.url === e.url && r.title === e.title);
    if (found) return found.n;
    refs.push({ ...e, rel: relOf(e, idea), n: refs.length + 1 });
    return refs.length;
  };
  idea.chain.forEach((s) => s.evidence.forEach(num));
  idea.risks.forEach((s) => s.evidence.forEach(num));
  const s = refs.filter((r) => r.id.startsWith("S"));
  const companyAt = maxDate(s.filter((r) => r.rel === "direct").map((r) => r.date));
  const industryAt = maxDate(s.filter((r) => r.rel !== "direct").map((r) => r.date));
  // 왜 지금: 주 기업 직접 근거가 있는 가장 최근 단계 → 없으면 가장 최근 근거가 있는 단계(업계)
  const steps = idea.chain.map((st) => {
    const ns = st.evidence.map(num);
    const rs = ns.map((n) => refs[n - 1]);
    const direct = rs.filter((r) => r.rel === "direct" && r.id.startsWith("S"));
    const recent = rs.filter((r) => r.id.startsWith("S"));
    return { st, ns, directAt: maxDate(direct.map((r) => r.date)), recentAt: maxDate(recent.map((r) => r.date)) };
  });
  const pick = [...steps].filter((x) => x.directAt).sort((a, b) => (b.directAt ?? "").localeCompare(a.directAt ?? ""))[0]
    ?? [...steps].filter((x) => x.recentAt).sort((a, b) => (b.recentAt ?? "").localeCompare(a.recentAt ?? ""))[0];
  // 날짜는 따로 보여 주므로 주장 맨 앞의 '10/27 ' 같은 날짜는 뺀다
  const whyNow = pick ? { text: pick.st.claim.replace(/^\d{1,2}\/\d{1,2}\s*(일\s*)?/, ""), rel: (pick.directAt ? "direct" : "industry") as EvidenceRel, date: pick.directAt ?? pick.recentAt, refs: pick.ns } : null;
  const updated = day(idea.updated_at) ?? "";
  const directFresh = !!companyAt && (Date.parse(updated) - Date.parse(companyAt)) / 864e5 <= 14;
  const shownTrend = idea.trend === "strengthened" && !directFresh ? "industry" : idea.trend ?? null;
  return { ...idea, shownTrend, companyAt, industryAt, whyNow, refs, primary: idea.companies.find((c) => c.id === idea.primary_company) ?? idea.companies[0] };
}

/** 아이디어 카드의 '관련 이슈' 한 줄: 아이디어가 근거로 쓴 업계 이슈(signal_refs)의 제목·날짜·첫 출처. */
export type RelatedIssue = { key: string; title: string; date: string | null; url?: string };
export type FeedIdea = IdeaView & { issues: RelatedIssue[]; issueCount: number; facts: CompanyFacts | null; valuation: Valuation | null; staleValuation: Valuation | null };
/** 리포트를 고쳐 쓴 뒤(updated_at) 산출한 목표주가가 없으면 지난 목표주가는 낡은 것이다 — 메인 문턱·카드에서는 '없음'으로 보고 재산출을 기다린다. */
export const isStale = (v: Valuation, idea: Pick<InvestmentIdea, "updated_at">) => {
  const made = v.created_at ? Date.parse(v.created_at) : Date.parse(`${v.as_of}T23:59:59Z`);
  return made < Date.parse(idea.updated_at) - 60_000;  // 리포트를 고쳐 쓴 시각보다 1분 넘게 앞선 산출은 그 리포트의 값이 아니다
};
export type Feed = { ideas: FeedIdea[]; source: "db" | "seed"; updatedAt: string | null; error?: string };

type IssueRow = { issue_key: string; title: string; latest_published_at: string | null; first_seen: string; sources: { url: string }[] | null };

/** 홈 피드 데이터: 활성 아이디어 + 아이디어마다 관련 이슈(최신 3개). 이슈 원문이 없으면(시드) 아이디어의 최근 근거 제목으로 대신한다. */
export async function loadFeed(): Promise<Feed> {
  const [{ ideas, source, error }, facts, valuations] = await Promise.all([loadIdeas(), loadFacts(), loadValuations()]);
  const views = ideas.map(viewIdea);
  const keys = Array.from(new Set(views.flatMap((v) => (v.signal_refs ?? []).filter((r) => !r.startsWith("events:")))));
  const byKey = new Map<string, RelatedIssue>();
  let err = error;
  if (keys.length && process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_KEY) {
    try {
      const { data, error: e } = await db("public").from("v_supply_chain_issues").select("issue_key,title,latest_published_at,first_seen,sources")
        .in("issue_key", keys).limit(500);
      for (const r of (data ?? []) as IssueRow[]) {
        byKey.set(r.issue_key, { key: r.issue_key, title: r.title, date: day(r.latest_published_at ?? r.first_seen), url: r.sources?.[0]?.url });
      }
      err = [err, e?.message].filter(Boolean).join("; ") || undefined;
    } catch (e) {
      err = e instanceof Error ? e.message : "연결 오류";
    }
  }
  const byDate = (a: RelatedIssue, b: RelatedIssue) => (b.date ?? "").localeCompare(a.date ?? "");
  const out = views.map((v): FeedIdea => {
    let iss = (v.signal_refs ?? []).map((k) => byKey.get(k)).filter((x): x is RelatedIssue => !!x);
    if (!iss.length) {  // 이슈를 못 읽었으면 아이디어 자신의 최근 근거(S)로
      const seen = new Set<string>();
      iss = v.refs.filter((r) => r.id.startsWith("S") && r.rel !== "background" && !seen.has(r.title) && seen.add(r.title))
        .map((r) => ({ key: r.id, title: r.title, date: day(r.date), url: r.url }));
    }
    iss.sort(byDate);
    const val = valuations.get(v.idea_key) ?? null;
    const stale = !!val && isStale(val, v);
    return { ...v, issues: iss.slice(0, 3), issueCount: iss.length, facts: facts.get(v.primary_company) ?? null, valuation: stale ? null : val, staleValuation: stale ? val : null };
  });
  const updatedAt = ideas.map((x) => x.updated_at).sort().at(-1) ?? null;
  return { ideas: orderByValue(out), source, updatedAt, error: err };
}

/** 메인 노출 문턱 (ADR-0023 개정 2): 근거가 약한 가설은 메인에 올리지 않는다 — ★2 이상(검증됨)이거나, 목표주가 여력이 FEED_MIN_UPSIDE 이상(기댓값이 큼)일 때만.
 *  나머지는 /ideas 의 '검토 중' 목록에만 있다. */
export const FEED_MIN_UPSIDE = 30;
export function onFeed(x: { stars: number; valuation: Valuation | null; facts: CompanyFacts | null }): boolean {
  if (x.stars >= 2) return true;
  return !!x.valuation && Math.round(liveUpside(x.valuation, x.facts?.close).upside) >= FEED_MIN_UPSIDE;  // 화면에 보이는 반올림 값 기준
}

/** 피드 순서 (ADR-0019): 가치평가가 있는 아이디어는 오늘 종가로 다시 계산한 기대 상승여력 순, 평가가 없는 아이디어는 그 뒤에 ★·근거 순. */
export function orderByValue<T extends IdeaView & { valuation: Valuation | null; facts: CompanyFacts | null }>(xs: T[]): T[] {
  const up = (x: T) => (x.valuation ? liveUpside(x.valuation, x.facts?.close).upside : null);
  return [...xs].sort((a, b) => {
    const ua = up(a), ub = up(b);
    if (ua != null && ub != null) return ub - ua || b.stars - a.stars;
    if (ua != null || ub != null) return ua != null ? -1 : 1;
    return b.stars - a.stars || (b.companyAt ?? "").localeCompare(a.companyAt ?? "") || (b.industryAt ?? "").localeCompare(a.industryAt ?? "");
  });
}

/** 같은 ★ 안에서는 기업 직접 근거가 새로운 아이디어가 위로, 그다음 업계 근거. */
export function orderIdeas<T extends IdeaView>(xs: T[]): T[] {
  return [...xs].sort((a, b) => b.stars - a.stars || (b.companyAt ?? "").localeCompare(a.companyAt ?? "")
    || (b.industryAt ?? "").localeCompare(a.industryAt ?? ""));
}

export const ecoLabel = (e?: string | null) => (e && ECO_KO[e] ? ECO_KO[e] : null);
/** 카드에 쓰는 짧은 기업 이름: 한국 상장사는 한글 이름, 긴 중화권 이름은 한자 이름, 그 밖은 Inc·Technology 같은 꼬리를 뗀다.
 *  'ASE Technology Holding' → 'ASE', 'Yunnan Lincang Xinyuan Germanium 云南锗业' → '云南锗业', 'Taiwan Semiconductor Manufacturing' → 'TSMC'. */
const TAIL = /,?\s+(Technology|Technologies|Holding|Industries|Manufacturing|Corporation|Corp\.?|Inc\.?|Co\.,?\s*Ltd\.?|Ltd\.?|plc|N\.V\.|S\.A\.|AG|SE)$/i;
const ALIAS: Record<string, string> = { TSM: "TSMC" };
export function shortName(c: { id: string; name: string; ticker?: string | null }): string {
  const native = NATIVE[c.id];
  if (native && /[가-힣]/.test(native)) return native;
  if (c.ticker && ALIAS[c.ticker]) return ALIAS[c.ticker];
  let base = c.name.split(" / ").map((s) => s.trim()).filter(Boolean).sort((a, b) => a.length - b.length)[0] ?? c.name;
  const cjk = base.match(/[\u3400-\u9fff]{2,}$/)?.[0];
  if (cjk && base.length > 18) return cjk;
  for (let prev = ""; prev !== base && base.length > 3;) { prev = base; base = base.replace(TAIL, "").trim(); }
  return base || c.name;
}

/** '오늘', '어제', '3일 전', 그보다 오래면 10/21. */
export function rel(d?: string | null): string {
  if (!d) return "없음";
  const t = new Date(`${d.slice(0, 10)}T00:00:00+09:00`).getTime();
  const today = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
  today.setHours(0, 0, 0, 0);
  const n = Math.round((today.getTime() - t) / 864e5);
  if (n <= 0) return "오늘";
  if (n === 1) return "어제";
  if (n < 8) return `${n}일 전`;
  const [, m, dd] = d.slice(0, 10).split("-");
  return `${Number(m)}/${Number(dd)}`;
}
