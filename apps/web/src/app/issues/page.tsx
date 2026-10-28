import Link from "next/link";
import { IssueCard } from "@/components/issues/IssueCards";
import { ECO_KO, loadIdeas, loadValuations } from "@/lib/ideas";
import { ideasByIssue, loadIssueHypotheses, loadIssues } from "@/lib/issues";
import { rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "이슈" };

type SP = { eco?: string; days?: string };

/**
 * 이슈 피드 (ADR-0023): 최근 공급망 이슈마다 — 무슨 일인가(제목·요약) · 공급망에서의 의미(why_it_matters) · 영향 경로 ≤3(1단계 가설, 기업이 붙으면 리포트 후보) · 이 이슈를 근거로 쓴 리포트.
 * 리서치 피드가 '기업'에서 출발한다면 여기는 '변화'에서 출발한다.
 */
export default async function IssuesPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const eco = sp.eco && ECO_KO[sp.eco] ? sp.eco : undefined;
  const days = sp.days === "30" ? 30 : 14;
  const [issuesAll, { ideas }, valuations] = await Promise.all([loadIssues(days, 5, 120), loadIdeas(), loadValuations()]);
  const issues = issuesAll.filter((i) => !eco || i.ecosystem === eco);
  const hyps = await loadIssueHypotheses(issues.map((i) => i.issue_key));
  const byIssue = ideasByIssue(ideas);
  const withPaths = issues.filter((i) => hyps.get(i.issue_key)?.paths.length);
  const latest = issuesAll[0]?.latest_published_at ?? issuesAll[0]?.first_seen ?? null;
  return <div className="fd">
    <header className="fd-head">
      <h1>이슈</h1>
      <p className="fd-summary">최근 {days}일 이슈 {issues.length}건 · 영향 경로가 있는 이슈 {withPaths.length}건{latest ? ` · 최신 ${rel(latest.slice(0, 10))}` : ""}
        <span className="fd-summary-note"> — 변화가 공급망의 어느 고리를 바꾸는지, 그 끝에 어느 기업이 있는지</span></p>
      <nav className="fd-tabs" aria-label="생태계">
        <Link className={!eco ? "on" : ""} href={`/issues${days === 30 ? "?days=30" : ""}`}>전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={eco === k ? "on" : ""} href={`/issues?eco=${k}${days === 30 ? "&days=30" : ""}`}>{v}</Link>)}
        <Link className={`fd-tabs-right${days === 30 ? " on" : ""}`} href={`/issues?days=30${eco ? `&eco=${eco}` : ""}`}>30일</Link>
      </nav>
    </header>
    {!issues.length ? <p className="fd-empty">최근 {days}일에 중요도 5 이상인 이슈가 없습니다.</p> : null}
    <div className="fd-ics">{issues.map((i) => <IssueCard key={i.issue_key} issue={i} hyp={hyps.get(i.issue_key)} ideas={byIssue.get(i.issue_key) ?? []} valuations={valuations}/>)}</div>
    <footer className="fd-footer">
      <span>더 보기</span>
      <Link href="/">리서치</Link><Link href="/feed">이슈 아카이브</Link><Link href="/bottlenecks">병목 보드</Link><Link href="/map">공급망 그래프</Link>
      <em>이슈는 공개 보도·공시에서 수집·요약한 것이며, 영향 경로는 모형의 가설입니다.</em>
    </footer>
  </div>;
}
