import Link from "next/link";
import { Icon } from "@/components/Icon";
export const metadata={title:"원천 데이터 워크스페이스"};
const GROUPS=[
 {title:"적재·모니터링",items:[["/data/collectors","수집기 실행·데이터 행 수"],["/entities","엔티티 매칭"],["/companies","상장기업 유니버스"]]},
 {title:"기존 분석",items:[["/briefs","기업 분석 브리프"],["/candidates","기존 후보 스크리너"],["/signals","종목별 신호"]]},
 {title:"원천 데이터",items:[["/filings","SEC 공시"],["/insider","내부자 거래"],["/finra","공매도·수급"],["/fda","FDA"],["/trials","임상시험"],["/awards","정부계약"]]},
];
export default function ResearchData(){return <div><div className="page-head"><div><div className="page-kicker">OPERATIONS / RESEARCH ARCHIVE</div><h1>데이터 워크스페이스</h1><p>기존 적재 상태·SEC·FDA·수급 원문 조회 기능은 여기에서 계속 사용할 수 있습니다. 새로운 메인 화면은 변화 탐지와 투자 가설에 집중합니다.</p></div><Link href="/" className="outline-button"><Icon name="arrow-right" size={15}/> 인사이트 홈</Link></div>
 {GROUPS.map(group=><section key={group.title}><div className="section-heading"><div><div className="eyebrow">DATA ACCESS / 02 DEPTH</div><h2>{group.title}</h2></div></div><div className="data-links-grid">{group.items.map(([href,label])=><Link className="data-link" key={href} href={href}><Icon name="database" size={17}/>{label}<Icon name="chevron-right" size={15}/></Link>)}</div></section>)}
 <div className="data-banner"><Icon name="shield" size={21}/><div><strong>원천 데이터와 투자 가설의 역할 분리</strong><p>이 영역은 적재와 검증을 위한 보조 기능입니다. 실질적인 해석과 영향 분석은 생태계·피드·투자 가설 화면에서 제공합니다.</p></div><Link href="/ecosystems">기술 지도 <Icon name="arrow-right" size={15}/></Link></div>
 </div>}
