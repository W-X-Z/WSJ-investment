import "server-only";
import seedJson from "@/data/ecosystem-seed.json";
import { db } from "@/lib/supabase";

export type GraphNode = { id: string; kind: string; label: string; ecosystem?: string; also_in?: string[]; measured_metrics?: string[]; role?: string; listing?: { ticker?: string|null; cik?: number|null; filer_type?: string }; in_universe?: boolean; size_band?: string };
export type Evidence = { url: string; source_quality?: string };
export type GraphEdge = {
  id: string; from: string; to: string; relation: string; evidence_tier: string; confidence?: number;
  polarity: string; evidence: Evidence[]; note?: string;
};
export type GraphEvent = {
  id: string; ecosystem: string; target_id: string; type: string;
  source_id: string; published_at?: string | null; date_precision: string;
  checked_as_of?: string; source_url: string; summary: string;
  data?: Record<string, string | number | undefined>; evidence_level?: string; interpretation?: string;
};
export type GraphWatch = {
  id: string; ecosystem: string; target_id: string; signal: string; condition: string;
  source_urls: string[]; cadence: string; severity: string;
  confirmations_needed: string; failure_mode: string;
};
export type Seed = {
  schema_version: string; as_of: string; nodes: GraphNode[]; edges: GraphEdge[];
  events: GraphEvent[]; watches: GraphWatch[]; notes?: string[];
};

export const seed: Seed = seedJson as unknown as Seed;

export type EcoId = "hbm" | "optics" | "power";
export type Ecosystem = {
  id: EcoId; label: string; eyebrow: string; title: string; name: string;
  summary: string; bottleneck: string; trajectory: string; latest: string;
  tier: string; metricLabel: string; metric: string; glyph: string; color: string;
  sources: string[];
};
export const ECOSYSTEMS: Ecosystem[] = [
  {
    id: "hbm", label: "첨단 반도체", eyebrow: "01 / ADVANCED PACKAGING",
    title: "HBM4 · 첨단 패키징", name: "HBM & Packaging",
    summary: "고적층 메모리의 연결 밀도가 높아질수록 접합 정밀도와 검사 수율이 중요한 제약이 됩니다.",
    bottleneck: "미세 접합 · 웨이퍼 변형 · 결함 검사", trajectory: "I/O 확대 → 본딩 난도 증가 → 검사·계측 요구 변화",
    latest: "Camtek Hawk 추가 주문 관련 자료 확인", tier: "핵심 추적",
    metricLabel: "HBM4 I/O", metric: "2,048", glyph: "cpu", color: "violet",
    sources: ["https://news.skhynix.com/en/tech-note-series-ep2/", "https://www.camtek.com/products/hawk/"],
  },
  {
    id: "optics", label: "차세대 네트워크", eyebrow: "02 / OPTICAL INTERCONNECT",
    title: "1.6T 광통신 · 포토닉스", name: "Optics & Photonics",
    summary: "광링크 대역폭 증가가 레이저·광엔진·광결합·DSP의 성능과 조립 경제성을 바꿉니다.",
    bottleneck: "광결합 손실 · 전력 밀도 · 조립 정밀도",
    trajectory: "대역폭 확대 → 신호·광손실 증가 → 광엔진 통합·패키징 전환",
    latest: "IEEE P802.3dj 초안 및 공동개발 자료 추적", tier: "핵심 추적",
    metricLabel: "차세대 Ethernet", metric: "1.6T", glyph: "network", color: "cyan",
    sources: ["https://standards.ieee.org/ieee/802.3dj/11115/"],
  },
  {
    id: "power", label: "전력 인프라", eyebrow: "03 / DATA CENTER POWER",
    title: "800VDC · 전력·냉각", name: "Power & Cooling",
    summary: "고밀도 AI 랙이 기존 배전·냉각 구조에 압력을 가하면서 전력변환·보호·열관리 기술이 재편됩니다.",
    bottleneck: "전력 변환 손실 · 구리 배선 · DC 보호",
    trajectory: "랙 전력 밀도 상승 → 고전압 배전 검토 → 변환·보호 부품 변화",
    latest: "OCP LVDC 백서 개정 이력 추적", tier: "성장 관찰",
    metricLabel: "검토 중인 DC 배전", metric: "800V", glyph: "zap", color: "amber",
    sources: ["https://www.opencompute.org/projects/data-center-facility/power-distribution/"],
  },
];
export const ECO_BY_ID: Record<EcoId, Ecosystem> = {
  hbm: ECOSYSTEMS[0], optics: ECOSYSTEMS[1], power: ECOSYSTEMS[2],
};
export const ECO_ID_FOR_GRAPH: Record<EcoId, string> = {
  hbm: "eco:hbm", optics: "eco:optics", power: "eco:power",
};
export const GRAPH_TO_ECO: Record<string, EcoId> = {
  "eco:hbm": "hbm", "eco:optics": "optics", "eco:power": "power",
};
export const KINDS: Record<string, string> = {
  ecosystem: "산업 생태계", product_generation: "제품 세대", standard: "표준·사양", requirement: "기술 요구",
  bottleneck: "핵심 병목", technology: "해결 기술", process: "공정·검사", component: "부품·모듈", material: "소재",
  equipment: "장비 유형", product: "제품", company: "기업",
};
export const RELATIONS: Record<string, string> = {
  drives_requirement: "요구를 만든다", specified_by: "규격으로 정의", succeeds: "다음 세대", creates_bottleneck: "병목을 만든다",
  mitigated_by: "완화 수단", requires: "필요로 한다", implements: "제품이 구현", offered_by: "공급 가능(판매 보유)",
  supplied_to: "확인된 납품", qualifying_with: "인증·협업 진행", adopts: "채택", defers: "채택 연기(부정)",
  substitutes_for: "대체 가능", displaces: "수요 잠식(부정)", competes_with: "경쟁", invests_in: "지분 투자",
};
export const TIERS: Record<string, string> = {
  independent_measurement: "독립 실측", standard_body: "표준 기구", official_issuer: "당사자 공식", customer_statement: "고객사 진술",
  third_party_report: "제3자 보도", vendor_claim: "공급사 주장", technical_inference: "기술적 추론", hypothesis: "가설",
};
export const EVENT_LABEL: Record<string, string> = {
  commercial_order: "상업화", repeat_order: "수주 확대", joint_development: "기술 협력",
  standard_status: "표준 동향", standard_revision: "표준 개정", material_agreement: "계약",
  status_change: "변화 감지", cluster_buy: "내부자", officer_buy: "내부자",
  tech_milestone: "기술 검증",
};
export function nodeName(id: string): string {
  return seed.nodes.find((n) => n.id === id)?.label ?? id;
}
export function ecoIdFromGraph(id: string): EcoId {
  return GRAPH_TO_ECO[id] ?? "hbm";
}
export function graphDate(dateValue: string | null | undefined, checked?: string): string {
  if (!dateValue) return checked ? `확인 ${checked}` : "일자 확인 중";
  return dateValue.replaceAll("-", ".");
}
export function dateShort(value: string | null | undefined): string {
  if (!value) return "날짜 미상";
  return value.slice(0, 10).replaceAll("-", ".");
}
export function trimText(value: string, length = 190) {
  return value.length > length ? value.slice(0, length).trim() + "…" : value;
}

export { starsOf, STAR_LABEL } from "@/lib/research-client";

export type IssueCompany = { company_id: string; label: string; ticker?: string|null; direction: "+"|"-"|"±"; size_band?: string|null; in_universe?: boolean; basis?: string };
export const chipName = (c: IssueCompany) => (c.ticker && /[A-Za-z]/.test(c.ticker) ? c.ticker : c.label.split(" (")[0].replace(/ Electronics$/, ""));
export type IssueSource = { url: string; title: string; publisher: string; published_at: string; source_type: string };
export type FeedItem = {
  id: string; title: string; summary: string; date: string; datePrecision?: string;
  ecoId: EcoId | "market" | "cross"; type: string; source: string; sourceUrl?: string;
  status: "source" | "observed" | "verified" | "hypothesis"; significance: "high" | "medium" | "watch";
  target?: string; secondary?: string;
  kind?: "issue" | "event" | "signal"; importance?: number; rationale?: string; why?: string;
  companies?: IssueCompany[]; nodes?: string[]; sources?: IssueSource[]; publisherCount?: number;
};
export type Idea = {
  id: string; ticker: string; company: string; title: string; description: string;
  ecoId: EcoId | "market"; state: "exploring" | "watching" | "strengthened" | "weakened";
  trigger: string; risk: string; evidenceUrl: string; evidenceType: string;
  relatedNode?: string; asOf: string; live?: boolean; href?: string;
};

const IDEA_SEED: Idea[] = [
  {
    id: "camt", ticker: "CAMT", company: "Camtek", title: "고집적 HBM에서 검사·계측 공정의 중요도 증가",
    description: "I/O 확대와 미세 접합은 고정밀 검사 요구를 강화할 수 있습니다. Hawk 장비 주문 이후 실제 인도·고객 양산 사용을 추적합니다.",
    ecoId: "hbm", state: "strengthened", trigger: "차세대 본딩·계측 사양 변경 또는 독립적인 고객 양산 확인",
    risk: "기존 검사 방식의 대체, 검사 빈도 감소, 수주와 매출 인식 차이",
    evidenceUrl: "https://www.camtek.com/products/hawk/", evidenceType: "장비 기술 사양 · 공급사",
    relatedNode: "company:camt", asOf: "2026-10-26",
  },
  {
    id: "poet", ticker: "POET", company: "POET Technologies", title: "광연결 밀도 상승에 따른 통합 광엔진 기회",
    description: "1.6T 광모듈 공동개발은 기술 적합성의 신호입니다. 상업적 리레이팅을 논하려면 고객사의 qualification과 양산 주문이 필요합니다.",
    ecoId: "optics", state: "watching", trigger: "대형 고객의 독립적인 1.6T 제품 인증·양산 발표",
    risk: "개발 협력의 상업화 지연, CPO/Pluggable 구조 변화, 경쟁 패키징",
    evidenceUrl: "https://www.poet-technologies.com/news/poet-technologies-and-lessengers-expand-partnership-to-deliver-1-6t-2xdr4-optical-transceivers-for-ai-network-connectivity",
    evidenceType: "공동개발 발표 · 회사 주장", relatedNode: "company:poet", asOf: "2026-10-26",
  },
  {
    id: "aehr", ticker: "AEHR", company: "Aehr Test Systems",
    title: "전력반도체 채택 확대가 번인 검사에 미칠 2차 영향",
    description: "800V 전력 아키텍처가 SiC 채택을 증가시킬 수 있지만, 특정 제품·고객의 부품 선정과 번인 장비 수요 연결은 아직 미검증입니다.",
    ecoId: "power", state: "exploring", trigger: "800VDC 양산 전력변환기의 실제 SiC BOM·고객 공급사 확인",
    risk: "SiC 미사용 설계, 대체 전력반도체, 기존 테스트 공정 충분성",
    evidenceUrl: "https://www.opencompute.org/projects/data-center-facility/power-distribution/",
    evidenceType: "OCP 기술 구조 · 조건부 가설", relatedNode: "company:aehr", asOf: "2026-10-26",
  },
];
export const seedIdeas = IDEA_SEED;

export const CURATED_FEED: FeedItem[] = seed.events.map((e) => {
  const ecoId = ecoIdFromGraph(e.ecosystem);
  const label = EVENT_LABEL[e.type] ?? "기술 변화";
  const title =
    e.id === "obs:camt_202606" ? "HBM 생산라인 관련 검사 장비 추가 주문" :
    e.id === "obs:camt_202411" ? "차세대 검사 장비 Hawk, 초기 주문 확인" :
    e.id === "obs:poet_202603" ? "1.6T 광엔진 공동개발 본격화" :
    e.id === "obs:ocp_202609" ? "OCP 800VDC 전력 규격 문서 갱신" :
    "IEEE 차세대 Ethernet 표준 개발 현황";
  return {
    id: e.id, title, summary: e.summary, date: e.published_at ?? e.checked_as_of ?? seed.as_of,
    datePrecision: e.date_precision, ecoId, type: label, source: e.source_id.replaceAll("_", " ").toUpperCase(),
    sourceUrl: e.source_url, status: "source" as const,
    significance: e.id === "obs:camt_202606" || e.id === "obs:poet_202603" ? "high" as const : "medium" as const,
    target: nodeName(e.target_id), secondary: e.interpretation,
  };
}).sort((a,b) => b.date.localeCompare(a.date));

type BriefRecord = { id: number; ticker?: string|null; name?: string; title?: string|null; created_at: string; as_of?: string; scores?: Record<string, unknown>; sector_bucket?: string };
type SignalRecord = { id: number; ticker?: string|null; name?: string|null; family?: string; kind?: string; summary?: string; signal_date?: string; url?: string|null; direction?: number; };
type IssueRecord = { issue_key: string; ecosystem: string|null; event_type: string|null; title: string; summary: string|null; why_it_matters: string|null;
  importance: number; importance_rationale: string|null; nodes: string[]; companies: IssueCompany[]|null; sources: IssueSource[];
  source_count: number; publisher_count: number; latest_published_at: string|null; first_seen: string; method: string };
type CandidateRecord = { cik: number; ticker?: string|null; name?: string; score?: number; family_count?: number; sector_bucket?: string; as_of?: string; top_signals?: {summary: string; url?: string}[] };

export type LiveData = { briefs: BriefRecord[]; signals: SignalRecord[]; candidates: CandidateRecord[]; issues: IssueRecord[]; online: boolean; lastError?: string };
export async function loadLiveData(): Promise<LiveData> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) {
    return { briefs: [], signals: [], candidates: [], issues: [], online: false, lastError: "Supabase 환경변수가 설정되지 않았습니다." };
  }
  try {
    const client = db("public");
    const since = new Date(Date.now() - 21 * 864e5).toISOString();
    const [briefs, signals, candidates, issues] = await Promise.all([
      client.from("v_briefs").select("id,ticker,name,title,created_at,as_of,scores,sector_bucket").eq("status", "final").order("created_at", {ascending:false}).limit(12),
      // 공급망 유니버스 기업의 신호만 (바이오 등 이전 유니버스 신호는 이 화면 대상이 아니다)
      client.from("v_signals").select("id,ticker,name,family,kind,summary,signal_date,url,direction").eq("sector_bucket", "supply_chain").order("signal_date", {ascending:false}).limit(20),
      client.from("v_candidates").select("cik,ticker,name,score,family_count,sector_bucket,as_of,top_signals").order("score", {ascending:false}).limit(15),
      client.from("v_supply_chain_issues").select("*").gte("latest_published_at", since).order("importance", {ascending:false}).order("latest_published_at", {ascending:false}).limit(60),
    ]);
    const failures = [briefs.error,signals.error,candidates.error,issues.error].filter(Boolean);
    return {
      briefs: (briefs.data ?? []) as BriefRecord[], signals: (signals.data ?? []) as SignalRecord[],
      candidates: (candidates.data ?? []) as CandidateRecord[], issues: (issues.data ?? []) as IssueRecord[],
      online: failures.length === 0, lastError: failures.map(x=>x?.message).join("; ") || undefined,
    };
  } catch (error) {
    return { briefs:[],signals:[],candidates:[],issues:[],online:false,lastError: error instanceof Error ? error.message : "연결 오류" };
  }
}

const EVENT_TYPE_KO: Record<string,string> = {
  capacity:"생산능력", technology:"기술", standard:"표준", regulation:"규제", order:"수주·계약", earnings:"실적·가이던스",
  m_and_a:"M&A·제휴", supply_disruption:"공급 차질", pricing:"가격", research:"연구", other:"이슈",
};
export function issueToFeed(r: IssueRecord): FeedItem {
  const eco = (r.ecosystem === "hbm" || r.ecosystem === "optics" || r.ecosystem === "power") ? r.ecosystem : "cross";
  const pubs = Array.from(new Set(r.sources.map(s => s.publisher))).slice(0, 2).join(", ");
  return {
    id: `issue-${r.issue_key}`, kind: "issue", title: r.title, summary: r.summary ?? r.sources[0]?.title ?? "",
    date: (r.latest_published_at ?? r.first_seen).slice(0, 10), ecoId: eco,
    type: EVENT_TYPE_KO[r.event_type ?? "other"] ?? "이슈",
    source: r.publisher_count > 2 ? `${pubs} 외 ${r.publisher_count - 2}곳` : pubs,
    sourceUrl: r.sources[0]?.url, status: "observed",
    significance: r.importance >= 8 ? "high" : r.importance >= 5 ? "medium" : "watch",
    importance: r.importance, rationale: r.importance_rationale ?? undefined, why: r.why_it_matters ?? undefined,
    companies: r.companies ?? [], nodes: r.nodes ?? [], sources: r.sources, publisherCount: r.publisher_count,
    target: (r.nodes ?? []).slice(0, 3).map(nodeName).join(" · ") || undefined,
  };
}

export function mergeFeed(live: LiveData): FeedItem[] {
  const issues = live.issues.map(issueToFeed);
  const signals: FeedItem[] = live.signals.map((s) => ({
    id: `signal-${s.id}`, title: s.ticker ? `${s.ticker} · ${s.kind ?? s.family ?? "신규 공시"}` : s.name ?? "기업 관련 신호",
    summary: s.summary ?? "원본 자료 확인 필요",
    date: s.signal_date ?? "2000-01-01", ecoId: "market",
    type: EVENT_LABEL[s.kind ?? ""] ?? (s.family === "contract" ? "계약" : "기업 신호"),
    source: "WSJ / SEC·공개 데이터", sourceUrl: s.url ?? undefined,
    status: "observed", significance: "watch", kind: "signal" as const,
  }));
  return [...issues, ...CURATED_FEED, ...signals].sort((a,b) => b.date.localeCompare(a.date) || (b.importance ?? 0) - (a.importance ?? 0));
}

export function mergeIdeas(live: LiveData): Idea[] {
  const dynamic: Idea[] = live.briefs.map((b) => ({
    id: `brief-${b.id}`, ticker: b.ticker ?? String(b.id), company: b.name ?? "기업",
    title: b.title ?? "기업 투자 브리프", description: "기존 Analyst·Risk 리서치가 작성한 기업 브리프입니다. 원문 및 판단 근거를 상세 화면에서 확인하세요.",
    ecoId:"market", state:"watching", trigger:"실적·사업 변화에 따른 가설 재검증",
    risk:"기존 브리프의 반증 조건과 수익성·희석 위험 확인", evidenceUrl:`/briefs/${b.id}`,evidenceType:"기존 정량·정성 리서치",
    asOf:b.as_of??b.created_at.slice(0,10),live:true,href:`/briefs/${b.id}`,
  }));
  return [...IDEA_SEED,...dynamic];
}

export function ecoNodes(id: EcoId): GraphNode[] {
  const start = ECO_ID_FOR_GRAPH[id];
  const result = new Set([start]);
  for(let depth=0;depth<6;depth++){
    for(const edge of seed.edges){
      if(result.has(edge.from))result.add(edge.to);
    }
  }
  // Link only nodes reachable from the ecosystem, including shared components.
  return seed.nodes.filter(n=>result.has(n.id));
}

// ---------------------------------------------------------------- 가격·실적 지표 (ADR-0014 개정, 0016)
export type IndicatorRecord = {
  indicator_id: string; label: string; category: "memory_spot"|"ppi"|"commodity"|"tw_revenue"|string; unit: string|null; frequency: string;
  source: string; source_url: string|null; ecosystem: string|null; nodes: string[]; companies: string[]; note: string|null;
  as_of: string; value: number; change_pct: number|null; yoy_pct: number|null; meta: Record<string, unknown>|null; value_1w: number|null; value_1m: number|null;
};
export type IndicatorPoint = { indicator_id: string; as_of: string; value: number };
export const INDICATOR_GROUPS: { id: string; title: string; cats: string[] }[] = [
  { id: "memory", title: "메모리 현물가", cats: ["memory_spot"] },
  { id: "tw", title: "대만 공급사 월매출", cats: ["tw_revenue"] },
  { id: "ppi", title: "미국 PPI·원자재", cats: ["ppi", "commodity"] },
  { id: "obs", title: "병목 상태 관측치 (원문에서 확인한 숫자)", cats: ["observation"] },
];
/** 지표의 대표 변화: 현물가는 1주(이력 없으면 출처 일간), 월간 지표는 YoY → 전월. */
export function indicatorMove(r: IndicatorRecord): { pct: number|null; label: string } {
  if (r.category === "memory_spot") {
    if (r.value_1w) return { pct: (r.value / r.value_1w - 1) * 100, label: "1주" };
    return { pct: r.change_pct, label: r.frequency === "daily" ? "전일" : "전주" };
  }
  if (r.yoy_pct != null) return { pct: r.yoy_pct, label: "YoY" };
  return { pct: r.change_pct, label: "전월" };
}
export async function loadIndicators(): Promise<{ indicators: IndicatorRecord[]; points: Record<string, IndicatorPoint[]>; error?: string }> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) return { indicators: [], points: {}, error: "Supabase 환경변수 없음" };
  try {
    const client = db("public");
    const [ind, pts] = await Promise.all([
      client.from("v_indicators").select("*").order("category").order("label"),
      client.from("v_indicator_points").select("indicator_id,as_of,value").order("as_of", { ascending: true }).limit(5000),
    ]);
    const points: Record<string, IndicatorPoint[]> = {};
    for (const p of (pts.data ?? []) as IndicatorPoint[]) (points[p.indicator_id] ??= []).push({ ...p, value: Number(p.value) });
    const indicators = ((ind.data ?? []) as IndicatorRecord[]).map((r) => ({ ...r, value: Number(r.value),
      change_pct: r.change_pct == null ? null : Number(r.change_pct), yoy_pct: r.yoy_pct == null ? null : Number(r.yoy_pct),
      value_1w: r.value_1w == null ? null : Number(r.value_1w), value_1m: r.value_1m == null ? null : Number(r.value_1m) }));
    return { indicators, points, error: ind.error?.message ?? pts.error?.message };
  } catch (error) {
    return { indicators: [], points: {}, error: error instanceof Error ? error.message : "연결 오류" };
  }
}
