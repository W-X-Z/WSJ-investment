import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { GraphExplorer, GraphTabs } from "@/components/GraphExplorer";
import { FeedStory, SectionHeading } from "@/components/ResearchCards";
import { ECOSYSTEMS, ECO_BY_ID, ECO_ID_FOR_GRAPH, CURATED_FEED, nodeName, seed, type EcoId } from "@/lib/research";

export const metadata = { title: "기술 생태계 심층 분석" };
export function generateStaticParams() {return ECOSYSTEMS.map(e=>({slug:e.id}));}

export default async function EcosystemDetail({params}: {params: Promise<{slug:string}>}) {
 const {slug} = await params;
 if(!(slug in ECO_BY_ID)) notFound();
 const id=slug as EcoId; const eco=ECO_BY_ID[id]; const graphId=ECO_ID_FOR_GRAPH[id];
 const relevantEvents=CURATED_FEED.filter(x=>x.ecoId===id);
 const relevantWatches=seed.watches.filter(x=>x.ecosystem===graphId);
 const companies=seed.nodes.filter(n=>n.kind==="company" && (n.ecosystem===id || (n.also_in??[]).includes(id)));
 const sources=Array.from(new Set(seed.edges.filter(e=>e.evidence.some(x=>eco.sources.includes(x.url)) || companies.some(c=>e.to===c.id)).flatMap(e=>e.evidence.map(x=>x.url)))).slice(0,6);
 return <div>
   <div className="breadcrumb"><Link href="/ecosystems">기술 생태계</Link><Icon name="chevron-right" size={13}/><span>{eco.title}</span></div>
   <div className="page-head"><div><div className="page-kicker">{eco.eyebrow}</div><h1>{eco.title}</h1><p>{eco.summary}</p></div><Link className="outline-button" href={`/search?q=${encodeURIComponent(eco.name)}`}><Icon name="search" size={15}/> 연관 자료 검색</Link></div>
   <div className="eco-hero"><div><div className="eyebrow">TECHNOLOGY THESIS</div><h2>{eco.trajectory}</h2><p><strong>핵심 제약:</strong> {eco.bottleneck}. 기술 문서와 고객 채택을 분리해서 관찰합니다. 기업의 기술적 관련성이 실제 매출 기여로 이어지는지는 별도 검증이 필요합니다.</p><div className="tag-row"><span className="tag">실물 물성</span><span className="tag">공정·장비</span><span className="tag">대체 기술</span><span className="tag">공개 근거</span></div></div><div className="eco-hero-metric"><span>{eco.metricLabel}</span><strong>{eco.metric}</strong><em>기술 요구 지표 · 매출 추정 아님</em></div></div>
   <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,marginBottom:14,flexWrap:"wrap"}}><GraphTabs current={id}/><span className="soft-text">노드를 선택해 기술 관계와 원문 검증</span></div>
   <GraphExplorer key={id} ecoId={id}/>
   <div className="dashboard-dual">
     <section><SectionHeading eyebrow="RECENT EVIDENCE" title="관련 주요 이슈" href={`/feed?eco=${id}`} action="전체 피드"/><div className="surface feed-list">{relevantEvents.length?relevantEvents.map(x=><FeedStory key={x.id} item={x}/>):<p style={{padding:22,color:"#8292a8"}}>큐레이션된 자료가 아직 없습니다.</p>}</div></section>
     <section><SectionHeading eyebrow="MONITORING CONDITIONS" title="검증을 기다리는 변화" href={`/triggers?eco=${id}`} action="감시 규칙 전체"/><div className="surface" style={{padding:"0 18px"}}>{relevantWatches.map(w=><div key={w.id} style={{borderBottom:"1px solid #edf0f6",padding:"17px 0"}}><div className="story-meta"><span className="event-level event-level-watch">{w.cadence==="weekly"?"주간":"월간"} 정의</span><span>실시간 평가 연동 전</span></div><div className="story-title">{nodeName(w.target_id)}</div><p style={{fontSize:11,color:"#8090a2",lineHeight:1.8,margin:0}}>{w.condition}</p></div>)}</div></section>
   </div>
   <SectionHeading eyebrow="PUBLIC COMPANIES / SUPPLY CHAIN" title="관련 공급기업·기술 주체" subtitle="공급 가능성은 검증된 납품계약과 다릅니다."/>
   <div className="insight-cols">{companies.map(n=><div className="insight-box" key={n.id}><div className="eyebrow">{n.role==="customer"?"CUSTOMER / DEMAND":n.role==="both"?"PRODUCER":"SUPPLIER CANDIDATE"}{n.in_universe?" · IN UNIVERSE":""}</div><h3>{n.label}</h3><p>{n.listing?.ticker?`${n.listing.ticker} · ${n.listing.filer_type} · ${n.size_band??""}`:"비상장 / 비SEC"}. 관계는 기술 보유·협업까지이며 매출 증거가 아닙니다.</p><Link href={`/search?q=${encodeURIComponent(n.label.split(" ")[0])}`}>관련 자료 찾기 <Icon name="arrow-right" size={14}/></Link></div>)}</div>
   <SectionHeading eyebrow="PRIMARY SOURCES" title="핵심 참고 원문"/>
   <div className="surface" style={{padding:"8px 20px"}}>{Array.from(new Set([...eco.sources,...sources])).map((url,i)=><a key={url} className="related-list" href={url} target="_blank" rel="noreferrer"><span style={{display:"flex",gap:10,alignItems:"center",padding:"10px 0",borderBottom:"1px solid #edf0f6",wordBreak:"break-all",fontSize:11,color:"#5972a2"}}><Icon name="external" size={15}/><span>{new URL(url).hostname} · {url}</span></span></a>)}</div>
 </div>;
}
