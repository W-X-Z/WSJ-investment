import { IndicatorTable } from "@/components/Indicators";
import { INDICATOR_GROUPS, loadIndicators } from "@/lib/research";

export const dynamic = "force-dynamic";
export const metadata = { title: "가격·실적 지표" };

export default async function IndicatorsPage() {
  const { indicators, points } = await loadIndicators();
  return <div>
    <div className="page-head"><div><div className="page-kicker">SUPPLY CHAIN INDICATORS</div><h1>가격·실적 지표</h1>
      <p>메모리 현물가, 대만 공급사 월매출, 미국 PPI·원자재. 임계치를 넘는 변화는 이슈 피드 후보가 됩니다.</p></div></div>
    {INDICATOR_GROUPS.map((g) => {
      const rows = indicators.filter((r) => g.cats.includes(r.category));
      return <section key={g.id} className="surface ind-section" id={g.id}>
        <div className="ind-section-head"><h2>{g.title}</h2><span>{rows.length}개</span></div>
        {rows.length ? <IndicatorTable rows={rows} points={points}/> : <p className="ind-empty">수집 전입니다.</p>}
      </section>;
    })}
  </div>;
}
