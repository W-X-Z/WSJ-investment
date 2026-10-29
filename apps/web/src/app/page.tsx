import Link from "next/link";
import { ReportCard } from "@/components/feed/Feed";
import { ECO_KO } from "@/lib/ideas";
import { loadFeed, onFeed, orderByValue, rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "리서치" };

type SP = { eco?: string };

/**
 * 홈 = 리서치 피드 (ADR-0023 개정). 기업마다 리포트 카드 하나: 기업 · 아이디어 제목·요지 · 값의 띠(목표주가·여력·약세~강세). 설명은 ? 에, 근거·시나리오·예측은 상세에.
 * 점수는 표면에 올리지 않는다 (ADR-0019).
 * 메인에는 ★2 이상이거나 여력이 큰 리포트만(onFeed). 나머지는 /ideas 의 '검토 중'. 순서는 상승여력 순 하나 (묶음 나누지 않는다).
 */
export default async function Home({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const feed = await loadFeed();
  const eco = sp.eco && ECO_KO[sp.eco] ? sp.eco : undefined;
  const pool = feed.ideas.filter((x) => !eco || x.ecosystems.includes(eco));
  const ideas = orderByValue(pool.filter(onFeed));
  const held = pool.length - ideas.length;
  const valued = ideas.filter((x) => x.valuation).length;
  return <div className="fd">
    <header className="fd-head">
      <h1>리서치</h1>
      <p className="fd-summary">리포트 {ideas.length} · 목표주가 {valued}{feed.updatedAt ? ` · ${rel(feed.updatedAt)} 갱신` : ""}</p>
      <nav className="fd-tabs" aria-label="생태계">
        <Link className={!eco ? "on" : ""} href="/">전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={eco === k ? "on" : ""} href={`/?eco=${k}`}>{v}</Link>)}
      </nav>
    </header>

    {!ideas.length ? <p className="fd-empty">조건에 맞는 리포트가 없습니다.</p> : null}
    {ideas.length ? <section className="fd-sec">
      <div className="fd-cards">{ideas.map((x) => <ReportCard key={x.idea_key} idea={x}/>)}</div>
    </section> : null}

    {held ? <p className="fd-held"><Link href="/ideas">검토 중인 가설 {held}</Link></p> : null}
    {feed.source === "seed" ? <p className="fd-empty">시드 데이터</p> : null}
  </div>;
}
