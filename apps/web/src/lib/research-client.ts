import seedJson from "@/data/ecosystem-seed.json";

// Client-safe, static projection of the same documented research seed.
export type EcoId = "hbm" | "optics" | "power";
export type Listing = { ticker?: string|null; exchange?: string|null; cik?: number|null; filer_type?: string };
export type GraphNode = { id: string; kind: string; label: string; ecosystem?: string; also_in?: string[]; measured_metrics?: string[]; role?: string; listing?: Listing; in_universe?: boolean; size_band?: string };
export type Edge = { id: string; from: string; to: string; relation: string; evidence_tier: string; confidence?: number; polarity: string; about?: string; note?: string; evidence: {url:string; source_type?: string; published_at?: string|null; note?: string}[] };
export const seed = seedJson as unknown as {nodes:GraphNode[];edges:Edge[]};
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
export const ECO_BY_ID = {
  hbm:{name:"HBM & Packaging",color:"violet"},
  optics:{name:"Optics & Photonics",color:"cyan"},
  power:{name:"Power & Cooling",color:"amber"},
} as const;
