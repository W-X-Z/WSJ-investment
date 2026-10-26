import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Icon } from "@/components/Icon";
import { dateShort, ECO_BY_ID, nodeName, seed, seedIdeas } from "@/lib/research";

export const metadata={title:"투자 가설 상세"};
export default async function IdeaDetail({params}:{params:Promise<{id:string}>}){
 const {id}=await params;
 if(id.startsWith("brief-") && /^brief-\d+$/.test(id))redirect(`/briefs/${id.slice(6)}`);
 const idea=seedIdeas.find(x=>x.id===id); if(!idea)notFound();
 const eco=idea.ecoId==="market"?null:ECO_BY_ID[idea.ecoId];
 const targetEdges=idea.relatedNode?seed.edges.filter(e=>e.from===idea.relatedNode||e.to===idea.relatedNode):[];
 const watches=eco?seed.watches.filter(w=>w.ecosystem===`eco:${eco.id}`):[];
 return <div>
  <div className="breadcrumb"><Link href="/ideas">투자 가설</Link><Icon name="chevron-right" size={13}/><span>{idea.ticker}</span></div>
  <div className="page-head"><div><div className="page-kicker">TECHNOLOGY INVESTMENT THESIS / {idea.ticker}</div><h1>{idea.title}</h1><p>{idea.company} · {eco?.title??"기업 리서치"} · 연구 기준 {dateShort(idea.asOf)}</p></div><Link className="outline-button" href={`/ecosystems/${idea.ecoId}`}><Icon name="network" size={16}/> 생태계 지도</Link></div>
  <div className="detail-layout">
   <article className="detail-card">
    <div className="detail-label">INVESTMENT HYPOTHESIS</div>
    <div className="detail-content-quote">{idea.description}</div>
    <h2>기술적 가치가 달라지는 경로</h2>
    <p>고객사의 기술 요구 변화가 어떤 소재·부품·공정의 중요도를 높이는지, 해당 기술의 공급기업이 새로운 고객을 확보할 수 있는지 확인하는 가설입니다. 산업 성장과 특정 상장기업의 경제적 이익을 직접 동일시하지 않습니다.</p>
    <div style={{marginTop:18}} className="research-note"><strong>아직 입증되지 않은 사항</strong>{idea.risk}</div>
    <h3>기술 그래프 내 인접 관계</h3>
    <div className="related-list">{targetEdges.map(edge=><div key={edge.id} style={{padding:"12px 0",borderBottom:"1px solid #eaeef5"}}><div className="story-meta"><span>{edge.relation.replaceAll("_"," ")}</span><span className="meta-sep">·</span><span>{edge.stage.replaceAll("_"," ")}</span></div><strong style={{display:"block",marginTop:5,fontSize:12,color:"#3d5370"}}>{nodeName(edge.from)} → {nodeName(edge.to)}</strong></div>)}</div>
    <h3>다음에 확인할 결정적 사실</h3>
    <div className="detail-content-quote" style={{borderColor:"#49bba7",background:"#f2faf7"}}>{idea.trigger}</div>
    <h3>독립 검증과 추적</h3>
    <p>고객사의 직접 발표·공식 표준·양산 인증·납품 이후의 경제성을 별도의 출처 그룹으로 수집해야 합니다. 동일한 회사 보도자료를 재인용한 기사 여러 개는 독립 증거로 세지 않습니다.</p>
   </article>
   <aside>
    <div className="detail-card" style={{padding:20,marginBottom:15}}><div className="detail-label">THESIS STATUS</div><div className="idea-card-top"><span className="ticker-badge">{idea.ticker}</span><span className="detail-status"><i/>{idea.state==="strengthened"?"근거 강화":idea.state==="watching"?"검증 중":"초기 가설"}</span></div><dl style={{marginTop:14}}>
     <div className="detail-key-value"><dt>기술 생태계</dt><dd>{eco?.name}</dd></div>
     <div className="detail-key-value"><dt>근거 분류</dt><dd>{idea.evidenceType}</dd></div>
     <div className="detail-key-value"><dt>연구 기준</dt><dd>{dateShort(idea.asOf)}</dd></div>
    </dl><a href={idea.evidenceUrl} target="_blank" rel="noreferrer" className="blue-button" style={{width:"100%",justifyContent:"center",marginTop:18}}>대표 원문 열기 <Icon name="external" size={15}/></a></div>
    <div className="surface aside-panel"><h3>연결된 감시 규칙</h3><p>기술 변경이 고객 매출로 이어지는 과정에서 다음 사건을 확인합니다.</p><div className="aside-links">{watches.slice(0,3).map(w=><Link href={`/triggers?eco=${idea.ecoId}`} key={w.id}><Icon name="radar" size={15}/>{nodeName(w.target_id).slice(0,24)}<Icon name="arrow-right" size={14}/></Link>)}</div></div>
   </aside>
  </div>
 </div>;
}
