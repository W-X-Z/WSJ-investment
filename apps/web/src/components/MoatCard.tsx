import Link from "next/link";
import { Para, Section, Url } from "@/components/BriefBits";

type Any = Record<string, unknown>;
const S = (v: unknown) => (typeof v === "string" ? v : v === null || v === undefined ? "" : JSON.stringify(v));
const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const obj = (v: unknown): Any => (v && typeof v === "object" && !Array.isArray(v) ? (v as Any) : {});
const FIT: Record<string, string> = { product: "제품으로 판매", capability: "역량 보유", mention_only: "언급만" };
const MOAT: Record<string, string> = { ip: "IP·라이선스", process_knowhow: "공정 노하우", switching_cost: "전환비용", scale: "규모·비용", standard: "표준 선점", none: "없음" };

function Score({ label, v }: { label: string; v: unknown }) {
  const n = Number(v);
  return <div className="border border-neutral-200 rounded bg-white px-2 py-1"><div className="text-xs text-neutral-500">{label}</div><div className="font-mono text-lg">{Number.isFinite(n) ? `${n}/5` : "–"}</div></div>;
}

/** 해자 카드(kind='moat') 렌더. 브리프 JSON 스키마와 다르다 (wsj/briefs/moat.py). */
export function MoatCard({ card, nodes }: { card: Any; nodes: string[] }) {
  const moat = obj(card.moat); const cust = obj(card.customers); const fin = obj(card.financial_capture); const tim = obj(card.timing); const tb = obj(card.tenbagger_path); const sc = obj(card.scores);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
        <Score label="종합" v={sc.overall} /><Score label="해자" v={sc.moat} /><Score label="타이밍" v={sc.timing} /><Score label="재무" v={sc.financial} /><Score label="데이터 품질" v={sc.data_quality} />
      </div>
      {!!sc.rationale && <p className="text-xs text-neutral-600">{S(sc.rationale)}</p>}

      <Section title="공급망 위치" sub={nodes.length ? `온톨로지 노드: ${nodes.join(", ")}` : undefined}>
        {arr<Any>(card.position_in_chain).map((p, i) => (
          <div key={i} className="flex gap-2 items-baseline"><Link href={`/map?focus=${nodes[i] ?? ""}`} className="font-medium whitespace-nowrap">{S(p.node)}</Link><span className="text-xs rounded px-1.5 py-0.5 bg-neutral-100">{FIT[S(p.fit)] ?? S(p.fit)}</span><span className="text-neutral-600">{S(p.evidence)} <span className="text-xs text-neutral-400 whitespace-nowrap">({S(p.source)})</span></span></div>
        ))}
      </Section>

      <Section title={`해자 — ${(MOAT[S(moat.type)] ?? S(moat.type)) || "–"} (강도 ${S(moat.strength) || "–"}/5)`}>
        <ul className="list-disc pl-5">{arr<Any>(moat.evidence).map((e, i) => <li key={i}>{S(e.claim)} <span className="text-xs text-neutral-400">({S(e.source)})</span></li>)}</ul>
        {!!moat.what_breaks_it && <p><span className="text-neutral-500">깨지는 조건:</span> {S(moat.what_breaks_it)}</p>}
      </Section>

      <div className="grid md:grid-cols-2 gap-3">
        <Section title="고객 증거">
          <p><span className="text-neutral-500">공개 고객:</span> {arr<string>(cust.named).join(", ") || "없음"}</p>
          <p><span className="text-neutral-500">집중도:</span> {S(cust.concentration)}</p>
          {!!arr(cust.qualification_events).length && <p><span className="text-neutral-500">인증 이벤트:</span> {arr<string>(cust.qualification_events).join(" · ")}</p>}
          <p><span className="text-neutral-500">세대 전환 고객:</span> {S(cust.generation_customers)}</p>
        </Section>
        <Section title={`재무 포착 — ${S(fin.stage) || "–"}`}>
          <p><span className="text-neutral-500">매출 TTM:</span> {S(fin.revenue_ttm)} · <span className="text-neutral-500">성장:</span> {S(fin.revenue_growth)}</p>
          <p><span className="text-neutral-500">매출총이익률:</span> {S(fin.gross_margin)}</p>
          <p><span className="text-neutral-500">R&D 강도:</span> {S(fin.rnd_intensity)}</p>
          <p><span className="text-neutral-500">OCF·런웨이:</span> {S(fin.ocf_and_runway)} · <span className="text-neutral-500">희석:</span> {S(fin.dilution)}</p>
        </Section>
      </div>

      <Section title="타이밍">
        <p><span className="text-neutral-500">수요를 키우는 것:</span> {S(tim.demand_unlock)} <span className="font-mono text-xs">{S(tim.when)}</span></p>
        <p><span className="text-neutral-500">첫 증거:</span> {S(tim.first_evidence)}</p>
        <p><span className="text-neutral-500">위협 방향:</span> {S(tim.threat_direction)}</p>
      </Section>

      {!!arr(card.competition).length && (
        <Section title="경쟁">
          <table className="w-full text-sm"><tbody>{arr<Any>(card.competition).map((c, i) => <tr key={i} className="border-t border-neutral-100 align-top"><td className="py-1 pr-2 whitespace-nowrap font-medium">{S(c.name)}</td><td className="py-1 pr-2 text-xs text-neutral-500">{S(c.relative_size)}</td><td className="py-1">{S(c.position)}</td></tr>)}</tbody></table>
        </Section>
      )}

      <Section title={`텐배거 경로 — ${S(tb.feasibility) || "–"}`}>
        <p>{S(tb.current_market_cap)} → {S(tb.target_market_cap)} · {S(tb.years)}년 · 희석 {S(tb.dilution_assumption)}</p>
        <p><span className="text-neutral-500">필요 매출·배수:</span> {S(tb.required_revenue_and_multiple)}</p>
        <Para text={tb.why} />
      </Section>

      {!!arr(card.falsifiers).length && (
        <Section title="반증 조건">
          <table className="w-full text-sm"><tbody>{arr<Any>(card.falsifiers).map((f, i) => <tr key={i} className="border-t border-neutral-100 align-top"><td className="py-1 pr-2 font-mono text-xs whitespace-nowrap">{S(f.check_by)}</td><td className="py-1 pr-2">{S(f.statement)}</td><td className="py-1 text-xs text-neutral-500">{S(f.metric)} {S(f.threshold)}</td></tr>)}</tbody></table>
        </Section>
      )}
      {(!!arr(card.hard_data).length || !!arr(card.data_gaps).length) && (
        <Section title="근거·공백">
          <ul className="list-disc pl-5 text-xs">{arr<Any>(card.hard_data).map((x, i) => <li key={i}>{S(x.label)} <Url u={x.url} /></li>)}</ul>
          {!!arr(card.data_gaps).length && <p className="text-xs text-neutral-500">공백: {arr<string>(card.data_gaps).join(" · ")}</p>}
        </Section>
      )}
    </div>
  );
}
