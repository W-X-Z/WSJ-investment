/** Pure graph model + deterministic layouts for the supply-chain canvas.
 *
 * Layout is a small Sugiyama-style layered placement: the layer (column) of every node is
 * fixed by its ontology kind, so only in-layer ordering (barycenter sweeps) and column
 * wrapping are computed. That keeps the result deterministic, synchronous (no layout jump,
 * no web worker) and dependency-free — elkjs would add ~1.5 MB for a ~140-node graph.
 */
import { seed, type Edge, type EcoId, type GraphNode } from "@/lib/research-client";

export type Scope = EcoId | "all";
export type Mode = "layers" | "clusters" | "impact";
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

/** Text guides drawn in flow coordinates; (x, y) is the bottom-left anchor of the label.
 *  `stacked` column headers sit one line above the first band's label. */
export type Guide = { x: number; y: number; w: number; label: string; kind: "column" | "band"; color?: string; stacked?: boolean };
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

/** Focus + context: selected node in the middle, upstream hops to the left, downstream to the right. */
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
  const signed = new Map<string, number>();
  for (const [id, d] of down) signed.set(id, d);
  for (const [id, d] of up) if (!signed.has(id) || d < signed.get(id)!) signed.set(id, -d);
  // Nodes connected only through mixed directions (e.g. sibling suppliers) join at their undirected hop.
  const undirected = neighborhood(focus, depth, adjacency(edges));
  for (const [id, d] of undirected) if (!signed.has(id)) signed.set(id, d);
  const min = Math.min(...signed.values()), max = Math.max(...signed.values());
  const cols: string[][][] = [];
  const labels: string[] = [];
  for (let c = min; c <= max; c++) {
    const list = [...signed].filter(([, d]) => d === c).map(([id]) => id).sort((a, b) => (LAYER[nodeIndex.get(a)!.kind] ?? 4) - (LAYER[nodeIndex.get(b)!.kind] ?? 4) || byKindThenLabel(a, b));
    if (!list.length) continue;
    cols.push([list]);
    labels.push(c === 0 ? "선택 노드" : c < 0 ? `상류 ${-c}단계` : `하류 ${c}단계`);
  }
  const sub = new Set(signed.keys());
  orderColumns(cols, adjacency(edges.filter((e) => sub.has(e.from) && sub.has(e.to))));
  return placeColumns(cols, vp, labels, null);
}

/** Ecosystem clusters: the ecosystem root in the centre, one elliptical ring per ontology layer
 *  around it (ellipses because nodes are ~3× wider than tall). Ring order follows the mean angle
 *  of inner-ring neighbours to limit crossings. Scope "all" stacks the clusters vertically. */
export function clusterLayout(nodes: GraphNode[], edges: Edge[], scope: Scope): Layout {
  const positions = new Map<string, Vec>();
  const guides: Guide[] = [];
  const adj = adjacency(edges);
  const bands: EcoId[] = scope === "all" ? ECOS.map((e) => e.id) : [scope];
  const RX = NODE_W + 44, RY = NODE_H + 34, SLOT = 250;
  let top = 0;
  bands.forEach((eco) => {
    const members = nodes.filter((n) => (scope === "all" ? (ecoOf(n) ?? "hbm") === eco : true));
    const rings = new Map<number, string[]>();
    for (const n of members) {
      const l = n.kind === "ecosystem" ? -1 : LAYER[n.kind] ?? 4;
      (rings.get(l) ?? rings.set(l, []).get(l)!).push(n.id);
    }
    const angle = new Map<string, number>();
    const placed: { list: string[]; rx: number; ry: number }[] = [];
    let k = 0;
    for (const l of [...rings.keys()].sort((a, b) => a - b)) {
      const list = rings.get(l)!.sort(byKindThenLabel);
      if (l === -1 && list.length === 1) { placed.push({ list, rx: 0, ry: 0 }); angle.set(list[0], -Math.PI / 2); continue; }
      k++;
      // Ring must be long enough for its nodes: ellipse perimeter ≈ 2π·sqrt((rx²+ry²)/2).
      let rx = k * RX, ry = k * RY;
      const need = (list.length * SLOT) / (2 * Math.PI);
      const have = Math.sqrt((rx * rx + ry * ry) / 2);
      if (have < need) { rx *= need / have; ry *= need / have; }
      const key = new Map(list.map((id, i) => {
        let sx = 0, sy = 0;
        for (const nb of adj.get(id) ?? []) { const a = angle.get(nb); if (a !== undefined) { sx += Math.cos(a); sy += Math.sin(a); } }
        return [id, sx || sy ? Math.atan2(sy, sx) : -Math.PI / 2 + (2 * Math.PI * i) / list.length] as const;
      }));
      list.sort((a, b) => ((key.get(a)! + 2.5 * Math.PI) % (2 * Math.PI)) - ((key.get(b)! + 2.5 * Math.PI) % (2 * Math.PI)));
      list.forEach((id, i) => angle.set(id, -Math.PI / 2 + (2 * Math.PI * i) / list.length));
      placed.push({ list, rx, ry });
    }
    const maxX = Math.max(NODE_W, ...placed.map((p) => p.rx)), maxY = Math.max(NODE_H, ...placed.map((p) => p.ry));
    const cx = maxX + NODE_W / 2, cy = top + maxY + NODE_H / 2;
    for (const { list, rx, ry } of placed) {
      for (const id of list) {
        const a = angle.get(id)!;
        positions.set(id, { x: cx + Math.cos(a) * rx - NODE_W / 2, y: cy + Math.sin(a) * ry - NODE_H / 2 });
      }
    }
    guides.push({ kind: "band", x: 0, y: top - 14, w: maxX * 2 + NODE_W, label: ECO_NAME[eco], color: ECOS.find((e) => e.id === eco)?.color });
    top = cy + maxY + NODE_H / 2 + BAND_GAP + 40;
  });
  return { positions, guides };
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
