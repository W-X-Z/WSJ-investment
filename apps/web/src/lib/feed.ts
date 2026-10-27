import "server-only";
import { db } from "@/lib/supabase";
import nativeNames from "@/data/company-names.json";
import { ECO_KO, loadIdeas, type IdeaEvidence, type InvestmentIdea } from "@/lib/ideas";
import { nodeName } from "@/lib/research";

const NATIVE = nativeNames as Record<string, string>;

/**
 * 홈 피드 = 아이디어(그래서 무엇) + 업계 이슈·확인된 기업 소식(무슨 일이 있었나). ADR-0016 개정 3.
 * 참고한 형식: Axios Smart Brevity(한 화면에 결론·왜 중요한가), Semafor(사실 / 해석 / 반대 근거 분리),
 * Particle·Techmeme(한 사건에 여러 출처를 묶고 출처는 요약 아래 텍스트로), 각주식 인용(칩 대신 [1]).
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

export type IssueItem = {
  kind: "issue"; key: string; date: string; title: string; summary: string | null; why: string | null; stars: number; ecosystem: string | null;
  publishers: string[]; sourceCount: number; url?: string; ideaKeys: string[];
};
export type EventItem = {
  kind: "event"; key: string; date: string; title: string; text: string | null; companyId: string; company?: string; url: string;
  publisher: string | null; importance: number; ecosystem: string | null; ideaKeys: string[];
  more: { title: string; url: string; publisher: string | null }[];  // 같은 날 같은 기업의 다른 출처 (Particle 식 묶음)
};
export type TimelineItem = IssueItem | EventItem;

type IssueRow = { issue_key: string; ecosystem: string | null; title: string; summary: string | null; why_it_matters: string | null; stars?: number | null;
  importance: number; sources: { url: string; publisher: string; published_at: string }[]; source_count: number; publisher_count: number;
  latest_published_at: string | null; first_seen: string };
type EventRow = { event_id: string; company_id: string; kind: string; published_at: string; title: string; url: string; publisher: string | null;
  importance: number; text?: string | null; verified?: boolean };

export type Feed = { ideas: IdeaView[]; timeline: TimelineItem[]; source: "db" | "seed"; updatedAt: string | null; error?: string };

/** 홈 피드 데이터: 활성 아이디어 + 최근 5일 업계 이슈(★2+) + 원문 확인된 기업 소식(7일). */
export async function loadFeed(): Promise<Feed> {
  const { ideas, source, error } = await loadIdeas();
  const views = ideas.map(viewIdea);
  const byIssue = new Map<string, string[]>();
  const byCompany = new Map<string, string[]>();
  for (const v of views) {
    for (const r of v.signal_refs ?? []) byIssue.set(r, [...(byIssue.get(r) ?? []), v.idea_key]);
    // 기업 소식은 그 기업이 주 기업인 아이디어에만 잇는다 (고객·경쟁사로 나온 아이디어까지 잇면 연결이 흐려진다)
    if (v.primary_company) byCompany.set(v.primary_company, [...(byCompany.get(v.primary_company) ?? []), v.idea_key]);
  }
  const nameOf = new Map(views.flatMap((v) => v.companies.map((c) => [c.id, c.name] as const)));
  const timeline: TimelineItem[] = [];
  let err = error;
  if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_KEY) {
    try {
      const client = db("public");
      const since = (d: number) => new Date(Date.now() - d * 864e5).toISOString();
      const [iss, evs] = await Promise.all([
        client.from("v_supply_chain_issues").select("issue_key,ecosystem,title,summary,why_it_matters,stars,importance,sources,source_count,publisher_count,latest_published_at,first_seen")
          .gte("latest_published_at", since(5)).gte("importance", 5).order("latest_published_at", { ascending: false }).limit(40),
        client.from("v_company_events").select("event_id,company_id,kind,published_at,title,url,publisher,importance,text,verified")
          .gte("published_at", since(7)).eq("verified", true).gte("importance", 2).order("published_at", { ascending: false }).limit(40),
      ]);
      for (const r of (iss.data ?? []) as IssueRow[]) {
        const pubs = Array.from(new Set((r.sources ?? []).map((s) => s.publisher).filter(Boolean)));
        timeline.push({ kind: "issue", key: r.issue_key, date: day(r.latest_published_at ?? r.first_seen) ?? "", title: r.title, summary: r.summary,
          why: r.why_it_matters, stars: r.stars ?? (r.importance >= 8 ? 3 : r.importance >= 5 ? 2 : 1), ecosystem: r.ecosystem, publishers: pubs,
          sourceCount: r.source_count, url: r.sources?.[0]?.url, ideaKeys: byIssue.get(r.issue_key) ?? [] });
      }
      // 같은 날 같은 기업의 소식은 한 줄로 묶는다: 확인 내용이 가장 긴 것(공시 우선)이 머리, 나머지는 출처로
      const groups = new Map<string, EventRow[]>();
      for (const r of (evs.data ?? []) as EventRow[]) {
        if (r.text?.startsWith("관련 없음")) continue;
        const k = `${day(r.published_at)}|${r.company_id}`;
        groups.set(k, [...(groups.get(k) ?? []), r]);
      }
      for (const rows of groups.values()) {
        const [head, ...rest] = [...rows].sort((a, b) => (b.kind === "news" ? 0 : 1) - (a.kind === "news" ? 0 : 1) || (b.text?.length ?? 0) - (a.text?.length ?? 0));
        timeline.push({ kind: "event", key: head.event_id, date: day(head.published_at) ?? "", title: head.title, text: head.text ?? null, companyId: head.company_id,
          company: nameOf.get(head.company_id) ?? cleanLabel(nodeName(head.company_id)), url: head.url, publisher: head.publisher,
          importance: Math.max(...rows.map((r) => r.importance)), ecosystem: null, ideaKeys: byCompany.get(head.company_id) ?? [],
          more: rest.map((r) => ({ title: r.title, url: r.url, publisher: r.publisher })) });
      }
      err = [err, iss.error?.message, evs.error?.message].filter(Boolean).join("; ") || undefined;
    } catch (e) {
      err = e instanceof Error ? e.message : "연결 오류";
    }
  }
  // 같은 날 안에서는 기업 소식(사실) → 업계 이슈(★순)
  timeline.sort((a, b) => b.date.localeCompare(a.date) || (a.kind === b.kind ? 0 : a.kind === "event" ? -1 : 1)
    || (b.kind === "issue" && a.kind === "issue" ? b.stars - a.stars : 0));
  const updatedAt = ideas.map((x) => x.updated_at).sort().at(-1) ?? null;
  return { ideas: views, timeline, source, updatedAt, error: err };
}

/** 같은 ★ 안에서는 기업 직접 근거가 새로운 아이디어가 위로, 그다음 업계 근거. */
export function orderIdeas(xs: IdeaView[]): IdeaView[] {
  return [...xs].sort((a, b) => b.stars - a.stars || (b.companyAt ?? "").localeCompare(a.companyAt ?? "")
    || (b.industryAt ?? "").localeCompare(a.industryAt ?? ""));
}

export const ecoLabel = (e?: string | null) => (e && ECO_KO[e] ? ECO_KO[e] : null);
/** 'Shenzhen Taichenglight 太辰光 (SZSE 300570, 비SEC)' → 'Shenzhen Taichenglight 太辰光' */
export const cleanLabel = (l: string) => (l.startsWith("company:") ? l.slice(8) : l.replace(/\s*\(.*\)\s*$/, "").split(" — ")[0]);

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

export function dayLabel(d: string): string {
  const r = rel(d);
  if (r === "오늘" || r === "어제") return r;
  const dt = new Date(`${d}T00:00:00+09:00`);
  return `${dt.getMonth() + 1}월 ${dt.getDate()}일 (${"일월화수목금토"[dt.getDay()]})`;
}
