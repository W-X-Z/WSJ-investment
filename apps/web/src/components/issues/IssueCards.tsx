import Link from "next/link";
import { StarText } from "@/components/feed/Feed";
import { ECO_KO, money, pct, type InvestmentIdea, type Valuation } from "@/lib/ideas";
import { EVENT_TYPE_KO, issueDate, nodeLabel, type Issue, type IssueHypotheses, type IssuePath } from "@/lib/issues";

const md = (d?: string | null) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "");
/** 수집기의 중요도(1~10) → ★ 1~3 (이슈 피드의 눈금). */
export const issueStars = (i: Issue) => i.stars ?? (i.importance >= 8 ? 3 : i.importance >= 6 ? 2 : 1);

/** 영향 경로 한 줄 (ADR-0023): 변화 → 노드 → … → (기업). 기업이 붙은 경로는 리포트 후보, selected 면 리포트가 쓰였다. */
export function PathLine({ p, idea, valuation }: { p: IssuePath; idea?: InvestmentIdea | null; valuation?: Valuation | null }) {
  const labels = p.path_labels?.length ? p.path_labels : p.path.map(nodeLabel);
  return <li className={`fd-ip ${p.company ? "co" : "ind"}${p.selected ? " sel" : ""}`}>
    <p className="fd-ip-path">{labels.map((l, i) => <span key={i}>{i ? <i> → </i> : null}{l}</span>)}</p>
    <p className="fd-ip-claim">{p.claim}</p>
    <p className="fd-ip-meta">
      {p.company ? <span className="fd-ip-co">{p.company_label ?? p.company}{p.lead_quarters != null ? ` · ${p.lead_quarters}분기 뒤` : ""}{p.effect_pct != null ? ` · 매출 대비 ${pct(p.effect_pct)}` : ""}</span>
        : <span className="fd-ip-ind">업계 영향{p.effect_pct != null ? ` · ${pct(p.effect_pct)}` : ""}{p.lead_quarters != null ? ` · ${p.lead_quarters}분기 뒤` : ""}</span>}
      {p.falsifier ? <span className="fd-ip-f">반증: {p.falsifier}</span> : null}
      {idea ? <Link href={`/ideas/${idea.idea_key}`} className="fd-ip-link">리포트 보기{valuation ? ` · 목표주가 ${money(valuation.expected_price, valuation.currency)} (${pct(valuation.expected_upside_pct)})` : ""}</Link>
        : p.selected ? <span className="fd-ip-link muted">리포트 작성 중</span> : null}
    </p>
  </li>;
}

/** 이슈 카드: 날짜 · 생태계 · 유형 · ★ → 제목 → 공급망에서의 의미(why_it_matters) → 영향 경로 ≤3 → 연결된 리포트. */
export function IssueCard({ issue, hyp, ideas, valuations, detail }: { issue: Issue; hyp?: IssueHypotheses | null; ideas: InvestmentIdea[];
  valuations: Map<string, Valuation>; detail?: boolean }) {
  const href = `/issues/${issue.issue_key}`;
  const paths = (hyp?.paths ?? []).slice(0, 3);
  const ideaByCompany = new Map(ideas.map((x) => [x.primary_company, x]));
  const linked = ideas.filter((x) => !paths.some((p) => p.company === x.primary_company));
  const nodes = (issue.nodes ?? []).slice(0, 4);
  return <article className={`fd-ic${detail ? " fd-ic-detail" : ""}`}>
    <header className="fd-ic-top">
      <time dateTime={issueDate(issue) ?? undefined}>{md(issueDate(issue))}</time>
      <span>{[issue.ecosystem ? ECO_KO[issue.ecosystem] : null, issue.event_type ? EVENT_TYPE_KO[issue.event_type] ?? issue.event_type : null].filter(Boolean).join(" · ")}</span>
      <StarText n={issueStars(issue)}/>
      {issue.publisher_count ? <small>출처 {issue.publisher_count}곳</small> : null}
    </header>
    <h3>{detail ? issue.title : <Link href={href}>{issue.title}</Link>}</h3>
    {detail && issue.summary ? <p className="fd-ic-sum">{issue.summary}</p> : null}
    {issue.why_it_matters ? <p className="fd-ic-why"><b>공급망에서의 의미</b>{issue.why_it_matters}</p> : null}
    {nodes.length ? <p className="fd-ic-nodes">{nodes.map((n) => <Link key={n} href={`/map?focus=${encodeURIComponent(n)}`}>{nodeLabel(n)}</Link>)}</p> : null}
    {paths.length ? <div className="fd-ic-paths"><b>영향 경로<small>{hyp?.as_of ? ` ${md(hyp.as_of)} 가설` : ""} · 이슈당 최대 3개 · 기업이 붙은 경로가 리포트 후보</small></b>
      <ul>{paths.map((p) => <PathLine key={p.id} p={p} idea={p.company ? ideaByCompany.get(p.company) : null} valuation={p.company && ideaByCompany.get(p.company) ? valuations.get(ideaByCompany.get(p.company)!.idea_key) : null}/>)}</ul>
    </div> : detail ? <p className="fd-ic-none">영향 경로는 다음 아침 실행의 1단계 가설이 씁니다.</p> : null}
    {linked.length ? <p className="fd-ic-ideas"><b>이 이슈를 근거로 쓴 리포트</b>{linked.map((x) => {
      const v = valuations.get(x.idea_key);
      return <Link key={x.idea_key} href={`/ideas/${x.idea_key}`}>{x.companies.find((c) => c.id === x.primary_company)?.name ?? x.title}{v ? <small> {pct(v.expected_upside_pct)}</small> : null}</Link>;
    })}</p> : null}
    {detail && issue.sources?.length ? <ul className="fd-ic-src">{issue.sources.slice(0, 8).map((s, i) => <li key={i}>
      <a href={s.url} target="_blank" rel="noreferrer">{s.title ?? s.url}</a><small>{[s.publisher, s.published_at?.slice(0, 10)].filter(Boolean).join(" · ")}</small></li>)}</ul> : null}
  </article>;
}
