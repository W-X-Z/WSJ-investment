import "server-only";
import seedJson from "@/data/ecosystem-seed.json";
import { db } from "@/lib/supabase";

export type GraphNode = { id: string; kind: string; label: string; measured_metrics?: string[]; disclosure_note?: string };
export type Evidence = { url: string; source_quality?: string };
export type GraphEdge = {
  id: string; from: string; to: string; relation: string; stage: string;
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
  ecosystem: "산업 생태계", requirement: "기술 요구", bottleneck: "핵심 병목",
  technology: "해결 기술", component: "부품", material: "소재",
  process: "공정", company: "기업", equipment: "장비",
};
export const RELATIONS: Record<string, string> = {
  drives_requirement: "요구를 생성", creates_bottleneck: "병목을 야기",
  mitigated_by: "해결 기술", offered_by: "공급·개발",
  substitutes_for: "대체 가능", requires_component_or_material: "부품·소재 요구",
  uses_component_or_equipment: "공정 사용",
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

export type FeedItem = {
  id: string; title: string; summary: string; date: string; datePrecision?: string;
  ecoId: EcoId | "market"; type: string; source: string; sourceUrl?: string;
  status: "source" | "observed" | "verified" | "hypothesis"; significance: "high" | "medium" | "watch";
  target?: string; secondary?: string;
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
type CandidateRecord = { cik: number; ticker?: string|null; name?: string; score?: number; family_count?: number; sector_bucket?: string; as_of?: string; top_signals?: {summary: string; url?: string}[] };

export type LiveData = { briefs: BriefRecord[]; signals: SignalRecord[]; candidates: CandidateRecord[]; online: boolean; lastError?: string };
export async function loadLiveData(): Promise<LiveData> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_KEY) {
    return { briefs: [], signals: [], candidates: [], online: false, lastError: "Supabase 환경변수가 설정되지 않았습니다." };
  }
  try {
    const client = db("public");
    const [briefs, signals, candidates] = await Promise.all([
      client.from("v_briefs").select("id,ticker,name,title,created_at,as_of,scores,sector_bucket").eq("status", "final").order("created_at", {ascending:false}).limit(12),
      client.from("v_signals").select("id,ticker,name,family,kind,summary,signal_date,url,direction").order("signal_date", {ascending:false}).limit(20),
      client.from("v_candidates").select("cik,ticker,name,score,family_count,sector_bucket,as_of,top_signals").order("score", {ascending:false}).limit(15),
    ]);
    const failures = [briefs.error,signals.error,candidates.error].filter(Boolean);
    return {
      briefs: (briefs.data ?? []) as BriefRecord[], signals: (signals.data ?? []) as SignalRecord[],
      candidates: (candidates.data ?? []) as CandidateRecord[],
      online: failures.length < 3, lastError: failures.map(x=>x?.message).join("; ") || undefined,
    };
  } catch (error) {
    return { briefs:[],signals:[],candidates:[],online:false,lastError: error instanceof Error ? error.message : "연결 오류" };
  }
}

export function mergeFeed(live: LiveData): FeedItem[] {
  const signals: FeedItem[] = live.signals.map((s) => ({
    id: `signal-${s.id}`, title: s.ticker ? `${s.ticker} · ${s.kind ?? s.family ?? "신규 공시"}` : s.name ?? "기업 관련 신호",
    summary: s.summary ?? "원본 자료 확인 필요",
    date: s.signal_date ?? "2000-01-01", ecoId: "market",
    type: EVENT_LABEL[s.kind ?? ""] ?? (s.family === "contract" ? "계약" : "기업 신호"),
    source: "WSJ / SEC·공개 데이터", sourceUrl: s.url ?? undefined,
    status: "observed", significance: s.direction === -1 ? "high" : "watch",
  }));
  return [...CURATED_FEED, ...signals].sort((a,b) => b.date.localeCompare(a.date));
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
