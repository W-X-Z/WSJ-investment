"use client";

import { createContext, memo, useContext } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { KINDS, type GraphNode } from "@/lib/research-client";
import { SIZE_NAME, displayLabel, isSmallCap } from "./graph-model";

export type SupplyNodeData = { node: GraphNode };
export type SupplyFlowNode = Node<SupplyNodeData, "supply">;

/** Selection/search highlight lives in context so node objects (and drag state) never change
 *  when the user selects something: only this context value does. */
export type Highlight = { selected: string | null; near: Map<string, number> | null; matches: Set<string> };
export const HighlightContext = createContext<Highlight>({ selected: null, near: null, matches: new Set() });

function SupplyNodeView({ id, data }: NodeProps<SupplyFlowNode>) {
  const hl = useContext(HighlightContext);
  const n = data.node;
  const hop = hl.near?.get(id);
  const state = !hl.near ? "" : hl.selected === id ? "is-focus" : hop !== undefined ? `is-near hop-${hop}` : "is-dim";
  const company = n.kind === "company";
  const small = company && isSmallCap(n);
  return <div className={`snode snode-${n.kind} ${state} ${small ? "snode-smallcap" : ""} ${hl.matches.has(id) ? "is-match" : ""}`} title={n.label}>
    <Handle type="target" position={Position.Left} isConnectable={false} className="snode-handle"/>
    {company ? <>
      <strong className="snode-label">{displayLabel(n)}</strong>
      <span className="snode-chips">
        {n.listing?.ticker ? <b>{n.listing.ticker}</b> : <b className="chip-muted">비상장</b>}
        {n.size_band ? <em className={`chip-size chip-${n.size_band}`}>{small ? "★ " : ""}{SIZE_NAME[n.size_band] ?? n.size_band}</em> : null}
        {n.in_universe ? <em className="chip-universe">유니버스</em> : null}
      </span>
    </> : <>
      <span className="snode-kind"><i className={`sc-kind-dot sc-dot-${n.kind}`}/>{KINDS[n.kind] ?? n.kind}</span>
      <strong className="snode-label">{n.label}</strong>
    </>}
    <Handle type="source" position={Position.Right} isConnectable={false} className="snode-handle"/>
  </div>;
}

export const SupplyNode = memo(SupplyNodeView);
