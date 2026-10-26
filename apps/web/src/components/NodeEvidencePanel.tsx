"use client";

import evidence from "@/data/graph-evidence-index.json";
import { Icon } from "@/components/Icon";
import "./NodeEvidencePanel.css";

/** Human-review only: lexical candidates from a point-in-time-cautious archive. */
type CandidateMetric = {
 value:number;unit:string;literal:string;passage:string;source_id:string;
 source_url:string;published_at:string;conditions_verified:boolean;
};
type CandidateSource = {
 id:string;title:string;published_at:string;published_precision?:string;
 first_seen_at?:string;source:string;url:string;rank:number;
 matched_terms:string[];verification_status:string;
 metric_candidates:CandidateMetric[];
};
type EvidenceNode = {
 node_id:string;total_document_leads:number;year_counts:Record<string,number>;
 source_counts:Record<string,number>;
 measurement_candidates:CandidateMetric[];sources:CandidateSource[];
};
type EvidenceData = {summary:{
 total_historical_records_read:number;documents_with_ontology_matches:number;
 nodes_with_at_least_one_match:number;new_confirmed_supply_edges:number;
 interpretation:string;
};nodes:Record<string,EvidenceNode>};
const data=evidence as EvidenceData;
function yearLabel(value:string,precision?:string){
 if(precision==="year")return value.slice(0,4)+"년 · 연도까지만 확인";
 if(precision==="month")return value.slice(0,7)+" · 월까지만 확인";
 return value.slice(0,10);
}

export function NodeEvidencePanel({nodeId}:{nodeId:string}){
 const row=data.nodes[nodeId];
 if(!row||!row.total_document_leads)
  return <section className="ne-empty"><h4>공개자료 연결</h4><p>이 기술 노드와 일치하는 연구 원천이 아직 색인되지 않았습니다. 자료가 없다는 사실이 해당 기술의 가능성을 부정하지는 않습니다.</p></section>;
 const years=Object.entries(row.year_counts).sort((a,b)=>a[0].localeCompare(b[0]));
 const max=Math.max(1,...years.map(([,n])=>n));
 return <section className="ne-panel" aria-label="기술 노드의 역사적 공개자료">
  <div className="ne-head"><div><span>HISTORICAL RESEARCH / UNREVIEWED</span><h4>기술 근거 탐색</h4></div><strong>{row.total_document_leads.toLocaleString("ko-KR")}<small>문헌 매칭 후보</small></strong></div>
  <p className="ne-disclosure">자동 키워드 매칭 결과입니다. 독립적으로 확인된 기술적 성과나 납품·매출 근거가 아닙니다.</p>
  <div className="ne-subheader">자료 공개 시기 <span>색인 건수 · 산업 채택률 아님</span></div>
  <div className="ne-timeline" role="img" aria-label={"연도별 자료 "+years.map(([y,n])=>y+"년 "+n+"건").join(", ")}>
   {years.map(([year,count])=><div key={year} title={year+"년 "+count+"건"}><span>{count}</span><i style={{height:Math.max(5,Math.round(count/max*50))+"px"}}/><small>{year.slice(2)}</small></div>)}
  </div>
  {!!row.measurement_candidates?.length&&<>
   <div className="ne-subheader">정량 표현 후보 <span>시험 조건·기준치 미검증</span></div>
   <div className="ne-metric-list">{row.measurement_candidates.slice(0,3).map((m,i)=>
    <a key={m.source_id+"-"+i} href={m.source_url} target="_blank" rel="noreferrer" className="ne-metric">
     <div><strong>{m.literal}</strong><small>{m.published_at}</small></div>
     <p>{m.passage}</p><span>원문을 열어 수치의 측정 대상·조건을 확인하세요. <Icon name="arrow-up-right" size={13}/></span>
    </a>
   )}</div>
  </>}
  <div className="ne-subheader">관련 원천 자료 <span>상위 {Math.min(8,row.sources.length)}개 표시</span></div>
  <div className="ne-docs">{row.sources.slice(0,8).map(source=>
   <a key={source.id} href={source.url} target="_blank" rel="noreferrer" className="ne-doc">
    <small>{yearLabel(source.published_at,source.published_precision)} · {source.source.toUpperCase()}</small>
    <strong>{source.title}</strong>
    <span>매칭 키워드: {source.matched_terms.slice(0,3).join(" · ")} <Icon name="arrow-up-right" size={13}/></span>
   </a>
  )}</div>
  <div className="ne-bottom">초록의 수치는 기업 상용화 실적이 아닐 수 있습니다. 같은 DOI의 여러 학술 색인은 독립된 증거로 중복 계산하지 않습니다.</div>
 </section>;
}
