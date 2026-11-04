import Link from "next/link";
import { notFound } from "next/navigation";
import { CompanyLine, Prose, Stars5 } from "@/components/opps/Opps";
import { IdeaTimeline } from "@/components/opps/IdeaTimeline";
import { loadOpportunities, loadOpportunity, loadPrices, marketKo, primaryOf, chipsOf, relatedTo, touchedAt, type OppChip, type OppEvidence } from "@/lib/opportunities";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  return { title: o?.title ?? "투자 아이디어" };
}

const ROLE_KO: Record<string, string> = { customer: "고객", competitor: "경쟁사", peer: "비교 대상", supplier: "공급사", related: "관련" };

/** 근거를 종류별로: 공시 · 회사 발표·IR · 실적 발표·콜 · 증권사·리서치 · 언론·업계. 제목의 ' — 메모' 는 작은 글씨로 뗀다. */
function groupEvidence(items: OppEvidence[]) {
  const kind = (e: OppEvidence) => {
    const u = e.url.toLowerCase(), t = `${e.title} ${e.publisher ?? ""}`.toLowerCase();
    if (/sec\.gov|dart\.fss|kind\.krx|edgar/.test(u)) return "공시";
    if (/transcript|earnings|call|콜|녹취|fool\.com\/earnings|allmind|webull|earningswhispers|equibles/.test(u + " " + t)) return "실적 발표·콜";
    if (/businesswire|prnewswire|globenewswire|accessnewswire|ir\.|investor|q4cdn|company-ir|\/ir\//.test(u + " " + t) || /\bir\b/.test(t)) return "회사 발표·IR";
    if (/증권|리서치|research|consensus|stock-research|market-report|substack|semianalysis|tikr|aletheia/.test(u + " " + t)) return "증권사·리서치";
    return "언론·업계";
  };
  const order = ["공시", "회사 발표·IR", "실적 발표·콜", "증권사·리서치", "언론·업계"];
  const g = new Map<string, OppEvidence[]>();
  for (const e of items) (g.get(kind(e)) ?? g.set(kind(e), []).get(kind(e))!).push(e);
  return order.filter((k) => g.has(k)).map((k) => ({ k, items: g.get(k)!.sort((a, b) => (b.date ?? "").localeCompare(a.date ?? "")) }));
}

/** 근거 칩: 사실 한 토막 + 출처. 링크가 있으면 원문으로. */
function Chips({ items }: { items: OppChip[] }) {
  return <ul className="od-chips">{items.map((c, i) => {
    const body = <>{c.label}{c.src ? <small>{c.src}</small> : null}</>;
    return <li key={i}>{c.url ? <a href={c.url} target="_blank" rel="noreferrer" title={c.src ?? undefined}>{body}<i aria-hidden="true">↗</i></a> : <span>{body}</span>}</li>;
  })}</ul>;
}

function splitTitle(t: string): [string, string | null] {
  const i = t.indexOf(" — ");
  return i > 0 ? [t.slice(0, i), t.slice(i + 3)] : [t, null];
}

/** 투자 아이디어 상세 v2 (사용자 2026-11-04): 요약 3칸(투자 아이디어·주가 전망·리스크, 근거는 접힘) → 차트·히스토리(연동) → 관련 자료. 숫자 스트립은 걷었다. */
export default async function OpportunityPage({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  if (!o) notFound();
  const primary = primaryOf(o);
  const [all, prices] = await Promise.all([loadOpportunities(), loadPrices(primary)]);
  const related = relatedTo(o, all);
  const others = o.companies.filter((c) => c.role !== "primary");
  const b = o.brief;
  // 투자 아이디어 → 주가 전망 → 리스크 (사용자 2026-11-04). 옛 칸(change·position·price)만 있으면 합쳐 보인다.
  const join = (...xs: (string | undefined)[]) => xs.filter(Boolean).join("\n") || undefined;
  const ch = b.chips ?? {};
  const cells = ([
    ["투자 아이디어", b.idea ?? join(b.change, b.position), chipsOf(ch.idea), "od-idea"],
    ["주가 전망", b.outlook ?? b.price, chipsOf(ch.outlook), "od-outlook"],
    ["리스크", b.risk, chipsOf(ch.risk), "od-risk"],
  ] as [string, string | undefined, OppChip[], string][]).filter(([, v]) => v) as [string, string, OppChip[], string][];
  const touched = touchedAt(o);
  const groups = groupEvidence(o.evidence);
  return <article className="od">
    <p className="op-back"><Link href="/">← 투자 아이디어</Link></p>

    <header className="od-head">
      <div className="od-top"><Stars5 n={o.stars} large/><CompanyLine o={o}/><span className="od-upd">갱신 {Number(touched.slice(5, 7))}/{Number(touched.slice(8, 10))}</span></div>
      <h1>{o.title}</h1>
    </header>

    {cells.length ? <section className="od-three" aria-label="투자 아이디어 요약">
      {cells.map(([h, v, cs, c]) => <div key={h} className={`od-cell ${c}`}><h2>{h}</h2><Prose text={v}/>{cs.length ? <details className="od-acc"><summary>근거 {cs.length}</summary><Chips items={cs}/></details> : null}</div>)}
    </section> : o.interpretation ? <section className="od-three"><div className="od-cell od-idea"><h2>핵심</h2><Prose text={o.interpretation}/></div></section> : null}

    <div className="od-main">
        {o.history.length ? <><h2 className="od-h2">주가와 히스토리</h2><IdeaTimeline prices={prices} history={o.history} name={primary?.name ?? o.title}/></>
          : <section className="op-sec"><h2>투자 아이디어</h2><Prose text={o.idea}/></section>}
        {o.history.length ? <details className="op-more"><summary>아이디어 전문</summary><Prose text={o.idea}/></details> : null}

        {others.length ? <section className="od-sec"><h2>함께 볼 기업</h2>
          <ul className="od-cos">{others.map((c, i) => <li key={`${c.name}-${i}`}><b>{c.name}</b><span>{[c.ticker, marketKo(c.exchange)].filter(Boolean).join(" · ")}</span>{c.role && ROLE_KO[c.role] ? <em>{ROLE_KO[c.role]}</em> : null}</li>)}</ul>
        </section> : null}

        {related.length ? <section className="od-sec"><h2>같은 흐름의 아이디어</h2>
          <ul className="op-rel">{related.map((r) => <li key={r.opportunity_key}><Link href={`/opportunities/${r.opportunity_key}`}>{r.title}</Link></li>)}</ul>
        </section> : null}

        <section className="od-sec"><h2>관련 자료</h2>
          <div className="od-ev">{groups.map((g) => <div key={g.k} className="od-evg"><h3>{g.k} <small>{g.items.length}</small></h3>
            <ul>{g.items.map((e, i) => { const [t, note] = splitTitle(e.title); return <li key={`${e.url}-${i}`}>
              <a href={e.url} target="_blank" rel="noreferrer">{t}</a>
              {note ? <p>{note}</p> : null}
              <span>{[e.publisher, e.date ? e.date.slice(0, 10) : null].filter(Boolean).join(" · ")}</span>
            </li>; })}</ul>
          </div>)}</div>
        </section>
    </div>
  </article>;
}
