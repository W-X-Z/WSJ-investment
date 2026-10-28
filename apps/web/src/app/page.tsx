import Link from "next/link";
import { IdeaCard } from "@/components/feed/Feed";
import { ECO_KO } from "@/lib/ideas";
import { loadFeed, orderByValue, rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "오늘의 피드" };

type SP = { eco?: string };

/**
 * 홈 = 오늘의 피드. 아이디어마다 카드 하나: 제목 · 가치평가 결과(현재 → 기대 주가, 상승여력, 확신) · 관련 기업 · 생성일 · 관련 이슈.
 * 논리·근거·반대 근거·시나리오는 아이디어 상세에 있다 — 피드는 훑어보는 곳이라 설명을 싣지 않는다. 점수는 표면에 올리지 않는다 (ADR-0019).
 * 순서: 최근 36시간에 새로·강화·약화된 아이디어 → 나머지. 각 묶음 안에서는 기대 상승여력 순(평가 없는 아이디어는 뒤에 ★ 순).
 */
export default async function Home({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const feed = await loadFeed();
  const eco = sp.eco && ECO_KO[sp.eco] ? sp.eco : undefined;
  const ideas = orderByValue(feed.ideas.filter((x) => !eco || x.ecosystems.includes(eco)));
  const since = Date.now() - 36 * 36e5;
  const isChanged = (x: (typeof ideas)[number]) => new Date(x.updated_at).getTime() >= since && ["new", "strengthened", "weakened"].includes(x.shownTrend ?? "");
  const changed = ideas.filter(isChanged);
  const rest = ideas.filter((x) => !isChanged(x));
  return <div className="fd">
    <header className="fd-head">
      <h1>오늘의 피드</h1>
      <p className="fd-summary">아이디어 {ideas.length}건{changed.length ? ` · 최근 바뀐 ${changed.length}건` : ""}{feed.updatedAt ? ` · ${rel(feed.updatedAt)} 갱신` : ""}</p>
      <nav className="fd-tabs" aria-label="생태계">
        <Link className={!eco ? "on" : ""} href="/">전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={eco === k ? "on" : ""} href={`/?eco=${k}`}>{v}</Link>)}
      </nav>
    </header>

    {!ideas.length ? <p className="fd-empty">조건에 맞는 아이디어가 없습니다.</p> : null}
    {changed.length ? <section className="fd-sec">
      <h2>최근 바뀐 아이디어</h2>
      <div className="fd-cards">{changed.map((x) => <IdeaCard key={x.idea_key} idea={x} changed/>)}</div>
    </section> : null}
    {rest.length ? <section className="fd-sec">
      {changed.length ? <h2>나머지 아이디어</h2> : null}
      <div className="fd-cards">{rest.map((x) => <IdeaCard key={x.idea_key} idea={x} changed={false}/>)}</div>
    </section> : null}

    <footer className="fd-footer">
      <span>더 보기</span>
      <Link href="/feed">이슈 전체</Link><Link href="/bottlenecks">병목 보드</Link><Link href="/indicators">가격·실적 지표</Link><Link href="/map">공급망 그래프</Link>
      <em>투자 판단을 돕는 정리이며 매수·매도 권유가 아닙니다.{feed.source === "seed" ? " · 시드 데이터" : ""}</em>
    </footer>
  </div>;
}
