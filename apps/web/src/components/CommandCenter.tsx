"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { GraphExplorer } from "@/components/GraphExplorer";
import { IndustryMilestones } from "@/components/IndustryMilestones";
import { type EcoId } from "@/lib/research-client";

type Story = {id:string;title:string;summary:string;date:string;ecoId:string;type:string;source:string;significance:string;status:string;sourceUrl?:string;target?:string;importance?:number};
type Thesis = {id:string;ticker:string;company:string;title:string;description:string;ecoId:string;state:string;trigger:string;risk:string;href?:string;live?:boolean};
type Ecosystem = {id:EcoId;title:string;summary:string;bottleneck:string;trajectory:string;metric:string;metricLabel:string};
const ORDER:EcoId[]=["hbm","optics","power"];
const NAMES:Record<string,string>={hbm:"첨단 패키징",optics:"광통신·포토닉스",power:"전력·냉각",cross:"공급망 공통",market:"기업 공시"};
const STATUS:Record<string,string>={strengthened:"근거 강화",weakened:"근거 약화",watching:"검증 중",exploring:"초기 가설"};
const fmt=(value:string)=>value.slice(0,10).replaceAll("-",".");
export function CommandCenter({stories,ideas,ecosystems,sourceOnline,asOf}:{stories:Story[];ideas:Thesis[];ecosystems:Ecosystem[];sourceOnline:boolean;asOf:string}){
 const [eco,setEco]=useState<"all"|EcoId>("all");
 const [tab,setTab]=useState<"all"|"high"|"ideas">("all");
 const [focus,setFocus]=useState<EcoId>("hbm");
 const [expanded,setExpanded]=useState(false);
 const visible=useMemo(()=>{
  const rows=[
   ...stories.map(x=>({kind:"event" as const,id:x.id,date:x.date,ecoId:x.ecoId,priority:x.significance==="high"?0:x.significance==="medium"?1:2,story:x,idea:null as Thesis|null})),
   ...ideas.map(x=>({kind:"idea" as const,id:x.id,date:"",ecoId:x.ecoId,priority:x.state==="strengthened"?0:1,story:null as Story|null,idea:x})),
  ];
  return rows.filter(x=>(eco==="all"||x.ecoId===eco)&&(tab==="all"||(tab==="high"?x.priority===0:x.kind==="idea")))
   .sort((a,b)=>a.priority-b.priority||(b.date||"").localeCompare(a.date||""));
 },[stories,ideas,eco,tab]);
 const selected=ecosystems.find(x=>x.id===focus)!;
 const headline=[...stories].sort((a,b)=>(b.importance??0)-(a.importance??0)||b.date.localeCompare(a.date))[0];
 const topIdeas=ideas.filter(x=>(x.state==="strengthened"||x.state==="watching")&&(ORDER as string[]).includes(x.ecoId)).slice(0,3);
 const issues=stories.filter(x=>x.importance!=null&&x.id!==headline?.id).sort((a,b)=>(b.importance??0)-(a.importance??0)||b.date.localeCompare(a.date)).slice(0,6);
 return <div className="cc">
  <div className="cc-topline"><span><i className="cc-live-dot"/> SIGNAL ATLAS / RESEARCH INTELLIGENCE</span><span>연구 기준일 {fmt(asOf)} · {sourceOnline?"기업 데이터 연결":"기업 데이터 연결 미확인"}</span></div>
  <div className="cc-intro">
   <div><div className="cc-eyebrow">RESEARCH INTELLIGENCE BRIEF</div><h1>기술은 어디서 바뀌고,<br/><span>가치는 어디로 이동하는가.</span></h1></div>
   <Link href="/search" className="cc-search"><Icon name="search" size={19}/><span>기업·기술·소재·공정 통합 검색</span><kbd>⌘ K</kbd></Link>
  </div>
  <div className="cc-priority">
   <div className="cc-priority-main"><div className="cc-eyebrow">01 / IMPORTANT SIGNAL</div><span className="cc-overline">우선 검토할 기술 변화 · {headline?NAMES[headline.ecoId]??"공급망":"연구 이벤트"}</span>
    {headline?<><Link href={`/feed/${encodeURIComponent(headline.id)}`} className="cc-lead-title">{headline.title}<Icon name="arrow-up-right" size={20}/></Link><p>{headline.summary}</p><div className="cc-lead-foot"><span>{fmt(headline.date)} · {headline.source}</span><Link href={`/feed/${encodeURIComponent(headline.id)}`}>변화의 영향 분석 <Icon name="arrow-right" size={15}/></Link></div></>:<p>검토 가능한 주요 이슈가 아직 없습니다. 수집 현황은 연구 데이터에서 확인할 수 있습니다.</p>}
   </div>
   <div className="cc-priority-aside"><div className="cc-eyebrow">02 / ACTIVE THESES</div><h2>검증할 투자 가설</h2>{topIdeas.length?topIdeas.map(x=><Link key={x.id} href={x.href??`/ideas/${x.id}`} className="cc-mini-idea"><div><strong>{x.ticker}</strong><span>{STATUS[x.state]??"조사 중"}</span></div><p>{x.title}</p><Icon name="arrow-up-right" size={16}/></Link>):<p>현재 검증할 가설이 없습니다.</p>}<Link className="cc-aside-link" href="/ideas">모든 투자 가설 <Icon name="arrow-right" size={15}/></Link></div>
  </div>
  {!!issues.length&&<><div className="cc-section-heading"><div><div className="cc-eyebrow">SUPPLY CHAIN ISSUES</div><h2>최근 공급망 이슈</h2></div><Link href="/feed">전체 피드 <Icon name="arrow-up-right" size={15}/></Link></div>
  <div className="cc-issue-grid">{issues.map(x=><Link key={x.id} href={`/feed/${encodeURIComponent(x.id)}`} className="cc-issue"><div className="cc-issue-top"><span className="story-score">{x.importance}/10</span><span>{NAMES[x.ecoId]??"공급망"}</span><small>{fmt(x.date)}</small></div><strong>{x.title}</strong><p>{x.summary}</p></Link>)}</div></>}
  <IndustryMilestones compact/>
  <div className="cc-section-heading"><div><div className="cc-eyebrow">03 / TECHNOLOGY SYSTEMS</div><h2>산업망의 주요 흐름</h2></div><Link href="/ecosystems">전체 산업망 <Icon name="arrow-up-right" size={15}/></Link></div>
  <div className="cc-system-tabs" role="group" aria-label="기술 생태계 선택">{ecosystems.map((x,i)=><button key={x.id} type="button" className={focus===x.id?"cc-system-tab cc-system-tab-active":"cc-system-tab"} onClick={()=>setFocus(x.id)} aria-pressed={focus===x.id}><span>0{i+1} / {NAMES[x.id]}</span><strong>{x.title}</strong><small>{x.trajectory}</small></button>)}</div>
  <div className="cc-system-detail"><div><span className="cc-system-badge">{selected.metricLabel} · {selected.metric}</span><strong>핵심 병목: {selected.bottleneck}</strong><p>{selected.summary}</p></div><Link href={`/ecosystems/${focus}`}>기술·근거 상세 <Icon name="arrow-right" size={15}/></Link></div>
  <GraphExplorer key={focus} ecoId={focus} compact/>
  <div className="cc-section-heading cc-feed-heading"><div><div className="cc-eyebrow">04 / INTELLIGENCE STREAM</div><h2>주요 이슈 · 투자 아이디어 피드</h2></div><Link href="/feed">전체 피드 <Icon name="arrow-up-right" size={15}/></Link></div>
  <div className="cc-feed-controls"><div className="cc-segments" role="group" aria-label="피드 유형">{[["all","전체"],["high","핵심 변화"],["ideas","투자 가설"]].map(([v,label])=><button key={v} type="button" aria-pressed={tab===v} onClick={()=>{setTab(v as typeof tab);setExpanded(false)}} className={tab===v?"active":""}>{label}</button>)}</div><div className="cc-eco-filters"><button className={eco==="all"?"active":""} onClick={()=>setEco("all")}>모든 산업</button>{ORDER.map(id=><button key={id} className={eco===id?"active":""} onClick={()=>setEco(id)}>{NAMES[id]}</button>)}</div></div>
  <div className="cc-feed-list">{visible.length?visible.slice(0,expanded?16:6).map(row=>row.kind==="event"&&row.story?<Link className="cc-feed-item" key={row.kind+row.id} href={`/feed/${encodeURIComponent(row.id)}`}><div className="cc-feed-rail"><span className={row.priority===0?"cc-marker cc-marker-hot":"cc-marker"}/><small>{fmt(row.story.date)}</small></div><div className="cc-feed-copy"><div className="cc-feed-tags"><span>{NAMES[row.ecoId]??"기업 공시"}</span><span>{row.story.type}</span><span>{row.story.status==="source"?"원문 근거":"관측 데이터"}</span></div><strong>{row.story.title}</strong><p>{row.story.summary}</p><small>출처 · {row.story.source}</small></div><Icon name="arrow-up-right" size={18}/></Link>:row.idea?<Link className="cc-feed-item" key={row.kind+row.id} href={row.idea.href??`/ideas/${row.idea.id}`}><div className="cc-feed-rail"><span className="cc-marker cc-marker-thesis"/><small>THESIS</small></div><div className="cc-feed-copy"><div className="cc-feed-tags"><span>{row.idea.ticker}</span><span>{NAMES[row.ecoId]??"기업 리서치"}</span><span>{STATUS[row.idea.state]??"조사 중"}</span></div><strong>{row.idea.title}</strong><p>{row.idea.description}</p><small>다음 검증 · {row.idea.trigger}</small></div><Icon name="arrow-up-right" size={18}/></Link>:null):<div className="cc-feed-empty">해당 조건에 맞는 자료가 없습니다. 다른 산업이나 유형을 선택해 보세요.</div>}</div>
  {visible.length>6&&<button className="cc-load-more" onClick={()=>setExpanded(x=>!x)}>{expanded?"간략히 보기":`더 보기 · ${visible.length-6}건`} <Icon name="chevron-down" size={15}/></button>}
  <div className="cc-bottom"><div><strong>깊이 있는 검증은 상세 화면에서</strong><p>원문 증거·측정 조건·대체 기술·공급망 기업의 경제적 노출은 2차 탐색에서 확인할 수 있습니다. 기술적 관련성은 매출 수혜의 증명이 아닙니다.</p></div><Link href="/triggers">다음 검증 트리거 <Icon name="arrow-right" size={15}/></Link></div>
 </div>;
}
