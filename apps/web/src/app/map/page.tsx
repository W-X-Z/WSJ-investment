import Link from "next/link";
import { Icon } from "@/components/Icon";
import { SupplyNetworkCanvas } from "@/components/SupplyNetworkCanvas";

export const metadata={title:"산업망 탐색 캔버스 | Signal Atlas"};
type Params={eco?:string;focus?:string};
export default async function TechnologyMap({searchParams}:{searchParams:Promise<Params>}) {
 const params=await searchParams;
 const scope=params.eco==="hbm"||params.eco==="optics"||params.eco==="power"?params.eco:"all";
 return <div className="map-screen">
   <div className="map-screen-header"><div><span className="page-kicker">TECHNOLOGY DEPENDENCY CANVAS</span><h1>산업망 캔버스</h1><p>소재·부품·공정·설비·기술적 병목·공급망 기업의 연결을 자유롭게 탐색합니다.</p></div><div className="map-screen-actions"><Link href="/ecosystems"><Icon name="layers" size={16}/> 분야별 연구</Link><Link href="/history"><Icon name="archive" size={16}/> 과거 자료</Link></div></div>
   <SupplyNetworkCanvas initialEcosystem={scope} initialFocus={params.focus??null}/>
 </div>;
}
