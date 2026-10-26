import Link from "next/link";
import { Icon } from "@/components/Icon";
import { EcosystemCard, SectionHeading } from "@/components/ResearchCards";
import { GraphExplorer } from "@/components/GraphExplorer";
import { ECOSYSTEMS, seed } from "@/lib/research";

export const metadata = { title: "기술 생태계" };

export default function Ecosystems() {
  return <div>
    <div className="page-head"><div><div className="page-kicker">ECOSYSTEM INTELLIGENCE / 01</div><h1>산업을 이루는 기술의 지도를 탐색하다</h1><p>최종 제품이 아니라 소재·부품·공정·계측·전력의 기술적 제약에서 출발합니다. 각 관계에는 공개 근거와 미해결 검증 항목이 연결됩니다.</p></div><Link href="/search" className="outline-button"><Icon name="search" size={16}/> 전체 검색</Link></div>
    <div className="ecosystem-grid">{ECOSYSTEMS.map((eco,i)=><EcosystemCard key={eco.id} eco={eco} index={i}/>)}</div>
    <SectionHeading eyebrow="DEPENDENCY EXPLORER" title="기술적 병목에서 공급기업까지" subtitle="관련 회사 표시만으로 매출 수혜를 확정하지 않습니다. 연결 관계를 클릭해 근거를 확인하세요." href="/ecosystems/hbm" action="확대 분석"/>
    <GraphExplorer ecoId="hbm" compact/>
    <SectionHeading eyebrow="RESEARCH FRAMEWORK" title="연구 깊이를 결정하는 네 가지 질문"/>
    <div className="insight-cols">
      {[
        ["기술의 변화","성능·규격·공정 조건 중 정확히 어떤 값이 달라졌는가?"],
        ["새로운 병목","그 변화 때문에 해결해야 하는 공학적 문제가 무엇인가?"],
        ["공급망 연결","어떤 소재·부품·공정이 필요하며 공급자는 누구인가?"],
        ["경제적 효과","실제 채택 시 수량·단가·마진·교체주기 가운데 무엇이 변하는가?"],
      ].map((x,i)=><div className="insight-box" key={x[0]}><div className="eyebrow">{String(i+1).padStart(2,"0")} / FRAMEWORK</div><h3>{x[0]}</h3><p>{x[1]}</p></div>)}
    </div>
    <div className="data-banner"><Icon name="shield" size={20}/><div><strong>출처·검증 수준을 포함한 {seed.edges.length}개 관계</strong><p>표준·공식 자료, 제조사 주장, 기술적 추론을 구분합니다. 완전한 고객 BOM이나 매출 기여가 확인되지 않은 경우 명시적으로 미확인으로 처리합니다.</p></div><Link href="/triggers">변화 추적 <Icon name="arrow-right" size={15}/></Link></div>
  </div>;
}
