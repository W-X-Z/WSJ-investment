import { CommandCenter } from "@/components/CommandCenter";
import { IndicatorMovers } from "@/components/Indicators";
import { ECOSYSTEMS, loadIndicators, loadLiveData, mergeFeed, mergeIdeas, seed } from "@/lib/research";

export const dynamic = "force-dynamic";
export const metadata = { title: "Signal Atlas | 기술 변화와 투자 기회" };

export default async function Home() {
 const [live, ind] = await Promise.all([loadLiveData(), loadIndicators()]);
 const stories = mergeFeed(live);
 const ideas = mergeIdeas(live);
 return <CommandCenter
  stories={stories}
  ideas={ideas}
  ecosystems={ECOSYSTEMS.map(({id,title,summary,bottleneck,trajectory,metric,metricLabel})=>({id,title,summary,bottleneck,trajectory,metric,metricLabel}))}
  sourceOnline={live.online}
  asOf={seed.as_of}
  indicators={ind.indicators.length ? <IndicatorMovers rows={ind.indicators} points={ind.points}/> : null}
 />;
}
