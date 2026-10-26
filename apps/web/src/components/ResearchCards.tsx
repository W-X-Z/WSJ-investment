import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ECO_BY_ID, dateShort, type Ecosystem, type FeedItem, type Idea } from "@/lib/research";

export function SectionHeading({ eyebrow, title, subtitle, href, action = "전체 보기" }: {
  eyebrow?: string;title:string;subtitle?:string;href?:string;action?:string
}) {
  return <div className="section-heading">
    <div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
    {href && <Link className="section-action" href={href}>{action}<Icon name="arrow-right" size={16}/></Link>}
  </div>;
}
export function EcosystemCard({eco,index=0}: {eco:Ecosystem;index?:number}) {
  return <Link href={`/ecosystems/${eco.id}`} className={`ecosystem-card ecosystem-card-${eco.color}`}>
    <div className="eco-card-top"><span className="eco-card-category"><i/>{eco.label}</span><Icon name="arrow-up-right" size={17}/></div>
    <div className="eco-card-index">{String(index+1).padStart(2,"0")}</div>
    <div className="eco-card-icon"><Icon name={eco.glyph as "cpu"|"network"|"zap"} size={21}/></div>
    <h3>{eco.title}</h3>
    <p>{eco.summary}</p>
    <div className="eco-card-divider"/>
    <div className="eco-card-bottom">
      <div><span>{eco.metricLabel}</span><strong>{eco.metric}</strong></div>
      <div className="eco-card-arrow"><Icon name="arrow-right" size={18}/></div>
    </div>
  </Link>;
}
export function EventChip({kind}: {kind:FeedItem["significance"]}) {
  return <span className={`event-level event-level-${kind}`}>{kind==="high"?"핵심 변화":kind==="medium"?"기술 동향":"관찰 신호"}</span>;
}
export function FeedStory({item,featured=false}: {item:FeedItem;featured?:boolean}) {
  const eco = item.ecoId==="market"?null:ECO_BY_ID[item.ecoId];
  return <article className={`story ${featured?"story-featured":""}`}>
    <div className="story-glyph"><Icon name={item.ecoId==="hbm"?"cpu":item.ecoId==="optics"?"network":item.ecoId==="power"?"zap":"file"} size={19}/></div>
    <div className="story-copy">
      <div className="story-meta"><span className="story-eco">{eco?.label??"기업 신호"}</span><span className="meta-sep">·</span><span>{item.type}</span><span className="meta-sep">·</span><span>{dateShort(item.date)}</span>{item.datePrecision==="unknown" && <span className="date-unknown">확인일 기준</span>}</div>
      <Link href={`/feed/${encodeURIComponent(item.id)}`} className="story-title">{item.title}</Link>
      <p>{item.summary}</p>
      <div className="story-foot"><EventChip kind={item.significance}/><span className="story-source">출처 · {item.source}</span></div>
    </div>
    <Link aria-label={`${item.title} 상세 보기`} className="story-go" href={`/feed/${encodeURIComponent(item.id)}`}><Icon name="arrow-up-right" size={18}/></Link>
  </article>;
}
const STATES: Record<string,{text:string;className:string}> = {
  strengthened:{text:"근거 강화",className:"status-positive"},
  watching:{text:"검증 중",className:"status-neutral"},
  exploring:{text:"초기 가설",className:"status-exploring"},
  weakened:{text:"근거 약화",className:"status-negative"},
};
export function IdeaTile({idea}: {idea:Idea}) {
  const state=STATES[idea.state]??STATES.exploring;
  const eco=idea.ecoId==="market"?null:ECO_BY_ID[idea.ecoId];
  const url=idea.href??`/ideas/${idea.id}`;
  return <article className="idea-card">
    <div className="idea-card-top">
      <span className="ticker-badge">{idea.ticker}</span>
      <span className={`idea-status ${state.className}`}><i/>{state.text}</span>
    </div>
    <div className="idea-company">{idea.company} <span>· {eco?.label??"기업 리서치"}</span></div>
    <Link href={url} className="idea-title">{idea.title}<Icon name="arrow-up-right" size={16}/></Link>
    <p>{idea.description}</p>
    <div className="idea-trigger"><Icon name="target" size={16}/><span><strong>다음 검증</strong>{idea.trigger}</span></div>
    <div className="idea-card-foot"><span>{idea.live?"운영 DB 브리프":"가설 연구 시드"}</span><Link href={url}>근거 보기 <Icon name="arrow-right" size={14}/></Link></div>
  </article>;
}

export function EmptyState({title,copy,href}: {title:string;copy:string;href?:string}) {
  return <div className="empty-state"><div className="empty-state-icon"><Icon name="search" size={23}/></div><h3>{title}</h3><p>{copy}</p>{href && <Link href={href}>전체 보기 <Icon name="arrow-right" size={16}/></Link>}</div>;
}
