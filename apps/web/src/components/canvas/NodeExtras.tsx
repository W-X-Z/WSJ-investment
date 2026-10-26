"use client";

/** Heavy, data-backed inspector sections. Loaded with next/dynamic only after a node is
 *  selected, so impact-index / graph-evidence-index / historical-evidence JSON stay out of
 *  the initial bundle of every page that embeds the canvas. */
import { useMemo } from "react";
import history from "@/data/historical-evidence.json";
import { relevantHistoricalTerms } from "@/lib/technical-keywords";
import { ImpactPanel } from "@/components/ImpactPanel";
import { IndustryMilestones } from "@/components/IndustryMilestones";
import { NodeEvidencePanel } from "@/components/NodeEvidencePanel";
import { nodeIndex, safeUrl, type Scope } from "./graph-model";

type HistItem = { id: string; ecosystem: string; published_at: string; title: string; source: string; url: string; kind: string };
const events = (history as unknown as { events: HistItem[] }).events;
const fmt = (date: string) => date.slice(0, 10).replaceAll("-", ".");

export default function NodeExtras({ nodeId, scope }: { nodeId: string; scope: Scope }) {
  const rows = useMemo(() => {
    const node = nodeIndex.get(nodeId);
    if (!node) return [];
    const keywords = relevantHistoricalTerms(node);
    if (!keywords.length) return [];
    return events
      .filter((x) => scope === "all" || x.ecosystem === scope)
      .map((x) => ({ x, hit: keywords.reduce((sum, key) => sum + (x.title.toLowerCase().includes(key) ? 1 : 0), 0) }))
      .filter((x) => x.hit > 0)
      .sort((a, b) => b.hit - a.hit || b.x.published_at.localeCompare(a.x.published_at))
      .slice(0, 4)
      .map((x) => x.x);
  }, [nodeId, scope]);
  return <>
    <ImpactPanel nodeId={nodeId}/>
    <IndustryMilestones nodeId={nodeId} compact/>
    <NodeEvidencePanel nodeId={nodeId}/>
    {rows.length > 0 && <>
      <h4>관련 키워드로 찾은 과거 자료 · 미검증</h4>
      <div className="sc-history">{rows.map((x) => {
        const url = safeUrl(x.url);
        const body = <><small>{fmt(x.published_at)} · {x.source}</small><strong>{x.title}</strong></>;
        return url ? <a key={x.id} href={url.href} target="_blank" rel="noreferrer noopener">{body}</a> : <div key={x.id}>{body}</div>;
      })}</div>
    </>}
  </>;
}
