"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { type EcoId } from "@/lib/research-client";

/** The canvas (React Flow + graph seed) is below the fold on every page that embeds it, so it is
 *  code-split out of the page's initial bundle. The placeholder reserves the same height. */
const SupplyNetworkCanvas = dynamic(() => import("@/components/SupplyNetworkCanvas").then((m) => m.SupplyNetworkCanvas), {
  ssr: false,
  loading: () => <div aria-busy="true" aria-label="산업망 캔버스 불러오는 중" style={{ height: 760, border: "1px solid #dae3ee", borderRadius: 17, background: "#f6f9fe", marginBottom: 28 }}/>,
});

/** All existing ecosystem routes now use the freely navigable graph. */
export function GraphExplorer({ecoId,compact=false}:{ecoId:EcoId;compact?:boolean}) {
 return <SupplyNetworkCanvas initialEcosystem={ecoId} compact={compact}/>;
}
export function GraphTabs({current}:{current:EcoId}) {
 const tabs=[{id:"hbm" as EcoId,name:"HBM · 첨단 패키징"},{id:"optics" as EcoId,name:"광통신·포토닉스"},{id:"power" as EcoId,name:"전력·냉각"}];
 return <div className="graph-tabs">{tabs.map(({id,name})=><Link key={id} href={`/ecosystems/${id}`} className={current===id?"graph-tab active":"graph-tab"}>{name}</Link>)}<Link href="/map" className="graph-tab">전체 산업망 캔버스 ↗</Link></div>;
}
