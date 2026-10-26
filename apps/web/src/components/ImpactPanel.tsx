"use client";

import impactIndex from "@/data/impact-index.json";

/** "이 노드에 변화가 생기면 어느 기업이 어느 경로로 영향받나" — pipeline(impact.py)이 미리 계산한 결과.
 *  방향·근거 등급의 곱(신뢰도)·부호를 보여 준다. 매출 증거가 아니다. */
type ImpactCompany = {
 company_id:string;company:string;direction:"positive"|"negative"|"mixed";confidence:number;band:string;
 in_universe:boolean;size_band:string|null;ticker:string|null;role:string;path:string[];
 weakest:{id:string;relation:string;tier:string;confidence:number};upgrade_needed:string;
};
type Substitution = {technology:string;alternative:string;relation:string;polarity:string;note:string};
type Index = {meta:{as_of:string;nodes_indexed:number;caveat:string};nodes:Record<string,{companies:ImpactCompany[];substitutions:Substitution[]}>};
const index=impactIndex as unknown as Index;

const ROLE:Record<string,string>={supplier:"공급사",supplier_via_customer:"고객 경유 공급사",adopter:"채택 고객",customer:"고객"};
const BAND:Record<string,string>={documented:"문서화",claimed:"주장 수준",inferred:"추론"};
const TIER:Record<string,string>={independent_measurement:"독립 실측",standard_body:"표준 기구",official_issuer:"당사자 공식",customer_statement:"고객사 진술",third_party_report:"제3자 보도",vendor_claim:"공급사 주장",technical_inference:"기술적 추론",hypothesis:"가설"};

export function ImpactPanel({nodeId}:{nodeId:string}){
 const entry=index.nodes[nodeId];
 if(!entry) return null;
 return <div className="sc-impact">
  <h4>이 노드가 바뀌면 — 영향 기업 (방향 전파, 근거 가중)</h4>
  {entry.companies.length===0&&<p className="sc-impact-empty">기업까지 닿는 경로 없음</p>}
  {entry.companies.map(c=><div key={c.company_id} className={`sc-impact-row sc-impact-${c.direction}`}>
   <div className="sc-impact-head">
    <span className={`sc-impact-sign sc-sign-${c.direction}`}>{c.direction==="positive"?"＋":c.direction==="negative"?"－":"±"}</span>
    <strong>{c.company}</strong>
    <span className="sc-impact-meta">{ROLE[c.role]??c.role} · {BAND[c.band]??c.band} {Math.round(c.confidence*100)}%{c.in_universe?" · 유니버스":""}</span>
   </div>
   <div className="sc-impact-path">{c.path.join(" → ")}</div>
   <div className="sc-impact-weak">가장 약한 고리: {c.weakest.relation} ({TIER[c.weakest.tier]??c.weakest.tier}) · 승격 조건: {c.upgrade_needed}</div>
  </div>)}
  {entry.substitutions.length>0&&<>
   <h4>대체·잠식 시나리오 (수치 영향 없음)</h4>
   {entry.substitutions.map((s,i)=><div key={i} className="sc-impact-sub"><strong>{s.technology}</strong> <span>{s.relation==="displaces"?"잠식 →":"대체 가능 ↔"}</span> <strong>{s.alternative}</strong>{s.note&&<small> — {s.note}</small>}</div>)}
  </>}
  <div className="sc-caution">{index.meta.caveat}</div>
 </div>;
}
