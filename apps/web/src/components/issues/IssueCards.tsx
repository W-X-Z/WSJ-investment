import Link from "next/link";
import { ECO_CLASS, StarText } from "@/components/feed/Feed";
import { pct, type InvestmentIdea, type Valuation } from "@/lib/ideas";
import { EVENT_TYPE_KO, issueDate, nodeLabel, type Issue, type IssueHypotheses, type IssuePath } from "@/lib/issues";

const md = (d?: string | null) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "");
/** 수집기의 중요도(1~10) → ★ 1~3. */
export const issueStars = (i: Issue) => i.stars ?? (i.importance >= 8 ? 3 : i.importance >= 6 ? 2 : 1);

/** 영향 경로 한 줄: 노드 사슬 → 주장. 기업이 붙은 경로는 색 테두리, 리포트가 있으면 그 링크. 말은 최소로. */
export function PathLine({ p, idea, valuation }: { p: IssuePath; idea?: InvestmentIdea | null; valuation?: Valuation | null }) {
  const labels = p.path_labels?.length ? p.path_labels : p.path.map(nodeLabel);
  return <li className={`fd-ip ${p.company ? "co" : "ind"}${p.selected ? " sel" : ""}`}>
    <p className="fd-ip-path">{labels.map((l, i) => <span key={i}>{i ? <i>→</i> : null}{l}</span>)}</p>
    <p className="fd-ip-claim">{p.claim}</p>
    {idea ? <Link href={`/ideas/${idea.idea_key}`} className="fd-ip-link">{p.company_label ?? p.company}{valuation ? <b className={valuation.expected_upside_pct >= 0 ? "up" : "down"}>{pct(valuation.expected_upside_pct)}</b> : null}<span>›</span></Link>
      : p.company ? <span className="fd-ip-co">{p.company_label ?? p.company}{p.selected ? " · 리포트 작성 중" : ""}</span> : null}
  </li>;
}

/** 이슈 카드: 날짜 · 유형 · ★ → 제목 → 의미 → 경로 → 연결 리포트. 카드는 생태계 색 띠로 묶인다. */
export function IssueCard({ issue, hyp, ideas, valuations, detail }: { issue: Issue; hyp?: IssueHypotheses | null; ideas: InvestmentIdea[];
  valuations: Map<string, Valuation>; detail?: boolean }) {
  const href = `/issues/${issue.issue_key}`;
  const paths = (hyp?.paths ?? []).slice(0, 3);
  const ideaByCompany = new Map(ideas.map((x) => [x.primary_company, x]));
  const linked = ideas.filter((x) => !paths.some((p) => p.company === x.primary_company));
  const nodes = (issue.nodes ?? []).slice(0, 4);
  const Title = detail ? "h1" : "h3";
  return <article className={`fd-ic ${ECO_CLASS[issue.ecosystem ?? ""] ?? ""}${detail ? " fd-ic-detail" : ""}`}>
    <header className="fd-ic-top">
      <time dateTime={issueDate(issue) ?? undefined}>{md(issueDate(issue))}</time>
      {issue.event_type ? <span>{EVENT_TYPE_KO[issue.event_type] ?? issue.event_type}</span> : null}
      <StarText n={issueStars(issue)}/>
      {!detail ? <Link href={href} className="fd-ic-go" aria-label="이슈 상세">›</Link> : null}
    </header>
    <Title>{detail ? issue.title : <Link href={href}>{issue.title}</Link>}</Title>
    {detail && issue.summary ? <p className="fd-ic-sum">{issue.summary}</p> : null}
    {issue.why_it_matters ? <p className="fd-ic-why">{issue.why_it_matters}</p> : null}
    {nodes.length && !detail ? <p className="fd-ic-nodes">{nodes.map((n) => <span key={n}>{nodeLabel(n)}</span>)}</p> : null}
    {paths.length ? <ul className="fd-ic-paths">{paths.map((p) => <PathLine key={p.id} p={p} idea={p.company ? ideaByCompany.get(p.company) : null}
      valuation={p.company && ideaByCompany.get(p.company) ? valuations.get(ideaByCompany.get(p.company)!.idea_key) : null}/>)}</ul> : null}
    {linked.length ? <p className="fd-ic-ideas">{linked.map((x) => {
      const v = valuations.get(x.idea_key);
      return <Link key={x.idea_key} href={`/ideas/${x.idea_key}`}>{x.companies.find((c) => c.id === x.primary_company)?.name ?? x.title}
        {v ? <b className={v.expected_upside_pct >= 0 ? "up" : "down"}>{pct(v.expected_upside_pct)}</b> : null}<span>›</span></Link>;
    })}</p> : null}
    {detail && issue.sources?.length ? <ul className="fd-ic-src">{issue.sources.slice(0, 8).map((s, i) => <li key={i}>
      <a href={s.url} target="_blank" rel="noreferrer">{s.title ?? s.url}</a><small>{[s.publisher, s.published_at?.slice(0, 10)].filter(Boolean).join(" ")}</small></li>)}</ul> : null}
  </article>;
}
