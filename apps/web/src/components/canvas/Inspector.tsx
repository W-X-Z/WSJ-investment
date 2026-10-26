"use client";

import { memo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { KINDS, RELATIONS, seed } from "@/lib/research-client";
import { ECO_NAME, SIZE_NAME, TIER_NAME, ecoOf, edgeIndex, edgesByNode, epistemic, isSmallCap, nodeIndex, safeUrl, type Scope } from "./graph-model";

const NodeExtras = dynamic(() => import("./NodeExtras"), {
  ssr: false,
  loading: () => <p className="sc-extras-loading">영향 기업 · 근거 자료 불러오는 중…</p>,
});

type Props = {
  nodeId: string | null;
  edgeId: string | null;
  scope: Scope;
  onSelectNode: (id: string) => void;
  onSelectEdge: (id: string) => void;
  onExpand: () => void;
  onClose: () => void;
};

function InspectorView({ nodeId, edgeId, scope, onSelectNode, onSelectEdge, onExpand, onClose }: Props) {
  const edge = edgeId ? edgeIndex.get(edgeId) : undefined;
  const node = !edge && nodeId ? nodeIndex.get(nodeId) : undefined;
  return <aside className="sc-inspector" aria-label="노드·관계 검증 패널">
    <div className="sc-inspector-top">
      <div><small>NODE / RELATION INSPECTOR</small><strong>연결과 원문 검증</strong></div>
      <button type="button" title="패널 닫기" aria-label="검증 패널 닫기" onClick={onClose}><Icon name="x" size={17}/></button>
    </div>
    {edge ? <div className="sc-inspector-content">
      <span className="sc-inspector-kicker">RELATIONSHIP · {RELATIONS[edge.relation] ?? edge.relation}</span>
      <h3 className="sc-edge-title">
        <button type="button" onClick={() => onSelectNode(edge.from)}>{nodeIndex.get(edge.from)?.label ?? edge.from}</button>
        <span aria-hidden>→</span>
        <button type="button" onClick={() => onSelectNode(edge.to)}>{nodeIndex.get(edge.to)?.label ?? edge.to}</button>
      </h3>
      <span className={`sc-evidence-class sc-evidence-${epistemic(edge)}`}>
        {TIER_NAME[edge.evidence_tier] ?? edge.evidence_tier} · 신뢰도 {Math.round((edge.confidence ?? 0) * 100)}%
        {edge.polarity !== "positive" ? ` · ${edge.polarity === "negative" ? "부정" : "조건부"}` : ""}
      </span>
      {edge.note && <p>{edge.note}</p>}
      <h4>출처 및 검증 근거</h4>
      {edge.evidence.length ? edge.evidence.map((src, i) => {
        const url = safeUrl(src.url);
        const meta = [src.source_type ? TIER_NAME[src.source_type] ?? src.source_type : null, src.published_at?.slice(0, 10)].filter(Boolean).join(" · ");
        return url
          ? <a className="sc-source-card" target="_blank" rel="noreferrer noopener" key={i} href={url.href}><Icon name="external" size={15}/><span>{url.hostname}<small>{meta || url.href}</small></span></a>
          : <div className="sc-source-card" key={i}><Icon name="file" size={15}/><span>{src.url}<small>{meta || "링크 아님"}</small></span></div>;
      }) : <p>연결된 원문이 없습니다 — 기술적 추론으로만 남아 있는 관계입니다.</p>}
    </div> : node ? <div className="sc-inspector-content">
      <span className="sc-inspector-kicker">{KINDS[node.kind] ?? node.kind} · {(ecoOf(node) ? ECO_NAME[ecoOf(node)!] : "NETWORK")}{node.also_in?.length ? ` + ${node.also_in.map((x) => x.toUpperCase()).join(", ")}` : ""}</span>
      <h3>{node.label}</h3>
      {node.kind === "company" && <div className="sc-company-chips">
        {node.listing?.ticker ? <span>{node.listing.ticker}{node.listing.exchange ? ` · ${node.listing.exchange}` : ""}</span> : <span>비상장 / 비SEC</span>}
        {node.size_band && <span className={isSmallCap(node) ? "is-small" : ""}>{isSmallCap(node) ? "★ " : ""}{SIZE_NAME[node.size_band] ?? node.size_band}</span>}
        {node.role && <span>{node.role === "customer" ? "수요처" : node.role === "both" ? "공급·수요" : "공급사 후보"}</span>}
        {node.in_universe && <span>유니버스 편입</span>}
      </div>}
      <div className="sc-inspector-stats"><span><b>{edgesByNode.get(node.id)?.length ?? 0}</b> 연결 관계</span><span><b>{node.measured_metrics?.length ?? 0}</b> 검증 지표</span></div>
      {node.measured_metrics?.length ? <><h4>관측해야 할 물리량</h4><div className="sc-metrics">{node.measured_metrics.map((m) => <span key={m}>{m.replaceAll("_", " ")}</span>)}</div></> : null}
      <h4>직접 연결된 기술 관계</h4>
      <div className="sc-related-edges">{(edgesByNode.get(node.id) ?? []).map((e) => {
        const other = nodeIndex.get(e.from === node.id ? e.to : e.from);
        return <button key={e.id} type="button" onClick={() => onSelectEdge(e.id)}>
          <span className={`sc-small-mark sc-mark-${epistemic(e)}`}/>
          <div><span>{e.from === node.id ? "→ " : "← "}{RELATIONS[e.relation] ?? e.relation}{e.polarity === "negative" ? " (부정)" : e.polarity === "conditional" ? " (조건부)" : ""}</span><strong>{other?.label}</strong></div>
          <Icon name="chevron-right" size={14}/>
        </button>;
      })}</div>
      <NodeExtras nodeId={node.id} scope={scope}/>
      <div className="sc-inspector-actions">
        <button type="button" onClick={onExpand}><Icon name="network" size={15}/> 이 노드 중심으로 펼치기</button>
        <Link href={`/search?q=${encodeURIComponent(node.label)}`}><Icon name="search" size={15}/> 전체 근거 검색</Link>
      </div>
    </div> : <div className="sc-inspector-content sc-empty-inspector">
      <Icon name="network" size={28}/><h3>노드를 선택하세요</h3><p>관계·근거·영향 기업을 봅니다.</p>
      <div><span>{seed.nodes.length}개 기술·기업 노드</span><span>공식 근거 / 기술 추론 분리</span><span>1–3단계 연결 강조</span></div>
    </div>}
  </aside>;
}

export const Inspector = memo(InspectorView);
