import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ReportCard } from "@/components/feed/Feed";
import { companyId, companyWiki, loadFundamentals, loadIssuesMentioning, reportsOf } from "@/lib/company";
import { loadFeed } from "@/lib/feed";
import { ECO_KO, EVENT_KIND_KO, SIZE_KO, loadCompanyEvents, pct, usdB } from "@/lib/ideas";
import { issueDate } from "@/lib/issues";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const w = companyWiki(companyId((await params).slug));
  return { title: w?.name ?? "기업" };
}

const md = (d?: string | null) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "");
const fmtBig = (x?: number | null, cur?: string | null) => {
  if (x == null) return "—";
  if (cur === "KRW") return x >= 1e12 ? `${(x / 1e12).toFixed(2)}조원` : `${Math.round(x / 1e8).toLocaleString()}억원`;
  if (cur === "USD" || !cur) return x >= 1e9 ? `$${(x / 1e9).toFixed(2)}B` : `$${Math.round(x / 1e6).toLocaleString()}M`;
  return `${x.toLocaleString()} ${cur}`;
};

/** 기업 위키: 공급망 위치(무엇을 공급하고 어떤 병목을 푸나) · 시세·재무 · 이 기업에 닿는 변화 · 리포트 · 소식 · 이슈. */
export default async function CompanyPage({ params }: { params: Promise<{ slug: string }> }) {
  const id = companyId((await params).slug);
  const w = companyWiki(id);
  if (!w) notFound();
  const [feed, fund, events, issues] = await Promise.all([loadFeed(), loadFundamentals(id), loadCompanyEvents([id], 10), loadIssuesMentioning(id)]);
  const facts = feed.ideas.find((x) => x.primary_company === id)?.facts ?? null;
  const { primary, related } = reportsOf(id, feed.ideas);
  const stat = [
    facts?.market_cap_usd != null ? ["시총", usdB(facts.market_cap_usd)] : null,
    facts?.r12m != null ? ["12개월", pct(facts.r12m)] : null,
    facts?.from_high != null ? ["고점 대비", pct(facts.from_high)] : null,
    fund?.revenue != null ? ["매출 TTM", fmtBig(fund.revenue, fund.currency ?? facts?.currency)] : null,
    fund?.revenue_yoy_pct != null ? ["매출 성장", pct(fund.revenue_yoy_pct)] : null,
    fund?.op_margin_pct != null ? ["영업이익률", `${fund.op_margin_pct}%`] : null,
    fund?.ps != null ? ["P/S", fund.ps.toFixed(1)] : null,
    fund?.pe != null && fund.pe > 0 ? ["P/E", fund.pe.toFixed(1)] : null,
  ].filter((x): x is [string, string] => !!x && !!x[1]);
  return <div className="fd fd-detail">
    <div className="breadcrumb"><Link href="/">리서치</Link><Icon name="chevron-right" size={13}/><span>{w.name}</span></div>
    <header className="fd-dhead">
      <p className="fd-dco"><span>{[w.ticker, w.exchange, w.size_band ? SIZE_KO[w.size_band] : null, ...w.ecosystems.map((e) => ECO_KO[e] ?? e)].filter(Boolean).join(" ")}</span></p>
      <h1>{w.name}{w.label !== w.name ? <small>{w.label.replace(/\s+\(.*$/, "")}</small> : null}</h1>
      {stat.length ? <dl className="cw-stats">{stat.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl> : null}
    </header>

    <div className="fd-dgrid">
      <div>
        {primary.length ? <section className="fd-dsec"><h2>리포트</h2><div className="fd-cards one">{primary.map((x) => <ReportCard key={x.idea_key} idea={x}/>)}</div></section> : null}
        {related.length ? <section className="fd-dsec"><h2>관련 리포트</h2><ul className="cw-list">{related.map((x) => <li key={x.idea_key}><Link href={`/ideas/${x.idea_key}`}>{x.title}<span>›</span></Link>
          <small>{x.companies.find((c) => c.id === id)?.why ?? ""}</small></li>)}</ul></section> : null}

        {w.reaches.length ? <section className="fd-dsec"><h2>이 기업에 닿는 변화</h2>
          <ul className="cw-reach">{w.reaches.map((r) => <li key={r.node}>
            <b style={{ opacity: 0.45 + 0.55 * r.confidence }}>{r.confidence.toFixed(2)}</b>
            <p>{r.path.map((l, i) => <span key={i}>{i ? <i>→</i> : null}{l.replace(/\s+\(.*$/, "")}</span>)}</p>
          </li>)}</ul></section> : null}

        {events.length ? <section className="fd-dsec"><h2>최근 소식</h2>
          <ul className="fd-events">{events.map((e) => <li key={e.event_id}>
            <div className="fd-ref-meta">{[e.published_at.slice(0, 10), EVENT_KIND_KO[e.kind] ?? e.kind, e.publisher].filter(Boolean).join(" ")}</div>
            {e.text && e.verified ? <p className="fd-ref-note">{e.text}</p> : null}
            <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a>
          </li>)}</ul></section> : null}

        {issues.length ? <section className="fd-dsec"><h2>이슈</h2>
          <ul className="cw-list">{issues.map((i) => <li key={i.issue_key}><Link href={`/issues/${i.issue_key}`}><time>{md(issueDate(i))}</time>{i.title}<span>›</span></Link></li>)}</ul></section> : null}
      </div>

      <aside className="fd-aside">
        {w.supplies.length ? <><h2>공급·개발</h2><p className="cw-chips">{w.supplies.map((s) => <Link key={s.id} href={`/map?focus=${encodeURIComponent(s.id)}`}>{s.label}</Link>)}</p></> : null}
        {w.bottlenecks.length ? <><h2>푸는 병목</h2><p className="cw-chips">{w.bottlenecks.map((b) => <Link key={b.id} href={`/bottlenecks#${encodeURIComponent(b.id)}`}>{b.label}</Link>)}</p></> : null}
        {w.peers.length ? <><h2>동종</h2><ul className="cw-peers">{w.peers.map((p) => <li key={p.id}><Link href={`/companies/${p.id.replace(/^company:/, "")}`} className={p.inScope ? "" : "out"}>{p.name}{p.ticker ? <small>{p.ticker}</small> : null}</Link></li>)}</ul></> : null}
        {w.customers.length ? <><h2>고객</h2><ul className="cw-peers">{w.customers.map((c) => <li key={c.id}><Link href={`/companies/${c.id.replace(/^company:/, "")}`}>{c.name}</Link></li>)}</ul></> : null}
        <div className="fd-aside-meta"><Link href={`/map?focus=${encodeURIComponent(id)}`}>공급망 그래프에서 보기</Link></div>
      </aside>
    </div>
  </div>;
}
