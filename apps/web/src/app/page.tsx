import Link from "next/link";
import { IdeaTable, StoryCard, Timeline } from "@/components/feed/Feed";
import { ECO_KO } from "@/lib/ideas";
import { loadFeed, orderIdeas, rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "오늘의 피드" };

type SP = { eco?: string };

/**
 * 홈 = 오늘의 피드 (ADR-0016 개정 3).
 * 1) 바뀐 아이디어 — 결론부터 (Axios 식 한 화면: 제목·두 문장·왜 지금·기업)
 * 2) 무슨 일이 있었나 — 확인된 기업 소식과 업계 이슈를 날짜별로, 연결된 아이디어로 화살표
 * 3) 모든 아이디어 — 관심 종목표처럼 한 줄씩 (★ → 기업 근거가 새로운 순)
 */
export default async function Home({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const feed = await loadFeed();
  const eco = sp.eco && ECO_KO[sp.eco] ? sp.eco : undefined;
  const ideas = orderIdeas(feed.ideas.filter((x) => !eco || x.ecosystems.includes(eco)));
  const keys = new Set(ideas.map((x) => x.idea_key));
  const timeline = feed.timeline.filter((x) => !eco || (x.kind === "issue" ? x.ecosystem === eco : x.ideaKeys.some((k) => keys.has(k)))).slice(0, 30);
  const since = Date.now() - 36 * 36e5;
  // 바뀐 아이디어: 최근 36시간의 새로·기업 근거 강화·약화. 기업 근거 강화 → 새로 → 약화 순, 같은 무리 안에서는 최근 갱신 순. 다섯 개까지.
  const rank: Record<string, number> = { strengthened: 0, new: 1, weakened: 2 };
  const changed = ideas.filter((x) => new Date(x.updated_at).getTime() >= since && x.shownTrend && x.shownTrend in rank)
    .sort((a, b) => rank[a.shownTrend!] - rank[b.shownTrend!] || b.stars - a.stars || b.updated_at.localeCompare(a.updated_at));
  const lead = changed.length ? changed.slice(0, 5) : ideas.slice(0, 3);
  const count = (t: string) => changed.filter((x) => x.shownTrend === t).length;
  const events = feed.timeline.filter((x) => x.kind === "event").length;
  const issues = feed.timeline.filter((x) => x.kind === "issue").length;
  const industryOnly = ideas.filter((x) => new Date(x.updated_at).getTime() >= since && x.shownTrend === "industry").length;
  const summary = [count("new") && `새 아이디어 ${count("new")}`, count("strengthened") && `기업 근거로 강화 ${count("strengthened")}`,
    count("weakened") && `약화 ${count("weakened")}`, industryOnly && `업계 근거만 갱신 ${industryOnly}`,
    events && `확인된 기업 소식 ${events}`, issues && `업계 이슈 ${issues}`].filter(Boolean).join(" · ");
  return <div className="fd">
    <header className="fd-head">
      <div className="page-kicker">오늘의 피드</div>
      <h1>무엇이 바뀌었고, 어디에 기회가 있나</h1>
      <p className="fd-summary">{summary || "어제 이후 바뀐 아이디어가 없습니다"}{feed.updatedAt ? ` — 아이디어 ${rel(feed.updatedAt)} 갱신` : ""}</p>
      <nav className="fd-tabs" aria-label="생태계">
        <Link className={!eco ? "on" : ""} href="/">전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={eco === k ? "on" : ""} href={`/?eco=${k}`}>{v}</Link>)}
      </nav>
    </header>

    <section className="fd-sec">
      <h2>{changed.length ? "바뀐 아이디어" : "주목할 아이디어"}<small>{changed.length ? "최근 36시간 · 기업 근거로 강화 · 새로 · 약화" : "★ 높은 순"}</small></h2>
      <div className="fd-stories">{lead.length ? lead.map((x) => <StoryCard key={x.idea_key} idea={x}/>) : <p className="fd-empty">조건에 맞는 아이디어가 없습니다.</p>}</div>
      {changed.length > lead.length ? <p className="fd-more">나머지 {changed.length - lead.length}건은 아래 ‘모든 아이디어’에 있습니다.</p> : null}
    </section>

    <section className="fd-sec">
      <h2>무슨 일이 있었나<small>원문을 확인한 기업 소식 · 업계 이슈(★2 이상) · 최근 5일</small></h2>
      <Timeline items={timeline} ideas={feed.ideas}/>
    </section>

    <section className="fd-sec">
      <h2>모든 아이디어<small>{ideas.length}건 · ★ → 기업 근거가 새로운 순</small></h2>
      <IdeaTable ideas={ideas}/>
    </section>

    <footer className="fd-footer">
      <span>근거 데이터</span>
      <Link href="/feed">이슈 전체</Link><Link href="/indicators">가격·실적 지표</Link><Link href="/map">공급망 그래프</Link><Link href="/discovery">공급사 발굴</Link>
      <em>투자 판단을 돕는 정리이며 매수·매도 권유가 아닙니다.{feed.source === "seed" ? " · 시드 데이터" : ""}</em>
    </footer>
  </div>;
}
