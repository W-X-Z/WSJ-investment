"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { OppHistory, PricePoint } from "@/lib/opportunities";

/** 아이디어 상세의 주가 차트. 히스토리 항목마다 번호 점을 찍고, 점을 누르면 그 항목으로 내려간다 (사용자 2026-11-04). */
const W = 960, H = 320, PAD = { l: 48, r: 16, t: 18, b: 30 };

function fmtPx(v: number) { return v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toFixed(v >= 100 ? 1 : 2); }
function fmtDay(d: string) { return `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`; }

export function IdeaChart({ prices, history, name }: { prices: PricePoint[]; history: OppHistory[]; name: string }) {
  const [active, setActive] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const m = useMemo(() => {
    if (prices.length < 2) return null;
    const xs = prices.map((p) => Date.parse(p.d)), ys = prices.map((p) => p.c);
    const x0 = xs[0], x1 = xs[xs.length - 1];
    const lo = Math.min(...ys), hi = Math.max(...ys);
    const y0 = lo - (hi - lo) * 0.08, y1 = hi + (hi - lo) * 0.14;
    const X = (t: number) => PAD.l + ((t - x0) / Math.max(1, x1 - x0)) * (W - PAD.l - PAD.r);
    const Y = (v: number) => PAD.t + (1 - (v - y0) / Math.max(1e-9, y1 - y0)) * (H - PAD.t - PAD.b);
    const path = prices.map((p, i) => `${i ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(p.c).toFixed(1)}`).join(" ");
    const area = `${path} L${X(x1).toFixed(1)},${(H - PAD.b).toFixed(1)} L${X(x0).toFixed(1)},${(H - PAD.b).toFixed(1)} Z`;
    // 히스토리 → 가장 가까운 거래일. 차트 범위 밖(옛 사건)은 왼쪽 끝에 모아 둔다.
    const marks = history.map((h, i) => {
      const t = Date.parse(h.date);
      let k = 0, best = Infinity;
      xs.forEach((x, j) => { const d = Math.abs(x - t); if (d < best) { best = d; k = j; } });
      return { i, h, x: X(Math.max(x0, Math.min(x1, t))), y: Y(prices[k].c), px: prices[k].c, outside: t < x0 - 864e5 * 3 };
    });
    // 같은 자리에 겹치는 번호는 조금씩 밀어 올린다
    const sorted = [...marks].sort((a, b) => a.x - b.x);
    for (let j = 1; j < sorted.length; j++) {
      const a = sorted[j - 1], b = sorted[j];
      if (Math.abs(a.x - b.x) < 22 && Math.abs(a.y - b.y) < 22) b.y = a.y - 24;
    }
    const ticks: { x: number; label: string }[] = [];
    let last = "";
    prices.forEach((p, i) => { const ym = p.d.slice(0, 7); if (ym !== last) { last = ym; if (i) ticks.push({ x: X(xs[i]), label: `${Number(ym.slice(5))}월` }); } });
    const yt = [lo, (lo + hi) / 2, hi].map((v) => ({ y: Y(v), label: fmtPx(v) }));
    const first = prices[0].c, lastPx = prices[prices.length - 1].c;
    return { path, area, marks, ticks, yt, hi, lo, first, lastPx, from: prices[0].d, to: prices[prices.length - 1].d };
  }, [prices, history]);

  useEffect(() => {
    if (active == null) return;
    const el = document.getElementById(`hist-${active}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("hist-flash");
    const t = setTimeout(() => el.classList.remove("hist-flash"), 1600);
    return () => clearTimeout(t);
  }, [active]);

  if (!m) return null;
  const chg = (m.lastPx / m.hi - 1) * 100;
  const shown = hover ?? active;
  return (
    <figure className="op-chart">
      <figcaption>
        <b>{name}</b> 종가 · {fmtDay(m.from)}~{fmtDay(m.to)} · 고점 {fmtPx(m.hi)} → {fmtPx(m.lastPx)} <span className={chg < 0 ? "dn" : "up"}>({chg > 0 ? "+" : ""}{chg.toFixed(0)}%)</span>
        <small>번호를 누르면 아래 그 이슈로 갑니다</small>
      </figcaption>
      <div className="op-chart-scroll"><svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${name} 주가와 이슈`}>
        {m.yt.map((t, i) => <g key={i}><line x1={PAD.l} x2={W - PAD.r} y1={t.y} y2={t.y} className="grid"/><text x={PAD.l - 6} y={t.y + 4} textAnchor="end" className="tick">{t.label}</text></g>)}
        {m.ticks.map((t, i) => <text key={i} x={t.x} y={H - 10} textAnchor="middle" className="tick">{t.label}</text>)}
        <path d={m.area} className="area"/>
        <path d={m.path} className="line"/>
        {m.marks.map((k) => <g key={k.i} className={`mark ${shown === k.i ? "mark-on" : ""}`} onClick={() => setActive(k.i)}
            onMouseEnter={() => setHover(k.i)} onMouseLeave={() => setHover(null)} role="button" tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActive(k.i); } }}>
          <circle cx={k.x} cy={k.y} r={13}/>
          <text x={k.x} y={k.y + 4} textAnchor="middle">{k.i + 1}</text>
        </g>)}
        {shown != null && m.marks[shown] ? (() => { const k = m.marks[shown]; const left = k.x > W * 0.6; return (
          <g className="tip" transform={`translate(${left ? k.x - 12 : k.x + 12},${Math.max(PAD.t + 14, k.y - 30)})`}>
            <text textAnchor={left ? "end" : "start"}><tspan className="tip-d">{k.h.date} · {fmtPx(k.px)}</tspan><tspan x="0" dy="16">{k.h.title.length > 46 ? k.h.title.slice(0, 45) + "…" : k.h.title}</tspan></text>
          </g>); })() : null}
      </svg></div>
    </figure>
  );
}
