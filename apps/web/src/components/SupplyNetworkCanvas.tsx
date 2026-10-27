"use client";

/** Interactive evidence-aware supply-chain canvas (React Flow).
 * - Default "network" view is force-directed (canvas/force-layout.ts): position follows the
 *   relations, not the node kind. Secondary views: layered LEFT → RIGHT by ontology layer, and a
 *   radial impact view around the selected node (see canvas/graph-model.ts).
 * - Click / Enter / Space selects a node or edge, Escape clears; selection highlights a
 *   1–3 hop neighbourhood. Search and `?focus=<nodeId>` select + centre a node.
 * - Wheel scrolls the page; Ctrl/⌘ + wheel or trackpad pinch zooms (canvas is embedded in
 *   scrolling pages, so it must not trap the wheel). Drag pans, nodes are draggable.
 */
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Background, BackgroundVariant, ControlButton, Controls, MarkerType, MiniMap, Panel, ReactFlow, ReactFlowProvider,
  ViewportPortal, useKeyPress, useNodesState, useReactFlow, useStore,
  type EdgeChange, type NodeChange, type NodeTypes, type EdgeTypes, type XYPosition,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Icon } from "@/components/Icon";
import { KINDS, RELATIONS, seed } from "@/lib/research-client";
import {
  ECOS, NODE_H, NODE_W, adjacency, ecoOf, epistemic, impactLayout, inScope, isSmallCap, layeredLayout, networkLayout,
  edgeIndex, neighborhood, nodeIndex, scopeNodes, visibleEdges,
  type Guide, type Layout, type Mode, type Scope, type Trust, type Viewport,
} from "@/components/canvas/graph-model";
import { HiddenContext, HighlightContext, SupplyNode, type Highlight, type SupplyFlowNode } from "@/components/canvas/SupplyNode";
import { DEPTHS, MAX_LEVEL, PILL_ZOOM, autoLevel, declutter, hiddenNeighbours, lodIndex, quantizeZoom, zoomOfStep } from "@/components/canvas/lod";
import { SupplyEdge, type SupplyFlowEdge } from "@/components/canvas/SupplyEdge";
import { Inspector } from "@/components/canvas/Inspector";
import "./SupplyNetworkCanvas.css";

type Props = {
  initialEcosystem?: Scope;
  initialFocus?: string | null;
  compact?: boolean;
  /** Mirror selection/scope into `?focus=` / `?eco=` (history.replaceState: no scroll, no server round trip). */
  syncUrl?: boolean;
};

const nodeTypes: NodeTypes = { supply: SupplyNode };
const edgeTypes: EdgeTypes = { supply: SupplyEdge };
const MIN_ZOOM = 0.04;
const FOCUS_ZOOM = 1;
/** Below this zoom cards become constant-size pills and are decluttered (canvas/lod.ts). */
const OVERVIEW_ZOOM = PILL_ZOOM;
/** Fit leaves room for the column headers + hint (top) and the zoom controls (left), in screen px. */
const FIT = { padding: { top: "84px", right: "28px", bottom: "26px", left: "58px" }, minZoom: MIN_ZOOM } as const;
/** Network / impact views have no column headers; phones need every pixel (controls overlay). */
const FIT_FREE = { padding: { top: "64px", right: "28px", bottom: "26px", left: "58px" }, minZoom: MIN_ZOOM } as const;
const FIT_PHONE = { padding: { top: "58px", right: "12px", bottom: "12px", left: "12px" }, minZoom: MIN_ZOOM } as const;
type Fit = typeof FIT | typeof FIT_FREE | typeof FIT_PHONE;
const fitFor = (columns: boolean): Fit =>
  typeof window !== "undefined" && window.matchMedia("(max-width: 760px)").matches ? FIT_PHONE : columns ? FIT : FIT_FREE;
const ARIA = {
  "node.a11yDescription.default": "Enter 또는 Space로 노드를 선택하고 Escape로 해제합니다. 화살표 키로 선택한 노드를 옮길 수 있습니다.",
  "node.a11yDescription.keyboardDisabled": "Enter 또는 Space로 노드를 선택하고 Escape로 해제합니다.",
  "edge.a11yDescription.default": "Enter 또는 Space로 관계를 선택해 근거를 확인합니다. Escape로 해제합니다.",
  "controls.ariaLabel": "캔버스 컨트롤",
  "controls.zoomIn.ariaLabel": "캔버스 확대",
  "controls.zoomOut.ariaLabel": "캔버스 축소",
  "controls.fitView.ariaLabel": "화면에 맞추기",
  "minimap.ariaLabel": "전체 그래프 미니맵",
};
const MINIMAP_COLOR: Record<string, string> = {
  company: "#eab061", bottleneck: "#dd739e", requirement: "#7c86d8", technology: "#48a7a3", product: "#d26a9c", ecosystem: "#394e83",
};
const minimapColor = (n: SupplyFlowNode) => MINIMAP_COLOR[n.data.node.kind] ?? "#8aaad5";
const EDGE_COLOR = { displace: "#c2417a", substitute: "#8e5bd0", negative: "#d14343", conditional: "#c98a1d", inferred: "#a7b4c8", base: "#7d91b3" };

export function SupplyNetworkCanvas(props: Props) {
  return <ReactFlowProvider><CanvasInner {...props}/></ReactFlowProvider>;
}

function CanvasInner({ initialEcosystem = "all", initialFocus = null, compact = false, syncUrl = false }: Props) {
  const validFocus = initialFocus && nodeIndex.has(initialFocus) ? initialFocus : null;
  const [scope, setScope] = useState<Scope>(() => validFocus && !inScope(nodeIndex.get(validFocus)!, initialEcosystem) ? "all" : initialEcosystem);
  const [base, setBase] = useState<Exclude<Mode, "impact">>("network");
  const [impactOn, setImpactOn] = useState(false);
  const mode: Mode = impactOn ? "impact" : base;
  const [trust, setTrust] = useState<Trust>("all");
  const [depth, setDepth] = useState(2);
  /** Level of detail: "auto" = depth follows the zoom; a number pins the depth (1 골격 … 4 기업). */
  const [depthMode, setDepthMode] = useState<"auto" | number>("auto");
  const zoomStep = useStore((s) => quantizeZoom(s.transform[2]));
  const [cameraReady, setCameraReady] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(validFocus);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(!!validFocus);
  const [showMinimap, setShowMinimap] = useState(!compact);
  const [vp, setVp] = useState<Viewport | null>(null);
  const [centerSeq, setCenterSeq] = useState(0);
  const [wheelHint, setWheelHint] = useState(false);
  const pendingCenter = useRef<string | null>(validFocus);
  const firstView = useRef(true);
  const shellRef = useRef<HTMLElement>(null);
  const flowRef = useRef<HTMLDivElement>(null);
  const wheelTimer = useRef<number | undefined>(undefined);
  const rf = useReactFlow<SupplyFlowNode, SupplyFlowEdge>();
  const zoomKey = useKeyPress(["Meta", "Control"]);

  // Measure once so the layout can pick column wrapping that suits the canvas aspect ratio.
  useLayoutEffect(() => {
    // Use the whole body width (canvas without the inspector column) — the inspector closes on scope change.
    const r = flowRef.current?.parentElement?.getBoundingClientRect();
    setVp({ w: Math.max(320, r?.width ?? 1100), h: Math.max(320, r?.height ?? 640) });
  }, []);

  const scoped = useMemo(() => scopeNodes(scope), [scope]);
  const ids = useMemo(() => new Set(scoped.map((n) => n.id)), [scoped]);
  const scopeEdges = useMemo(() => visibleEdges(ids, "all"), [ids]);
  const shownEdges = useMemo(() => visibleEdges(ids, trust), [ids, trust]);
  const adj = useMemo(() => adjacency(shownEdges), [shownEdges]);
  const impactFocus = mode === "impact" && selected && ids.has(selected) ? selected : null;

  // Trust filtering hides edges but intentionally does not move nodes (or the camera).
  const baseLayout = useMemo<Layout | null>(() => {
    if (!vp) return null;
    return base === "network" ? networkLayout(scoped, scopeEdges, scope, vp) : layeredLayout(scoped, scopeEdges, scope, vp);
  }, [vp, base, scoped, scopeEdges, scope]);
  const impact = useMemo(() => vp && impactFocus ? impactLayout(impactFocus, depth, scoped, shownEdges, vp) : null, [vp, impactFocus, depth, scoped, shownEdges]);
  const layout = impact ?? baseLayout;
  /** Identifies the drawing, so node drags survive switching scope / view and coming back. */
  const layoutKey = impact ? `impact|${scope}|${impactFocus}|${depth}|${trust}` : `${base}|${scope}`;
  const floating = !!impact || base === "network";

  const layoutNodes = useMemo<SupplyFlowNode[]>(() => layout ? [...layout.positions].map(([id, position]) => {
    const n = nodeIndex.get(id)!;
    return {
      id, type: "supply", position, width: NODE_W, height: NODE_H, data: { node: n },
      ariaLabel: `${KINDS[n.kind] ?? n.kind}: ${n.label}${n.kind === "company" && isSmallCap(n) ? " · 소형주" : ""}`,
    };
  }) : [], [layout]);

  const near = useMemo(() => {
    if (selected && ids.has(selected)) return neighborhood(selected, depth, adj);
    const e = selectedEdge ? edgeIndex.get(selectedEdge) : undefined;
    return e && ids.has(e.from) && ids.has(e.to) ? new Map([[e.from, 0], [e.to, 0]]) : null; // edge: keep its two endpoints lit
  }, [selected, selectedEdge, depth, adj, ids]);
  const hits = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return [];
    return seed.nodes.filter((n) => n.label.toLocaleLowerCase().includes(term) || n.id.toLowerCase().includes(term) || n.listing?.ticker?.toLowerCase() === term || n.measured_metrics?.some((m) => m.toLowerCase().includes(term))).slice(0, 9);
  }, [query]);
  const highlight = useMemo<Highlight>(() => ({ selected, near, matches: new Set(hits.map((n) => n.id)) }), [selected, near, hits]);

  // ----- level of detail -----
  const lod = useMemo(() => lodIndex(scoped, scopeEdges), [scoped, scopeEdges]);
  /** Until the first fit, React Flow's zoom is 1: estimate the fit zoom so the first paint is already decluttered. */
  const fitZoom = useMemo(() => {
    if (!layout || !vp) return 1;
    const P = [...layout.positions.values()];
    if (!P.length) return 1;
    const bw = Math.max(...P.map((p) => p.x)) - Math.min(...P.map((p) => p.x)) + NODE_W;
    const bh = Math.max(...P.map((p) => p.y)) - Math.min(...P.map((p) => p.y)) + NODE_H;
    return Math.min(1, (vp.w - 90) / bw, (vp.h - 100) / bh);
  }, [layout, vp]);
  const lodZoom = cameraReady ? zoomOfStep(zoomStep) : fitZoom;
  const cumulative = useMemo(() => {
    const c = Array(MAX_LEVEL + 1).fill(0);
    if (layout) for (const id of layout.positions.keys()) c[lod.level.get(id) ?? MAX_LEVEL]++;
    for (let L = 1; L <= MAX_LEVEL; L++) c[L] += c[L - 1];
    return c;
  }, [layout, lod]);
  const autoDepth = vp ? autoLevel(cumulative, fitZoom, lodZoom, vp) : MAX_LEVEL;
  const maxLevel = mode === "impact" ? MAX_LEVEL : depthMode === "auto" ? autoDepth : depthMode;
  const visible = useMemo(() => {
    if (!layout) return null;
    const forced = new Set<string>();
    const priority: string[] = [];
    if (near) for (const [id, hop] of near) (hop <= 1 ? forced.add(id) : priority.push(id));
    for (const n of hits) forced.add(n.id);
    return declutter(lod.order, lod.level, layout.positions, lodZoom, maxLevel, forced, priority);
  }, [layout, lod, lodZoom, maxLevel, near, hits]);
  const hiddenCounts = useMemo(() => visible && layout ? hiddenNeighbours(visible, adj, (id) => layout.positions.has(id)) : new Map<string, number>(), [visible, adj, layout]);

  const flowEdges = useMemo<SupplyFlowEdge[]>(() => {
    if (!layout) return [];
    const route = floating ? "floating" : "layered";
    const drawn = shownEdges.filter((e) => layout.positions.has(e.from) && layout.positions.has(e.to) && (!visible || (visible.has(e.from) && visible.has(e.to))));
    // Several relations between the same pair: fan them out so they don't draw on top of each other.
    const pairs = new Map<string, string[]>();
    for (const e of drawn) { const k = e.from < e.to ? `${e.from}|${e.to}` : `${e.to}|${e.from}`; (pairs.get(k) ?? pairs.set(k, []).get(k)!).push(e.id); }
    const bendOf = new Map<string, number>();
    for (const list of pairs.values()) if (list.length > 1) list.forEach((id, i) => bendOf.set(id, (2 * i - (list.length - 1)) / (list.length - 1)));
    return drawn.map((e) => {
      const ep = epistemic(e);
      const rel = e.relation === "displaces" ? "displace" : e.relation === "substitutes_for" ? "substitute" : null;
      const pol = e.polarity === "negative" ? "negative" : e.polarity === "conditional" ? "conditional" : null;
      const color = EDGE_COLOR[rel ?? pol ?? (ep === "inferred" ? "inferred" : "base")];
      const active = !!selected && (e.from === selected || e.to === selected);
      const isSel = e.id === selectedEdge;
      return {
        id: e.id, source: e.from, target: e.to, type: "supply", selected: isSel, zIndex: active || isSel ? 2 : 0,
        ariaLabel: `${nodeIndex.get(e.from)?.label} → ${RELATIONS[e.relation] ?? e.relation} → ${nodeIndex.get(e.to)?.label}`,
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 13, height: 13, markerUnits: "userSpaceOnUse" },
        data: { edge: e, route, cls: `tier-${ep}${pol ? ` pol-${pol}` : ""}${rel ? ` rel-${rel}` : ""}${pol || rel ? "" : " neutral"}`, active, dim: !!near && !(near.has(e.from) && near.has(e.to)), bend: bendOf.get(e.id),
          labelAt: floating && active ? (e.from === selected ? 0.74 : 0.26) : 0.5 },
      };
    });
  }, [layout, floating, shownEdges, selected, selectedEdge, near, visible]);

  // ----- camera -----
  useEffect(() => {
    if (!layout) return;
    // Two frames: the inspector column may have just opened/closed, and React Flow learns the new
    // pane size from a ResizeObserver that fires before the second frame.
    let raf = requestAnimationFrame(() => { raf = requestAnimationFrame(() => {
      const id = pendingCenter.current;
      const duration = firstView.current ? 0 : 380;
      firstView.current = false;
      setCameraReady(true);
      if (id && layout.positions.has(id)) {
        pendingCenter.current = null;
        const z = Math.max(FOCUS_ZOOM, rf.getZoom());
        void rf.fitView({ nodes: [{ id }], minZoom: z, maxZoom: z, duration });
      } else {
        void rf.fitView({ ...fitFor(!floating), duration });
      }
    }); });
    return () => cancelAnimationFrame(raf);
  }, [layout, floating, centerSeq, rf]);

  /** Pan (without zooming) so `id` is not hidden behind the canvas edge or the mobile sheet. */
  const ensureVisible = useCallback((id: string, minZoom = 0) => {
    const n = rf.getInternalNode(id), el = flowRef.current;
    if (!n || !el) return;
    const r = el.getBoundingClientRect();
    const top = r.top + 60; // selection hint overlay
    let bottom = r.bottom;
    const sheet = shellRef.current?.querySelector<HTMLElement>(".sc-inspector");
    if (sheet && getComputedStyle(sheet).position === "fixed") bottom = Math.min(bottom, sheet.getBoundingClientRect().top);
    const current = rf.getViewport().zoom, zoom = Math.max(current, minZoom);
    const p = rf.flowToScreenPosition(n.internals.positionAbsolute);
    if (zoom !== current || p.x < r.left || p.x + NODE_W * zoom > r.right || p.y < top || p.y + NODE_H * zoom > bottom) {
      const cx = n.internals.positionAbsolute.x + NODE_W / 2, cy = n.internals.positionAbsolute.y + NODE_H / 2;
      // setCenter puts the point at the pane centre; shift it to the centre of the visible band.
      const shift = ((top + bottom) / 2 - (r.top + r.bottom) / 2) / zoom;
      void rf.setCenter(cx, cy - shift, { zoom, duration: 300 });
    }
  }, [rf]);

  // ----- selection -----
  const selectNode = useCallback((id: string | null) => {
    setSelected(id);
    setSelectedEdge(null);
    if (id) setInspectorOpen(true);
    else setImpactOn(false);
  }, []);
  const selectEdge = useCallback((id: string | null) => {
    setSelectedEdge(id);
    if (id) { setSelected(null); setInspectorOpen(true); setImpactOn(false); }
  }, []);
  /** Select + centre, switching scope when the node lives outside the current one. */
  const go = useCallback((id: string) => {
    const n = nodeIndex.get(id);
    if (!n) return;
    setScope((s) => (inScope(n, s) ? s : ecoOf(n) ?? "all"));
    selectNode(id);
    pendingCenter.current = id;
    setCenterSeq((x) => x + 1);
  }, [selectNode]);
  const clearAll = useCallback(() => { selectNode(null); setSelectedEdge(null); setInspectorOpen(false); }, [selectNode]);

  // Phones: the inspector is a bottom sheet. Don't let a deep link cover the page on arrival,
  // and when a tap opens the sheet, bring the canvas to the top so the node stays visible above it.
  const isSheet = () => window.matchMedia("(max-width: 760px)").matches;
  const deepLinked = useRef(!!validFocus);
  useEffect(() => { if (deepLinked.current && isSheet()) setInspectorOpen(false); }, []);
  useEffect(() => {
    if (!selected || !inspectorOpen || pendingCenter.current) return;
    const sheet = isSheet();
    if (sheet) flowRef.current?.scrollIntoView({ block: "start" });
    const t = window.setTimeout(() => ensureVisible(selected, sheet ? 0.85 : 0), 80);
    return () => window.clearTimeout(t);
    // Only when the inspector (or bottom sheet) has just opened / selection moved.
  }, [selected, inspectorOpen, ensureVisible]);

  // Deep link changed by a client-side navigation (e.g. Link to /map?focus=…).
  const lastFocusProp = useRef(initialFocus);
  useEffect(() => {
    if (initialFocus === lastFocusProp.current) return;
    lastFocusProp.current = initialFocus;
    if (initialFocus && nodeIndex.has(initialFocus)) go(initialFocus);
  }, [initialFocus, go]);

  // URL sync — history.replaceState is integrated with the App Router (no scroll, no RSC fetch).
  useEffect(() => {
    if (!syncUrl) return;
    const url = new URL(window.location.href);
    if (selected) url.searchParams.set("focus", selected);
    else url.searchParams.delete("focus");
    if (scope !== "all") url.searchParams.set("eco", scope);
    else url.searchParams.delete("eco");
    if (url.href !== window.location.href) window.history.replaceState(null, "", url);
  }, [syncUrl, selected, scope]);

  const shiftScope = (value: Scope) => {
    setScope(value); setSelected(null); setSelectedEdge(null); setQuery(""); setInspectorOpen(false);
    setImpactOn(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "Escape") return;
    if ((e.target as HTMLElement).tagName === "INPUT" && query) { setQuery(""); return; }
    clearAll();
  };
  const onWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) return;
    if (!wheelHint) setWheelHint(true);
    window.clearTimeout(wheelTimer.current);
    wheelTimer.current = window.setTimeout(() => setWheelHint(false), 1400);
  };
  useEffect(() => () => window.clearTimeout(wheelTimer.current), []);

  const showInspector = inspectorOpen;
  const selectedNode = selected ? nodeIndex.get(selected) : null;
  return <section ref={shellRef} className={`sc-shell ${compact ? "sc-compact" : ""}`} aria-label="기술 산업망 그래프 캔버스" onKeyDown={onKeyDown}>
    <div className="sc-heading">
      <div><div className="sc-kicker"><i/> TECHNOLOGY DEPENDENCY GRAPH</div><h2>{compact ? "산업망 탐색 캔버스" : "기술·소재·공정 연결망"}</h2><p>{mode === "layers" ? "왼쪽 요구·병목 → 오른쪽 공급 기업" : mode === "impact" ? "선택 노드 중심 · 바깥 고리일수록 먼 연결" : "연결된 노드끼리 가까이 모입니다"} · 노드를 선택하면 근거를 봅니다.</p></div>
      <div className="sc-heading-actions">{compact && <Link href={selected ? `/map?focus=${encodeURIComponent(selected)}` : "/map"}>전체 화면에서 탐색 <Icon name="arrow-up-right" size={16}/></Link>}<span>{visible && layout && visible.size < layout.positions.size ? <>{visible.size} / </> : null}{layout?.positions.size ?? ids.size} NODES <b>·</b> {flowEdges.length} LINKS</span></div>
    </div>
    <div className="sc-toolbar">
      <div className="sc-scope-tabs" role="group" aria-label="산업망 범위">
        <button type="button" aria-pressed={scope === "all"} className={scope === "all" ? "active" : ""} onClick={() => shiftScope("all")}>전체 산업망</button>
        {ECOS.map((x) => <button key={x.id} type="button" aria-pressed={scope === x.id} className={scope === x.id ? "active" : ""} onClick={() => shiftScope(x.id)}><i style={{ background: x.color }}/>{x.short}</button>)}
      </div>
      <div className="sc-toolbar-right">
        <label className="sc-search"><Icon name="search" size={16}/>
          <input aria-label="그래프 노드 검색" placeholder="노드·기업·티커·수치 검색" value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) { go(hits[0].id); setQuery(""); } }}/>
          {query && <button type="button" title="검색 초기화" aria-label="검색 초기화" onClick={() => setQuery("")}>×</button>}
        </label>
        <select value={mode} aria-label="그래프 배치" onChange={(e) => {
          const v = e.target.value as Mode;
          if (v === "impact") setImpactOn(true);
          else { setBase(v); setImpactOn(false); }
        }}>
          <option value="network">네트워크</option><option value="layers">계층 보기</option><option value="impact" disabled={!selected}>선택 노드 중심</option>
        </select>
        <button type="button" className="sc-icon-button" title="화면에 맞추기" aria-label="화면에 맞추기" onClick={() => void rf.fitView({ ...fitFor(!floating), duration: 300 })}><Icon name="maximize" size={17}/></button>
      </div>
      {query.trim() && <div className="sc-search-results" role="listbox" aria-label="검색 결과">{hits.length ? hits.map((n) => <button type="button" role="option" aria-selected={false} key={n.id} onClick={() => { go(n.id); setQuery(""); }}><span className={`sc-kind-dot sc-dot-${n.kind}`}/><span>{n.label}</span><small>{KINDS[n.kind] ?? n.kind}{inScope(n, scope) ? "" : " · 다른 범위"}</small></button>) : <span>일치하는 노드를 찾지 못했습니다.</span>}</div>}
    </div>
    <div className="sc-context">
      <div className="sc-type-legend"><span><i className="sc-kind-dot sc-dot-requirement"/>기술 요구</span><span><i className="sc-kind-dot sc-dot-bottleneck"/>병목</span><span><i className="sc-kind-dot sc-dot-technology"/>기술</span><span><i className="sc-kind-dot sc-dot-component"/>소재·부품·공정</span><span><i className="sc-kind-dot sc-dot-product"/>제품</span><span><i className="sc-kind-dot sc-dot-company"/>기업</span><span><i className="sc-kind-dot sc-dot-standard"/>세대·표준</span><span className="sc-legend-small">★ 소형·초소형주</span></div>
      <div className="sc-depth" role="group" aria-label="상세도 (최대 깊이)">
        <span className="sc-depth-label">깊이</span>
        <button type="button" aria-pressed={depthMode === "auto"} className={depthMode === "auto" ? "active" : ""} onClick={() => setDepthMode("auto")} title="확대할수록 더 깊은 층이 나타납니다">자동</button>
        {DEPTHS.map((d) => <button key={d.level} type="button" title={d.hint} aria-pressed={depthMode === d.level}
          className={depthMode === d.level ? "active" : maxLevel >= d.level ? "within" : ""} onClick={() => setDepthMode(d.level)}>{d.name}</button>)}
        {depthMode === "auto" && <span className="sc-depth-hint">현재 {DEPTHS[maxLevel - 1].name}까지 · 확대하면 더 깊이</span>}
      </div>
      <div className="sc-trust-toggle" role="group" aria-label="근거 필터"><button type="button" aria-pressed={trust === "all"} className={trust === "all" ? "active" : ""} onClick={() => setTrust("all")}>전체 관계</button><button type="button" aria-pressed={trust === "documented"} className={trust === "documented" ? "active" : ""} onClick={() => setTrust("documented")}>추론 제외</button></div>
    </div>
    <div className={`sc-body ${showInspector ? "has-inspector" : ""}`}>
      <div ref={flowRef} className="sc-flow" onWheel={onWheel}>
        <HighlightContext.Provider value={highlight}><HiddenContext.Provider value={hiddenCounts}>
          <FlowArea layoutNodes={layoutNodes} layoutKey={layoutKey} visible={visible} fit={fitFor(!floating)} edges={flowEdges} selected={selected} selectedEdge={selectedEdge}
            onSelectNode={selectNode} onSelectEdge={selectEdge} zoomKey={zoomKey} wrapperRef={flowRef}
            guides={layout?.guides ?? null} showMinimap={showMinimap} onToggleMinimap={() => setShowMinimap((v) => !v)}/>
        </HiddenContext.Provider></HighlightContext.Provider>
        <div className="sc-overlay-top">
          {selectedNode ? <div className="sc-selection-hint">
            <span className="sc-selection-name">{selectedNode.label}</span>
            <span className="sc-hop" role="group" aria-label="연결 강조 범위">{[1, 2, 3].map((d) => <button key={d} type="button" aria-pressed={depth === d} className={depth === d ? "active" : ""} onClick={() => setDepth(d)}>{d}-hop</button>)}</span>
            <button type="button" className="sc-clear" onClick={clearAll}>해제 <kbd>Esc</kbd></button>
          </div> : <div className="sc-selection-hint sc-idle-hint">노드·연결선을 클릭하면 근거 패널이 열립니다 · 드래그로 이동</div>}
          {!showInspector && <button type="button" className="sc-reopen-inspector" onClick={() => setInspectorOpen(true)}><Icon name="panel-right" size={16}/> 근거 패널</button>}
        </div>
        <div className={`sc-wheel-hint ${wheelHint ? "is-on" : ""}`} aria-hidden>Ctrl / ⌘ + 스크롤 또는 핀치로 확대 · 축소</div>
      </div>
      {showInspector && <Inspector nodeId={selected} edgeId={selectedEdge} scope={scope} onSelectNode={go} onSelectEdge={selectEdge}
        onExpand={() => setImpactOn(true)} onClose={() => setInspectorOpen(false)}/>}
    </div>
    <div className="sc-footnote">
      <div className="sc-edge-legend">
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg tier-documented"/></svg>공식·실측</span>
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg tier-claimed"/></svg>주장·보도</span>
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg tier-inferred"/></svg>추론·가설</span>
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg pol-negative"/></svg>부정 관계</span>
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg pol-conditional"/></svg>조건부</span>
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg rel-substitute"/></svg>대체 기술</span>
        <span><svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4" className="lg rel-displace"/></svg>수요 잠식</span>
      </div>
      <span>연구 그래프 {seed.nodes.length}개 노드 · {seed.edges.length}개 관계 · 관계 이름은 연결선에 마우스를 올리거나 선택하면 표시</span>
    </div>
  </section>;
}

type FlowAreaProps = {
  layoutNodes: SupplyFlowNode[];
  layoutKey: string;
  /** Level of detail: ids to draw (null = all). */
  visible: Set<string> | null;
  fit: Fit;
  edges: SupplyFlowEdge[];
  selected: string | null;
  selectedEdge: string | null;
  onSelectNode: (id: string | null) => void;
  onSelectEdge: (id: string | null) => void;
  zoomKey: boolean;
  wrapperRef: React.RefObject<HTMLDivElement | null>;
  guides: Guide[] | null;
  showMinimap: boolean;
  onToggleMinimap: () => void;
};

/** Owns the controlled node state, so drag frames re-render only this subtree (and React Flow
 *  only re-renders the dragged node + its edges), never the toolbar or inspector. */
const FlowArea = memo(function FlowArea({ layoutNodes, layoutKey, visible, fit, edges, selected, selectedEdge, onSelectNode, onSelectEdge, zoomKey, wrapperRef, guides, showMinimap, onToggleMinimap }: FlowAreaProps) {
  const [nodes, setNodes, applyNodes] = useNodesState<SupplyFlowNode>([]);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const edgeRef = useRef(selectedEdge);
  edgeRef.current = selectedEdge;
  const visibleRef = useRef(visible);
  visibleRef.current = visible;

  /** Positions the user dragged, per drawing; kept for the lifetime of the page. */
  const drags = useRef(new Map<string, Map<string, XYPosition>>());
  const keyRef = useRef(layoutKey);
  keyRef.current = layoutKey;

  useEffect(() => {
    const moved = drags.current.get(layoutKey);
    const vis = visibleRef.current;
    setNodes(layoutNodes.map((n) => {
      const p = moved?.get(n.id), hidden = !!vis && !vis.has(n.id);
      return p || hidden || n.id === selectedRef.current ? { ...n, ...(p ? { position: p } : null), selected: n.id === selectedRef.current, hidden } : n;
    }));
  }, [layoutNodes, layoutKey, setNodes]);
  useEffect(() => {
    setNodes((ns) => ns.map((n) => {
      const hidden = !!visible && !visible.has(n.id);
      return !!n.hidden === hidden ? n : { ...n, hidden };
    }));
  }, [visible, setNodes]);
  useEffect(() => {
    setNodes((ns) => ns.map((n) => ((n.id === selected) === !!n.selected ? n : { ...n, selected: n.id === selected })));
  }, [selected, setNodes]);

  const onNodesChange = useCallback((changes: NodeChange<SupplyFlowNode>[]) => {
    applyNodes(changes);
    let picked: string | null | undefined;
    for (const c of changes) {
      if (c.type === "position" && c.position) {
        const m = drags.current.get(keyRef.current) ?? drags.current.set(keyRef.current, new Map()).get(keyRef.current)!;
        m.set(c.id, c.position);
      }
      if (c.type !== "select") continue;
      if (c.selected) picked = c.id;
      else if (picked === undefined && c.id === selectedRef.current) picked = null;
    }
    if (picked !== undefined && picked !== selectedRef.current) onSelectNode(picked);
  }, [applyNodes, onSelectNode]);
  const onEdgesChange = useCallback((changes: EdgeChange<SupplyFlowEdge>[]) => {
    let picked: string | null | undefined;
    for (const c of changes) {
      if (c.type !== "select") continue;
      if (c.selected) picked = c.id;
      else if (picked === undefined && c.id === edgeRef.current) picked = null;
    }
    if (picked !== undefined && picked !== edgeRef.current) onSelectEdge(picked);
  }, [onSelectEdge]);

  return <ReactFlow<SupplyFlowNode, SupplyFlowEdge>
    nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
    onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
    minZoom={MIN_ZOOM} maxZoom={2.2}
    zoomOnScroll={false} preventScrolling={zoomKey} zoomOnPinch zoomOnDoubleClick
    nodesConnectable={false} selectNodesOnDrag={false} deleteKeyCode={null} selectionKeyCode={null} multiSelectionKeyCode={null}
    elevateEdgesOnSelect onlyRenderVisibleElements ariaLabelConfig={ARIA} proOptions={{ hideAttribution: true }}>
    <Background variant={BackgroundVariant.Dots} gap={22} size={1.1} color="#c3d2e2"/>
    {guides && <ViewportPortal>{guides.map((g, i) => <div key={i} className={`sc-guide sc-guide-${g.kind}${g.stacked ? " sc-guide-stacked" : ""}`} style={{ transform: `translate(${g.x}px, ${g.y}px)`, minWidth: g.w, ...(g.color ? { ["--guide" as string]: g.color } : {}) }}>{g.label}</div>)}</ViewportPortal>}
    <Controls position="bottom-left" showInteractive={false} fitViewOptions={{ ...fit, duration: 300 }}>
      <ControlButton onClick={onToggleMinimap} title={showMinimap ? "미니맵 숨기기" : "미니맵 보기"} aria-label={showMinimap ? "미니맵 숨기기" : "미니맵 보기"} aria-pressed={showMinimap}><Icon name="grid" size={14}/></ControlButton>
    </Controls>
    {showMinimap && <AutoMiniMap/>}
    <ZoomWatcher wrapperRef={wrapperRef}/>
  </ReactFlow>;
});

/** The minimap only appears once part of the graph is off-screen — at fit-to-view it would just
 *  cover nodes in the corner without adding anything. */
function AutoMiniMap() {
  const clipped = useStore((s) => {
    const [tx, ty, z] = s.transform;
    if (!s.width || !s.height) return false;
    for (const n of s.nodeLookup.values()) {
      if (n.hidden) continue;
      const p = n.internals.positionAbsolute, x = p.x * z + tx, y = p.y * z + ty;
      if (x < 0 || y < 0 || x + NODE_W * z > s.width || y + NODE_H * z > s.height) return true;
    }
    return false;
  });
  return clipped ? <MiniMap<SupplyFlowNode> position="bottom-right" pannable zoomable nodeColor={minimapColor} nodeStrokeWidth={0} maskColor="rgba(240,245,252,.72)" className="sc-minimap" style={{ width: 168, height: 104 }}/> : null;
}

/** Writes the zoom into a CSS variable / class on the wrapper (semantic zoom without React
 *  re-rendering any node) and shows the zoom level. */
function ZoomWatcher({ wrapperRef }: { wrapperRef: React.RefObject<HTMLDivElement | null> }) {
  const zoom = useStore((s) => s.transform[2]);
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    el.style.setProperty("--sc-z", String(zoom));
    el.classList.toggle("sc-lod", zoom < OVERVIEW_ZOOM);
  }, [zoom, wrapperRef]);
  return <Panel position="bottom-left" className="sc-zoom-label">{Math.round(zoom * 100)}%{zoom < OVERVIEW_ZOOM ? " · 개요 (확대하면 더 보임)" : ""}</Panel>;
}
