import Link from "next/link";
import { Icon } from "@/components/Icon";
import { EcosystemCard, FeedStory, IdeaTile, SectionHeading } from "@/components/ResearchCards";
import { GraphExplorer } from "@/components/GraphExplorer";
import { ECOSYSTEMS, loadLiveData, mergeFeed, mergeIdeas, seed } from "@/lib/research";

export const dynamic = "force-dynamic";

function Metric({ title,value,caption,icon }: { title:string;value:string|number;caption:string;icon:"layers"|"network"|"radar"|"file" }) {
  return <div className="overview-metric">
    <div className="overview-metric-head"><span>{title}</span><Icon name={icon} size={16}/></div>
    <div className="overview-metric-number"><strong>{value}</strong></div>
    <div className="overview-metric-foot">{caption}</div>
  </div>;
}

export default async function Home() {
  const live = await loadLiveData();
  const feed = mergeFeed(live);
  const ideas = mergeIdeas(live);
  const wBy = ECOSYSTEMS.map(eco=>({label:eco.name,value:seed.watches.filter(w=>w.ecosystem===`eco:${eco.id}`).length}));
  return <div>
    <section className="hero">
      <div className="hero-main">
        <div className="hero-kicker"><i/> TECHNOLOGY-DRIVEN INVESTMENT INTELLIGENCE</div>
        <h1>기술의 변화를 읽고,<br/><em>가치의 연결을 발견합니다.</em></h1>
        <p className="hero-description">소재·부품·공정에서 시작되는 기술적 병목을 탐색하고, 공개 근거를 연결해 아직 검증되지 않은 투자 가설까지 추적합니다.</p>
        <div className="hero-actions">
          <Link className="hero-primary" href="/ecosystems">기술 생태계 탐색 <Icon name="arrow-right" size={16}/></Link>
          <Link className="hero-secondary" href="/feed">최신 변화 살펴보기 <Icon name="arrow-up-right" size={15}/></Link>
        </div>
      </div>
      <div className="hero-side">
        <div className="hero-side-label">FOCUS AREAS / RESEARCH COVERAGE</div>
        <div className="hero-track">{wBy.map(x=><div className="hero-track-row" key={x.label}><strong>{x.label}</strong><div className="hero-track-bar"><i style={{width:`${Math.round(x.value/3*100)}%`}}/></div><span>{x.value}</span></div>)}</div>
        <div className="hero-side-note"><span>분야별 정의된 감시 규칙</span><strong>{seed.watches.length} WATCH RULES</strong></div>
      </div>
    </section>
    <div className="overview-metrics">
      <Metric title="집중 연구 생태계" value={ECOSYSTEMS.length} caption="HBM · 광통신 · 전력 인프라" icon="layers"/>
      <Metric title="기술·기업 관계 노드" value={seed.nodes.length} caption="세부 소재·부품·공정 포함" icon="network"/>
      <Metric title="출처 기반 연결 관계" value={seed.edges.length} caption="검증된 사실과 추론을 구별" icon="file"/>
      <Metric title="트리거 감시 규칙" value={seed.watches.length} caption="규칙 초안 · 실제 실행 상태는 별도" icon="radar"/>
    </div>
    <SectionHeading eyebrow="01 / ECOSYSTEM INTELLIGENCE" title="핵심 산업 기술 생태계" subtitle="최종 제품보다 더 깊은 곳의 병목과 해결 기술을 살펴보세요." href="/ecosystems"/>
    <section className="ecosystem-grid">{ECOSYSTEMS.map((eco,i)=><EcosystemCard key={eco.id} eco={eco} index={i}/>)}</section>
    <div className="dashboard-dual">
      <section>
        <SectionHeading eyebrow="02 / WHAT CHANGED" title="최근 주요 기술 이슈" subtitle="자료 원문 공개일을 기준으로 정렬한 연구 이벤트" href="/feed" action="이슈 피드 열기"/>
        <div className="surface feed-list">{feed.slice(0,4).map(x=><FeedStory item={x} key={x.id}/>)}</div>
      </section>
      <section>
        <SectionHeading eyebrow="03 / INVESTMENT THESES" title="주목할 투자 가설" subtitle="경제적 수혜가 입증되기 전인 검증 후보 포함" href="/ideas" action="모든 가설"/>
        <div className="surface feed-list">
          {ideas.slice(0,3).map(idea=><Link href={idea.href??`/ideas/${idea.id}`} className="story" key={idea.id} style={{display:"block"}}>
            <div className="story-meta"><span className="ticker-badge">{idea.ticker}</span><span>{idea.company}</span><span className="meta-sep">·</span><span>{idea.state==="strengthened"?"근거 강화":"검증 진행"}</span></div>
            <div className="story-title" style={{marginTop:10}}>{idea.title}</div>
            <p style={{margin:0,color:"#8490a2",fontSize:11,lineHeight:1.75}}>{idea.description}</p>
            <div className="story-foot" style={{marginTop:11}}><span className="event-level event-level-watch">{idea.live?"운영 DB 브리프":"연구 시드"}</span><span className="story-source">다음 검증 필요</span></div>
          </Link>)}
        </div>
      </section>
    </div>
    <SectionHeading eyebrow="04 / SUPPLY CHAIN IMPACT MAP" title="기술 변화의 영향 경로" subtitle="노드를 선택하면 기술 의존관계와 근거·미확인 사항을 함께 확인합니다." href="/ecosystems/hbm" action="전체 지도 보기"/>
    <GraphExplorer ecoId="hbm" compact/>
    <SectionHeading eyebrow="05 / DEEPER RESEARCH" title="기술에서 기업까지" subtitle="기술적 적합성과 실제 고객 매출을 구별해 보는 투자 가설" href="/ideas"/>
    <div className="idea-grid">{ideas.slice(0,3).map(idea=><IdeaTile key={idea.id} idea={idea}/>)}</div>
    <div className="data-banner"><Icon name="database" size={20}/><div><strong>근거 중심 리서치 · 2026.10.26 기술 생태계 스냅샷</strong><p>{live.online?"기존 Supabase 기업 신호·브리프를 함께 조회합니다.":"기존 DB와 연결되지 않은 경우에도 검증 가능한 연구 시드를 표시합니다."} 연구 그래프는 수집 시점 이후의 공개 원문으로 검증이 필요합니다.</p></div><Link href="/data">데이터실 <Icon name="arrow-right" size={15}/></Link></div>
  </div>;
}
