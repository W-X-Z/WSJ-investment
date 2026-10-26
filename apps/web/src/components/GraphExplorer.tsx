"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ECO_BY_ID, KINDS, RELATIONS, seed, type EcoId, type GraphNode } from "@/lib/research-client";

const COLUMNS: Record<EcoId, string[][]> = {
  hbm: [
    ["req:hbm_io","req:hbm_stack"],
    ["bottleneck:hbm_overlay","bottleneck:hbm_wafer_warpage","bottleneck:hbm_thermal"],
    ["process:microbump_metrology","tech:hybrid_bond","tech:hawk"],
    ["company:camt"],
  ],
  optics: [
    ["req:1p6t"],
    ["bottleneck:optic_coupling","bottleneck:optic_power","bottleneck:optic_ber"],
    ["tech:poet_interposer","tech:lessengers_dow","tech:cpo"],
    ["company:poet","company:lessengers"],
  ],
  power: [
    ["req:800v","req:highdensity"],
    ["bottleneck:conversion","bottleneck:dc_protection","bottleneck:copper"],
    ["tech:sidecar","tech:directmv","tech:sic","tech:busbar"],
    ["company:aehr"],
  ],
};
const COL_LABEL = ["TECHNOLOGY SHIFT","NEW BOTTLENECK","SOLUTION LAYER","COMPANY EXPOSURE"];

function NodeButton({ node, active, related, onClick }: {
  node: GraphNode; active: boolean; related: boolean; onClick: () => void
}) {
  return <button type="button" onClick={onClick} aria-pressed={active}
    className={`graph-node graph-node-${node.kind} ${active?"graph-node-active":""} ${related?"graph-node-related":""}`}>
    <span className="graph-node-bullet"/>
    <span className="graph-node-label">{node.label}</span>
    <Icon name="chevron-right" size={13} className="graph-node-arrow"/>
  </button>;
}

export function GraphExplorer({ ecoId, compact=false }: { ecoId: EcoId; compact?: boolean }) {
  const groups = COLUMNS[ecoId];
  const [selected, setSelected] = useState<string>(groups[1]?.[0] ?? groups[0][0]);
  const nodeMap = useMemo(()=>new Map(seed.nodes.map(node=>[node.id,node])),[]);
  const node = nodeMap.get(selected) ?? nodeMap.get(groups[0][0])!;
  const connected = seed.edges.filter(e=>e.from===selected || e.to===selected);
  const related = new Set(connected.map(e=>e.from===selected?e.to:e.from));
  const evidence = Array.from(new Set(connected.flatMap(e=>e.evidence.map(src=>src.url)))).slice(0,5);
  return <div className={`graph-explorer graph-explorer-${ecoId} ${compact?"graph-compact":""}`}>
    <div className="graph-visual">
      <div className="graph-heading"><span className="graph-heading-signal"><Icon name="network" size={15}/> SUPPLY CHAIN IMPACT MAP</span><span className="graph-heading-count">{groups.flat().length} nodes / focused view</span></div>
      <div className="graph-columns">
        {groups.map((column,i)=><div className="graph-column" key={i}>
          <div className="graph-col-label">{String(i+1).padStart(2,"0")} <span>{COL_LABEL[i]}</span></div>
          <div className="graph-col-nodes">
            {column.map(id=>{
              const n=nodeMap.get(id);
              return n?<NodeButton key={id} node={n} active={selected===id} related={related.has(id)} onClick={()=>setSelected(id)}/>:null;
            })}
          </div>
          {i<groups.length-1 && <span className="graph-col-chevron">›</span>}
        </div>)}
      </div>
      <div className="graph-footline"><span><i className="legend-dot legend-purple"/>선택된 기술</span><span><i className="legend-dot legend-teal"/>연결된 노드</span><span>엣지별 기술적 관계는 상세 패널에서 검증</span></div>
    </div>
    <div className="graph-inspector">
      <div className="inspector-overline">NODE INSPECTOR <Icon name="target" size={14}/></div>
      <div className="inspector-type">{KINDS[node.kind] ?? node.kind}</div>
      <h3>{node.label}</h3>
      {node.measured_metrics?.length ? <div className="inspector-metrics"><span>관측할 정량 지표</span>{node.measured_metrics.slice(0,4).map(m=><code key={m}>{m}</code>)}</div> :
        <p className="inspector-intro">이 노드는 기술 의존관계 분석용 연구 항목입니다. 기업 매출 또는 고객 채택 여부는 별도로 검증해야 합니다.</p>}
      <div className="inspector-subhead">연결 근거 <strong>{connected.length}</strong></div>
      <div className="inspector-edges">
        {connected.slice(0,3).map(e=><div key={e.id} className="inspector-edge">
          <div><span className="inspector-relation">{RELATIONS[e.relation] ?? e.relation}</span>
            <span className={`edge-state ${e.stage.includes("inference")||e.stage.includes("hypothesis")?"edge-inferred":""}`}>
            {e.stage.includes("inference")||e.stage.includes("hypothesis")?"추론":e.stage==="vendor_claim"?"기업 주장":"근거 연결"}</span>
          </div>
          <strong>{nodeMap.get(e.from===selected?e.to:e.from)?.label}</strong>
        </div>)}
        {!connected.length && <p className="soft-text">연결된 증거를 추가 조사 중입니다.</p>}
      </div>
      {evidence[0] && <a className="inspector-source" href={evidence[0]} target="_blank" rel="noreferrer"><Icon name="external" size={14}/> 참고 원문 확인 <Icon name="arrow-up-right" size={14}/></a>}
      <div className="inspector-disclaimer">연결 관계는 연구 가설을 포함하며 공급계약·매출의 확증이 아닙니다.</div>
      {compact && <Link href={`/ecosystems/${ecoId}`} className="inspector-deeplink">생태계 전체 보기 <Icon name="arrow-right" size={15}/></Link>}
    </div>
  </div>;
}

export function GraphTabs({ current }: {current: EcoId}) {
  return <div className="graph-tabs">
    {(["hbm","optics","power"] as EcoId[]).map(id=><Link key={id} href={`/ecosystems/${id}`} className={id===current?"graph-tab active":"graph-tab"}>
      <span className={`mini-signal mini-${ECO_BY_ID[id].color}`}/>{ECO_BY_ID[id].name}
    </Link>)}
  </div>;
}
