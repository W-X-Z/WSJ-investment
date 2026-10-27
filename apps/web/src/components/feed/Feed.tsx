import Link from "next/link";
import { IDEA_TYPE, SIZE_KO, TREND_KO } from "@/lib/ideas";
import { REL_KO, dayLabel, ecoLabel, rel, type IdeaView, type TimelineItem } from "@/lib/feed";

/** ★ 를 글자로 (배지 없이). */
export function StarText({ n }: { n: number }) {
  return <span className="fd-stars" aria-label={`별 ${n}개 (3개 만점)`}>{"★".repeat(n)}<i>{"★".repeat(Math.max(0, 3 - n))}</i></span>;
}

/** 각주 번호 — 칩 대신 [1][2]. href 가 있으면 상세 화면의 출처로 간다. */
export function Cites({ ns, href }: { ns: number[]; href?: string }) {
  if (!ns.length) return null;
  return <sup className="fd-cite">{ns.map((n) => <a key={n} href={`${href ?? ""}#ref-${n}`}>{n}</a>)}</sup>;
}

/** 한 줄 메타: ★ · 변화 · 유형 · 생태계 — 모두 텍스트. */
export function MetaLine({ idea }: { idea: IdeaView }) {
  const t = idea.shownTrend;
  const trend = t && TREND_KO[t] ? <b className={`fd-trend fd-trend-${t}`}>{TREND_KO[t]}</b> : null;
  const parts = [IDEA_TYPE[idea.type]?.label ?? idea.type, ...idea.ecosystems.map((e) => ecoLabel(e))].filter(Boolean);
  return <div className="fd-meta"><StarText n={idea.stars}/>{trend ? <> · {trend}</> : null} · {parts.join(" · ")}</div>;
}

/** 근거의 나이 — 기업 직접 근거가 없으면 그 사실을 먼저 말한다. */
export function Freshness({ idea }: { idea: IdeaView }) {
  return <span className="fd-fresh">
    {idea.companyAt ? <span className={rel(idea.companyAt) === "오늘" || rel(idea.companyAt) === "어제" ? "fd-hot" : ""}>기업 근거 {rel(idea.companyAt)}</span>
      : <span className="fd-warn">기업 직접 근거 없음</span>}
    {idea.industryAt ? <> · 업계 근거 {rel(idea.industryAt)}</> : null}
  </span>;
}

function CompanyLine({ idea }: { idea: IdeaView }) {
  const p = idea.primary;
  if (!p) return null;
  const others = idea.companies.filter((c) => c.id !== p.id && c.role !== "customer").slice(0, 3).map((c) => c.name);
  const customers = idea.companies.filter((c) => c.role === "customer").slice(0, 2).map((c) => c.name);
  return <div className="fd-co">
    <b>{p.name}</b> <span>{[p.ticker, p.exchange, p.size_band ? SIZE_KO[p.size_band] : null].filter(Boolean).join(" · ")}</span>
    {others.length ? <em>함께 보는 기업 {others.join(", ")}</em> : null}
    {customers.length ? <em>수요처 {customers.join(", ")}</em> : null}
  </div>;
}

/** 아이디어 이야기 카드 (Axios 식): 메타 한 줄 → 제목 → 두 문장 → 왜 지금 → 기업 → 근거 나이. */
export function StoryCard({ idea }: { idea: IdeaView }) {
  const href = `/ideas/${idea.idea_key}`;
  const w = idea.whyNow;
  return <article className={`fd-story fd-tone-${idea.type}`}>
    <MetaLine idea={idea}/>
    <h3><Link href={href}>{idea.title}</Link></h3>
    <p className="fd-thesis">{idea.thesis}</p>
    {w ? <p className="fd-why"><b>{w.rel === "direct" ? "왜 지금" : "왜 지금 · 업계 신호"}</b>{w.date ? <span className="fd-date">{w.date.slice(5).replace("-", "/")}</span> : null}
      {w.text}<Cites ns={w.refs} href={href}/></p> : null}
    <CompanyLine idea={idea}/>
    <div className="fd-foot"><Freshness idea={idea}/><Link href={href}>근거 {idea.refs.length}개 · 반대 근거 보기 →</Link></div>
  </article>;
}

/** 무슨 일이 있었나 — 날짜별, 기업 소식(확인된 사실) 먼저, 업계 이슈. 출처는 텍스트, 연결된 아이디어는 화살표 링크. */
export function Timeline({ items, ideas }: { items: TimelineItem[]; ideas: IdeaView[] }) {
  const titleOf = new Map(ideas.map((v) => [v.idea_key, v.primary?.name ?? v.title]));
  const days = Array.from(new Set(items.map((x) => x.date))).filter(Boolean);
  if (!items.length) return <p className="fd-empty">최근 5일 동안 정리된 소식이 없습니다.</p>;
  return <div className="fd-tl">{days.map((d) => <section key={d}>
    <h4>{dayLabel(d)}</h4>
    <ul>{items.filter((x) => x.date === d).map((x) => <li key={x.kind + x.key} className={`fd-tl-${x.kind}`}>
      <span className="fd-tl-kind">{x.kind === "event" ? "기업" : "업계"}</span>
      <div>
        {x.kind === "event"
          ? <><p className="fd-tl-head"><b>{x.company ?? x.companyId.replace("company:", "")}</b> {firstSentence(stripDate(x.text)) ?? x.title}</p>
              <p className="fd-tl-sub"><a href={x.url} target="_blank" rel="noreferrer">{x.title}</a></p>
              {x.more.slice(0, 2).map((m) => <p key={m.url} className="fd-tl-sub"><a href={m.url} target="_blank" rel="noreferrer">{m.title}</a></p>)}
              <div className="fd-tl-meta">{[x.publisher, ...x.more.map((m) => m.publisher)].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(", ")}
                {x.ideaKeys.map((k) => <Link key={k} href={`/ideas/${k}`}>→ {titleOf.get(k)} 아이디어</Link>)}</div></>
          : <><p className="fd-tl-head">{x.stars >= 3 ? <StarText n={3}/> : null}{x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.title}</a> : x.title}</p>
              {x.why || x.summary ? <p className="fd-tl-sub">{trim(x.why ?? x.summary ?? "", 150)}</p> : null}
              <div className="fd-tl-meta">{pubs(x.publishers, x.sourceCount)}{ecoLabel(x.ecosystem) ? ` · ${ecoLabel(x.ecosystem)}` : ""}
                {x.ideaKeys.map((k) => <Link key={k} href={`/ideas/${k}`}>→ {titleOf.get(k)} 아이디어</Link>)}</div></>}
      </div>
    </li>)}</ul>
  </section>)}</div>;
}

/** 모든 아이디어 — 관심 종목표처럼 한 줄씩. */
export function IdeaTable({ ideas }: { ideas: IdeaView[] }) {
  return <div className="fd-table" role="table" aria-label="모든 투자 아이디어">
    <div className="fd-tr fd-th" role="row"><span>★</span><span>아이디어</span><span>주 기업</span><span>기업 근거</span><span>업계 근거</span></div>
    {ideas.map((v) => <Link key={v.idea_key} href={`/ideas/${v.idea_key}`} className={`fd-tr ${v.stale ? "fd-stale" : ""}`} role="row">
      <span><StarText n={v.stars}/></span>
      <span className="fd-td-title">{v.title}{v.shownTrend && TREND_KO[v.shownTrend] ? <em className={`fd-trend fd-trend-${v.shownTrend}`}>{TREND_KO[v.shownTrend]}</em> : null}</span>
      <span className="fd-td-co">{v.primary?.name}<small>{v.primary?.ticker}</small></span>
      <span className={v.companyAt ? "" : "fd-warn"}>{v.companyAt ? rel(v.companyAt) : "없음"}</span>
      <span>{rel(v.industryAt)}</span>
    </Link>)}
  </div>;
}

/** 상세 화면 출처 목록 (각주 대상). 층(기업 직접·관련·업계·그래프 배경)을 글자로. */
export function References({ idea }: { idea: IdeaView }) {
  return <ol className="fd-refs">{idea.refs.map((r) => <li key={r.n} id={`ref-${r.n}`}>
    <span className="fd-ref-n">{r.n}</span>
    <div>
      <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
      <div className="fd-ref-meta">{[r.date ? r.date.slice(0, 10) : null, r.publisher, REL_KO[r.rel], r.tier_ko].filter(Boolean).join(" · ")}</div>
      {r.note ? <p className="fd-ref-note">{r.note}</p> : null}
    </div>
  </li>)}</ol>;
}

const trim = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);
/** 확인 내용 앞의 '2026-10-27 발표' 같은 날짜는 날짜 묶음 제목과 겹치니 뺀다. */
const stripDate = (s: string | null) => (s ? s.replace(/^\d{4}-\d{2}-\d{2}(\s*(발표|공시|실적설명회))?\s*[:：]?\s*/, "") : s);
const firstSentence = (s: string | null) => {
  if (!s) return null;
  const m = s.match(/^.{20,220}?[.。](\s|$)/);
  return trim((m ? m[0] : s).trim(), 220);
};
const pubs = (ps: string[], n: number) => (ps.length > 2 ? `${ps.slice(0, 2).join(", ")} 외 ${Math.max(n, ps.length) - 2}곳` : ps.join(", "));
