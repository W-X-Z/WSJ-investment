"use client";

import Link from "next/link";
import { type EcoId } from "@/lib/research-client";
import { SupplyNetworkCanvas } from "@/components/SupplyNetworkCanvas";

/** All existing ecosystem routes now use the freely navigable graph. */
export function GraphExplorer({ecoId,compact=false}:{ecoId:EcoId;compact?:boolean}) {
 return <SupplyNetworkCanvas initialEcosystem={ecoId} compact={compact}/>;
}
export function GraphTabs({current}:{current:EcoId}) {
 const tabs=[{id:"hbm" as EcoId,name:"HBM · 첨단 패키징"},{id:"optics" as EcoId,name:"광통신·포토닉스"},{id:"power" as EcoId,name:"전력·냉각"}];
 return <div className="graph-tabs">{tabs.map(({id,name})=><Link key={id} href={`/ecosystems/${id}`} className={current===id?"graph-tab active":"graph-tab"}>{name}</Link>)}<Link href="/map" className="graph-tab">전체 산업망 캔버스 ↗</Link></div>;
}
