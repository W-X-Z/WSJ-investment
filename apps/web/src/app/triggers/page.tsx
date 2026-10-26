import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ECOSYSTEMS, ECO_BY_ID, graphDate, nodeName, seed, type EcoId } from "@/lib/research";

export const metadata={title:"트리거 추적"};
type SP={eco?:string;q?:string};
export default async function Triggers({searchParams}:{searchParams:Promise<SP>}){
 const sp=await searchParams;const eco=sp.eco??"";const q=(sp.q??"").trim().toLowerCase();
 const rows=seed.watches.filter(w=>(!eco||w.ecosystem===`eco:${eco}`)&&(!q||[w.condition,w.signal,w.target_id,w.confirmations_needed].join(" ").toLowerCase().includes(q)));
 return <div>
  <div className="page-head"><div><div className="page-kicker">CHANGE WATCH / 04</div><h1>어떤 사실이 달라지면 가설을 다시 볼까?</h1><p>기술 표준·제품 성능·고객 채택·생산 일정의 변화 조건을 미리 정의합니다. 긍정적 변화뿐 아니라 기존 기술의 대체와 실패 신호도 추적합니다.</p></div><Link href="/feed" className="outline-button"><Icon name="rss" size={16}/> 이슈 피드</Link></div>
  <div className="notice-inline"><Icon name="alert" size={16}/> <span>현재 화면은 <strong>9개 감시 규칙의 정의 및 검증 기준</strong>을 보여줍니다. 기존 GitHub 데이터 수집 워크플로는 별도로 운영 중이나, 이 9개 조건의 자동 판정·푸시 알림과 정식 지식 그래프 DB 연동은 아직 구현 전입니다.</span></div>
  <form action="/triggers" method="get" className="filterbar">
   <input type="search" name="q" aria-label="트리거 검색" placeholder="감시 조건·성능 지표 검색" defaultValue={sp.q??""}/>
   <select name="eco" aria-label="생태계" defaultValue={eco}><option value="">전체 생태계</option>{ECOSYSTEMS.map(e=><option key={e.id} value={e.id}>{e.title}</option>)}</select>
   <button type="submit"><Icon name="filter" size={14}/> 필터 적용</button><span className="count">{rows.length}개 규칙</span>
  </form>
  <div className="watch-list">{rows.map(w=>{
    const id=w.ecosystem.replace("eco:","") as EcoId;const e=ECO_BY_ID[id];
    return <article className="watch-card" key={w.id}>
      <div className="watch-card-head"><span>{e?.label??w.ecosystem}</span><span className="event-level event-level-watch">{w.cadence==="weekly"?"주간 점검 조건":"월간 점검 조건"}</span></div>
      <div className="watch-card-title">{nodeName(w.target_id)}</div>
      <div className="eyebrow" style={{letterSpacing:".7px",fontSize:9}}>IF / TRIGGER CONDITION</div>
      <p>{w.condition}</p>
      <div className="eyebrow" style={{letterSpacing:".7px",fontSize:9}}>THEN / VALIDATE</div>
      <p>{w.confirmations_needed}</p>
      <div className="watch-card-foot"><span className="watch-card-flag"><i/> 규칙 정의됨 · 자동 판정 미연동</span><Link href={`/ecosystems/${id}`} className="section-action">영향 경로 <Icon name="arrow-right" size={14}/></Link></div>
    </article>;
   })}</div>
  <div className="insight-cols">
   {[["01","수집·스냅샷","공시·표준·논문 원문을 주기적으로 확인하고 이전 버전과 비교합니다."],["02","가설 영향 분석","변화가 기술적 요구·병목·대체 기술·기업 노출에 어떻게 연결되는지 분석합니다."],["03","인간 검증 및 추적","독립 원천과 실제 고객 채택을 확인한 뒤 중요한 변화만 투자 리서치에 반영합니다."]].map(x=><div className="insight-box" key={x[0]}><div className="eyebrow">{x[0]} / WORKFLOW</div><h3>{x[1]}</h3><p>{x[2]}</p></div>)}
  </div>
  <p className="soft-text"><a href="https://github.com/W-X-Z/WSJ-investment/actions/workflows/technology-intelligence-monitor.yml" target="_blank" rel="noreferrer">6시간 모니터 실행 로그 ↗</a></p>
 </div>;
}
