import Link from "next/link";
import discovery from "@/data/discovery.json";
import { db } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const metadata = { title: "공급사 발굴" };

type Node = { id: string; label: string; queries: string[] };
type Company = { cik: number; ticker: string | null; name: string; size_band: string; public_float: number | null; sic: number | null; score: number; node_count: number; promoted: boolean; nodes: Node[]; filing: { form: string; date: string } | null };
type NodeView = { label: string | null; companies_total: number; companies_small: number; small: { cik: number; ticker: string | null; name: string; public_float: number | null; score: number }[] };
type Data = { as_of: string; window_start: string; summary: Record<string, unknown>; nodes: Record<string, NodeView>; companies: Company[] };
const data = discovery as unknown as Data;
type MoatRow = { id: number; cik: number; title: string | null; scores: { overall?: number; moat?: number; timing?: number; financial?: number; data_quality?: number } | null; status: string; as_of: string };

const BAND: Record<string, string> = { micro: "마이크로", small: "소형", mid: "중형", unknown: "미상(20-F 등)" };
const fmtUsd = (v: number | null) => (v === null ? "–" : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`);

export default async function Discovery({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const band = (Array.isArray(sp.band) ? sp.band[0] : sp.band) ?? "";
  const onlyPromoted = (Array.isArray(sp.promoted) ? sp.promoted[0] : sp.promoted) === "1";
  let moats: MoatRow[] = [];
  try {
    const { data: rows } = await db("public").from("v_briefs").select("id,cik,title,scores,status,as_of").eq("kind", "moat").eq("status", "final").order("created_at", { ascending: false });
    moats = (rows ?? []) as MoatRow[];
  } catch { /* 읽기 실패 시 카드 없이 렌더 */ }
  const latestMoat = new Map<number, MoatRow>();
  for (const m of moats) if (!latestMoat.has(m.cik)) latestMoat.set(m.cik, m);
  const rows = data.companies.filter((c) => (!band || c.size_band === band) && (!onlyPromoted || c.promoted));
  const nodesWithSmall = Object.entries(data.nodes).filter(([, v]) => v.companies_small > 0).sort((a, b) => b[1].companies_small - a[1].companies_small);
  const nodesWithout = Object.entries(data.nodes).filter(([, v]) => v.companies_small === 0);

  return (
    <div>
      <div className="page-head"><div><div className="page-kicker">SUPPLY-CHAIN DISCOVERY</div><h1>병목별 소형 공급사 발굴</h1>
        <p>온톨로지 노드 {Object.keys(data.nodes).length}개의 구문을 10-K/20-F 본문({data.window_start} ~ {data.as_of})에서 검색. 승격(그래프 편입)은 사람이 결정하고, 해자 카드는 승격된 회사에만 만든다.</p></div>
        <div className="tag-row">
          <Link className={`tag ${!band ? "tag-active" : ""}`} href="/discovery">전체 {data.companies.length}</Link>
          {(["micro", "small", "mid", "unknown"] as const).map((b) => <Link key={b} className={`tag ${band === b ? "tag-active" : ""}`} href={`/discovery?band=${b}`}>{BAND[b]} {data.companies.filter((c) => c.size_band === b).length}</Link>)}
          <Link className={`tag ${onlyPromoted ? "tag-active" : ""}`} href="/discovery?promoted=1">승격됨 {data.companies.filter((c) => c.promoted).length}</Link>
        </div></div>

      <div className="dashboard-dual">
        <section>
          <h2 style={{ fontSize: 14, margin: "0 0 10px" }}>소형사가 존재하는 병목 ({nodesWithSmall.length})</h2>
          <div className="surface" style={{ padding: "4px 16px" }}>
            {nodesWithSmall.map(([id, v]) => <div key={id} style={{ padding: "10px 0", borderBottom: "1px solid #edf0f6" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}><Link href={`/map?focus=${id}`} style={{ fontWeight: 650, fontSize: 12 }}>{v.label ?? id}</Link><span className="soft-text">소형 {v.companies_small} / 전체 {v.companies_total}</span></div>
              <div style={{ fontSize: 11, color: "#4a5a70", marginTop: 3 }}>{v.small.map((s) => s.ticker ?? s.name).join(" · ")}</div>
            </div>)}
          </div>
        </section>
        <section>
          <h2 style={{ fontSize: 14, margin: "0 0 10px" }}>소형사가 없는 병목 ({nodesWithout.length}) — 대형사 영역 또는 미발굴</h2>
          <div className="surface" style={{ padding: "12px 16px", fontSize: 11, color: "#6f7d90", lineHeight: 1.9 }}>{nodesWithout.map(([id, v]) => v.label ?? id).join(" · ")}</div>
        </section>
      </div>

      <h2 style={{ fontSize: 14, margin: "24px 0 10px" }}>후보 회사 ({rows.length})</h2>
      <div className="surface" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
          <thead><tr style={{ textAlign: "left", color: "#6f7d90", fontSize: 11 }}><th style={{ padding: "10px 12px" }}>티커</th><th>회사</th><th>규모</th><th>공개유동</th><th>특정성 점수</th><th>매칭 노드</th><th>해자 카드</th></tr></thead>
          <tbody>{rows.map((c) => { const m = latestMoat.get(c.cik); return (
            <tr key={c.cik} style={{ borderTop: "1px solid #edf0f6", verticalAlign: "top" }}>
              <td style={{ padding: "9px 12px", fontFamily: "ui-monospace, monospace" }}>{c.ticker ?? "–"}{c.promoted && <span title="그래프에 승격" style={{ marginLeft: 6, color: "#2f9e6a" }}>●</span>}</td>
              <td style={{ padding: "9px 6px" }}>{c.name}<div className="soft-text" style={{ fontSize: 10 }}>SIC {c.sic ?? "–"} · {c.filing?.form} {c.filing?.date}</div></td>
              <td style={{ padding: "9px 6px" }}>{BAND[c.size_band] ?? c.size_band}</td>
              <td style={{ padding: "9px 6px", fontFamily: "ui-monospace, monospace" }}>{fmtUsd(c.public_float)}</td>
              <td style={{ padding: "9px 6px", fontFamily: "ui-monospace, monospace" }}>{c.score.toFixed(2)}</td>
              <td style={{ padding: "9px 6px" }}>{c.nodes.slice(0, 4).map((n) => <Link key={n.id} href={`/map?focus=${n.id}`} className="tag" style={{ marginRight: 4, marginBottom: 3 }} title={n.queries.join(", ")}>{n.label}</Link>)}{c.nodes.length > 4 && <span className="soft-text">+{c.nodes.length - 4}</span>}</td>
              <td style={{ padding: "9px 6px" }}>{m ? <Link href={`/briefs/${m.id}`}>종합 {m.scores?.overall ?? "–"}/5 · 해자 {m.scores?.moat ?? "–"} · 타이밍 {m.scores?.timing ?? "–"}</Link> : c.promoted ? <span className="soft-text">미생성</span> : <span className="soft-text">—</span>}</td>
            </tr>); })}</tbody>
        </table>
      </div>
      <p className="soft-text" style={{ marginTop: 10 }}>● 승격 = `research/ecosystems/seed_graph.json` 기업 노드. 해자 카드는 Actions `moat` 워크플로.</p>
    </div>
  );
}
