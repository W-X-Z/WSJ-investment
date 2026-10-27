import Link from "next/link";
import { Icon } from "@/components/Icon";
import { EmptyState } from "@/components/ResearchCards";
import { ECOSYSTEMS, loadLiveData, mergeFeed, seed, type EcoId } from "@/lib/research";
import { loadIdeas } from "@/lib/ideas";

export const dynamic="force-dynamic";
export const metadata={title:"통합 검색"};
type SP={q?:string};
export default async function Search({searchParams}:{searchParams:Promise<SP>}){
 const sp=await searchParams;const q=(sp.q??"").trim();const term=q.toLocaleLowerCase("ko-KR");
 const live=await loadLiveData(); const events=mergeFeed(live); const {ideas}=await loadIdeas();
 const nodes=term?seed.nodes.filter(x=>[x.id,x.label,x.kind,...(x.measured_metrics??[])].join(" ").toLocaleLowerCase("ko-KR").includes(term)).slice(0,24):[];
 const foundEvents=term?events.filter(x=>[x.title,x.summary,x.type,x.target??"",x.source].join(" ").toLocaleLowerCase("ko-KR").includes(term)).slice(0,20):[];
 const foundIdeas=term?ideas.filter(x=>[x.title,x.thesis,...x.companies.flatMap(c=>[c.name,c.ticker??""]),...x.chain.map(c=>c.claim)].join(" ").toLocaleLowerCase("ko-KR").includes(term)).slice(0,16):[];
 const ecosystems=term?ECOSYSTEMS.filter(x=>[x.title,x.name,x.bottleneck,x.trajectory,x.summary].join(" ").toLocaleLowerCase("ko-KR").includes(term)):[];
 const total=nodes.length+foundEvents.length+foundIdeas.length+ecosystems.length;
 function guessEco(nodeId:string):EcoId {
   if(nodeId.includes("optic")||nodeId.includes("poet")||nodeId.includes("laser")||nodeId.includes("photodiode"))return "optics";
   if(nodeId.includes("800v")||nodeId.includes("power")||nodeId.includes("sic")||nodeId.includes("dc_")||nodeId.includes("aehr")||nodeId.includes("copper"))return "power";
   return "hbm";
 }
 return <div>
  <div className="page-head"><div><div className="page-kicker">RESEARCH SEARCH</div><h1>연결된 기술·기업·근거 검색</h1><p>공급망 관계, 소재·부품·공정, 수치 변수, 투자 가설과 공개 원천 이슈를 함께 검색합니다.</p></div></div>
  <form action="/search" method="get" className="filterbar" style={{padding:"16px",background:"#fff",border:"1px solid #e1e7f1",borderRadius:11}}>
    <Icon name="search" size={21}/><input style={{border:0,outline:0,fontSize:15}} autoFocus type="search" name="q" defaultValue={q} placeholder="예: HBM · 광결합 손실 · CAMT · SiC"/>
    <button type="submit">검색 <Icon name="arrow-right" size={15}/></button>
  </form>
  {!q?<div><SectionSuggestions/></div>:total===0?<div className="surface"><EmptyState title={`“${q}”에 대한 결과를 찾지 못했습니다`} copy="검색어를 줄이거나 기술 분야명, 회사 티커, 공정명을 사용해보세요."/></div>:<div>
   <div className="notice-inline"><Icon name="search" size={15}/> <span>“{q}” 검색 결과 <strong>{total}건</strong></span></div>
   {ecosystems.length>0&&<section><h2 className="section-heading" style={{fontSize:17,fontWeight:750}}>기술 생태계 <span className="soft-text">{ecosystems.length}</span></h2><div className="data-links-grid">{ecosystems.map(e=><Link key={e.id} className="data-link" href={`/ecosystems/${e.id}`}><Icon name={e.glyph as "cpu"|"network"|"zap"} size={18}/>{e.title}<Icon name="arrow-right" size={15}/></Link>)}</div></section>}
   {nodes.length>0&&<section><div className="section-heading"><h2>기술·소재·공정 그래프 <span className="soft-text">{nodes.length}</span></h2></div><div className="surface" style={{padding:"8px 20px"}}><div className="related-list">{nodes.map(n=><Link href={`/ecosystems/${guessEco(n.id)}`} key={n.id}><span style={{display:"flex",flexDirection:"column",gap:3}}><strong>{n.label}</strong><span style={{fontSize:10,color:"#95a1b0"}}>{n.kind} · {n.measured_metrics?.join(" · ")??"관계 그래프에서 상세 확인"}</span></span><Icon name="chevron-right" size={16}/></Link>)}</div></div></section>}
   {foundEvents.length>0&&<section><div className="section-heading"><h2>연결된 이슈 <span className="soft-text">{foundEvents.length}</span></h2></div><div className="surface"><div className="related-list" style={{padding:"4px 20px"}}>{foundEvents.map(e=><Link href={`/feed/${encodeURIComponent(e.id)}`} key={e.id}><span style={{display:"flex",flexDirection:"column",gap:3}}><strong>{e.title}</strong><span style={{fontSize:10,color:"#95a1b0"}}>{e.date} · {e.type} · {e.source}</span></span><Icon name="chevron-right" size={16}/></Link>)}</div></div></section>}
   {foundIdeas.length>0&&<section><div className="section-heading"><h2>투자 아이디어 <span className="soft-text">{foundIdeas.length}</span></h2></div><div className="surface"><div className="related-list" style={{padding:"4px 20px"}}>{foundIdeas.map(x=><Link href={`/ideas/${x.idea_key}`} key={x.idea_key}><span style={{display:"flex",flexDirection:"column",gap:3}}><strong>{"★".repeat(x.stars)} {x.title}</strong><span style={{fontSize:10,color:"#95a1b0"}}>{x.companies.map(c=>c.name).slice(0,3).join(" · ")}</span></span><Icon name="chevron-right" size={16}/></Link>)}</div></div></section>}
  </div>}
 </div>;
}
function SectionSuggestions(){return <><div className="section-heading"><div><div className="eyebrow">QUICK START</div><h2>주요 분야로 시작하기</h2></div></div><div className="data-links-grid">{[["HBM4","HBM"],["광엔진","광"],["고전압 DC","800V"],["반도체 검사","검사"],["POET","POET"],["SiC 번인","SiC"]].map(([label,q])=><Link key={label} className="data-link" href={`/search?q=${encodeURIComponent(q)}`}><Icon name="search" size={15}/>{label}<Icon name="arrow-up-right" size={15}/></Link>)}</div></>}
