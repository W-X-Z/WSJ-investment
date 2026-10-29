import Link from "next/link";
import { StarText, ValueBand } from "@/components/feed/Feed";
import { type FeedIdea, shortName } from "@/lib/feed";
import { ECO_KO, pct } from "@/lib/ideas";
import { EVENT_TYPE_KO, VERDICT_KO, issueDate, nodeLabel, type Issue, type IssueHypotheses, type IssuePath } from "@/lib/issues";

const md = (d?: string | null) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "");
/** 수집기의 중요도(1~10) → ★ 1~3. */
export const issueStars = (i: Issue) => i.stars ?? (i.importance >= 8 ? 3 : i.importance >= 6 ? 2 : 1);
const slug = (id: string) => id.replace(/^company:/, "");

/** 영향 경로 한 줄: 노드 사슬 → 주장 → (기업). 기업은 위키로, 리포트가 있으면 리포트로. */
export function PathLine({ p, idea }: { p: IssuePath; idea?: FeedIdea | null }) {
  const labels = p.path_labels?.length ? p.path_labels : p.path.map(nodeLabel);
  const r = p.research_result;
  return <li className={`fd-ip${p.selected ? " sel" : ""}${r ? ` v-${r.verdict}` : ""}`}>
    <p className="fd-ip-path">{labels.map((l, i) => <span key={i}>{i ? <i>→</i> : null}{l}</span>)}{p.effect_pct != null && p.effect_pct < 0 ? <em className="fd-ip-neg">피해</em> : null}</p>
    <p className="fd-ip-claim">{p.claim}</p>
    {r ? <p className="fd-ip-research"><b>{VERDICT_KO[r.verdict]}</b>{r.summary}{r.sources?.[0]?.url ? <a href={r.sources[0].url} target="_blank" rel="noreferrer">원문</a> : null}</p> : null}
    {idea ? <Link href={`/ideas/${idea.idea_key}`} className="fd-ip-link">{p.company_label ?? p.company}{idea.valuation ? <b className={idea.valuation.expected_upside_pct >= 0 ? "up" : "down"}>{pct(idea.valuation.expected_upside_pct)}</b> : null}<span>›</span></Link>
      : p.company ? <Link href={`/companies/${slug(p.company)}`} className="fd-ip-link muted">{p.company_label ?? p.company}{p.selected ? " · 리포트 작성 중" : ""}<span>›</span></Link> : null}
  </li>;
}

/** 이슈 카드 (목록): 날짜 · 생태계 · 유형 · ★ → 제목 → 의미 → 노드 → 경로 → 리포트. */
export function IssueCard({ issue, hyp, ideas }: { issue: Issue; hyp?: IssueHypotheses | null; ideas: FeedIdea[] }) {
  const href = `/issues/${issue.issue_key}`;
  const paths = (hyp?.paths ?? []).slice(0, 3);
  const byCo = new Map(ideas.map((x) => [x.primary_company, x]));
  const nodes = (issue.nodes ?? []).slice(0, 4);
  return <article className="fd-ic">
    <header className="fd-ic-top">
      <time dateTime={issueDate(issue) ?? undefined}>{md(issueDate(issue))}</time>
      <span>{[issue.ecosystem ? ECO_KO[issue.ecosystem] : null, issue.event_type ? EVENT_TYPE_KO[issue.event_type] ?? issue.event_type : null].filter(Boolean).join(" ")}</span>
      <StarText n={issueStars(issue)}/>
      <Link href={href} className="fd-ic-go" aria-label="이슈 상세">›</Link>
    </header>
    <h3><Link href={href}>{issue.title}</Link></h3>
    {issue.why_it_matters ? <p className="fd-ic-why">{issue.why_it_matters}</p> : null}
    {nodes.length ? <p className="fd-ic-nodes">{nodes.map((n) => <span key={n}>{nodeLabel(n)}</span>)}</p> : null}
    {paths.length ? <ul className="fd-ic-paths">{paths.map((p) => <PathLine key={p.id} p={p} idea={p.company ? byCo.get(p.company) : null}/>)}</ul> : null}
    {ideas.length ? <p className="fd-ic-ideas">{ideas.map((x) => <Link key={x.idea_key} href={`/ideas/${x.idea_key}`}>{x.primary ? shortName(x.primary) : x.title}
      {x.valuation ? <b className={x.valuation.expected_upside_pct >= 0 ? "up" : "down"}>{pct(x.valuation.expected_upside_pct)}</b> : null}<span>›</span></Link>)}</p> : null}
  </article>;
}

/** 이슈 상세의 머리: 제목 · 요약 · 의미 · 출처. 경로·리포트·관련 기업은 상세 페이지가 절로 나눈다. */
export function IssueHead({ issue }: { issue: Issue }) {
  return <header className="fd-dhead fd-ic-detail">
    <p className="fd-dco"><time>{issueDate(issue)}</time><span>{[issue.ecosystem ? ECO_KO[issue.ecosystem] : null, issue.event_type ? EVENT_TYPE_KO[issue.event_type] ?? issue.event_type : null].filter(Boolean).join(" ")}</span><StarText n={issueStars(issue)}/></p>
    <h1>{issue.title}</h1>
    {issue.summary ? <p className="fd-thesis">{issue.summary}</p> : null}
    {issue.why_it_matters ? <p className="fd-ic-why">{issue.why_it_matters}</p> : null}
    {issue.sources?.length ? <ul className="fd-ic-src">{issue.sources.slice(0, 8).map((s, i) => <li key={i}>
      <a href={s.url} target="_blank" rel="noreferrer">{s.title ?? s.url}</a><small>{[s.publisher, s.published_at?.slice(0, 10)].filter(Boolean).join(" ")}</small></li>)}</ul> : null}
  </header>;
}

/** 이슈 상세의 '리포트' 절: 이 이슈를 근거로 쓴 리포트 — 카드 그대로. */
export function IssueReports({ ideas }: { ideas: FeedIdea[] }) {
  if (!ideas.length) return null;
  return <section className="fd-dsec"><h2>리포트</h2><div className="fd-cards">{ideas.map((x) => <article key={x.idea_key} className="fd-rc-wrap">
    <Link href={`/ideas/${x.idea_key}`} className="fd-rc">
      <div className="fd-rc-row"><span className="fd-rc-name">{x.primary ? shortName(x.primary) : x.title}</span><span className="fd-rc-tk">{x.primary?.ticker ?? ""}</span><StarText n={x.stars}/><span className="fd-rc-go" aria-hidden="true">›</span></div>
      <h3>{x.title}</h3>
      <ValueBand v={x.valuation} facts={x.facts} stale={x.staleValuation}/>
    </Link></article>)}</div></section>;
}

/** 이슈 상세의 '관련 기업' 절: 수집기가 이슈에서 읽은 기업(방향·근거)과 경로 끝의 기업 — 모두 기업 위키로. */
export function IssueCompanies({ issue, paths, ideas }: { issue: Issue; paths: IssuePath[]; ideas: FeedIdea[] }) {
  const rows = new Map<string, { id: string; name: string; direction?: string; basis?: string | null; report?: FeedIdea }>();
  for (const c of issue.companies ?? []) rows.set(c.company_id, { id: c.company_id, name: shortName({ id: c.company_id, name: c.label ?? c.company_id }), direction: c.direction, basis: c.basis });
  for (const p of paths) if (p.company && !rows.has(p.company)) rows.set(p.company, { id: p.company, name: p.company_label ?? p.company, basis: p.claim });
  for (const x of ideas) { const r = rows.get(x.primary_company); if (r) r.report = x; }
  if (!rows.size) return null;
  const DIR: Record<string, string> = { "+": "수혜", "-": "피해", "±": "혼재" };
  return <section className="fd-dsec"><h2>관련 기업</h2>
    <ul className="cw-list">{[...rows.values()].map((r) => <li key={r.id}>
      <Link href={`/companies/${slug(r.id)}`}>{r.name}{r.direction && DIR[r.direction] ? <em className={`dir-${r.direction === "+" ? "up" : r.direction === "-" ? "down" : "mix"}`}>{DIR[r.direction]}</em> : null}<span>›</span></Link>
      {r.basis ? <small>{r.basis}</small> : null}
      {r.report ? <Link href={`/ideas/${r.report.idea_key}`} className="cw-rep">리포트{r.report.valuation ? ` ${pct(r.report.valuation.expected_upside_pct)}` : ""} ›</Link> : null}
    </li>)}</ul></section>;
}
