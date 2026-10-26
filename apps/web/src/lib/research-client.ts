import seedJson from "@/data/ecosystem-seed.json";

// Client-safe, static projection of the same documented research seed.
export type EcoId = "hbm" | "optics" | "power";
export type GraphNode = { id: string; kind: string; label: string; measured_metrics?: string[] };
export type Edge = { id: string; from: string; to: string; relation: string; stage: string; polarity: string; note?: string; evidence: {url:string}[] };
export const seed = seedJson as unknown as {nodes:GraphNode[];edges:Edge[]};
export const KINDS: Record<string,string> = {
  ecosystem:"생태계",requirement:"기술 요구",bottleneck:"기술 병목",technology:"해결 기술",
  component:"부품",material:"소재",process:"제조 공정",company:"관련 기업",
};
export const RELATIONS: Record<string,string> = {
  drives_requirement:"요구를 생성",creates_bottleneck:"병목을 야기",mitigated_by:"해결 기술",
  offered_by:"공급·개발",substitutes_for:"대체 가능",
  requires_component_or_material:"부품·소재 요구",uses_component_or_equipment:"공정 사용",
};
export const ECO_BY_ID = {
  hbm:{name:"HBM & Packaging",color:"violet"},
  optics:{name:"Optics & Photonics",color:"cyan"},
  power:{name:"Power & Cooling",color:"amber"},
} as const;
