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
  <div className="page-head"><div><div className="page-kicker">SIGNAL STREAM / 02</div><h1>최근 기술 변화와 투자 단서</h1><p>공시·표준·제품 사양·고객 발표를 같은 피드에서 살펴보세요. 단순한 뉴스보다 기술적 병목과 기업에 미치는 영향에 집중합니다.</p></div><Link href="/triggers" className="outline-button"><Icon name="radar" size={17}/> 트리거 조건</Link></div>
  <div className="notice-inline"><Icon name="shield" size={15}/> 기존 수집 DB의 기업 신호와 검증된 기술 리서치 시드를 함께 보여줍니다. 기술 이벤트는 최초 공개일 기준이며, 새로운 이벤트 자동 수집·그래프 DB 연동은 구축 단계입니다.</div>
  <form className="filterbar" action="/feed" method="get">
   <input aria-label="피드에서 검색" type="search" name="q" placeholder="이슈·회사·기술 키워드 검색" defaultValue={q}/>
   <select aria-label="생태계" name="eco" defaultValue={eco}><option value="">모든 생태계</option>{ECOSYSTEMS.map(e=><option key={e.id} value={e.id}>{e.title}</option>)}<option value="market">기존 기업 신호</option></select>
   <select aria-label="중요도" name="level" defaultValue={level}><option value="">모든 중요도</option><option value="high">핵심 변화</option><option value="medium">기술 동향</option><option value="watch">관찰 신호</option></select>
   <button type="submit"><Icon name="filter" size={14}/> 필터 적용</button><span className="count">{rows.length}건 표시</span>
  </form>
  <div className="feed-layout">
   <div className="surface feed-list">{rows.length?rows.map(x=><FeedStory key={x.id} item={x}/>):<EmptyState title="검색된 이슈가 없습니다" copy="필터를 조정하거나 전체 생태계의 공개 근거를 살펴보세요." href="/feed"/>}</div>
   <aside style={{display:"flex",flexDirection:"column",gap:15}}>
    <div className="surface aside-panel"><div className="eyebrow">STREAM SOURCES</div><h3 style={{marginTop:8}}>지금 보고 있는 자료</h3><div className="aside-metric"><span>큐레이션된 기술 이벤트</span><strong>{seed.events.length}</strong></div><div className="aside-metric"><span>기존 DB 기업 신호</span><strong>{live.signals.length}</strong></div><div className="aside-metric"><span>기술 생태계</span><strong>{ECOSYSTEMS.length}</strong></div><p>기업 신호는 기존 Supabase 자료입니다. 기술 이벤트는 연구 시드이며 최신 자동 수집 결과가 모두 반영되는 라이브 DB는 아직 아닙니다.</p></div>
    <div className="surface aside-panel"><h3>분야별 바로가기</h3><div className="aside-links">{ECOSYSTEMS.map(e=><Link key={e.id} href={`/feed?eco=${e.id}`}><Icon name={e.glyph as "cpu"|"network"|"zap"} size={15}/>{e.title}<Icon name="chevron-right" size={13}/></Link>)}</div></div>
   </aside>
  </div>
 </div>;
}
