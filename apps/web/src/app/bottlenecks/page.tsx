import Link from "next/link";
import { ECO_KO, SIZE_KO, pct } from "@/lib/ideas";
import { loadBoard, type BoardRow } from "@/lib/board";

export const dynamic = "force-dynamic";
export const metadata = { title: "병목 보드" };

type SP = { eco?: string };

/** 병목 보드 (ADR-0017) — 온톨로지를 사람이 보는 화면. 어디가 조여지는지(이슈·상태 관측치), 길목의 상장 공급사, 이미 움직인 폭, 아이디어 유무. */
export default async function Bottlenecks({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const eco = sp.eco && ECO_KO[sp.eco] ? sp.eco : undefined;
  const { rows, priceCount, obsCount } = await loadBoard();
  const shown = rows.filter((r) => !eco || r.ecosystem === eco);
  const active = shown.filter((r) => r.activity > 0);
  const quiet = shown.filter((r) => r.activity === 0);
  const uncovered = active.reduce((a, r) => a + r.suppliers.filter((s) => !s.ideaKey).length, 0);
  return <div className="fd">
    <header className="fd-head">
      <div className="page-kicker">병목 보드</div>
      <h1>어디가 조여지고, 누가 그 길목에 있나</h1>
      <p className="fd-summary">최근 30일 이슈가 있거나 상태 관측치가 있는 병목 {active.length}곳 · 그 길목의 아이디어 없는 상장사 {uncovered}곳
        {` · 상태 관측치 ${obsCount}개 · 가격 ${priceCount}종목`}</p>
      <nav className="fd-tabs" aria-label="생태계">
        <Link className={!eco ? "on" : ""} href="/bottlenecks">전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={eco === k ? "on" : ""} href={`/bottlenecks?eco=${k}`}>{v}</Link>)}
      </nav>
    </header>
    <div className="bn-list">{active.map((r) => <Row key={r.id} r={r}/>)}</div>
    {quiet.length ? <details className="bn-quiet"><summary>최근 소식이 없는 병목 {quiet.length}곳</summary>
      <ul>{quiet.map((r) => <li key={r.id} id={r.id}>{r.label}<small> · 상장 공급사 {r.suppliers.length}곳{r.ideas.length ? ` · 아이디어 ${r.ideas.length}` : ""}</small></li>)}</ul>
    </details> : null}
    <footer className="fd-footer"><em>가격은 근거가 아니라 이미 움직인 폭입니다. 투자 판단을 돕는 정리이며 매수·매도 권유가 아닙니다.</em></footer>
  </div>;
}

const SIZE_ORDER: Record<string, number> = { micro: 0, small: 1, mid: 2, large: 3, mega: 4 };
/** 아이디어가 있는 기업 → 가격 급변 → 소형·중형 순 (길목의 작은 공급사가 먼저 보이게). */
const sortSup = (xs: BoardRow["suppliers"]) => [...xs].sort((a, b) => Number(!!b.ideaKey) - Number(!!a.ideaKey)
  || Math.abs(b.price?.r1m ?? 0) - Math.abs(a.price?.r1m ?? 0) || (SIZE_ORDER[a.size ?? ""] ?? 3) - (SIZE_ORDER[b.size ?? ""] ?? 3));

function Row({ r }: { r: BoardRow }) {
  return <article className="bn-row" id={r.id}>
    <div className="bn-head">
      <h3>{r.label}</h3>
      <span>{[r.ecosystem ? ECO_KO[r.ecosystem] : null, r.issues.length ? `최근 이슈 ${r.issues.length}건` : null,
        r.states.length ? `상태 관측치 ${r.states.length}개` : null, r.ideas.length ? `아이디어 ${r.ideas.length}건` : "아이디어 없음"].filter(Boolean).join(" · ")}</span>
    </div>
    {r.states.length ? <ul className="bn-states">{r.states.map((s) => <li key={s.id}>
      {s.label} <strong>{s.value}{s.unit ? ` ${s.unit}` : ""}</strong>
      {s.value_1m != null && s.value_1m !== 0 ? <small> (1개월 전 {s.value_1m})</small> : null}
      <small> · {s.as_of}</small>{s.url ? <> · <a href={s.url} target="_blank" rel="noreferrer">출처</a></> : null}
    </li>)}</ul> : null}
    {r.issues.length ? <ul className="bn-issues">{r.issues.map((i) => <li key={i.key}><span className="fd-date">{i.date?.slice(5).replace("-", "/")}</span>
      {i.url ? <a href={i.url} target="_blank" rel="noreferrer">{i.title}</a> : i.title}</li>)}</ul> : null}
    <p className="bn-via">길목: {r.via.map((v) => v.label.split(" (")[0]).join(" · ") || "—"}</p>
    {r.suppliers.length ? <div className="bn-sup" role="table">
      {sortSup(r.suppliers).slice(0, 8).map((s) => <div key={s.id} className="bn-sup-row" role="row">
        <span className="bn-sup-name">{s.name}<small>{[s.ticker, s.exchange, s.size ? SIZE_KO[s.size] : null].filter(Boolean).join(" · ")}</small></span>
        <span className="bn-sup-px">{s.price ? [s.price.r1m != null ? `1개월 ${pct(s.price.r1m)}` : null, s.price.r12m != null ? `12개월 ${pct(s.price.r12m)}` : null].filter(Boolean).join(" · ") : <small>가격 없음</small>}</span>
        <span className="bn-sup-idea">{s.ideaKey ? <Link href={`/ideas/${s.ideaKey}`}>아이디어 →</Link> : <small>아이디어 없음</small>}</span>
      </div>)}
      {r.suppliers.length > 8 ? <p className="bn-more">외 {r.suppliers.length - 8}곳: {sortSup(r.suppliers).slice(8).map((s) => s.name).join(", ")}</p> : null}
    </div> : null}
    {r.ideas.length ? <p className="bn-ideas">{r.ideas.map((x) => <Link key={x.key} href={`/ideas/${x.key}`}>{"★".repeat(x.stars)} {x.title}</Link>)}</p> : null}
  </article>;
}
