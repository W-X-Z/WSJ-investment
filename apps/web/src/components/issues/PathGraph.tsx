import Link from "next/link";
import { COL_LABEL, type IssueGraph } from "@/lib/issues";

/** 이슈의 온톨로지 그래프 (서버 SVG, 스크립트 없음): 네 열 — 변화 → 병목·기술 → 부품·공정·장비 → 기업.
 *  가설 경로의 간선은 굵은 색, 그래프에 없는 고리는 점선. 기업은 리포트가 있으면 찬 색, 범위 밖이면 점선 테두리. 노드를 누르면 그래프 탐색 또는 리포트로. */
const COL_W = 196, GAP = 46, NODE_W = 168, NODE_H = 30, ROW = 42, PAD_Y = 28;
const trunc = (s: string, n = 15) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export function PathGraph({ g }: { g: IssueGraph }) {
  if (!g.nodes.length) return null;
  const cols = [0, 1, 2, 3].map((c) => g.nodes.filter((n) => n.col === c));
  const rows = Math.max(...cols.map((c) => c.length), 1);
  const H = PAD_Y * 2 + rows * ROW;
  const W = 4 * COL_W + 3 * GAP;
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
    if (x2 - x1 < 10) {  // 같은 열끼리는 오른쪽으로 돌아 나간다
      const x = Math.max(A.x, B.x) + NODE_W + 14;
      return `M ${x1} ${y1} C ${x} ${y1}, ${x} ${y2}, ${x1} ${y2}`;
    }
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
  };
  return <figure className="pg">
    <div className="pg-cols">{COL_LABEL.map((l, i) => <span key={l} className={cols[i].length ? "" : "empty"}>{l}</span>)}</div>
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="이슈의 공급망 영향 경로 그래프" style={{ height: "auto" }}>
      <g className="pg-edges">
        {g.edges.filter((e) => !e.onPath).map((e) => { const d = edge(e.from, e.to); return d ? <path key={`${e.from}>${e.to}`} d={d} className="pg-e"><title>{e.relation}</title></path> : null; })}
        {g.edges.filter((e) => e.onPath).map((e) => { const d = edge(e.from, e.to); return d ? <path key={`p${e.from}>${e.to}`} d={d} className={`pg-e on${e.inferred ? " inf" : ""}`}><title>{e.inferred ? "추론 (그래프에 없는 고리)" : e.relation}</title></path> : null; })}
      </g>
      <g className="pg-nodes">
        {g.nodes.map((n) => {
          const p = pos.get(n.id)!;
          const cls = ["pg-n", `c${n.col}`, n.onPath ? "on" : "", n.tagged ? "tag" : "", n.company ? (n.company.ideaKey ? "rep" : n.company.inScope ? "co" : "out") : ""].filter(Boolean).join(" ");
          const href = n.company?.ideaKey ? `/ideas/${n.company.ideaKey}` : `/map?focus=${encodeURIComponent(n.id)}`;
          return <Link key={n.id} href={href} className={cls}>
            <rect x={p.x} y={p.y} width={NODE_W} height={NODE_H} rx={n.company ? 15 : 7}/>
            <text x={p.x + NODE_W / 2} y={p.y + NODE_H / 2 + 4.5} textAnchor="middle">{trunc(n.label)}</text>
            <title>{n.label}{n.company?.ticker ? ` (${n.company.ticker})` : ""}{n.company?.ideaKey ? " — 리포트 보기" : ""}</title>
          </Link>;
        })}
      </g>
    </svg>
    {g.truncated ? <figcaption>이웃이 많은 노드는 일부만 그렸습니다 — 전체는 공급망 그래프에서</figcaption> : null}
  </figure>;
}
