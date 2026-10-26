"use client";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import data from "@/data/industry-milestones.json";
import "./IndustryMilestones.css";

type Value={measure:string;value:number;unit:string;operator?:string;basis:string};
type Milestone={id:string;ecosystem:string;published_at:string;date_precision:string;node_ids:string[];
 title:string;publisher:string;source_url:string;fact:string;fact_type:string;values:Value[];
 upstream_implications:string;next_trigger:string};
const milestones=(data.milestones as Milestone[]).filter(x=>x.published_at<=data.as_of);
const names:Record<string,string>={hbm:"HBM·패키징",optics:"광통신·포토닉스",power:"전력·냉각"};
const kinds:Record<string,string>={
 issuer_technical_claim:"기업 발표·독립검증 전",
 official_process_record:"공식 표준화 절차 기록",
 official_standards_workgroup_record:"공식 기술 워킹그룹 발표"
};
function published(m:Milestone){return m.date_precision==="month"?m.published_at.slice(0,7)+" (월 기준)":m.published_at;}

export function IndustryMilestones({nodeId,compact=false}:{nodeId?:string;compact?:boolean}){
 const rows=(nodeId?milestones.filter(x=>x.node_ids.includes(nodeId)):milestones)
   .slice().sort((a,b)=>b.published_at.localeCompare(a.published_at));
 if(nodeId&&!rows.length)return null;
 return <section className={`im-rail ${compact?"im-rail-compact":""}`}>
   <div className="im-title"><div><small>DOCUMENTED TECHNICAL MILESTONES</small><h3>{nodeId?"확인된 산업 변화":"최근 산업 기술의 주요 변화"}</h3></div>{!nodeId&&<Link href="/map">공급망에서 탐색 <Icon name="arrow-right" size={15}/></Link>}</div>
   <div className="im-cards">{rows.slice(0,nodeId?4:3).map(m=><article key={m.id} className="im-card">
    <div className="im-card-top"><span>{names[m.ecosystem]??m.ecosystem}</span><time>{published(m)}</time></div>
    <strong>{m.title}</strong>
    <span className="im-confidence">{kinds[m.fact_type]??"공개자료 주장"}</span>
    <p>{m.fact}</p>
    {!compact&&<div className="im-implications"><b>공급망 의미 · 가설</b><p>{m.upstream_implications}</p></div>}
    <div className="im-next"><b>다음 검증</b><p>{m.next_trigger}</p></div>
    <a href={m.source_url} target="_blank" rel="noreferrer">공식 원문 · {m.publisher} <Icon name="arrow-up-right" size={14}/></a>
   </article>)}</div>
   <p className="im-disclaimer">공식 표준화 일정은 제품 양산·고객 인증·매출 발생과 다릅니다. 기술 공급 관계는 독립적인 공시·고객 자료로 검증해야 합니다.</p>
 </section>;
}
