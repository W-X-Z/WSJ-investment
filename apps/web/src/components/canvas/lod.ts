/** Zoom-driven level of detail (LOD) for the supply canvas — map-style: zoomed out you see the
 *  backbone (generations, requirements, bottlenecks); zooming in reveals technologies, then
 *  processes / materials / equipment / products, then the supplier companies.
 *
 * - Every node has a depth level by ontology kind (1 골격 … 4 기업) and a rank (level, then
 *   small caps first among companies, then degree). The user can cap the depth by hand.
 * - Below PILL_ZOOM cards are drawn as constant-screen-size pills (CSS `.sc-lod`), so they would
 *   overlap when zoomed out; `declutter` places pills greedily in rank order and hides any pill
 *   that would collide with one already placed (like map labels). At or above PILL_ZOOM the
 *   force layout already keeps cards apart, so every node within the depth cap is shown.
 * - The selected node, its direct neighbours and search hits are always shown; the rest of the
 *   selection's neighbourhood is placed before everything else.
 * Pure functions only (no React) so the behaviour can be checked from a script.
 */
import type { Edge, GraphNode } from "@/lib/research-client";

export const DEPTHS = [
  { level: 1, name: "골격", hint: "세대·요구·병목" },
  { level: 2, name: "기술", hint: "+ 해결 기술·핵심 부품" },
  { level: 3, name: "공정·소재", hint: "+ 공정·소재·장비·제품" },
  { level: 4, name: "기업", hint: "+ 공급·수요 기업" },
] as const;
export const MAX_LEVEL = 4;

const KIND_LEVEL: Record<string, number> = {
  ecosystem: 1, product_generation: 1, standard: 1, requirement: 1, bottleneck: 1,
  technology: 2, component: 2,
  process: 3, material: 3, equipment: 3, product: 3,
  company: 4,
};
export const levelOf = (n: GraphNode) => KIND_LEVEL[n.kind] ?? 3;

/** Card size in flow px (must match graph-model NODE_W / NODE_H). */
const CARD_W = 196, CARD_H = 60;
/** Zoom below which cards become pills of constant screen size (= the card at this zoom). */
export const PILL_ZOOM = 0.66;
const PILL_W = CARD_W * PILL_ZOOM, PILL_H = CARD_H * PILL_ZOOM;
/** Free space kept around each pill, screen px. */
const GAP = 8;
/** Zoom is quantised to 6 % steps so visibility is recomputed only when it can change. */
export const ZOOM_STEP = 1.06;
export const quantizeZoom = (z: number) => Math.round(Math.log(Math.max(z, 1e-3)) / Math.log(ZOOM_STEP));
export const zoomOfStep = (q: number) => ZOOM_STEP ** q;

const SMALL = new Set(["small", "micro"]);

/** Rank order (most important first) and level per node, for a fixed node / edge set. */
export function lodIndex(nodes: GraphNode[], edges: Edge[]): { order: string[]; level: Map<string, number> } {
  const degree = new Map<string, number>();
  for (const e of edges) { degree.set(e.from, (degree.get(e.from) ?? 0) + 1); degree.set(e.to, (degree.get(e.to) ?? 0) + 1); }
  const level = new Map(nodes.map((n) => [n.id, levelOf(n)]));
  const key = (n: GraphNode) => [
    level.get(n.id)!,
    n.kind === "ecosystem" ? 0 : 1,
    n.kind === "company" && SMALL.has(n.size_band ?? "") ? 0 : 1,
    -(degree.get(n.id) ?? 0),
  ];
  const order = [...nodes].sort((a, b) => {
    const ka = key(a), kb = key(b);
    for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  }).map((n) => n.id);
  return { order, level };
}

type Pt = { x: number; y: number };

/** Share of the canvas that pills may cover before the next depth level is let in. */
const DENSITY = 0.3;
/** Automatic depth: the deepest level whose nodes, at this zoom, would cover no more than DENSITY
 *  of the canvas as pills (assuming they spread over the whole drawing like at fit-to-view).
 *  `cumulative[L]` = number of nodes with level ≤ L (index 0 unused). */
export function autoLevel(cumulative: number[], fitZoom: number, zoom: number, canvas: { w: number; h: number }): number {
  if (zoom >= PILL_ZOOM) return MAX_LEVEL;
  const budget = (canvas.w * canvas.h * DENSITY) / (PILL_W * PILL_H);
  const share = Math.min(1, (fitZoom / zoom) ** 2); // part of the drawing that is on screen
  let level = 1;
  for (let L = 2; L <= MAX_LEVEL; L++) if (cumulative[L] * share <= budget) level = L;
  return level;
}

/** Ids to draw at `zoom`: forced ids always, then `priority`, then `order`, skipping nodes deeper
 *  than `maxLevel` and (below PILL_ZOOM) pills that would overlap an already placed one. */
export function declutter(
  order: string[], level: Map<string, number>, positions: Map<string, Pt>, zoom: number,
  maxLevel: number, forced: Iterable<string> = [], priority: Iterable<string> = [],
): Set<string> {
  const shown = new Set<string>();
  const pill = zoom < PILL_ZOOM;
  // Work in screen px: pill size is fixed there, card size scales with zoom.
  const w = (pill ? PILL_W : CARD_W * zoom) + GAP, h = (pill ? PILL_H : CARD_H * zoom) + GAP;
  const grid = new Map<string, Pt[]>();
  const cellOf = (x: number, y: number) => `${Math.floor(x / w)},${Math.floor(y / h)}`;
  const centre = (id: string): Pt | null => {
    const p = positions.get(id);
    return p ? { x: (p.x + CARD_W / 2) * zoom, y: (p.y + CARD_H / 2) * zoom } : null;
  };
  const collides = (c: Pt) => {
    const gx = Math.floor(c.x / w), gy = Math.floor(c.y / h);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      for (const q of grid.get(`${gx + dx},${gy + dy}`) ?? []) if (Math.abs(q.x - c.x) < w && Math.abs(q.y - c.y) < h) return true;
    }
    return false;
  };
  const put = (id: string, c: Pt) => {
    shown.add(id);
    const k = cellOf(c.x, c.y);
    (grid.get(k) ?? grid.set(k, []).get(k)!).push(c);
  };
  for (const id of forced) { const c = centre(id); if (c && !shown.has(id)) put(id, c); }
  const tryPlace = (id: string) => {
    if (shown.has(id) || (level.get(id) ?? MAX_LEVEL) > maxLevel) return;
    const c = centre(id);
    if (!c) return;
    if (pill && collides(c)) return;
    put(id, c);
  };
  for (const id of priority) tryPlace(id);
  for (const id of order) tryPlace(id);
  return shown;
}

/** Per shown node: how many of its neighbours are hidden (badge "+N"). */
export function hiddenNeighbours(shown: Set<string>, adj: Map<string, Set<string>>, inLayout: (id: string) => boolean): Map<string, number> {
  const out = new Map<string, number>();
  for (const id of shown) {
    let n = 0;
    for (const nb of adj.get(id) ?? []) if (!shown.has(nb) && inLayout(nb)) n++;
    if (n) out.set(id, n);
  }
  return out;
}
