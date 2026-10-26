import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { dateShort, ECOSYSTEMS, ECO_BY_ID, EVENT_LABEL, loadLiveData, mergeFeed, nodeName, seed } from "@/lib/research";

export const dynamic="force-dynamic";
export const metadata={title:"이슈 분석"};
export default async function FeedDetail({params}:{params:Promise<{id:string}>}){
 const {id}=await params;
 const live=await loadLiveData();
 const item=mergeFeed(live).find(x=>x.id===id);
 if(!item)notFound();
 const original=seed.events.find(x=>x.id===id);
 const edges=original?seed.edges.filter(x=>x.from===original.target_id||x.to===original.target_id):[];
 const eco=item.ecoId==="market"?null:ECO_BY_ID[item.ecoId];
 const validSource=item.sourceUrl?.startsWith("https://")?item.sourceUrl:null;
 return <div>
  <div className="breadcrumb"><Link href="/feed">이슈 피드</Link><Icon name="chevron-right" size={13}/><span>{item.title}</span></div>
  <div className="page-head"><div><div className="page-kicker">EVIDENCE BRIEF / {item.type.toUpperCase()}</div><h1>{item.title}</h1><p>{eco?.title??"기업별 공개 데이터"} · {dateShort(item.date)} · 출처 {item.source}</p></div>{validSource&&<a href={validSource} target="_blank" rel="noreferrer" className="outline-button">원문 확인 <Icon name="external" size={15}/></a>}</div>
  <div className="detail-layout">
   <article className="detail-card">
    <div className="detail-label">WHAT CHANGED / 공개된 사실</div>
    <div className="detail-content-quote">{item.summary}</div>
    <h2>무엇을 검증해야 할까?</h2>
    <p>기술적 사실, 제조사의 해석, 최종 고객의 상업적 채택을 분리해야 합니다. 단일 뉴스가 기업가치 리레이팅을 증명하지는 않으며, 동일 기술 변화에 따른 경쟁사·대체 기술의 영향도 살펴봐야 합니다.</p>
    {original && <><h3>원천 자료의 정량 관측값</h3><dl>{Object.entries(original.data??{}).length?Object.entries(original.data??{}).map(([k,v])=><div className="detail-key-value" key={k}><dt>{k.replaceAll("_"," ")}</dt><dd>{String(v)}</dd></div>):<div className="research-note">추가 수치 확인 필요. 문서의 개정 내역과 측정 조건을 검토해야 합니다.</div>}</dl>
      <h3>기술 영향 경로</h3><div className="related-list">{edges.map(x=><div key={x.id} style={{borderBottom:"1px solid #edf0f6",padding:"14px 0"}}><div className="story-meta"><span className="event-level event-level-medium">{x.relation.replaceAll("_"," ")}</span><span>{x.evidence_tier.replaceAll("_"," ")}</span></div><div style={{fontSize:12,fontWeight:680,color:"#31465e",marginTop:7}}>{nodeName(x.from)} → {nodeName(x.to)}</div>{x.note&&<p style={{fontSize:11,margin:"6px 0 0",color:"#8b96a5"}}>{x.note}</p>}</div>)}</div>
    </>}
    <h3>가설을 약화시킬 수 있는 정보</h3>
    <div className="research-note"><strong>반증을 먼저 확인하세요</strong>{original?.interpretation??"단일 기업 신호를 기술적 리레이팅으로 곧바로 연결하지 않습니다."} 검증 시 원문 발표일·실제 수치·독립 근거·미래 일정 및 대체 기술을 대조해야 합니다.</div>
   </article>
   <aside>
    <div className="detail-card" style={{padding:20,marginBottom:14}}><div className="detail-label">EVIDENCE PROVENANCE</div><dl>
     <div className="detail-key-value"><dt>자료 유형</dt><dd>{item.type}</dd></div>
     <div className="detail-key-value"><dt>공개 시점</dt><dd>{dateShort(item.date)}</dd></div>
     <div className="detail-key-value"><dt>출처</dt><dd>{item.source}</dd></div>
     <div className="detail-key-value"><dt>근거 수준</dt><dd>{original?.evidence_level??"운영 수집 신호"}</dd></div>
     <div className="detail-key-value"><dt>연결 기술</dt><dd>{item.target??"별도 확인 필요"}</dd></div>
    </dl>{validSource&&<a className="blue-button" style={{marginTop:20,justifyContent:"center",width:"100%"}} href={validSource} target="_blank" rel="noreferrer">출처 원문 열기 <Icon name="external" size={14}/></a>}</div>
    {eco&&<div className="surface aside-panel"><h3>관련 생태계</h3><p>{eco.summary}</p><Link className="outline-button" href={`/ecosystems/${eco.id}`}>영향 지도 보기 <Icon name="arrow-right" size={15}/></Link></div>}
   </aside>
  </div>
 </div>;
}
