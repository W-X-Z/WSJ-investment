/** Pure graph model + deterministic layouts for the supply-chain canvas.
 *
 * - network (default): force-directed (see force-layout.ts) — position comes from the relations,
 *   not from the node kind; ecosystems form loose regions in scope "all".
 * - layers: Sugiyama-style columns fixed by ontology kind (secondary view).
 * - impact: radial focus + context around the selected node, one ring per hop.
 * All layouts are synchronous and deterministic (no layout jump, no web worker, no elkjs).
 */
import { seed, type Edge, type EcoId, type GraphNode } from "@/lib/research-client";
import { forceLayout } from "./force-layout";

export type Scope = EcoId | "all";
export type Mode = "network" | "layers" | "impact";
export type Trust = "all" | "documented";
export type Epistemic = "documented" | "claimed" | "inferred";
export type Vec = { x: number; y: number };

export const ECOS: { id: EcoId; name: string; short: string; color: string }[] = [
  { id: "hbm", name: "HBM · 첨단 패키징", short: "HBM", color: "#8c79ec" },
  { id: "optics", name: "광통신 · 포토닉스", short: "OPTICS", color: "#29aac3" },
  { id: "power", name: "전력변환 · 냉각", short: "POWER", color: "#ecab60" },
];
export const ECO_NAME: Record<string, string> = Object.fromEntries(ECOS.map((e) => [e.id, e.name]));

/** Ontology layer = column, left → right. */
export const LAYER: Record<string, number> = {
  ecosystem: 0, product_generation: 0, standard: 0,
  requirement: 1, bottleneck: 2, technology: 3,
  process: 4, component: 4, material: 4, equipment: 4,
  product: 5, company: 6,
};
export const LAYER_NAME = ["세대 · 표준", "기술 요구", "핵심 병목", "해결 기술", "공정 · 부품 · 소재", "제품", "기업"];
const KIND_RANK: Record<string, number> = {
  ecosystem: 0, product_generation: 1, standard: 2, process: 0, component: 1, material: 2, equipment: 3,
};

export const SIZE_NAME: Record<string, string> = {
  mega: "초대형", large: "대형", mid: "중형", small: "소형", micro: "초소형", private: "비상장", unknown: "규모 미상",
};
export const isSmallCap = (n: GraphNode) => n.size_band === "small" || n.size_band === "micro";

const DOCUMENTED = new Set(["independent_measurement", "standard_body", "official_issuer", "customer_statement"]);
const CLAIMED = new Set(["vendor_claim", "third_party_report"]);
/** documented = 공식·실측, claimed = 당사자 주장·보도, inferred = 기술 추론·가설·조건부. */
export function epistemic(e: Edge): Epistemic {
  if (e.polarity === "conditional") return "inferred";
  if (DOCUMENTED.has(e.evidence_tier)) return "documented";
  if (CLAIMED.has(e.evidence_tier)) return "claimed";
  return "inferred";
}
export const TIER_NAME: Record<string, string> = {
  independent_measurement: "독립 실측", standard_body: "표준 기구 문서", official_issuer: "당사자 공식 공시",
  customer_statement: "고객사 공식 진술", third_party_report: "제3자 보도", vendor_claim: "공급사 성능 주장",
  technical_inference: "기술적 추론 · 검증 필요", hypothesis: "가설",
};

// ---------- indexes (built once per module load; seed is static) ----------
export const nodeIndex = new Map(seed.nodes.map((n) => [n.id, n]));
export const edgeIndex = new Map(seed.edges.map((e) => [e.id, e]));
export const edgesByNode = new Map<string, Edge[]>();
for (const e of seed.edges) {
  for (const id of [e.from, e.to]) {
    const list = edgesByNode.get(id);
    if (list) list.push(e);
    else edgesByNode.set(id, [e]);
  }
}

export function ecoOf(n: GraphNode): EcoId | null {
  if (n.kind === "ecosystem") return n.id.replace(/^eco:/, "") as EcoId;
  return (n.ecosystem as EcoId | undefined) ?? null;
}
export function inScope(n: GraphNode, scope: Scope): boolean {
  if (scope === "all") return true;
  return ecoOf(n) === scope || (n.also_in ?? []).includes(scope);
}
export function scopeNodes(scope: Scope): GraphNode[] {
  return seed.nodes.filter((n) => inScope(n, scope));
}
export function visibleEdges(ids: Set<string>, trust: Trust): Edge[] {
  return seed.edges.filter((e) => ids.has(e.from) && ids.has(e.to) && (trust === "all" || epistemic(e) !== "inferred"));
}
export function adjacency(edges: Edge[]): Map<string, Set<string>> {
  const adj = new Map<string, Set<string>>();
  const add = (a: string, b: string) => {
    const s = adj.get(a);
    if (s) s.add(b);
    else adj.set(a, new Set([b]));
  };
  for (const e of edges) { add(e.from, e.to); add(e.to, e.from); }
  return adj;
}
/** Undirected hop distance from `start`, limited to `depth`. */
export function neighborhood(start: string, depth: number, adj: Map<string, Set<string>>): Map<string, number> {
  const dist = new Map([[start, 0]]);
  const queue = [start];
  for (let i = 0; i < queue.length; i++) {
    const id = queue[i];
    const d = dist.get(id)!;
    if (d >= depth) continue;
    for (const nb of adj.get(id) ?? []) if (!dist.has(nb)) { dist.set(nb, d + 1); queue.push(nb); }
  }
  return dist;
}

// ---------- layout ----------
export const NODE_W = 196;
export const NODE_H = 60;
const ROW_H = NODE_H + 14;
const SUB_GAP = 26;
const LAYER_GAP = 96;
const BAND_GAP = 110;

/** Text guides drawn in flow coordinates; (x, y) is the bottom-left anchor of the label
 *  (the centre for "region"). `stacked` column headers sit one line above the first band's label. */
export type Guide = { x: number; y: number; w: number; label: string; kind: "column" | "band" | "region"; color?: string; stacked?: boolean };
export type Layout = { positions: Map<string, Vec>; guides: Guide[] };
export type Viewport = { w: number; h: number };

/** Barycenter sweeps: reorder each (column, band) group by the mean position of neighbours
 *  in already-ordered columns. A handful of alternating sweeps removes most crossings. */
function orderColumns(cols: string[][][], adj: Map<string, Set<string>>) {
  const pos = new Map<string, number>();
  const colOf = new Map<string, number>();
  const assign = (c: number, b: number, ids: string[]) =>
    ids.forEach((id, i) => { pos.set(id, b + (ids.length > 1 ? i / (ids.length - 1) : 0.5) * 0.98); colOf.set(id, c); });
  cols.forEach((bands, c) => bands.forEach((ids, b) => assign(c, b, ids)));
  for (let iter = 0; iter < 6; iter++) {
    const forward = iter % 2 === 0;
    for (let step = 0; step < cols.length; step++) {
      const c = forward ? step : cols.length - 1 - step;
      cols[c].forEach((ids, b) => {
        const key = new Map<string, number>();
        for (const id of ids) {
          let sum = 0, cnt = 0;
          for (const nb of adj.get(id) ?? []) {
            const nc = colOf.get(nb);
            if (nc === undefined || nc === c || (forward ? nc > c : nc < c)) continue;
            sum += pos.get(nb)!; cnt++;
          }
          key.set(id, cnt ? sum / cnt : pos.get(id)!);
        }
        ids.sort((x, y) => key.get(x)! - key.get(y)!);
        assign(c, b, ids);
      });
    }
  }
}

/** Place ordered columns; wraps tall columns into sub-columns, choosing the wrap height that
 *  maximises the zoom at which the whole scope fits the viewport. */
function placeColumns(cols: string[][][], vp: Viewport, columnLabels: string[], bandLabels: { label: string; color?: string }[] | null): Layout {
  const nBands = cols[0]?.length ?? 1;
  const tallest = Math.max(1, ...cols.flatMap((bands) => bands.map((ids) => ids.length)));
  let best: { k: number[]; bandRows: number[]; z: number } | null = null;
  for (let r = 3; r <= Math.max(3, tallest); r++) {
    const k = cols.map((bands) => Math.max(1, ...bands.map((ids) => Math.ceil(ids.length / r))));
    const bandRows = Array.from({ length: nBands }, (_, b) => Math.max(1, ...cols.map((bands, c) => Math.ceil(bands[b].length / k[c]))));
    const W = k.reduce((s, kc) => s + kc * NODE_W + (kc - 1) * SUB_GAP, 0) + (cols.length - 1) * LAYER_GAP;
    const H = bandRows.reduce((s, rows) => s + rows * ROW_H, 0) + (nBands - 1) * BAND_GAP + 80;
    const z = Math.min(vp.w / W, vp.h / H);
    if (!best || z > best.z + 1e-6) best = { k, bandRows, z };
  }
  const { k, bandRows } = best!;
  const positions = new Map<string, Vec>();
  const guides: Guide[] = [];
  const bandTop: number[] = [];
  let y = 0;
  for (let b = 0; b < nBands; b++) { bandTop.push(y); y += bandRows[b] * ROW_H + BAND_GAP; }
  let x = 0;
  cols.forEach((bands, c) => {
    const width = k[c] * NODE_W + (k[c] - 1) * SUB_GAP;
    guides.push({ kind: "column", x, y: -14, w: width, label: columnLabels[c], stacked: !!bandLabels && nBands > 1 });
    bands.forEach((ids, b) => {
      const rows = Math.ceil(ids.length / k[c]);
      const offset = ((bandRows[b] - rows) * ROW_H) / 2;
      ids.forEach((id, j) => {
        const row = Math.floor(j / k[c]), sub = j % k[c];
        positions.set(id, { x: x + sub * (NODE_W + SUB_GAP), y: bandTop[b] + offset + row * ROW_H });
      });
    });
    x += width + LAYER_GAP;
  });
  if (bandLabels && nBands > 1) {
    bandLabels.forEach((band, b) => guides.push({ kind: "band", x: 0, y: bandTop[b] - 14, w: x - LAYER_GAP, label: band.label, color: band.color }));
  }
  return { positions, guides };
}

function byKindThenLabel(a: string, b: string) {
  const na = nodeIndex.get(a)!, nb = nodeIndex.get(b)!;
  return (KIND_RANK[na.kind] ?? 0) - (KIND_RANK[nb.kind] ?? 0) || na.label.localeCompare(nb.label);
}

/** Layered (LEFT → RIGHT by ontology layer). Scope "all" stacks one band per ecosystem with
 *  columns aligned across bands. */
export function layeredLayout(nodes: GraphNode[], edges: Edge[], scope: Scope, vp: Viewport): Layout {
  const bands: EcoId[] = scope === "all" ? ECOS.map((e) => e.id) : [scope];
  const cols: string[][][] = LAYER_NAME.map(() => bands.map(() => [] as string[]));
  for (const n of nodes) {
    const b = scope === "all" ? Math.max(0, bands.indexOf(ecoOf(n) ?? "hbm")) : 0;
    cols[LAYER[n.kind] ?? 4][b].push(n.id);
  }
  cols.forEach((bs) => bs.forEach((ids) => ids.sort(byKindThenLabel)));
  const keep = cols.map((bs, i) => ({ bs, i })).filter(({ bs }) => bs.some((ids) => ids.length));
  const filtered = keep.map((x) => x.bs);
  orderColumns(filtered, adjacency(edges));
  return placeColumns(filtered, vp, keep.map((x) => LAYER_NAME[x.i]), bands.map((id) => ({ label: ECO_NAME[id], color: ECOS.find((e) => e.id === id)?.color })));
}

/** Viewport aspect, bucketed so small window differences give the identical drawing. */
function aspectBucket(vp: Viewport): number {
  const a = vp.w / vp.h;
  return a >= 1.55 ? 1.8 : a >= 1.15 ? 1.35 : a >= 0.8 ? 1 : 0.7;
}
const isStrong = (e: Edge) => epistemic(e) === "documented";

/** Network (default): force-directed, position independent of node kind. In scope "all" each
 *  ecosystem gets a weak anchor so hbm / optics / power form loose regions; multi-ecosystem
 *  nodes have no anchor and settle between them. */
export function networkLayout(nodes: GraphNode[], edges: Edge[], scope: Scope, vp: Viewport): Layout {
  const groupOf = (n: GraphNode) => (scope === "all" && !(n.also_in?.length) ? ecoOf(n) : null);
  const positions = forceLayout(
    nodes.map((n) => ({ id: n.id, group: groupOf(n) })),
    edges.map((e) => ({ source: e.from, target: e.to, strong: isStrong(e) })),
    { w: NODE_W, h: NODE_H, aspect: aspectBucket(vp), groups: ECOS.map((e) => e.id) },
  );
  return { positions, guides: scope === "all" ? regionLabels(nodes, positions, groupOf, vp) : [] };
}

/** Ecosystem names for the network view: for each region, the free spot nearest its centroid
 *  (no card underneath, inside the drawing, and closer to its own cards than to any other
 *  region's). Label size is estimated at the fit-to-view zoom, matching .sc-guide-region. */
function regionLabels(nodes: GraphNode[], positions: Map<string, Vec>, groupOf: (n: GraphNode) => string | null, vp: Viewport): Guide[] {
  const P = nodes.map((n) => ({ g: groupOf(n), p: positions.get(n.id)! }));
  const x0 = Math.min(...P.map((q) => q.p.x)), y0 = Math.min(...P.map((q) => q.p.y));
  const x1 = Math.max(...P.map((q) => q.p.x)) + NODE_W, y1 = Math.max(...P.map((q) => q.p.y)) + NODE_H;
  const z = Math.min(1, Math.max(0.08, Math.min((vp.w - 86) / (x1 - x0), (vp.h - 110) / (y1 - y0))));
  const font = Math.max(14, 15 / z); // matches .sc-guide-region
  const taken: { x: number; y: number; w: number; h: number }[] = P.map((q) => ({ x: q.p.x - 10, y: q.p.y - 10, w: NODE_W + 20, h: NODE_H + 20 }));
  const hit = (a: { x: number; y: number; w: number; h: number }) => taken.some((b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h);
  const guides: Guide[] = [];
  for (const eco of ECOS) {
    const own = P.filter((q) => q.g === eco.id);
    if (!own.length) continue;
    const cx = own.reduce((s, q) => s + q.p.x, 0) / own.length + NODE_W / 2, cy = own.reduce((s, q) => s + q.p.y, 0) / own.length + NODE_H / 2;
    const lw = eco.name.length * font * 0.86, lh = font * 1.5;
    let best: { x: number; y: number; d: number } | null = null;
    for (let x = x0 + lw / 2; x <= x1 - lw / 2; x += font / 2) {
      for (let y = y0 + lh / 2; y <= y1 - lh / 2; y += font / 2) {
        const d = Math.hypot(x - cx, (y - cy) * 1.6);
        if (best && d >= best.d) continue;
        if (hit({ x: x - lw / 2, y: y - lh / 2, w: lw, h: lh })) continue;
        let nearest = Infinity, mine = false;
        for (const q of P) {
          const dd = Math.hypot(q.p.x + NODE_W / 2 - x, q.p.y + NODE_H / 2 - y);
          if (dd < nearest) { nearest = dd; mine = q.g === eco.id; }
        }
        if (mine) best = { x, y, d };
      }
    }
    if (!best) continue;
    taken.push({ x: best.x - lw / 2, y: best.y - lh / 2, w: lw, h: lh });
    guides.push({ kind: "region", x: best.x, y: best.y, w: 0, label: eco.name, color: eco.color });
  }
  return guides;
}

/** Focus + context, radial: the selected node in the centre, one ring per hop. Upstream nodes
 *  start on the left half and downstream on the right, then relax with the same forces. */
export function impactLayout(focus: string, depth: number, nodes: GraphNode[], edges: Edge[], vp: Viewport): Layout {
  const ids = new Set(nodes.map((n) => n.id));
  const out = new Map<string, string[]>(), inc = new Map<string, string[]>();
  for (const e of edges) {
    (out.get(e.from) ?? out.set(e.from, []).get(e.from)!).push(e.to);
    (inc.get(e.to) ?? inc.set(e.to, []).get(e.to)!).push(e.from);
  }
  const walk = (next: Map<string, string[]>) => {
    const dist = new Map([[focus, 0]]);
    const queue = [focus];
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i], d = dist.get(id)!;
      if (d >= depth) continue;
      for (const nb of next.get(id) ?? []) if (ids.has(nb) && !dist.has(nb)) { dist.set(nb, d + 1); queue.push(nb); }
    }
    return dist;
  };
  const down = walk(out), up = walk(inc);
  const hop = neighborhood(focus, depth, adjacency(edges));
  const side = new Map<string, number>();
  for (const id of hop.keys()) side.set(id, up.has(id) && (!down.has(id) || up.get(id)! < down.get(id)!) ? -1 : down.has(id) ? 1 : 0);
  const sub = [...hop.keys()];
  const subSet = new Set(sub);
  const positions = forceLayout(
    sub.map((id) => ({ id })),
    edges.filter((e) => subSet.has(e.from) && subSet.has(e.to)).map((e) => ({ source: e.from, target: e.to, strong: isStrong(e) })),
    // The inspector column (≈340px) is always open in this view on wide screens.
    { w: NODE_W, h: NODE_H, aspect: aspectBucket({ w: vp.w > 900 ? vp.w - 340 : vp.w, h: vp.h }), rings: hop, focus, side, ticks: 240 },
  );
  return { positions, guides: [] };
}

/** Only http(s) URLs become links; anything else is shown as text. */
export function safeUrl(raw: string): URL | null {
  try {
    const u = new URL(raw);
    return u.protocol === "https:" || u.protocol === "http:" ? u : null;
  } catch {
    return null;
  }
}

/** "Camtek (CAMT)" → "Camtek" when the ticker is shown as a chip anyway. */
export function displayLabel(n: GraphNode): string {
  const t = n.listing?.ticker;
  return t ? n.label.replace(new RegExp(`\\s*\\(${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\)`), "") : n.label;
}
