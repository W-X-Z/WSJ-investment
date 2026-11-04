"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { OppHistory, OppHistoryKind, PricePoint } from "@/lib/opportunities";
import { Prose } from "@/components/opps/Prose";

/** 주가 차트 + 날짜별 히스토리를 한 덩어리로 (사용자 2026-11-04).
 *  - 점 = 히스토리 항목. 종류별 색, 누르면 그 항목으로 간다.
 *  - 히스토리를 스크롤하면 지금 보는 항목의 점이 켜진다 (데스크톱에선 차트가 위에 고정).
 *  - 그날의 주가 반응은 글이 아니라 가격 데이터로 계산한다. */

export const KIND: Record<Exclude<OppHistoryKind, "ours">, { label: string; cls: string }> = {
  earnings: { label: "실적", cls: "k-earn" },
  deal: { label: "계약·수주", cls: "k-deal" },
  filing: { label: "공시·자본", cls: "k-file" },
  flow: { label: "수급·주가", cls: "k-flow" },
  external: { label: "업계·외부", cls: "k-ext" },
};
type Kind = keyof typeof KIND;

/** kind 가 없는 옛 항목은 제목으로 가늠한다. */
function guessKind(h: OppHistory): Kind | "ours" {
  if (h.kind) return h.kind as Kind | "ours";
  const t = h.title;
  if (/아이디어|★|검토|재검수|리포트 작성/.test(t)) return "ours";
  if (/실적|분기|매출 \$|매출 [0-9]|가이던스|FY\d+ ?\d?Q|[1-4]Q\d{2}/.test(t)) return "earnings";
  if (/계약|수주|주문|협약|MOU|선급|LTA/i.test(t)) return "deal";
  if (/증자|매각|상장|공모|8-K|CFO|사임|주총|공시|ATM|Form 4/i.test(t)) return "filing";
  if (/고점|저점|급락|하락|조정|−\d+%|-\d+%/.test(t)) return "flow";
  return "external";
}

const PAD = { l: 44, r: 62, t: 22, b: 26 };
const fmtPx = (v: number) => (v >= 1000 ? Math.round(v).toLocaleString("en-US") : v.toFixed(v >= 100 ? 1 : 2));
const md = (d: string) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

type Item = OppHistory & { n: number; kind: Kind; move: number | null; moveDay: "d0" | "d1" | null };

export function IdeaTimeline({ prices, history, name }: { prices: PricePoint[]; history: OppHistory[]; name: string }) {
  const items: Item[] = useMemo(() => {
    const idx = (d: string) => prices.findIndex((p) => p.d >= d);
    let n = 0;
    return history.flatMap((h) => {
      const k = guessKind(h);
      if (k === "ours") return [];
      n += 1;
      let move: number | null = null, moveDay: Item["moveDay"] = null;
      const i = idx(h.date);
      if (i > 0) {
        const d0 = prices[i].c / prices[i - 1].c - 1;
        const d1 = i + 1 < prices.length ? prices[i + 1].c / prices[i].c - 1 : 0;
        // 장 마감 뒤 발표는 다음 날 반응한다 — 더 큰 쪽을 보이고 어느 날인지 표시
        if (Math.abs(d1) > Math.abs(d0) * 1.5 && Math.abs(d1) >= 0.04) { move = d1 * 100; moveDay = "d1"; } else { move = d0 * 100; moveDay = "d0"; }
      }
      return [{ ...h, n, kind: k, move, moveDay }];
    });
  }, [history, prices]);

  const [active, setActive] = useState<number | null>(null);   // 스크롤로 보고 있는 항목
  const [hover, setHover] = useState<number | null>(null);
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const listRef = useRef<HTMLOListElement>(null);
  // 차트는 실제 폭으로 그린다 — 글자가 화면 크기에 맞게 남도록 (폰에서 viewBox 축소로 글자가 깨알이 되지 않게)
  const figRef = useRef<HTMLElement>(null);
  const [W, setW] = useState(900);
  useEffect(() => {
    const el = figRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(300, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = W < 560 ? 210 : 290;

  // 스크롤 따라 점 켜기
  useEffect(() => {
    const els = listRef.current?.querySelectorAll<HTMLElement>("[data-n]");
    if (!els?.length) return;
    const io = new IntersectionObserver((ents) => {
      const vis = ents.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (vis[0]) setActive(Number((vis[0].target as HTMLElement).dataset.n));
    }, { rootMargin: "-58% 0px -32% 0px" });   // 위에 고정된 차트 아래쪽 띠
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [items.length]);

  function jump(n: number) {
    const el = document.getElementById(`hist-${n}`);
    if (!el) return;
    setOpen((o) => ({ ...o, [n]: true }));
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("hist-flash");
    setTimeout(() => el.classList.remove("hist-flash"), 1500);
  }

  const m = useMemo(() => {
    if (prices.length < 2) return null;
    const xs = prices.map((p) => Date.parse(p.d)), ys = prices.map((p) => p.c);
    const x0 = xs[0], x1 = xs[xs.length - 1];
    const lo = Math.min(...ys), hi = Math.max(...ys);
    const y0 = lo - (hi - lo) * 0.06, y1 = hi + (hi - lo) * 0.18;
    const X = (t: number) => PAD.l + ((t - x0) / Math.max(1, x1 - x0)) * (W - PAD.l - PAD.r);
    const Y = (v: number) => PAD.t + (1 - (v - y0) / Math.max(1e-9, y1 - y0)) * (H - PAD.t - PAD.b);
    const path = prices.map((p, i) => `${i ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(p.c).toFixed(1)}`).join(" ");
    const area = `${path} L${X(x1).toFixed(1)},${H - PAD.b} L${X(x0).toFixed(1)},${H - PAD.b} Z`;
    const hiI = ys.indexOf(hi);
    const marks = items.map((it) => {
      const t = Math.max(x0, Math.min(x1, Date.parse(it.date)));
      let k = 0, best = Infinity;
      xs.forEach((x, j) => { const d = Math.abs(x - t); if (d < best) { best = d; k = j; } });
      return { n: it.n, kind: it.kind, x: X(t), y: Y(prices[k].c), fy: Y(prices[k].c) };
    });
    // 가까운 점은 위로 쌓는다 (점 위치는 선 위에 두고 깃발만 올린다)
    const byX = [...marks].sort((a, b) => a.x - b.x);
    for (let j = 1; j < byX.length; j++) {
      const a = byX[j - 1], b = byX[j];
      const gap = W < 560 ? 20 : 24;   // 깃발 지름 + 여백
      if (Math.abs(a.x - b.x) < gap && Math.abs(a.fy - b.fy) < gap) b.fy = Math.min(b.fy, a.fy - gap);
    }
    const ticks: { x: number; label: string }[] = [];
    let last = "";
    const every = W < 560 ? 2 : 1;
    let mi = 0;
    prices.forEach((p, i) => { const ym = p.d.slice(0, 7); if (ym !== last) { last = ym; if (i && mi++ % every === 0) ticks.push({ x: X(xs[i]), label: `${Number(ym.slice(5))}월` }); } });
    const lastPx = ys[ys.length - 1];
    return { path, area, marks, ticks, hi, lo, lastPx, lastY: Y(lastPx), hiX: X(xs[hiI]), hiY: Y(hi), from: prices[0].d, to: prices[prices.length - 1].d, yt: [lo, (lo + hi) / 2, hi].map((v) => ({ y: Y(v), v })) };
  }, [prices, items, W, H]);

  const on = hover ?? active;
  const onItem = items.find((i) => i.n === on);
  const used = [...new Set(items.map((i) => i.kind))];

  return <section className="tl" aria-label="주가와 히스토리">
    {m ? <figure className="tl-chart" ref={figRef}>
      <figcaption>
        <span className="tl-name">{name}</span>
        <span className="tl-range">{m.from.slice(0, 4) !== m.to.slice(0, 4) ? `${m.from.slice(2, 4)}.${md(m.from)}` : md(m.from)}~{md(m.to)} 종가</span>
        <span className="tl-legend">{used.map((k) => <span key={k} className={`tl-key ${KIND[k].cls}`}><i/>{KIND[k].label}</span>)}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${name} 주가와 이슈`}>
        {m.yt.map((t, i) => <g key={i}><line x1={PAD.l} x2={W - PAD.r} y1={t.y} y2={t.y} className="grid"/><text x={PAD.l - 8} y={t.y + 4} textAnchor="end" className="tick">{fmtPx(t.v)}</text></g>)}
        {m.ticks.map((t, i) => <text key={i} x={t.x} y={H - 8} textAnchor="middle" className="tick">{t.label}</text>)}
        <path d={m.area} className="area"/>
        <path d={m.path} className="line"/>
        <line x1={PAD.l} x2={W - PAD.r} y1={m.lastY} y2={m.lastY} className="now"/>
        <g className="now-tag" transform={`translate(${W - PAD.r + 4},${m.lastY})`}><rect x="0" y="-11" width="58" height="22" rx="5"/><text x="29" y="4" textAnchor="middle">{fmtPx(m.lastPx)}</text></g>
        <text x={Math.min(m.hiX + 16, W - PAD.r - 4)} y={m.hiY + 4} textAnchor={m.hiX + 80 > W - PAD.r ? "end" : "start"} className="hi">고점 {fmtPx(m.hi)}</text>
        {m.marks.map((k) => {
          const isOn = on === k.n;
          return <g key={k.n} className={`mk ${KIND[k.kind].cls} ${isOn ? "mk-on" : ""} ${on != null && !isOn ? "mk-dim" : ""}`}
            onClick={() => jump(k.n)} onMouseEnter={() => setHover(k.n)} onMouseLeave={() => setHover(null)}
            role="button" tabIndex={0} aria-label={`${k.n}번 이슈로 이동`}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); jump(k.n); } }}>
            {k.fy < k.y - 1 ? <line x1={k.x} x2={k.x} y1={k.y} y2={k.fy} className="stem"/> : null}
            <circle cx={k.x} cy={k.y} r={3} className="dot"/>
            <circle cx={k.x} cy={k.fy} r={(W < 560 ? 9 : 11) + (isOn ? 2 : 0)} className="flag"/>
            <text x={k.x} y={k.fy + 4} textAnchor="middle">{k.n}</text>
          </g>;
        })}
      </svg>
      <div className="tl-now" aria-live="polite">
        {onItem ? <><b className={`tl-chip ${KIND[onItem.kind].cls}`}>{onItem.n}</b><span className="tl-now-d">{onItem.date.replace(/-/g, ".")}</span><span className="tl-now-t">{onItem.title}</span></>
          : <span className="tl-now-hint">번호를 누르면 그 이슈로 갑니다 · 아래 목록을 내리면 점이 따라 켜집니다</span>}
      </div>
    </figure> : null}

    <ol className="tl-list" ref={listRef}>
      {items.map((it) => {
        const long = (it.body?.length ?? 0) > 160;
        const isOpen = open[it.n] || !long;
        return <li key={it.n} id={`hist-${it.n}`} data-n={it.n} className={on === it.n ? "tl-on" : undefined}>
          <button className={`tl-n ${KIND[it.kind].cls}`} onClick={() => jump(it.n)} aria-label={`${it.n}번`}>{it.n}</button>
          <div className="tl-body">
            <div className="tl-meta">
              <time dateTime={it.date}>{it.date.replace(/-/g, ".")}</time>
              <span className={`tl-kind ${KIND[it.kind].cls}`}>{KIND[it.kind].label}</span>
              {it.move != null && Math.abs(it.move) >= 0.5 ? <span className={`tl-move ${it.move < 0 ? "dn" : "up"}`} title={it.moveDay === "d1" ? "다음 거래일 종가 변화" : "당일 종가 변화"}>
                {pct(it.move)}{it.moveDay === "d1" ? <small> 다음날</small> : null}</span> : null}
            </div>
            <h3>{it.url ? <a href={it.url} target="_blank" rel="noreferrer">{it.title}</a> : it.title}</h3>
            {it.body ? <div className={`tl-text ${isOpen ? "" : "tl-clamp"}`}><Prose text={it.body}/></div> : null}
            {it.body && long ? <button className="tl-more" onClick={() => setOpen((o) => ({ ...o, [it.n]: !o[it.n] }))}>{isOpen ? "접기" : "자세히"}</button> : null}
          </div>
        </li>;
      })}
    </ol>
  </section>;
}
