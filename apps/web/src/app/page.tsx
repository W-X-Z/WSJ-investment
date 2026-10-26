import { CommandCenter } from "@/components/CommandCenter";
import { ECOSYSTEMS, loadLiveData, mergeFeed, mergeIdeas, seed } from "@/lib/research";

export const dynamic = "force-dynamic";
export const metadata = { title: "Signal Atlas | 기술 변화와 투자 기회" };

export default async function Home() {
 const live = await loadLiveData();
 const stories = mergeFeed(live);
 const ideas = mergeIdeas(live);
 return <CommandCenter
  stories={stories}
  ideas={ideas}
  ecosystems={ECOSYSTEMS.map(({id,title,summary,bottleneck,trajectory,metric,metricLabel})=>({id,title,summary,bottleneck,trajectory,metric,metricLabel}))}
  sourceOnline={live.online}
  asOf={seed.as_of}
 />;
}
