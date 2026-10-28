import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { IssueCard } from "@/components/issues/IssueCards";
import { PathGraph } from "@/components/issues/PathGraph";
import { loadIdeas, loadValuations } from "@/lib/ideas";
import { ideasByIssue, issueGraph, loadIssue, loadIssueHypotheses } from "@/lib/issues";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const issue = await loadIssue((await params).key);
  return { title: issue?.title ?? "이슈" };
}

/** 이슈 상세: 카드의 전체 판(요약·의미·경로·연결 리포트·출처) + 온톨로지 그래프(변화 → 병목·기술 → 부품·공정·장비 → 기업, 가설 경로는 굵게). */
export default async function IssueDetail({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const issue = await loadIssue(key);
  if (!issue) notFound();
  const [hyps, { ideas }, valuations] = await Promise.all([loadIssueHypotheses([key]), loadIdeas(), loadValuations()]);
  const paths = hyps.get(key)?.paths ?? [];
  const reportByCompany = new Map(ideas.map((x) => [x.primary_company, x.idea_key]));
  const g = issueGraph(issue, paths, reportByCompany);
  return <div className="fd fd-detail">
    <div className="breadcrumb"><Link href="/issues">이슈</Link><Icon name="chevron-right" size={13}/><span>{issue.title}</span></div>
    <IssueCard issue={issue} hyp={hyps.get(key)} ideas={ideasByIssue(ideas).get(key) ?? []} valuations={valuations} detail/>
    {g.nodes.length ? <section className="fd-dsec"><h2>공급망 그래프</h2><PathGraph g={g}/></section> : null}
  </div>;
}
