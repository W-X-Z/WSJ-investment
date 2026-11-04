import Link from "next/link";
import { notFound } from "next/navigation";
import { CompanyLine, Prose, Stars5 } from "@/components/opps/Opps";
import { IdeaTimeline } from "@/components/opps/IdeaTimeline";
import { loadOpportunities, loadOpportunity, loadPrices, marketKo, primaryOf, relatedTo, touchedAt, type OppEvidence, type OppFact, type PricePoint } from "@/lib/opportunities";

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

function splitTitle(t: string): [string, string | null] {
  const i = t.indexOf(" — ");
  return i > 0 ? [t.slice(0, i), t.slice(i + 3)] : [t, null];
}

function priceFacts(px: PricePoint[]): OppFact[] {
  if (px.length < 2) return [];
  const last = px[px.length - 1], hi = px.reduce((a, b) => (b.c > a.c ? b : a));
  const f = (v: number) => (v >= 1000 ? Math.round(v).toLocaleString("en-US") : v.toFixed(2));
  return [
    { label: "현재가", value: f(last.c), note: `${Number(last.d.slice(5, 7))}/${Number(last.d.slice(8, 10))} 종가` },
    { label: "고점 대비", value: `${Math.round((last.c / hi.c - 1) * 100)}%`, note: `고점 ${f(hi.c)} (${Number(hi.d.slice(5, 7))}/${Number(hi.d.slice(8, 10))})` },
  ];
}

/** 투자 아이디어 상세 v2 (사용자 2026-11-04): 판단 스트립 → 요약 3칸(투자 아이디어·주가 전망·리스크) → 차트·히스토리(연동) → 관련 자료. */
export default async function OpportunityPage({ params }: { params: Promise<{ key: string }> }) {
  const o = await loadOpportunity((await params).key);
  if (!o) notFound();
  const primary = primaryOf(o);
  const [all, prices] = await Promise.all([loadOpportunities(), loadPrices(primary)]);
  const related = relatedTo(o, all);
  const others = o.companies.filter((c) => c.role !== "primary");
  const b = o.brief;
  const facts = [...priceFacts(prices), ...(b.facts ?? [])];
  // 투자 아이디어 → 주가 전망 → 리스크 (사용자 2026-11-04). 옛 칸(change·position·price)만 있으면 합쳐 보인다.
  const join = (...xs: (string | undefined)[]) => xs.filter(Boolean).join("\n") || undefined;
  const cells = ([
    ["투자 아이디어", b.idea ?? join(b.change, b.position), "od-idea"],
    ["주가 전망", b.outlook ?? b.price, "od-outlook"],
    ["리스크", b.risk, "od-risk"],
  ] as [string, string | undefined, string][]).filter(([, v]) => v) as [string, string, string][];
  const touched = touchedAt(o);
  const groups = groupEvidence(o.evidence);
  return <article className="od">
    <p className="op-back"><Link href="/">← 투자 아이디어</Link></p>

    <header className="od-head">
      <div className="od-top"><Stars5 n={o.stars} large/><CompanyLine o={o}/><span className="od-upd">갱신 {Number(touched.slice(5, 7))}/{Number(touched.slice(8, 10))}</span></div>
      <h1>{o.title}</h1>
      {facts.length || b.next ? <dl className="od-strip">
        {facts.map((f, i) => <div key={i} className={[f.label === "고점 대비" && f.value.startsWith("-") ? "dn" : "", i === facts.length - 1 && facts.length % 2 ? "od-wide" : ""].join(" ").trim() || undefined}><dt>{f.label}</dt><dd>{f.value}</dd>{f.note ? <span>{f.note}</span> : null}</div>)}
        {b.next ? <div className="od-next"><dt>다음 확인</dt><dd>{b.next}</dd></div> : null}
      </dl> : null}
    </header>

    {cells.length ? <section className="od-three" aria-label="투자 아이디어 요약">
      {cells.map(([h, v, c]) => <div key={h} className={`od-cell ${c}`}><h2>{h}</h2><Prose text={v}/></div>)}
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
