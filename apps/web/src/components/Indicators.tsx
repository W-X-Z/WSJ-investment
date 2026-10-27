import Link from "next/link";
import { indicatorMove, nodeName, type IndicatorPoint, type IndicatorRecord } from "@/lib/research";

const fmtNum = (v: number, cat: string) =>
  cat === "tw_revenue" ? `${(v / 1e5).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억 NT$`
  : v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toLocaleString("en-US", { maximumFractionDigits: 3 });

export function Pct({ v, label }: { v: number | null; label?: string }) {
  if (v == null || Number.isNaN(v)) return <span className="ind-pct">–</span>;
  const cls = v > 0.05 ? "ind-pct up" : v < -0.05 ? "ind-pct down" : "ind-pct";
  return <span className={cls}>{label ? <small>{label}</small> : null}{v > 0 ? "+" : ""}{v.toFixed(1)}%</span>;
}

export function Sparkline({ points, w = 110, h = 28 }: { points: IndicatorPoint[] | undefined; w?: number; h?: number }) {
  const pts = (points ?? []).slice(-60);
  if (pts.length < 2) return <svg width={w} height={h} aria-hidden="true" className="ind-spark ind-spark-empty"><line x1="0" y1={h / 2} x2={w} y2={h / 2}/></svg>;
  const vs = pts.map((p) => p.value);
  const lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const d = pts.map((p, i) => `${(i / (pts.length - 1)) * w},${h - 3 - ((p.value - lo) / span) * (h - 6)}`).join(" ");
  const up = vs[vs.length - 1] >= vs[0];
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" className={`ind-spark ${up ? "up" : "down"}`}><polyline points={d}/></svg>;
}

export function IndicatorTable({ rows, points }: { rows: IndicatorRecord[]; points: Record<string, IndicatorPoint[]> }) {
  return <div className="ind-table" role="table">
    <div className="ind-row ind-head" role="row"><span>지표</span><span>최신</span><span>변화</span><span>추이</span><span>연결 노드</span></div>
    {rows.map((r) => {
      const mv = indicatorMove(r);
      const second = r.category === "tw_revenue" || r.category === "ppi" || r.category === "commodity" ? { v: r.change_pct, l: "전월" } : r.value_1m ? { v: (r.value / r.value_1m - 1) * 100, l: "1개월" } : null;
      return <div className="ind-row" role="row" key={r.indicator_id}>
        <span className="ind-name"><strong>{r.label}</strong><small>{r.note ? `${r.note} · ` : ""}{r.source_url ? <a href={r.source_url} target="_blank" rel="noreferrer">{r.source}</a> : r.source}</small></span>
        <span className="ind-val"><strong>{fmtNum(r.value, r.category)}</strong><small>{r.unit && r.category !== "tw_revenue" ? `${r.unit} · ` : ""}{r.frequency === "monthly" ? r.as_of.slice(0, 7) : r.as_of}</small></span>
        <span className="ind-moves"><Pct v={mv.pct} label={mv.label}/>{second && <Pct v={second.v} label={second.l}/>}</span>
        <span><Sparkline points={points[r.indicator_id]}/></span>
        <span className="ind-nodes">{r.nodes.slice(0, 3).map((n) => <Link key={n} href={`/map?focus=${encodeURIComponent(n)}`}>{nodeName(n)}</Link>)}</span>
      </div>;
    })}
  </div>;
}

/** 홈용: 변화가 큰 지표 상위 n개 */
export function IndicatorMovers({ rows, points, n = 6 }: { rows: IndicatorRecord[]; points: Record<string, IndicatorPoint[]>; n?: number }) {
  const top = [...rows].map((r) => ({ r, mv: indicatorMove(r) })).filter((x) => x.mv.pct != null)
    .sort((a, b) => Math.abs(b.mv.pct ?? 0) - Math.abs(a.mv.pct ?? 0)).slice(0, n);
  if (!top.length) return null;
  return <div className="ind-movers">{top.map(({ r, mv }) => <Link key={r.indicator_id} href={`/indicators#${encodeURIComponent(r.indicator_id)}`} className="ind-mover">
    <span className="ind-mover-label">{r.label}</span>
    <span className="ind-mover-row"><strong>{fmtNum(r.value, r.category)}</strong><Pct v={mv.pct} label={mv.label}/></span>
    <Sparkline points={points[r.indicator_id]} w={150} h={26}/>
  </Link>)}</div>;
}
