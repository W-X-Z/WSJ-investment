import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/components/Icon";
import { IssueCard } from "@/components/issues/IssueCards";
import { loadIdeas, loadValuations } from "@/lib/ideas";
import { ideasByIssue, loadIssue, loadIssueHypotheses } from "@/lib/issues";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const issue = await loadIssue((await params).key);
  return { title: issue?.title ?? "이슈" };
}

/** 이슈 상세: 카드의 전체 판 — 요약 · 공급망에서의 의미 · 태깅 노드 · 영향 경로 ≤3 · 연결된 리포트 · 출처. */
export default async function IssueDetail({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const issue = await loadIssue(key);
  if (!issue) notFound();
  const [hyps, { ideas }, valuations] = await Promise.all([loadIssueHypotheses([key]), loadIdeas(), loadValuations()]);
  return <div className="fd fd-detail">
    <div className="breadcrumb"><Link href="/issues">이슈</Link><Icon name="chevron-right" size={13}/><span>{issue.title}</span></div>
    <IssueCard issue={issue} hyp={hyps.get(key)} ideas={ideasByIssue(ideas).get(key) ?? []} valuations={valuations} detail/>
    <footer className="fd-footer"><span>더 보기</span><Link href="/issues">이슈 피드</Link><Link href="/">리서치</Link><em>영향 경로는 모형의 가설이며 매수·매도 권유가 아닙니다.</em></footer>
  </div>;
}
