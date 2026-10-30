import { OppCard } from "@/components/opps/Opps";
import { loadOpportunities } from "@/lib/opportunities";
import { rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "투자 아이디어" };

/** 홈 = 투자 아이디어 (ADR-0028): ★ 높은 순. 카드에는 ★ · 기업 · 제목 · 한 줄 요지만. */
export default async function Home() {
  const items = await loadOpportunities();
  const latest = items.map((x) => x.published_at ?? x.updated_at).sort().at(-1);
  return <div className="fd op">
    <header className="fd-head">
      <h1>투자 아이디어</h1>
      <p className="fd-summary">{items.length}개{latest ? ` · ${rel(latest)} 갱신` : ""}</p>
    </header>
    {items.length ? <div className="op-list">{items.map((o) => <OppCard key={o.opportunity_key} o={o}/>)}</div>
      : <p className="fd-empty">아직 낸 아이디어가 없습니다.</p>}
  </div>;
}
