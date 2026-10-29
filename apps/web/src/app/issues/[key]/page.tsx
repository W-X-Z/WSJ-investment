import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { IssueCompanies, IssueHead, IssueReports, PathLine } from "@/components/issues/IssueCards";
import { PathGraph } from "@/components/issues/PathGraph";
import { loadFeed } from "@/lib/feed";
import { ideasByIssue, issueGraph, loadIssue, loadIssueHypotheses } from "@/lib/issues";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const issue = await loadIssue((await params).key);
  return { title: issue?.title ?? "이슈" };
}

/** 이슈 상세 (ADR-0023 개정 2): 이슈 → 영향 경로(가중치 그래프 + 가설 경로) → 리포트 → 관련 기업(위키로). */
export default async function IssueDetail({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const issue = await loadIssue(key);
  if (!issue) notFound();
  const [hyps, feed] = await Promise.all([loadIssueHypotheses([key]), loadFeed()]);
  const paths = hyps.get(key)?.paths ?? [];
  const linked = ideasByIssue(feed.ideas).get(key) ?? [];
  const byCo = new Map(feed.ideas.map((x) => [x.primary_company, x]));
  const g = issueGraph(issue, paths, new Map(feed.ideas.map((x) => [x.primary_company, x.idea_key])));
  return <div className="fd fd-detail">
    <div className="breadcrumb"><Link href="/issues">이슈</Link><Icon name="chevron-right" size={13}/><span>{issue.title}</span></div>
    <IssueHead issue={issue}/>
    {g.nodes.length || paths.length ? <section className="fd-dsec">
      <h2>영향 경로</h2>
      {g.nodes.length ? <PathGraph g={g}/> : null}
      {paths.length ? <ul className="fd-ic-paths">{paths.map((p) => <PathLine key={p.id} p={p} idea={p.company ? byCo.get(p.company) : null}/>)}</ul> : null}
    </section> : null}
    <IssueReports ideas={linked}/>
    <IssueCompanies issue={issue} paths={paths} ideas={linked}/>
  </div>;
}
