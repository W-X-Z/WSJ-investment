"use client";

import { memo, useState } from "react";
import { EdgeLabelRenderer, Position, getBezierPath, useInternalNode, type Edge as FlowEdge, type EdgeProps, type InternalNode } from "@xyflow/react";
import { RELATIONS, type Edge } from "@/lib/research-client";
import { NODE_H, NODE_W } from "./graph-model";

/** Floating route only — `bend`: −1…1 when several relations join the same pair of nodes;
 *  `labelAt`: label position along the edge (0 = source), pushed away from a selected hub so
 *  the labels of its relations fan out instead of piling up next to it. */
export type SupplyEdgeData = { edge: Edge; route: "layered" | "floating"; cls: string; active: boolean; dim: boolean; bend?: number; labelAt?: number };
export type SupplyFlowEdge = FlowEdge<SupplyEdgeData, "supply">;

type Box = { x: number; y: number; w: number; h: number };
const box = (n: InternalNode): Box => ({ x: n.internals.positionAbsolute.x, y: n.internals.positionAbsolute.y, w: n.measured.width ?? NODE_W, h: n.measured.height ?? NODE_H });

/** Point where the segment from the centre of `a` towards (ox, oy) leaves the rectangle. */
function border(a: Box, ox: number, oy: number): [number, number] {
  const cx = a.x + a.w / 2, cy = a.y + a.h / 2, dx = ox - cx, dy = oy - cy;
  const s = Math.min(dx ? a.w / 2 / Math.abs(dx) : Infinity, dy ? a.h / 2 / Math.abs(dy) : Infinity);
  return Number.isFinite(s) ? [cx + dx * s, cy + dy * s] : [cx, cy];
}

/** Floating edges (network / impact views): straight line between the borders closest to the
 *  other node. Path is derived from the live node boxes, so dragging a node only
 *  re-renders the edges attached to it. Layered routing keeps arrows flowing left → right;
 *  same-column links arc out on the right, backward links leave from the left side. */
function geometry(s: Box, t: Box, route: SupplyEdgeData["route"], bend = 0, at = 0.5): [string, number, number] {
  const scx = s.x + s.w / 2, scy = s.y + s.h / 2, tcx = t.x + t.w / 2, tcy = t.y + t.h / 2;
  if (route === "floating") {
    if (bend) {
      // Parallel relations between the same pair arc to opposite sides (stable for A→B / B→A).
      const flip = scx < tcx || (scx === tcx && scy < tcy) ? 1 : -1;
      const dx = tcx - scx, dy = tcy - scy, len = Math.hypot(dx, dy) || 1, k = bend * flip * Math.min(70, len * 0.22);
      const cx = (scx + tcx) / 2 - (dy / len) * k, cy = (scy + tcy) / 2 + (dx / len) * k;
      const [x1, y1] = border(s, cx, cy), [x2, y2] = border(t, cx, cy);
      const a = (1 - at) ** 2, b = 2 * at * (1 - at), c = at ** 2;
      return [`M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`, a * x1 + b * cx + c * x2, a * y1 + b * cy + c * y2];
    }
    const [x1, y1] = border(s, tcx, tcy), [x2, y2] = border(t, scx, scy);
    return [`M ${x1} ${y1} L ${x2} ${y2}`, x1 + (x2 - x1) * at, y1 + (y2 - y1) * at];
  }
  const reach = (s.w + t.w) / 2 - 1, dx = tcx - scx;
  if (dx > reach) {
    const [p, lx, ly] = getBezierPath({ sourceX: s.x + s.w, sourceY: scy, sourcePosition: Position.Right, targetX: t.x, targetY: tcy, targetPosition: Position.Left });
    return [p, lx, ly];
  }
  if (dx < -reach) {
    const [p, lx, ly] = getBezierPath({ sourceX: s.x, sourceY: scy, sourcePosition: Position.Left, targetX: t.x + t.w, targetY: tcy, targetPosition: Position.Right });
    return [p, lx, ly];
  }
  const sx = s.x + s.w, tx = t.x + t.w, k = 34 + Math.abs(tcy - scy) * 0.2;
  return [`M ${sx} ${scy} C ${sx + k} ${scy}, ${tx + k} ${tcy}, ${tx} ${tcy}`, (sx + tx) / 2 + 0.75 * k, (scy + tcy) / 2];
}

function SupplyEdgeView({ source, target, markerEnd, data, selected }: EdgeProps<SupplyFlowEdge>) {
  const s = useInternalNode(source), t = useInternalNode(target);
  const [hover, setHover] = useState(false);
  if (!s || !t || !data) return null;
  const [path, lx, ly] = geometry(box(s), box(t), data.route, data.bend, data.labelAt);
  const e = data.edge;
  const showLabel = hover || selected || data.active;
  return <>
    <path d={path} className={`sedge ${data.cls} ${selected ? "is-selected" : ""} ${data.active ? "is-active" : ""} ${data.dim ? "is-dim" : ""} ${hover ? "is-hover" : ""}`} markerEnd={markerEnd} fill="none"/>
    <path d={path} className="sedge-hit" fill="none" onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}/>
    {showLabel && !data.dim ? <EdgeLabelRenderer>
      <div className={`sedge-label ${data.cls} ${selected ? "is-selected" : ""}`} style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)` }}>
        {RELATIONS[e.relation] ?? e.relation}{e.polarity === "negative" ? " · 부정" : e.polarity === "conditional" ? " · 조건부" : ""}
      </div>
    </EdgeLabelRenderer> : null}
  </>;
}

export const SupplyEdge = memo(SupplyEdgeView);
