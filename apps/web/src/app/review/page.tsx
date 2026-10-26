import Link from "next/link";
import { Icon } from "@/components/Icon";
import graph from "@/data/ecosystem-seed.json";
import candidates from "@/data/relation-candidates.json";

type Candidate={left_node_id:string;right_node_id:string;shared_source_count:number;years:string[];example_documents:{source_id:string;url:string;title:string;published_at:string}[];status:string;should_create_graph_edge:boolean};
type SP={q?:string;kind?:string;page?:string};
const graphNodes=new Map(graph.nodes.map(n=>[n.id,n]));
const existing=new Set(graph.edges.map(e=>[e.from,e.to].sort().join("|")));
const safeNumber=(value:string|undefined)=>{const n=Number(value);return Number.isSafeInteger(n)?Math.max(1,n):1;};
const pairKind=(x:Candidate)=>[graphNodes.get(x.left_node_id)?.kind,graphNodes.get(x.right_node_id)?.kind].includes("company")?"company":"technical";
function priority(x:Candidate){
 const breadth=Math.min(x.years.length,7);
 const volume=Math.min(5,Math.log2(1+x.shared_source_count));
 const commercial=pairKind(x)==="company"?3:0;
 return Math.round((breadth*.6+volume+commercial)*10)/10;
}
export const metadata={title:"관계 후보 검토 | Signal Atlas"};
export default async function RelationReview({searchParams}:{searchParams:Promise<SP>}){
 const sp=await searchParams;
 const q=(sp.q??"").trim().toLowerCase().slice(0,120),kind=sp.kind??"all",page=safeNumber(sp.page);
 const rows=(candidates.candidates as Candidate[]).map(x=>({
  ...x,left:graphNodes.get(x.left_node_id),right:graphNodes.get(x.right_node_id),
  existing:existing.has([x.left_node_id,x.right_node_id].sort().join("|")),score:priority(x),
 })).filter(x=>(kind==="all"||kind==="company"&&pairKind(x)==="company"||kind==="technical"&&pairKind(x)==="technical"||kind==="unmapped"&&!x.existing)
  &&(!q||[x.left?.label,x.right?.label,x.left_node_id,x.right_node_id,...x.example_documents.map(d=>d.title)].join(" ").toLowerCase().includes(q)))
  .sort((a,b)=>b.score-a.score||b.shared_source_count-a.shared_source_count);
 const pageSize=12,totalPages=Math.max(1,Math.ceil(rows.length/pageSize)),p=Math.min(page,totalPages);
 const selected=rows.slice((p-1)*pageSize,p*pageSize);
 const pageLink=(n:number)=>"/review?"+new URLSearchParams({q,kind,page:String(n)}).toString();
 return <div className="review-screen">
  <div className="map-screen-header"><div><span className="page-kicker">GRAPH DISCOVERY / HUMAN REVIEW QUEUE</span><h1>새로운 기술 연결 후보</h1><p>과거 공개자료의 동시 언급을 검토해, 기존 산업망에서 빠진 관계를 발견합니다.</p></div><Link href="/map" className="outline-button"><Icon name="network" size={16}/> 산업망 캔버스</Link></div>
  <div className="review-stats">
   <div><small>문헌 동시언급 후보</small><strong>{candidates.summary.relation_pairs}</strong></div>
   <div><small>기존 그래프에 없는 후보</small><strong>{(candidates.candidates as Candidate[]).filter(x=>!existing.has([x.left_node_id,x.right_node_id].sort().join("|"))).length}</strong></div>
   <div><small>독립 검증 완료 신규 관계</small><strong>0</strong></div>
  </div>
  <div className="history-notice"><Icon name="info" size={17}/><span>두 기술이 같은 논문에 등장했다는 사실만으로 공급·대체·인과 관계를 입증할 수 없습니다. 우선순위는 동시 언급 빈도·연도 폭·기업 연관성에 따른 <strong>검토 순서</strong>이며 투자 점수가 아닙니다. 승인되지 않은 후보는 그래프에 자동 추가되지 않습니다.</span></div>
  <form className="history-filters" action="/review"><label><Icon name="search" size={16}/><input name="q" defaultValue={sp.q??""} placeholder="기술, 소재, 기업, 논문 제목 검색" aria-label="관계 후보 검색"/></label>
   <select name="kind" defaultValue={kind} aria-label="후보 유형"><option value="all">전체 관계</option><option value="unmapped">그래프에 없는 관계</option><option value="company">기업 연관</option><option value="technical">기술·공정 연관</option></select><button type="submit">적용</button><Link href="/review">초기화</Link>
  </form>
  <div className="review-grid">{selected.length?selected.map(x=><article key={x.left_node_id+"|"+x.right_node_id} className="review-card">
   <div className="review-top"><span>REVIEW PRIORITY {x.score.toFixed(1)}</span><span>{x.existing?"기존 그래프에 관계 있음":"신규 연결 후보 · 미확인"}</span></div>
   <div className="review-pair"><div><small>{x.left?.kind??"기술"}</small><strong>{x.left?.label??x.left_node_id}</strong></div><Icon name="link" size={19}/><div><small>{x.right?.kind??"기술"}</small><strong>{x.right?.label??x.right_node_id}</strong></div></div>
   <div className="review-count"><span>동시 언급 {x.shared_source_count.toLocaleString("ko-KR")}건</span><span>{x.years[0]}–{x.years[x.years.length-1]}</span><span>검증 대기</span></div>
   <h3>검토할 원문</h3>
   {x.example_documents.map(d=><a key={d.source_id} href={d.url} target="_blank" rel="noopener noreferrer" className="review-document"><small>{d.published_at}</small><span>{d.title}</span><Icon name="arrow-up-right" size={14}/></a>)}
   <p className="review-question">원문에서 실제 물리적 의존성·성능 개선·공정 적용이 확인되는가? 기업 공급계약·매출 연결은 별도 증빙이 있는가?</p>
   <Link href={"/map?focus="+encodeURIComponent(x.left_node_id)} className="review-explore"><Icon name="network" size={15}/> 그래프에서 관련 노드 보기</Link>
  </article>):<p className="history-empty">일치하는 검토 후보가 없습니다.</p>}</div>
  <div className="history-page-controls"><span>{rows.length}개 후보 · {p}/{totalPages} 페이지</span><div>{p>1&&<Link href={pageLink(p-1)}>이전</Link>}{p<totalPages&&<Link href={pageLink(p+1)}>다음</Link>}</div></div>
 </div>;
}
