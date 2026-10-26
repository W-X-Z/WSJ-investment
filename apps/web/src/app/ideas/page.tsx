import Link from "next/link";
import { Icon } from "@/components/Icon";
import { EmptyState, IdeaTile } from "@/components/ResearchCards";
import { ECOSYSTEMS, loadLiveData, mergeIdeas } from "@/lib/research";

export const dynamic="force-dynamic";
export const metadata={title:"투자 가설"};
type Params={eco?:string; state?:string; q?:string};
export default async function Ideas({searchParams}:{searchParams:Promise<Params>}){
 const sp=await searchParams;
 const live=await loadLiveData(); const ideas=mergeIdeas(live);
 const eco=sp.eco??"",state=sp.state??"",q=(sp.q??"").trim().toLowerCase();
 const filtered=ideas.filter(x=>(!eco||x.ecoId===eco)&&(!state||x.state===state)&&(!q||[x.ticker,x.company,x.title,x.description,x.trigger,x.risk].join(" ").toLowerCase().includes(q)));
 return <div>
  <div className="page-head"><div><div className="page-kicker">THESIS WORKBENCH / 03</div><h1>가치가 달라질 수 있는 이유</h1><p>사업의 확정적인 결론이 아니라, 공개 근거로 검증하고 반증할 수 있는 가설을 관리합니다. 기술적 적합성, 고객 양산, 실제 경제성은 별도 단계입니다.</p></div><Link href="/triggers" className="outline-button"><Icon name="target" size={16}/> 다음 검증 사건</Link></div>
  <form action="/ideas" method="get" className="filterbar">
   <input type="search" aria-label="투자 가설 검색" name="q" defaultValue={sp.q??""} placeholder="기업·티커·기술·반대 근거 검색"/>
   <select aria-label="생태계 필터" name="eco" defaultValue={eco}><option value="">모든 생태계</option>{ECOSYSTEMS.map(x=><option key={x.id} value={x.id}>{x.title}</option>)}<option value="market">기존 기업 브리프</option></select>
   <select aria-label="가설 상태" name="state" defaultValue={state}><option value="">모든 상태</option><option value="strengthened">근거 강화</option><option value="watching">검증 중</option><option value="exploring">초기 가설</option><option value="weakened">근거 약화</option></select>
   <button type="submit"><Icon name="filter" size={14}/> 적용</button><span className="count">{filtered.length}건</span>
  </form>
  <div className="notice-inline"><Icon name="alert" size={15}/> 아래 산업·기업 연결 중 일부는 조건부 연구 가설입니다. 실제 공급 계약·실적·주가 수익을 확인한 투자 추천으로 해석하면 안 됩니다.</div>
  {filtered.length?<div className="idea-grid">{filtered.map(i=><IdeaTile idea={i} key={i.id}/>)}</div>:<div className="surface"><EmptyState title="조건에 맞는 투자 가설이 없습니다" copy="검색어 또는 분야 필터를 조정해 보세요." href="/ideas"/></div>}
 </div>;
}
