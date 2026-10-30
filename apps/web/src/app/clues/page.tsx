import { KIND_KO, kstDay, loadClues } from "@/lib/clues";

export const dynamic = "force-dynamic";
export const metadata = { title: "단서" };

/** 단서 (ADR-0028): 최근 7일 동안 출처에서 들어온 작은 소식, 날짜별. 해석·판단은 투자 아이디어 쪽에 있다. */
export default async function CluesPage() {
  const clues = await loadClues();
  const days = new Map<string, typeof clues>();
  for (const c of clues) {
    const d = kstDay(c.seen_at);
    (days.get(d) ?? days.set(d, []).get(d)!).push(c);
  }
  return <div className="fd op">
    <header className="fd-head">
      <h1>단서</h1>
      <p className="fd-summary">최근 7일 · {clues.length}건</p>
    </header>
    {!clues.length ? <p className="fd-empty">아직 들어온 단서가 없습니다.</p> : null}
    {[...days.entries()].map(([d, list]) => <section key={d} className="op-sec">
      <h2 className="cl-day">{d.slice(5).replace("-", "/")} <small>{list.length}건</small></h2>
      <ul className="cl-list">{list.map((c) => <li key={c.clue_id}>
        <a href={c.url} target="_blank" rel="noreferrer">{c.title}</a>
        {c.note ? <p>{c.note}</p> : null}
        <div className="cl-meta">
          <span>{[c.source_name, c.source_kind ? KIND_KO[c.source_kind] ?? null : null].filter(Boolean).join(" · ")}</span>
          {c.companies.slice(0, 4).map((x, i) => <b key={`${x.name}-${i}`}>{x.name}</b>)}
        </div>
      </li>)}</ul>
    </section>)}
  </div>;
}
