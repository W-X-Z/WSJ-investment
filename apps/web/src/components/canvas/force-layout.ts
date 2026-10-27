/** Deterministic force-directed placement for fixed-size node cards (d3-force, run synchronously).
 *
 * Position is driven only by the relations: links pull (documented ones a bit shorter), a
 * cut-off many-body charge repels, a rectangular collision keeps 196×60 cards apart, and a weak
 * pull toward a group anchor lets ecosystems form loose regions (and keeps disconnected nodes
 * from drifting away). Initial positions are a BFS-ordered phyllotaxis spiral (no Math.random)
 * and the simulation runs a fixed number of ticks, then a hard overlap-removal pass — so the same
 * input always gives the same picture and nothing moves after first paint. Only d3-force's
 * simulation / link / x / y are used (no quadtree). Imports nothing from the app so it can be
 * tuned from a script.
 */
import { forceLink, forceSimulation, forceX, forceY, type Force, type SimulationLinkDatum, type SimulationNodeDatum } from "d3-force";

export type FVec = { x: number; y: number };
export type FNode = { id: string; group?: string | null };
export type FLink = { source: string; target: string; strong?: boolean };
export type ForceOptions = {
  /** Card size; positions returned are the top-left corner (React Flow convention). */
  w: number;
  h: number;
  /** Target width / height of the whole drawing (viewport aspect, bucketed by the caller). */
  aspect: number;
  /** Group anchors are laid out in this order; nodes whose group is null/unknown sit at the centre. */
  groups?: string[];
  /** Impact view: node → hop distance from `focus`; hop k is pulled to the k-th ellipse ring. */
  rings?: Map<string, number>;
  focus?: string;
  /** Impact view: preferred side per node (-1 upstream = left, +1 downstream = right). */
  side?: Map<string, number>;
  ticks?: number;
};

type SimNode = SimulationNodeDatum & { id: string; i: number; ax: number; ay: number; hop: number };
type SimLink = SimulationLinkDatum<SimNode> & { strong?: boolean };

/** Tuning (flow px). Mutable only so a script can explore values; the app never changes it. */
export const FORCE = {
  /** Link rest length between card centres = base · (strong ? strongFactor : 1). */
  linkBase: 162, strongFactor: 0.82,
  /** Many-body repulsion and its range (local spacing only, so regions stay compact). */
  charge: -700, chargeRange: 640,
  /** Anchor pull toward the ecosystem region / centre, and how far apart region anchors sit. */
  pull: 0.07, anchorSpread: 0.18,
  /** Max squash of the long axis toward the viewport aspect after the simulation (0 = off). */
  aspectFit: 0.3,
  ticks: 360,
};
const GAP_X = 40, GAP_Y = 28; // minimum clearance between cards

/** Index pairs whose x-extents (centres `xs`, width `W`) overlap — sort-and-sweep, so only
 *  horizontally close cards are compared. Order is deterministic (ties by index). */
function sweep(xs: number[], W: number, visit: (i: number, j: number) => void) {
  const order = xs.map((_, i) => i).sort((a, b) => xs[a] - xs[b] || a - b);
  for (let p = 0; p < order.length; p++) {
    const i = order[p];
    for (let q = p + 1; q < order.length && xs[order[q]] - xs[i] < W; q++) {
      const j = order[q];
      if (i < j) visit(i, j); else visit(j, i);
    }
  }
}

/** Many-body repulsion with a cut-off, computed exactly over x-sorted pairs. For a few hundred
 *  nodes this beats d3.forceManyBody's Barnes–Hut quadtree (≈5× faster here) and is the same
 *  force law: Δv = Δp · strength · alpha / d². */
function repulse(strength: number, range: number): Force<SimNode, undefined> {
  let nodes: SimNode[] = [];
  const r2 = range * range;
  const force = (alpha: number) => {
    sweep(nodes.map((n) => n.x!), range, (i, j) => {
      const a = nodes[i], b = nodes[j];
      let dx = b.x! - a.x!, dy = b.y! - a.y!;
      let l = dx * dx + dy * dy;
      if (l >= r2) return;
      if (l < 1) { dx = (j - i) * 1e-3; dy = 1e-3; l = 1; } // coincident: deterministic nudge
      const k = (strength * alpha) / l;
      a.vx! += dx * k; a.vy! += dy * k;
      b.vx! -= dx * k; b.vy! -= dy * k;
    });
  };
  force.initialize = (ns: SimNode[]) => { nodes = ns; };
  return force;
}

/** Rectangle collision between cards. Resolves along the axis of least overlap, using predicted
 *  positions like d3.forceCollide. */
function rectCollide(w: number, h: number, strength: number): Force<SimNode, undefined> {
  let nodes: SimNode[] = [];
  const W = w + GAP_X, H = h + GAP_Y;
  const force = () => {
    sweep(nodes.map((n) => n.x! + n.vx!), W, (i, j) => {
      const a = nodes[i], b = nodes[j];
      const dx = b.x! + b.vx! - (a.x! + a.vx!), dy = b.y! + b.vy! - (a.y! + a.vy!);
      const ox = W - Math.abs(dx), oy = H - Math.abs(dy);
      if (ox <= 0 || oy <= 0) return;
      // Normalise by card shape so wide cards prefer to slide vertically past each other.
      if (ox / W < oy / H) {
        const s = (dx >= 0 ? 1 : -1) * ox * 0.5 * strength;
        a.vx! -= s; b.vx! += s;
      } else {
        const s = (dy >= 0 ? 1 : -1) * oy * 0.5 * strength;
        a.vy! -= s; b.vy! += s;
      }
    });
  };
  force.initialize = (ns: SimNode[]) => { nodes = ns; };
  return force;
}

/** Pull node with hop k toward the ellipse radius[k]·(rx, ry) along its current angle (impact view). */
function ellipseRings(rx: number, ry: number, radius: Map<number, number>, strength: number): Force<SimNode, undefined> {
  let nodes: SimNode[] = [];
  const force = (alpha: number) => {
    for (const n of nodes) {
      if (n.hop <= 0) continue;
      const a = Math.atan2(n.y! / ry, n.x! / rx), r = radius.get(n.hop) ?? n.hop;
      const tx = Math.cos(a) * rx * r, ty = Math.sin(a) * ry * r;
      n.vx! += (tx - n.x!) * strength * alpha;
      n.vy! += (ty - n.y!) * strength * alpha;
    }
  };
  force.initialize = (ns: SimNode[]) => { nodes = ns; };
  return force;
}

/** Hard overlap removal after the simulation (collision forces are soft). Deterministic. */
export function removeOverlaps(pos: Map<string, FVec>, w: number, h: number, pinned?: string) {
  const ids = [...pos.keys()], P = ids.map((id) => pos.get(id)!);
  const W = w + GAP_X * 0.6, H = h + GAP_Y * 0.6;
  for (let pass = 0; pass < 400; pass++) {
    // A pass that moves nothing saw every pair (positions were stable), so the result is clean.
    let moved = false;
    sweep(P.map((p) => p.x), W, (i, j) => {
      const a = P[i], b = P[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const ox = W - Math.abs(dx), oy = H - Math.abs(dy);
      if (ox <= 0 || oy <= 0) return;
      moved = true;
      const ka = ids[i] === pinned ? 0 : ids[j] === pinned ? 1 : 0.5, kb = 1 - ka;
      if (ox / W < oy / H) {
        const s = (dx >= 0 ? 1 : -1) * (ox + 0.5);
        a.x -= s * ka; b.x += s * kb;
      } else {
        const s = (dy >= 0 ? 1 : -1) * (oy + 0.5);
        a.y -= s * ka; b.y += s * kb;
      }
    });
    if (!moved) break;
  }
}

/** Order members so neighbours are adjacent in the initial spiral (BFS from the best-connected). */
function bfsOrder(ids: string[], adj: Map<string, string[]>): string[] {
  const inSet = new Set(ids), seen = new Set<string>(), out: string[] = [];
  const byDegree = [...ids].sort((a, b) => (adj.get(b)?.length ?? 0) - (adj.get(a)?.length ?? 0) || (a < b ? -1 : a > b ? 1 : 0));
  for (const root of byDegree) {
    if (seen.has(root)) continue;
    seen.add(root);
    const queue = [root];
    for (let i = 0; i < queue.length; i++) {
      out.push(queue[i]);
      for (const nb of adj.get(queue[i]) ?? []) if (inSet.has(nb) && !seen.has(nb)) { seen.add(nb); queue.push(nb); }
    }
  }
  return out;
}

export function forceLayout(nodes: FNode[], links: FLink[], opt: ForceOptions): Map<string, FVec> {
  const { w, h } = opt;
  const aspect = Math.min(2.6, Math.max(0.55, opt.aspect));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ids = new Set(byId.keys());
  const valid = links.filter((l) => ids.has(l.source) && ids.has(l.target) && l.source !== l.target);
  const adj = new Map<string, string[]>();
  for (const l of valid) {
    (adj.get(l.source) ?? adj.set(l.source, []).get(l.source)!).push(l.target);
    (adj.get(l.target) ?? adj.set(l.target, []).get(l.target)!).push(l.source);
  }

  // Area-based scale: total footprint of the cards plus clearance, spread over the target aspect.
  const cell = (w + GAP_X) * (h + GAP_Y);
  const span = Math.sqrt(nodes.length * cell * 2.4);
  const sx = span * Math.sqrt(aspect), sy = span / Math.sqrt(aspect);

  // Group anchors on an ellipse (first group on the left), unknown groups at the centre.
  const groups = (opt.groups ?? []).filter((g) => nodes.some((n) => n.group === g));
  const anchor = new Map<string, FVec>();
  groups.forEach((g, k) => {
    if (groups.length < 2) return void anchor.set(g, { x: 0, y: 0 });
    const t = Math.PI + (2 * Math.PI * k) / groups.length;
    anchor.set(g, { x: Math.cos(t) * sx * FORCE.anchorSpread, y: Math.sin(t) * sy * FORCE.anchorSpread });
  });
  const anchorOf = (n: FNode) => (n.group && anchor.get(n.group)) || { x: 0, y: 0 };

  // Initial positions: per anchor, a phyllotaxis spiral in BFS order, stretched to the aspect.
  const rings = opt.rings;
  const byAnchor = new Map<string, FNode[]>();
  for (const n of nodes) {
    const key = rings ? "_" : (n.group && anchor.has(n.group) ? n.group : "_");
    (byAnchor.get(key) ?? byAnchor.set(key, []).get(key)!).push(n);
  }
  const start = new Map<string, FVec>();
  const step = Math.sqrt(cell) * 0.9;
  for (const [, members] of byAnchor) {
    const order = bfsOrder(members.map((n) => n.id), adj);
    order.forEach((id, i) => {
      const r = step * Math.sqrt(i + 0.5), t = i * 2.399963229728653;
      const a = anchorOf(byId.get(id)!);
      start.set(id, { x: a.x + Math.cos(t) * r * Math.sqrt(aspect), y: a.y + Math.sin(t) * r / Math.sqrt(aspect) });
    });
  }
  // Impact rings: unit ellipse (rx, ry); ring k is scaled by radius[k], grown until its cards fit.
  const rx = w + 170, ry = rx / Math.max(1.25, aspect);
  const radius = new Map<number, number>([[0, 0]]);
  if (rings) {
    // Upstream nodes start on the left half, downstream on the right.
    const byHop = new Map<number, string[]>();
    for (const n of nodes) { const k = rings.get(n.id) ?? 1; (byHop.get(k) ?? byHop.set(k, []).get(k)!).push(n.id); }
    const perimeter = 2 * Math.PI * Math.sqrt((rx * rx + ry * ry) / 2), slot = (w + h) * 0.62 + GAP_X;
    for (let k = 1; k <= Math.max(0, ...byHop.keys()); k++) {
      radius.set(k, Math.max(radius.get(k - 1)! + 1, ((byHop.get(k)?.length ?? 0) * slot) / perimeter));
    }
    const angle = new Map<string, number>();
    const TAU = Math.PI * 2;
    for (const k of [...byHop.keys()].sort((a, b) => a - b)) {
      const list = byHop.get(k)!;
      if (k === 0) { list.forEach((id) => { start.set(id, { x: 0, y: 0 }); angle.set(id, 0); }); continue; }
      let sorted: string[];
      let offset = Math.PI / 2; // ring 1: top → left (upstream) → bottom → right (downstream)
      if (k === 1) {
        sorted = [...list].sort((a, b) => (opt.side?.get(a) ?? 0) - (opt.side?.get(b) ?? 0) || (a < b ? -1 : 1));
      } else {
        // Outer rings follow their inner-ring neighbours (circular mean), evenly spaced, rotated
        // to best match those preferred angles — keeps links short and radial.
        const pref = new Map(list.map((id) => {
          let sx = 0, sy = 0;
          for (const nb of adj.get(id) ?? []) { const a = angle.get(nb); if (a !== undefined && rings.get(nb) === k - 1) { sx += Math.cos(a); sy += Math.sin(a); } }
          return [id, sx || sy ? (Math.atan2(sy, sx) + TAU) % TAU : 0] as const;
        }));
        sorted = [...list].sort((a, b) => pref.get(a)! - pref.get(b)! || (a < b ? -1 : 1));
        let cx = 0, cy = 0;
        sorted.forEach((id, i) => { const d = pref.get(id)! - (TAU * (i + 0.5)) / sorted.length; cx += Math.cos(d); cy += Math.sin(d); });
        offset = Math.atan2(cy, cx);
      }
      sorted.forEach((id, i) => {
        const t = offset + (TAU * (i + 0.5)) / sorted.length;
        angle.set(id, t);
        start.set(id, { x: Math.cos(t) * rx * radius.get(k)!, y: -Math.sin(t) * ry * radius.get(k)! });
      });
    }
  }

  const sim: SimNode[] = nodes.map((n, i) => {
    const p = start.get(n.id)!, a = anchorOf(n);
    return { id: n.id, i, x: p.x, y: p.y, vx: 0, vy: 0, ax: rings ? 0 : a.x, ay: rings ? 0 : a.y, hop: rings?.get(n.id) ?? -1 };
  });
  const focus = opt.focus ? sim.find((n) => n.id === opt.focus) : undefined;
  if (focus) { focus.fx = 0; focus.fy = 0; }

  const degree = (id: string) => adj.get(id)?.length ?? 0;
  const ticks = opt.ticks ?? FORCE.ticks;
  const simulation = forceSimulation<SimNode>(sim)
    .stop()
    .alphaDecay(1 - Math.pow(0.001, 1 / ticks))
    .force("link", forceLink<SimNode, SimLink>(valid.map((l) => ({ source: l.source, target: l.target, strong: l.strong })))
      .id((d) => d.id)
      .distance((l) => {
        if (!rings) return (l.strong ? FORCE.strongFactor : 1) * FORCE.linkBase;
        // Impact: links span the gap between their rings, so they don't fight the ring force.
        const a = l.source as SimNode, b = l.target as SimNode;
        return Math.max(FORCE.linkBase, Math.abs((radius.get(a.hop) ?? 0) - (radius.get(b.hop) ?? 0)) * (rx + ry) / 2);
      })
      // d3 default strength (1 / min degree) keeps hubs from collapsing their leaves.
      .strength((l) => (rings ? 0.4 : 0.9) / Math.min(degree((l.source as SimNode).id), degree((l.target as SimNode).id)) + (l.strong ? 0.08 : 0)))
    .force("charge", repulse(FORCE.charge, FORCE.chargeRange))
    .force("collide", rectCollide(w, h, 0.85))
    // Weak anchor pull (ecosystem region) — stronger vertically so the drawing matches the aspect.
    .force("x", forceX<SimNode>((d) => d.ax).strength(rings ? 0.02 : FORCE.pull / Math.sqrt(aspect)))
    .force("y", forceY<SimNode>((d) => d.ay).strength(rings ? 0.02 : FORCE.pull * Math.sqrt(aspect)));
  if (rings) simulation.force("rings", ellipseRings(rx, ry, radius, 0.9));
  simulation.tick(ticks);

  const pos = new Map<string, FVec>();
  for (const n of sim) pos.set(n.id, { x: n.x! - w / 2, y: n.y! - h / 2 });
  // Forces settle into a roundish blob; nudge it toward the viewport shape (bounded squash of
  // the long axis — the overlap removal below then lets cards slide past each other).
  if (!rings && FORCE.aspectFit > 0) {
    const P = [...pos.values()];
    const bw = Math.max(...P.map((p) => p.x)) - Math.min(...P.map((p) => p.x)) + w;
    const bh = Math.max(...P.map((p) => p.y)) - Math.min(...P.map((p) => p.y)) + h;
    const ratio = bw / bh / aspect;
    const f = Math.max(1 - FORCE.aspectFit, Math.sqrt(ratio > 1 ? 1 / ratio : ratio));
    if (f < 0.98) for (const p of P) { if (ratio > 1) p.x *= f; else p.y *= f; }
  }
  removeOverlaps(pos, w, h, opt.focus);
  return pos;
}
