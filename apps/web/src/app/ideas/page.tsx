import Link from "next/link";
import { ReportCard } from "@/components/feed/Feed";
import { FEED_MIN_UPSIDE, loadFeed, onFeed, orderByValue } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "모든 리포트" };

/** 모든 활성 리포트: 메인에 오른 것과, 문턱(★2 이상 또는 여력 +30%)에 못 미쳐 검토 중인 가설. */
export default async function AllIdeas() {
  const feed = await loadFeed();
  const all = orderByValue(feed.ideas);
  const main = all.filter(onFeed), held = all.filter((x) => !onFeed(x));
  return <div className="fd">
    <header className="fd-head"><h1>모든 리포트</h1><p className="fd-summary">메인 {main.length} · 검토 중 {held.length}</p></header>
    {main.length ? <section className="fd-sec"><h2>메인</h2><div className="fd-cards">{main.map((x) => <ReportCard key={x.idea_key} idea={x}/>)}</div></section> : null}
    {held.length ? <section className="fd-sec"><h2>검토 중<small>★1 이고 여력 +{FEED_MIN_UPSIDE}% 미만이거나 목표주가 산출 전</small></h2><div className="fd-cards">{held.map((x) => <ReportCard key={x.idea_key} idea={x}/>)}</div></section> : null}
    <p className="fd-held"><Link href="/">리서치로</Link></p>
  </div>;
}
