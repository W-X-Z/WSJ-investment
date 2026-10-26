import Link from "next/link";
import { Icon } from "@/components/Icon";
import { EmptyState, FeedStory } from "@/components/ResearchCards";
import { ECOSYSTEMS, loadLiveData, mergeFeed, seed, type EcoId } from "@/lib/research";

export const dynamic = "force-dynamic";
export const metadata = { title:"기술·투자 이슈 피드" };
type SP = {eco?:string; q?:string; level?:string};
export default async function FeedPage({searchParams}:{searchParams:Promise<SP>}) {
 const sp=await searchParams; const eco=sp.eco??""; const q=(sp.q??"").trim(); const level=sp.level??"";
 const live=await loadLiveData(); const all=mergeFeed(live);
 const rows=all.filter(x=>(!eco||x.ecoId===eco)&&(!level||x.significance===level)&&(!q||[x.title,x.summary,x.source,x.target??"",x.type].join(" ").toLowerCase().includes(q.toLowerCase())));
 return <div>
  <div className="page-head"><div><div className="page-kicker">SIGNAL STREAM / 02</div><h1>최근 기술 변화와 투자 단서</h1><p>뉴스·공시·관보·업계지에서 고른 공급망 이슈와 기업 신호.</p></div><Link href="/triggers" className="outline-button"><Icon name="radar" size={17}/> 트리거 조건</Link></div>
  <form className="filterbar" action="/feed" method="get">
   <input aria-label="피드에서 검색" type="search" name="q" placeholder="이슈·회사·기술 키워드 검색" defaultValue={q}/>
   <select aria-label="생태계" name="eco" defaultValue={eco}><option value="">모든 생태계</option>{ECOSYSTEMS.map(e=><option key={e.id} value={e.id}>{e.title}</option>)}<option value="cross">공급망 공통</option><option value="market">기업 신호</option></select>
   <select aria-label="중요도" name="level" defaultValue={level}><option value="">모든 중요도</option><option value="high">핵심 변화</option><option value="medium">기술 동향</option><option value="watch">관찰 신호</option></select>
   <button type="submit"><Icon name="filter" size={14}/> 필터 적용</button><span className="count">{rows.length}건 표시</span>
  </form>
  <div className="feed-layout">
   <div className="surface feed-list">{rows.length?rows.map(x=><FeedStory key={x.id} item={x}/>):<EmptyState title="검색된 이슈가 없습니다" copy="필터를 조정하거나 전체 생태계의 공개 근거를 살펴보세요." href="/feed"/>}</div>
   <aside style={{display:"flex",flexDirection:"column",gap:15}}>
    <div className="surface aside-panel"><div className="eyebrow">SOURCES</div><div className="aside-metric"><span>공급망 이슈 (21일)</span><strong>{live.issues.length}</strong></div><div className="aside-metric"><span>기업 신호</span><strong>{live.signals.length}</strong></div><div className="aside-metric"><span>기술 이벤트</span><strong>{seed.events.length}</strong></div></div>
    <div className="surface aside-panel"><h3>분야별 바로가기</h3><div className="aside-links">{ECOSYSTEMS.map(e=><Link key={e.id} href={`/feed?eco=${e.id}`}><Icon name={e.glyph as "cpu"|"network"|"zap"} size={15}/>{e.title}<Icon name="chevron-right" size={13}/></Link>)}</div></div>
   </aside>
  </div>
 </div>;
}
