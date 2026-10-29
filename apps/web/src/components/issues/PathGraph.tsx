import Link from "next/link";
import { colLabel, type IssueGraph } from "@/lib/issues";

/** 이슈의 영향 그래프 (서버 SVG): 변화 → 1차 영향 → 2차 → … 단계별 열. 가중치가 높은 흐름만 그린다 —
 *  간선 굵기 = 경로 신뢰도(0~1), 가설 경로는 색, 그래프에 없는 고리는 점선. 기업 칸에 신뢰도를 적고, 리포트가 있으면 찬 색, 범위 밖이면 점선 테두리. */
const COL_W = 196, GAP = 46, NODE_W = 168, NODE_H = 30, ROW = 42, PAD_Y = 26;
const trunc = (s: string, n = 15) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
/** 색은 종류로: 병목·요구·기술·세대·표준 (c1) / 부품·소재·공정·장비·제품 (c2). 열은 단계. */
const KIND_A = new Set(["bottleneck", "requirement", "technology", "product_generation", "standard"]);

export function PathGraph({ g }: { g: IssueGraph }) {
  if (!g.nodes.length) return null;
  const ncol = Math.max(...g.nodes.map((n) => n.col)) + 1;
  const cols = Array.from({ length: ncol }, (_, c) => g.nodes.filter((n) => n.col === c));
  // 열 안의 순서: 앞 열에서 들어오는 간선의 평균 자리(barycenter) → 가중치. 교차를 줄인다.
  const rowOf = new Map<string, number>();
  cols.forEach((list, c) => {
    if (c > 0) {
      const bary = (id: string) => { const ins = g.edges.filter((e) => e.to === id && rowOf.has(e.from)).map((e) => rowOf.get(e.from)!); return ins.length ? ins.reduce((a, b) => a + b, 0) / ins.length : Number.POSITIVE_INFINITY; };
      list.sort((a, b) => bary(a.id) - bary(b.id) || b.weight - a.weight);
    }
    list.forEach((n, i) => rowOf.set(n.id, i));
  });
  const rows = Math.max(...cols.map((c) => c.length), 1);
  const H = PAD_Y * 2 + rows * ROW;
  const W = ncol * COL_W + (ncol - 1) * GAP;
  const pos = new Map<string, { x: number; y: number }>();
  cols.forEach((list, c) => {
    const top = PAD_Y + ((rows - list.length) * ROW) / 2;
    list.forEach((n, i) => pos.set(n.id, { x: c * (COL_W + GAP) + (COL_W - NODE_W) / 2, y: top + i * ROW }));
  });
  const edge = (a: string, b: string) => {
    const A = pos.get(a), B = pos.get(b);
    if (!A || !B) return null;
    const left = A.x <= B.x ? A : B, right = A.x <= B.x ? B : A;
    const x1 = left.x + NODE_W, y1 = left.y + NODE_H / 2, x2 = right.x, y2 = right.y + NODE_H / 2;
    if (x2 - x1 < 10) { const x = Math.max(A.x, B.x) + NODE_W + 14; return `M ${x1} ${y1} C ${x} ${y1}, ${x} ${y2}, ${x1} ${y2}`; }
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
  };
  const sorted = [...g.edges].sort((a, b) => Number(a.onPath) - Number(b.onPath) || a.weight - b.weight);  // 굵은 것·가설이 위로
  return <figure className="pg">
    <div className="pg-cols" style={{ gridTemplateColumns: `repeat(${ncol}, 1fr)` }}>{cols.map((_, i) => <span key={i}>{colLabel(i)}</span>)}</div>
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="이슈의 영향 경로 — 가중치가 높은 흐름" style={{ height: "auto" }}>
      <g>{sorted.map((e) => { const d = edge(e.from, e.to); return d ? <path key={`${e.from}>${e.to}`} d={d} className={`pg-e${e.onPath ? " on" : ""}${e.inferred ? " inf" : ""}`}
        style={{ strokeWidth: 0.8 + 3.2 * e.weight, opacity: e.onPath ? 1 : 0.35 + 0.65 * e.weight }}><title>{`신뢰도 ${e.weight.toFixed(2)}${e.inferred ? " · 추론 (그래프에 없는 고리)" : ""}`}</title></path> : null; })}</g>
      <g>{g.nodes.map((n) => {
        const p = pos.get(n.id)!;
        const cls = ["pg-n", n.tagged ? "c0" : n.company ? "c3" : KIND_A.has(n.kind) ? "c1" : "c2", n.onPath ? "on" : "", n.company ? (n.company.ideaKey ? "rep" : n.company.inScope ? "co" : "out") : ""].filter(Boolean).join(" ");
        const href = n.company?.ideaKey ? `/ideas/${n.company.ideaKey}` : n.company ? `/companies/${n.id.replace(/^company:/, "")}` : `/map?focus=${encodeURIComponent(n.id)}`;
        const conf = n.company ? n.company.confidence.toFixed(2) : null;
        return <Link key={n.id} href={href} className={cls}>
          <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={n.company ? 15 : 7}/>
          <text x={p.x + (conf ? 12 : NODE_W / 2)} y={p.y + NODE_H / 2 + 4.5} textAnchor={conf ? "start" : "middle"}>{n.company?.direction === "negative" ? "− " : ""}{trunc(n.label, conf ? 12 : 15)}</text>
          {conf ? <text x={p.x + NODE_W - 10} y={p.y + NODE_H / 2 + 4.5} textAnchor="end" className="pg-w">{conf}</text> : null}
          <title>{n.label}{n.company?.ticker ? ` (${n.company.ticker})` : ""}{conf ? ` · 신뢰도 ${conf}` : ""}{n.company?.ideaKey ? " · 리포트 보기" : n.company ? " · 기업 페이지" : ""}</title>
        </Link>;
      })}</g>
    </svg>
    <figcaption>굵기 = 경로 신뢰도(간선 근거 등급의 곱), 색 = 가설 경로, 점선 = 그래프에 없는 추론 고리{g.dropped ? ` · 신뢰도 낮은 경로 ${g.dropped}개는 뺐습니다` : ""}</figcaption>
  </figure>;
}
