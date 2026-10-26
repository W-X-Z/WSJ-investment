"use client";

/** Interactive evidence-aware supply-chain canvas.
 * Real pan/zoom, free node dragging, cluster/chain layouts, 1-3 hop impact,
 * link selection, trusted-vs-inferred relation filtering, search and minimap.
 * Pure React/SVG; no heavyweight editor dependency or fabricated supplier edges.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { seed, KINDS, RELATIONS, type GraphNode, type Edge, type EcoId } from "@/lib/research-client";
import history from "@/data/historical-evidence.json";
import { relevantHistoricalTerms } from "@/lib/technical-keywords";
import "./SupplyNetworkCanvas.css";

type Scope = EcoId | "all";
type Mode = "layers" | "clusters" | "impact";
type Vec = {x:number;y:number};
type Camera = Vec & {z:number};
type DragState = {type:"pan";px:number;py:number;cam:Camera} |
 {type:"node";id:string;px:number;py:number;origin:Vec; moved:boolean};
type HistItem = {id:string;ecosystem:string;published_at:string;title:string;source:string;url:string;kind:string};
type History = {summary: {records?:number;historical_period?:number[]}|null;events:HistItem[]};
const h=history as History;
const W=204,H=76;
const ECOS:{id:EcoId;name:string;short:string;color:string}[]=[
 {id:"hbm",name:"HBM · 첨단 패키징",short:"HBM",color:"#8c79ec"},
 {id:"optics",name:"광통신 · 포토닉스",short:"OPTICS",color:"#29aac3"},
 {id:"power",name:"전력변환 · 냉각",short:"POWER",color:"#ecab60"},
];
const ECO_ROOT: Record<EcoId,string>={hbm:"eco:hbm",optics:"eco:optics",power:"eco:power"};
const KIND_ORDER: Record<string,number>={
 ecosystem:0,requirement:1,bottleneck:2,technology:3,process:4,material:4,component:4,equipment:4,company:5,
};
const KIND_NAME:Record<string,string>={
 ecosystem:"생태계",requirement:"요구사항",bottleneck:"기술 병목",technology:"해결 기술",
 process:"제조 공정",component:"부품·모듈",material:"소재",equipment:"장비",company:"기업",
};
const epistemic=(e:Edge)=>e.stage==="technical_inference"||e.stage==="unverified_hypothesis"||e.stage==="technology_option"||e.stage==="scenario"||e.polarity==="conditional"?"inferred":e.stage==="vendor_claim"?"issuer":"documented";
const nodeIndex=new Map(seed.nodes.map(n=>[n.id,n]));
const neighborIndex=new Map<string,Set<string>>();
for(const e of seed.edges){
 if(!neighborIndex.has(e.from))neighborIndex.set(e.from,new Set());
 if(!neighborIndex.has(e.to))neighborIndex.set(e.to,new Set());
 neighborIndex.get(e.from)!.add(e.to);
 neighborIndex.get(e.to)!.add(e.from);
}
function ownerMap():Map<string,EcoId>{
 const owners=new Map<string,EcoId>();
 const distance=new Map<string,number>();
 for(const eco of ECOS){
  const queue:Array<[string,number]>=[[ECO_ROOT[eco.id],0]];
  let head=0;
  while(head<queue.length){
   const [id,d]=queue[head++];
   if(distance.has(id)&&distance.get(id)! <= d)continue;
   distance.set(id,d);owners.set(id,eco.id);
   for(const adj of neighborIndex.get(id)??[])queue.push([adj,d+1]);
  }
 }
 return owners;
}
const owners=ownerMap();
function edgePath(a:Vec,b:Vec):string{
 const sx=a.x+W,sy=a.y+H/2,tx=b.x,ty=b.y+H/2;
 const dx=tx-sx;
 if(dx>=30){const curve=Math.min(170,Math.max(58,dx*.48));return `M ${sx} ${sy} C ${sx+curve} ${sy}, ${tx-curve} ${ty}, ${tx} ${ty}`;}
 const cy=(sy+ty)/2-54;
 return `M ${sx} ${sy} C ${sx+112} ${sy}, ${sx+75} ${cy}, ${(sx+tx)/2} ${cy} S ${tx-75} ${ty}, ${tx} ${ty}`;
}
function extent(points:Map<string,Vec>){
 const positions=Array.from(points.values());
 if(!positions.length)return {minx:0,miny:0,maxx:1000,maxy:700};
 return {minx:Math.min(...positions.map(p=>p.x)),miny:Math.min(...positions.map(p=>p.y)),
 maxx:Math.max(...positions.map(p=>p.x))+W,maxy:Math.max(...positions.map(p=>p.y))+H};
}
function levelsFrom(start:string):Map<string,number>{
 const out=new Map([[start,0]]);const queue=[start];
 for(let i=0;i<queue.length;i++){
  const id=queue[i];for(const n of neighborIndex.get(id)??[])if(!out.has(n)){out.set(n,out.get(id)!+1);queue.push(n);}
 }
 return out;
}
function arrange(ids:Set<string>,mode:Mode,scope:Scope,focus:string|null):Map<string,Vec>{
 const result=new Map<string,Vec>();
 if(mode==="impact"&&focus){
  const dist=levelsFrom(focus);
  const groups=new Map<number,string[]>();
  for(const id of ids)if(dist.has(id)&&dist.get(id)! <= 3){
   const rank=dist.get(id)!;groups.set(rank,[...(groups.get(rank)??[]),id]);
  }
  for(const [rank,values] of groups){
   values.sort((a,b)=>(KIND_ORDER[nodeIndex.get(a)?.kind??""]??8)-(KIND_ORDER[nodeIndex.get(b)?.kind??""]??8)||a.localeCompare(b));
   values.forEach((id,i)=>{
    if(rank===0)result.set(id,{x:860,y:660});
    else {const angle=(2*Math.PI*i/values.length)-(Math.PI/2)+rank*.25;
      const r=rank*400;result.set(id,{x:860+r*Math.cos(angle),y:660+r*Math.sin(angle)});}
   });
  }
  return result;
 }
 const selected=scope==="all"?ECOS.map(x=>x.id):[scope];
 const separated=selected.map((eco,index)=>{
  const members=Array.from(ids).filter(id=>owners.get(id)===eco);
  const grouped=new Map<number,string[]>();
  for(const id of members){
   const group=KIND_ORDER[nodeIndex.get(id)?.kind??""]??4;
   grouped.set(group,[...(grouped.get(group)??[]),id]);
  }
  const xBase=scope==="all"?index*1830+110:130;
  const maxRow=Math.max(2,...Array.from(grouped.values()).map(g=>g.length));
  for(const [col,list] of grouped){
   list.sort((a,b)=>a.localeCompare(b));
   const gap=112;
   const total=(list.length-1)*gap;
   list.forEach((id,i)=>result.set(id,{x:xBase+col*260,y:220+(maxRow-1)*gap/2-total/2+i*gap}));
  }
  return eco;
 });
 if(mode==="clusters"){
  for(const eco of separated){
   const members=Array.from(ids).filter(id=>owners.get(id)===eco).sort();
   const base=scope==="all"?separated.indexOf(eco)*1800+750:770;
   const cy=780;
   const byLayer=new Map<number,string[]>();
   for(const id of members){
    const layer=Math.min(KIND_ORDER[nodeIndex.get(id)?.kind??""]??4,5);
    byLayer.set(layer,[...(byLayer.get(layer)??[]),id]);
   }
   for(const [layer,list] of byLayer){
    const radius=layer*143;
    list.forEach((id,index)=>{
     const phi=Math.PI*2*index/Math.max(list.length,1)-Math.PI/2+(layer%2)*.3;
     result.set(id,{x:base+Math.cos(phi)*radius-W/2,y:cy+Math.sin(phi)*radius-H/2});
    });
   }
  }
 }
 return result;
}
function discover(id:string,depth:number):Set<string>{
 const dist=levelsFrom(id);return new Set(Array.from(dist).filter(([,d])=>d<=depth).map(([key])=>key));
}
const fmt=(date:string)=>date.slice(0,10).replaceAll("-",".");
function MiniMap({positions,camera,size,center}:{positions:Map<string,Vec>;camera:Camera;size:{w:number;h:number};center:(x:number,y:number)=>void}){
 const bounds=extent(positions),margin=12,fullW=bounds.maxx-bounds.minx+140,fullH=bounds.maxy-bounds.miny+140;
 const k=Math.min(205/fullW,128/fullH),shiftX=10-bounds.minx*k,shiftY=10-bounds.miny*k;
 const vx=(-camera.x/camera.z)*k+shiftX,vy=(-camera.y/camera.z)*k+shiftY;
 return <svg className="sc-minimap" viewBox="0 0 228 150" role="img" aria-label="전체 그래프 미니맵 — 클릭하여 이동"
 onClick={e=>{const rect=e.currentTarget.getBoundingClientRect();const px=(e.clientX-rect.left)*228/rect.width,py=(e.clientY-rect.top)*150/rect.height;center((px-shiftX)/k,(py-shiftY)/k)}}>
  <rect x={0} y={0} width={228} height={150} fill="#f8fbff" rx={10}/>
  {Array.from(positions).map(([id,p])=><rect key={id} x={p.x*k+shiftX} y={p.y*k+shiftY} width={Math.max(3,W*k)} height={Math.max(2,H*k)} rx={2} fill={id.startsWith("company:")?"#ed9f5b":id.startsWith("bottleneck:")?"#da749d":"#7193d0"} opacity=".85"/>)}
  <rect x={vx} y={vy} width={size.w/camera.z*k} height={size.h/camera.z*k} stroke="#3658ae" strokeWidth={1.8} fill="#5c83df18" rx={2}/>
 </svg>;
}

export function SupplyNetworkCanvas({initialEcosystem="all",compact=false}:{initialEcosystem?:Scope;compact?:boolean}){
 const [scope,setScope]=useState<Scope>(initialEcosystem);
 const [mode,setMode]=useState<Mode>("layers");
 const [trust,setTrust]=useState<"all"|"documented">("all");
 const [query,setQuery]=useState("");
 const [selected,setSelected]=useState<string|null>(null);
 const [selectedEdge,setSelectedEdge]=useState<string|null>(null);
 const [depth,setDepth]=useState(2);
 const [camera,setCamera]=useState<Camera>({x:40,y:40,z:.65});
 const [overrides,setOverrides]=useState<Record<string,Vec>>({});
 const [boundsSize,setBoundsSize]=useState({w:1000,h:600});
 const [inspectorOpen,setInspectorOpen]=useState(!compact);
 const canvasRef=useRef<HTMLDivElement>(null);
 const drag=useRef<DragState|null>(null);
 const touchPoints=useRef(new Map<number,Vec>());
 const pinchStart=useRef<{distance:number;camera:Camera;mid:Vec}|null>(null);
 const graphIds=useMemo(()=>new Set(seed.nodes.filter(n=>scope==="all"||owners.get(n.id)===scope).map(n=>n.id)),[scope]);
 const layout=useMemo(()=>arrange(graphIds,mode,scope,selected),[graphIds,mode,scope,selected]);
 const positions=useMemo(()=>new Map<string,Vec>(Array.from(layout).map(([id,pos]):[string,Vec]=>[id,overrides[id]??pos])),[layout,overrides]);
 const displayedEdges=useMemo(()=>seed.edges.filter(e=>positions.has(e.from)&&positions.has(e.to)&&
   (trust==="all"||epistemic(e)!=="inferred")),[positions,trust]);
 const neighbors=useMemo(()=>selected?discover(selected,depth):new Set<string>(),[selected,depth]);
 const focusedEdge=selectedEdge?seed.edges.find(e=>e.id===selectedEdge):null;
 const hit=useMemo(()=>{
  const term=query.trim().toLocaleLowerCase();
  if(!term)return [];
  return seed.nodes.filter(n=>n.label.toLocaleLowerCase().includes(term)||n.id.toLowerCase().includes(term)||n.measured_metrics?.some(m=>m.toLowerCase().includes(term))).slice(0,9);
 },[query]);
 const node=selected?nodeIndex.get(selected):null;
 const nodeEdges=selected?seed.edges.filter(e=>e.from===selected||e.to===selected):[];
 const activeEdges=displayedEdges.filter(e=>e.from===selected||e.to===selected||e.id===selectedEdge);
 const historyRows=useMemo(()=>{
  if(!node)return [];
  const keywords=relevantHistoricalTerms(node);
  return h.events.filter(x=>scope==="all"||x.ecosystem===scope)
    .map(x=>({x,hit:keywords.reduce((sum,key)=>sum+(x.title.toLowerCase().includes(key)?1:0),0)}))
    .filter(x=>x.hit>0).sort((a,b)=>b.hit-a.hit||b.x.published_at.localeCompare(a.x.published_at)).slice(0,4).map(x=>x.x);
 },[node,scope]);
 const fit=useCallback(()=>{
  const el=canvasRef.current;if(!el||!positions.size)return;
  const rect=el.getBoundingClientRect(),b=extent(positions);
  const scale=Math.max(.15,Math.min(1.1,(rect.width-125)/(b.maxx-b.minx+80),(rect.height-130)/(b.maxy-b.miny+80)));
  setBoundsSize({w:rect.width,h:rect.height});
  setCamera({x:(rect.width-(b.maxx+b.minx)*scale)/2,y:(rect.height-(b.maxy+b.miny)*scale)/2,z:scale});
 },[positions]);
 // Deliberately reframe on navigation/layout switches only, not during node dragging.\n // Reframe on sector/layout changes *after* the DOM has measured.
 // We use canonical layout rather than dragged positions so node repositioning does not
 // unexpectedly zoom the whole scene during a drag.
 useLayoutEffect(()=>{
  const el=canvasRef.current;if(!el||!layout.size)return;
  const apply=()=>{
   const rect=el.getBoundingClientRect();if(!rect.width||!rect.height)return;
   const b=extent(layout),z=Math.max(.13,Math.min(1.1,(rect.width-125)/(b.maxx-b.minx+80),(rect.height-130)/(b.maxy-b.miny+80)));
   setBoundsSize({w:rect.width,h:rect.height});
   setCamera({z,x:(rect.width-(b.maxx+b.minx)*z)/2,y:(rect.height-(b.maxy+b.miny)*z)/2});
  };
  apply();
  const frame=requestAnimationFrame(apply);
  const resize=new ResizeObserver(apply);resize.observe(el);
  return ()=>{cancelAnimationFrame(frame);resize.disconnect();};
 },[layout]);
 useEffect(()=>{
  const el=canvasRef.current;if(!el)return;
  const wheel=(ev:WheelEvent)=>{
   if(ev.ctrlKey||Math.abs(ev.deltaY)>0){ev.preventDefault();
    const r=el.getBoundingClientRect(),mx=ev.clientX-r.left,my=ev.clientY-r.top;
    const factor=Math.exp(-Math.sign(ev.deltaY)*Math.min(.17,Math.abs(ev.deltaY)*.002));
    setCamera(c=>{const z=Math.max(.13,Math.min(2.7,c.z*factor));return {x:mx-(mx-c.x)*z/c.z,y:my-(my-c.y)*z/c.z,z};});}
  };
  el.addEventListener("wheel",wheel,{passive:false});
  return ()=>el.removeEventListener("wheel",wheel);
 },[]);
 function centerAt(x:number,y:number,z?:number){
  const rect=canvasRef.current?.getBoundingClientRect();if(!rect)return;
  setCamera(c=>({z:z??c.z,x:rect.width/2-x*(z??c.z),y:rect.height/2-y*(z??c.z)}));
 }
 function go(id:string){
  if(scope!=="all"&&owners.get(id)!==scope)setScope(owners.get(id)??"all");
  setSelected(id);setSelectedEdge(null);setInspectorOpen(true);
  const pt=positions.get(id);if(pt)centerAt(pt.x+W/2,pt.y+H/2,Math.max(camera.z,.72));
 }
 function panDown(e:React.PointerEvent<HTMLDivElement>){
  if(e.button!==0|| (e.target as Element).closest(".sc-graph-node,.sc-link-path,.sc-canvas-tools,.sc-map-holder,.sc-selection-hint,.sc-reopen-inspector"))return;
  if(e.pointerType==="touch"){
   touchPoints.current.set(e.pointerId,{x:e.clientX,y:e.clientY});
   if(touchPoints.current.size===2){
    const [a,b]=Array.from(touchPoints.current.values());
    pinchStart.current={distance:Math.max(1,Math.hypot(b.x-a.x,b.y-a.y)),camera:{...camera},mid:{x:(a.x+b.x)/2,y:(a.y+b.y)/2}};
    drag.current=null;
    e.currentTarget.setPointerCapture(e.pointerId);
    return;
   }
  }
  drag.current={type:"pan",px:e.clientX,py:e.clientY,cam:camera};
  e.currentTarget.setPointerCapture(e.pointerId);
 }
 function panMove(e:React.PointerEvent<HTMLDivElement>){
  if(e.pointerType==="touch"&&touchPoints.current.has(e.pointerId)){
   touchPoints.current.set(e.pointerId,{x:e.clientX,y:e.clientY});
   if(pinchStart.current&&touchPoints.current.size>=2){
    const [a,b]=Array.from(touchPoints.current.values()),start=pinchStart.current;
    const distance=Math.max(1,Math.hypot(b.x-a.x,b.y-a.y));
    const rect=canvasRef.current?.getBoundingClientRect();
    if(!rect)return;
    const x=(a.x+b.x)/2-rect.left,y=(a.y+b.y)/2-rect.top;
    const z=Math.max(.13,Math.min(2.7,start.camera.z*distance/start.distance));
    const worldX=(start.mid.x-rect.left-start.camera.x)/start.camera.z;
    const worldY=(start.mid.y-rect.top-start.camera.y)/start.camera.z;
    setCamera({z,x:x-worldX*z,y:y-worldY*z});
    return;
   }
  }
  const d=drag.current;
  if(d?.type==="pan")setCamera({...d.cam,x:d.cam.x+e.clientX-d.px,y:d.cam.y+e.clientY-d.py});
 }
 function panEnd(e:React.PointerEvent<HTMLDivElement>){
  touchPoints.current.delete(e.pointerId);
  if(touchPoints.current.size<2)pinchStart.current=null;
  if(drag.current?.type==="pan")drag.current=null;
 }
 function nodeDown(e:React.PointerEvent<HTMLButtonElement>,id:string){
  if(e.button!==0)return;
  e.stopPropagation();const p=positions.get(id);if(!p)return;
  drag.current={type:"node",id,px:e.clientX,py:e.clientY,origin:p,moved:false};
  e.currentTarget.setPointerCapture(e.pointerId);
 }
 function nodeMove(e:React.PointerEvent<HTMLButtonElement>){
  const d=drag.current;if(d?.type!=="node")return;
  const dx=(e.clientX-d.px)/camera.z,dy=(e.clientY-d.py)/camera.z;
  if(Math.abs(dx)+Math.abs(dy)>3)d.moved=true;
  if(d.moved)setOverrides(prev=>({...prev,[d.id]:{x:d.origin.x+dx,y:d.origin.y+dy}}));
 }
 function nodeUp(e:React.PointerEvent<HTMLButtonElement>,id:string){
  e.stopPropagation();const d=drag.current;drag.current=null;
  setSelected(id);setSelectedEdge(null);setInspectorOpen(true);
  if(d?.type==="node"&&!d.moved&&e.detail===2)go(id);
 }
 function shiftScope(value:Scope){
  setScope(value);setSelected(null);setSelectedEdge(null);setOverrides({});setQuery("");
 }
 function shiftMode(value:Mode){setMode(value);setOverrides({});}
 const highlighted=selected?neighbors:new Set<string>();
 const edgeMarked=(e:Edge)=>!selected||highlighted.has(e.from)&&highlighted.has(e.to);
 const hasSearch=query.trim().length>0;
 return <section className={`sc-shell ${compact?"sc-compact":""}`} aria-label="기술 산업망 그래프 캔버스">
  <div className="sc-heading">
   <div><div className="sc-kicker"><i/> TECHNOLOGY DEPENDENCY GRAPH</div><h2>{compact?"산업망 탐색 캔버스":"기술·소재·공정 연결망"}</h2><p>드래그해 이동하고, 휠로 확대하며 노드를 선택해 기술의 영향 경로를 따라가세요.</p></div>
   <div className="sc-heading-actions">{compact&&<Link href="/map">전체 화면에서 탐색 <Icon name="arrow-up-right" size={16}/></Link>}<span>{positions.size} NODES <b>·</b> {displayedEdges.length} LINKS</span></div>
  </div>
  <div className="sc-toolbar">
   <div className="sc-scope-tabs" role="group" aria-label="산업망 범위">
    <button type="button" aria-pressed={scope==="all"} className={scope==="all"?"active":""} onClick={()=>shiftScope("all")}>전체 산업망</button>
    {ECOS.map(x=><button key={x.id} type="button" aria-pressed={scope===x.id} className={scope===x.id?"active":""} onClick={()=>shiftScope(x.id)}><i style={{background:x.color}}/>{x.short}</button>)}
   </div>
   <div className="sc-toolbar-right">
    <label className="sc-search"><Icon name="search" size={16}/><input aria-label="그래프 노드 검색" placeholder="노드·소재·기술 수치 검색" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button type="button" title="검색 초기화" onClick={()=>setQuery("")}>×</button>}</label>
    <select value={mode} aria-label="그래프 배치" onChange={e=>shiftMode(e.target.value as Mode)}><option value="layers">공급망 계층</option><option value="clusters">생태계 군집</option><option value="impact" disabled={!selected}>선택 노드 영향</option></select>
    <button type="button" className="sc-icon-button" title="화면에 맞추기" onClick={fit}><Icon name="maximize" size={17}/></button>
   </div>
   {hasSearch&&<div className="sc-search-results">{hit.length?hit.map(n=><button type="button" key={n.id} onClick={()=>{go(n.id);setQuery("");}}><span className={`sc-kind-dot sc-dot-${n.kind}`}/><span>{n.label}</span><small>{KIND_NAME[n.kind]??n.kind}</small></button>):<span>일치하는 노드를 찾지 못했습니다.</span>}</div>}
  </div>
  <div className="sc-context"><div className="sc-type-legend"><span><i className="sc-kind-dot sc-dot-requirement"/>기술 요구</span><span><i className="sc-kind-dot sc-dot-bottleneck"/>병목</span><span><i className="sc-kind-dot sc-dot-technology"/>기술</span><span><i className="sc-kind-dot sc-dot-component"/>소재·부품·공정</span><span><i className="sc-kind-dot sc-dot-company"/>기업</span></div><div className="sc-trust-toggle" role="group" aria-label="근거 필터"><button type="button" aria-pressed={trust==="all"} className={trust==="all"?"active":""} onClick={()=>setTrust("all")}>전체 관계</button><button type="button" aria-pressed={trust==="documented"} className={trust==="documented"?"active":""} onClick={()=>setTrust("documented")}>추론 제외</button></div></div>
  <div className="sc-body">
   <div ref={canvasRef} className="sc-viewport" onPointerDown={panDown} onPointerMove={panMove} onPointerUp={panEnd} onPointerCancel={e=>{panEnd(e);drag.current=null;}}>
    <div className="sc-grid-layer"/>
    <div className="sc-world" style={{transform:`translate(${camera.x}px,${camera.y}px) scale(${camera.z})`}}>
     <svg className="sc-links" width={7000} height={5500} viewBox="0 0 7000 5500" aria-label="산업망 기술 관계 연결선">
      <defs><marker id="sc-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="none" stroke="#96a7c1" strokeWidth="1.25"/></marker><marker id="sc-selected-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="none" stroke="#4c6ed0" strokeWidth="2"/></marker></defs>
      {displayedEdges.map(e=>{
       const a=positions.get(e.from)!,b=positions.get(e.to)!,d=edgePath(a,b);
       const active=activeEdges.includes(e),dim=!!selected&&!edgeMarked(e);
       return <g key={e.id} className="sc-edge-group">
        <path className={`sc-edge ${active?"sc-edge-active":""} ${dim?"sc-edge-dim":""} ${epistemic(e)==="inferred"?"sc-edge-inferred":""} ${e.relation==="substitutes_for"?"sc-edge-substitute":""}`} d={d} markerEnd={active?"url(#sc-selected-arrow)":"url(#sc-arrow)"}/>
        <path className="sc-link-path" d={d} stroke="transparent" strokeWidth={18} fill="none" onClick={event=>{event.stopPropagation();setSelectedEdge(e.id);setSelected(null);setInspectorOpen(true);}}/>
       </g>;
      })}
     </svg>
     {Array.from(positions).map(([id,p])=>{
      const n=nodeIndex.get(id)!;const match=hasSearch&&n.label.toLocaleLowerCase().includes(query.toLocaleLowerCase());
      return <button key={id} type="button"
        className={`sc-graph-node sc-node-${n.kind} ${selected===id?"sc-node-selected":""} ${selected&&!highlighted.has(id)?"sc-node-dim":""} ${match?"sc-node-match":""}`}
        style={{left:p.x,top:p.y,width:W,height:H}}
        title={n.label} aria-label={`${KIND_NAME[n.kind]??n.kind}: ${n.label}`}
        onPointerDown={e=>nodeDown(e,id)} onPointerMove={nodeMove} onPointerUp={e=>nodeUp(e,id)} onPointerCancel={()=>drag.current=null}
        onDoubleClick={()=>go(id)}>
       <span className="sc-node-type"><i className={`sc-kind-dot sc-dot-${n.kind}`}/>{KIND_NAME[n.kind]??n.kind}</span>
       <strong>{n.label}</strong>
       {n.measured_metrics?.length?<small>{n.measured_metrics[0].replaceAll("_"," ")}</small>:null}
      </button>;
     })}
    </div>
    <div className="sc-canvas-tools"><button title="확대" aria-label="캔버스 확대" onClick={()=>setCamera(c=>({...c,z:Math.min(2.7,c.z*1.22)}))}>+</button><button title="축소" aria-label="캔버스 축소" onClick={()=>setCamera(c=>({...c,z:Math.max(.13,c.z/1.22)}))}>−</button><button title="전체 맞춤" onClick={fit}><Icon name="maximize" size={15}/></button></div>
    <div className="sc-map-holder"><MiniMap positions={positions} camera={camera} size={boundsSize} center={(x,y)=>centerAt(x,y)}/></div>
    <div className="sc-zoom-label">{Math.round(camera.z*100)}% · 드래그 / 줌</div>
    {selected&&<div className="sc-selection-hint">선택 노드에서 <select aria-label="영향 관계 탐색 범위" value={depth} onChange={e=>setDepth(Number(e.target.value))}><option value={1}>1-hop</option><option value={2}>2-hop</option><option value={3}>3-hop</option></select> 연결 강조 <button type="button" onClick={()=>{setSelected(null);setSelectedEdge(null)}}>해제</button></div>}
   </div>
   {(inspectorOpen||!compact)&&<aside className="sc-inspector">
    <div className="sc-inspector-top"><div><small>NODE / RELATION INSPECTOR</small><strong>연결과 원문 검증</strong></div><button title="패널 닫기" onClick={()=>setInspectorOpen(false)}><Icon name="x" size={17}/></button></div>
    {focusedEdge?<div className="sc-inspector-content">
      <span className="sc-inspector-kicker">RELATIONSHIP · {RELATIONS[focusedEdge.relation]??focusedEdge.relation}</span>
      <h3>{nodeIndex.get(focusedEdge.from)?.label} → {nodeIndex.get(focusedEdge.to)?.label}</h3>
      <span className={`sc-evidence-class sc-evidence-${epistemic(focusedEdge)}`}>{epistemic(focusedEdge)==="inferred"?"기술적 추론·검증 필요":epistemic(focusedEdge)==="issuer"?"제조사 주장":"문서화된 관계"}</span>
      <p>{focusedEdge.note||"이 기술 관계의 정량적·상업적 의미는 원문과 시험 조건을 함께 확인해야 합니다."}</p>
      <h4>출처 및 검증 근거</h4>
      {focusedEdge.evidence.map((src,i)=><a className="sc-source-card" target="_blank" rel="noreferrer" key={i} href={src.url}><Icon name="external" size={15}/><span>{new URL(src.url).hostname}<small>{src.url}</small></span></a>)}
      <div className="sc-caution">공급망의 연결은 실제 납품 계약·영업이익 증가를 의미하지 않습니다.</div>
     </div>:node?<div className="sc-inspector-content">
      <span className="sc-inspector-kicker">{KIND_NAME[node.kind]??node.kind} · {owners.get(node.id)?.toUpperCase()??"NETWORK"}</span>
      <h3>{node.label}</h3>
      <div className="sc-inspector-stats"><span><b>{nodeEdges.length}</b> 연결 관계</span><span><b>{node.measured_metrics?.length??0}</b> 검증 지표</span></div>
      {node.measured_metrics?.length?<><h4>관측해야 할 물리량</h4><div className="sc-metrics">{node.measured_metrics.map(m=><span key={m}>{m.replaceAll("_"," ")}</span>)}</div></>:null}
      <h4>직접 연결된 기술 관계</h4>
      <div className="sc-related-edges">{nodeEdges.map(e=><button key={e.id} type="button" onClick={()=>setSelectedEdge(e.id)}><span className={`sc-small-mark sc-mark-${epistemic(e)}`}/><div><span>{RELATIONS[e.relation]??e.relation}</span><strong>{nodeIndex.get(e.from===node.id?e.to:e.from)?.label}</strong></div><Icon name="chevron-right" size={14}/></button>)}</div>
      {historyRows.length>0&&<><h4>관련 키워드로 찾은 과거 자료 · 미검증</h4><div className="sc-history">{historyRows.map(x=><a key={x.id} href={x.url} target="_blank" rel="noreferrer"><small>{fmt(x.published_at)} · {x.source}</small><strong>{x.title}</strong></a>)}</div></>}
      <div className="sc-inspector-actions"><button type="button" onClick={()=>{shiftMode("impact");setInspectorOpen(true)}}><Icon name="network" size={15}/> 이 노드 중심으로 펼치기</button><Link href={`/search?q=${encodeURIComponent(node.label)}`}><Icon name="search" size={15}/> 전체 근거 검색</Link></div>
      <div className="sc-caution">노드와 공개 문헌의 관련성은 실제 공급 실적이나 사업적 수혜의 확증이 아닙니다.</div>
     </div>:<div className="sc-inspector-content sc-empty-inspector"><Icon name="network" size={28}/><h3>복잡한 공급망을 탐색하세요</h3><p>캔버스의 노드·연결선을 선택하면 검증된 내용, 추론 관계, 물리적 측정 항목과 원문을 확인할 수 있습니다.</p><div><span>{seed.nodes.length}개 기술·기업 노드</span><span>공식 근거 / 기술 추론 분리</span><span>1–3단계 연결 강조</span></div></div>}
   </aside>}
   {!inspectorOpen&&compact&&<button type="button" className="sc-reopen-inspector" onClick={()=>setInspectorOpen(true)}><Icon name="panel-right" size={16}/> 근거 패널</button>}
  </div>
  <div className="sc-footnote"><div><strong>관계가 있다고 매출 수혜가 확정되지는 않습니다.</strong><span>실선: 문서·공식 주장 / 점선: 기술 가설·조건부 관계 / 핑크선: 대체 기술</span></div><span>연구 그래프 {seed.nodes.length}개 노드 · {seed.edges.length}개 관계 · 과거 데이터 {h.summary?.records??0}건</span></div>
 </section>;
}
