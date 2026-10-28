import Link from "next/link";
import { ReportCard } from "@/components/feed/Feed";
import { ECO_KO } from "@/lib/ideas";
import { loadFeed, orderByValue, rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "리서치" };

type SP = { eco?: string };

/**
 * 홈 = 리서치 피드 (ADR-0023). 기업마다 리포트 요약 카드 하나: 기업 · 목표주가(12개월 확률가중, 약세~강세 범위) · 투자 아이디어(제목·요지) · 데이터 근거 2개 · 예측 상태.
 * 논리·시나리오 표·가정·반대 근거·출처는 상세에 있다. 점수는 표면에 올리지 않는다 (ADR-0019).
 * 순서: 최근 36시간에 새로·강화·약화된 리포트 → 나머지. 각 묶음 안에서는 상승여력 순(목표주가가 없는 리포트는 뒤에 ★ 순).
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
  const valued = ideas.filter((x) => x.valuation).length;
  return <div className="fd">
    <header className="fd-head">
      <h1>리서치</h1>
      <p className="fd-summary">리포트 {ideas.length}건 · 목표주가 {valued}건{changed.length ? ` · 최근 바뀐 ${changed.length}건` : ""}{feed.updatedAt ? ` · ${rel(feed.updatedAt)} 갱신` : ""}
        <span className="fd-summary-note"> — 미국·한국 상장사 · 이슈 → 공급망 경로 → 기업 숫자로 세운 가설과 12개월 목표주가</span></p>
      <nav className="fd-tabs" aria-label="생태계">
        <Link className={!eco ? "on" : ""} href="/">전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={eco === k ? "on" : ""} href={`/?eco=${k}`}>{v}</Link>)}
      </nav>
    </header>

    {!ideas.length ? <p className="fd-empty">조건에 맞는 리포트가 없습니다.</p> : null}
    {changed.length ? <section className="fd-sec">
      <h2>최근 바뀐 리포트<small>새 리포트 · 기업 근거로 강화 · 근거 약화</small></h2>
      <div className="fd-cards">{changed.map((x) => <ReportCard key={x.idea_key} idea={x} changed/>)}</div>
    </section> : null}
    {rest.length ? <section className="fd-sec">
      {changed.length ? <h2>나머지 리포트<small>상승여력 순</small></h2> : null}
      <div className="fd-cards">{rest.map((x) => <ReportCard key={x.idea_key} idea={x} changed={false}/>)}</div>
    </section> : null}

    <footer className="fd-footer">
      <span>더 보기</span>
      <Link href="/issues">최근 이슈</Link><Link href="/bottlenecks">병목 보드</Link><Link href="/indicators">가격·실적 지표</Link><Link href="/map">공급망 그래프</Link>
      <em>목표주가는 모형이 산출한 12개월 확률가중 기대 주가이며 매수·매도 권유가 아닙니다.{feed.source === "seed" ? " · 시드 데이터" : ""}</em>
    </footer>
  </div>;
}
