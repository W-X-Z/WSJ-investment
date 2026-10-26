import Link from "next/link";
import { notFound } from "next/navigation";
import { Para, Prob, Section, Sev, Url, VERDICT } from "@/components/BriefBits";
import { fmtDate, fmtNum, fmtUsd } from "@/lib/format";
import { MoatCard } from "@/components/MoatCard";
import { db } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// LLM 산출물은 스키마를 강제하지 않으므로 느슨한 타입으로 읽고, 없는 필드는 비워 둔다.
type Any = Record<string, unknown>;
type Scenario = {
  probability?: number; horizon_months?: number; drivers?: string[]; first_evidence?: string;
  triggers?: { window?: string; event?: string }[]; financial_path?: string; price_implication?: string;
};
type Prediction = {
  id: number; claim: string; measurable: string | null; due_date: string; scenario: string | null; outcome: string; grade_note: string | null;
};

const S = (v: unknown) => (typeof v === "string" ? v : v === null || v === undefined ? "" : JSON.stringify(v));
const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const obj = (v: unknown): Any => (v && typeof v === "object" && !Array.isArray(v) ? (v as Any) : {});

function ScenarioCard({ name, sc, riskP }: { name: string; sc: Scenario; riskP?: number | null }) {
  const tone = name === "bull" ? "border-emerald-300" : name === "bear" ? "border-rose-300" : "border-neutral-300";
  return (
    <div className={`border-2 ${tone} rounded p-3 bg-white text-sm space-y-1`}>
      <div className="flex items-baseline gap-2">
        <span className="font-semibold uppercase">{name}</span>
        <span className="font-mono">Analyst {sc.probability !== undefined ? `${Math.round((sc.probability ?? 0) * 100)}%` : "–"}</span>
        {riskP !== undefined && riskP !== null && <span className="font-mono text-neutral-500">Risk {Math.round(riskP * 100)}%</span>}
        <span className="ml-auto text-neutral-500 text-xs">{sc.horizon_months ?? "–"}개월</span>
      </div>
      {!!sc.drivers?.length && (
        <ul className="list-disc pl-5">
          {sc.drivers.map((d, i) => (
            <li key={i}>{S(d)}</li>
          ))}
        </ul>
      )}
      {sc.first_evidence && (
        <p>
          <span className="text-neutral-500">첫 증거:</span> {S(sc.first_evidence)}
        </p>
      )}
      {!!sc.triggers?.length && (
        <p>
          <span className="text-neutral-500">트리거:</span>{" "}
          {sc.triggers.map((t, i) => (
            <span key={i} className="mr-2">
              <span className="font-mono text-xs">{S(t.window)}</span> {S(t.event)}
            </span>
          ))}
        </p>
      )}
      {sc.financial_path && (
        <p>
          <span className="text-neutral-500">재무 경로:</span> {S(sc.financial_path)}
        </p>
      )}
      {sc.price_implication && (
        <p>
          <span className="text-neutral-500">가격 함의:</span> {S(sc.price_implication)}
        </p>
      )}
    </div>
  );
}

export default async function BriefDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { data, error } = await db("ideas").from("briefs").select("*").eq("id", id).maybeSingle();
  if (error) return <pre className="text-red-600">{error.message}</pre>;
  if (!data) notFound();
  const row = data as Any;
  const b = obj(row.brief);
  const r = obj(row.research);
  const c = obj(row.critique);
  const dps = obj(row.datapack_summary);
  const scores = obj(row.scores);
  const { data: preds } = await db("ideas").from("predictions").select("*").eq("brief_id", id).order("due_date");
  const company = obj(dps.company);
  const px = obj(dps.prices);
  const der = obj(obj(dps.financials).derived);
  const scen = obj(b.scenarios);
  const riskP = obj(c.scenario_probability_adjustments);
  const tb = obj(b.tenbagger_path);
  const usage = obj(obj(row.usage).total);

  return (
    <div className="max-w-5xl space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Link href="/briefs" className="text-neutral-500 text-sm underline">
          ← 브리프
        </Link>
        <h1 className="text-lg font-semibold">
          {S(row.ticker) || S(row.cik)} · {S(company.name)}
        </h1>
        <span className="text-neutral-500 text-sm">
          {S(company.sector_bucket)} · 기준일 {S(row.as_of)} · v{S(row.version)} · {S(row.model)} · 프롬프트 {S(row.prompt_version)}
        </span>
        {!!c.verdict && <span className={`text-xs rounded px-1.5 py-0.5 ${VERDICT[S(c.verdict)] ?? "bg-neutral-100"}`}>Risk: {S(c.verdict)}</span>}
        {row.status !== "final" && <span className="text-xs rounded px-1.5 py-0.5 border">{S(row.status)}</span>}
      </div>

      {!!row.error && (
        <Section title="오류">
          <pre className="text-xs text-red-600 whitespace-pre-wrap">{S(row.error)}</pre>
        </Section>
      )}

      {/* 헤더 수치 */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
        {[
          ["종가", px.last_close !== undefined ? `$${fmtNum(px.last_close, 2)} (${S(px.as_of)})` : "–"],
          ["시총", fmtUsd(px.market_cap) || "–"],
          ["3M / 12M", `${pct(px.ret_3m)} / ${pct(px.ret_12m)}`],
          ["52주 고가 대비", pct(px.pct_from_52w_high)],
          ["현금+단기투자", fmtUsd(der.liquidity_cash_and_st_investments) || "–"],
          ["런웨이", der.runway_months ? `${fmtNum(der.runway_months, 0)}개월` : "–"],
        ].map(([k, v]) => (
          <div key={k as string} className="border border-neutral-200 rounded bg-white px-2 py-1">
            <div className="text-xs text-neutral-500">{k as string}</div>
            <div className="font-mono">{v as string}</div>
          </div>
        ))}
      </div>

      {row.kind === "moat" && (
        <>
          <Section title={S(b.one_liner) || "해자 카드"}>
            <p className="text-xs text-neutral-500">공급망 해자 카드 · {S(row.model)} · 프롬프트 {S(row.prompt_version)}</p>
          </Section>
          <MoatCard card={b} nodes={arr<string>(row.ontology_nodes)} />
        </>
      )}
      {row.kind !== "moat" && !!b.title && (
        <Section title={S(b.title)}>
          <Para text={b.one_paragraph} />
          <div className="flex flex-wrap gap-x-4 text-xs text-neutral-600 pt-1">
            <span>
              Analyst 확신 {S(scores.conviction) || "–"} · 비대칭 {S(scores.asymmetry) || "–"} · 데이터 {S(scores.data_quality) || "–"} · {S(scores.time_horizon_months) || "–"}개월
            </span>
            <span>
              Risk 확신 {S(scores.final_conviction) || "–"} · 비대칭 {S(scores.final_asymmetry) || "–"}
            </span>
            <span>
              Analyst <Prob p={scores.analyst_probabilities as never} /> · Risk <Prob p={scores.risk_probabilities as never} />
            </span>
          </div>
          {!!obj(b.scores).rationale && <p className="text-xs text-neutral-500">{S(obj(b.scores).rationale)}</p>}
        </Section>
      )}

      {!!Object.keys(scen).length && (
        <Section title="시나리오" sub="드라이버 → 첫 증거 → 트리거 → 재무 경로 → 가격 함의. 분기 점검 때 어느 길로 가는지 '첫 증거' 로 판정한다.">
          <div className="grid md:grid-cols-3 gap-2">
            {(["bull", "base", "bear"] as const).map((k) => (
              <ScenarioCard key={k} name={k} sc={obj(scen[k]) as Scenario} riskP={riskP[k] as number | null | undefined} />
            ))}
          </div>
          {!!riskP.rationale && (
            <p className="text-xs text-neutral-600">
              <span className="font-semibold">Risk 재조정 이유:</span> {S(riskP.rationale)}
            </p>
          )}
        </Section>
      )}

      {!!Object.keys(tb).length && (
        <Section title={`텐배거 경로 — ${S(tb.feasibility) || "–"}`}>
          <p>
            현재 시총 {S(tb.current_market_cap)} → 목표 {S(tb.target_market_cap)} · {S(tb.years)}년 · 현실적 배수 {S(tb.realistic_multiple)}
          </p>
          {!!arr(tb.what_must_be_true).length && (
            <ul className="list-disc pl-5">
              {arr<string>(tb.what_must_be_true).map((x, i) => (
                <li key={i}>{S(x)}</li>
              ))}
            </ul>
          )}
          <p>
            <span className="text-neutral-500">밸류에이션 브리지:</span> {S(tb.valuation_bridge)}
          </p>
          <p>
            <span className="text-neutral-500">희석 가정:</span> {S(tb.dilution_assumption)}
          </p>
        </Section>
      )}

      {(!!b.null_hypothesis || !!b.why_now || !!b.thesis) && (
        <Section title="반대 가설 → 왜 지금 → 논제">
          {!!b.null_hypothesis && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">반대 가설 (신호가 무의미할 가능성)</div>
              <Para text={b.null_hypothesis} />
            </div>
          )}
          {!!b.why_now && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">왜 지금</div>
              <Para text={b.why_now} />
            </div>
          )}
          {!!b.thesis && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">투자 논제</div>
              <Para text={b.thesis} />
            </div>
          )}
        </Section>
      )}

      {!!arr(b.risks).length && (
        <Section title="리스크 (논제를 깨는 것만)">
          <table className="w-full text-sm">
            <tbody>
              {arr<Any>(b.risks).map((x, i) => (
                <tr key={i} className="border-t border-neutral-100 align-top">
                  <td className="py-1 pr-2 w-16">
                    <Sev s={S(x.severity)} />
                  </td>
                  <td className="py-1 pr-2">
                    <div className="font-medium">{S(x.risk)}</div>
                    <div className="text-neutral-600">{S(x.evidence)}</div>
                    {!!x.mitigant && <div className="text-neutral-500 text-xs">완화: {S(x.mitigant)}</div>}
                    <Url u={x.source} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!!arr(c.missing_risks).length && (
            <div className="mt-2">
              <div className="text-xs font-semibold text-neutral-500">Risk 가 추가한 리스크</div>
              <ul className="list-disc pl-5">
                {arr<Any>(c.missing_risks).map((x, i) => (
                  <li key={i}>
                    <Sev s={S(x.severity)} /> {S(x.risk)} <span className="text-neutral-500">— {S(x.evidence)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Section>
      )}

      {!!(preds ?? []).length && (
        <Section title="예측·반증 (분기 채점)" sub="outcome 은 사람이 채운다: pending → hit / miss / unclear. 반증이 hit 이면 논제 철회.">
          <table className="w-full text-sm">
            <thead className="text-xs text-neutral-500 text-left">
              <tr>
                <th className="py-1 pr-2">기한</th>
                <th className="py-1 pr-2">시나리오</th>
                <th className="py-1 pr-2">진술</th>
                <th className="py-1 pr-2">판정 데이터</th>
                <th className="py-1 pr-2">결과</th>
              </tr>
            </thead>
            <tbody>
              {(preds as Prediction[]).map((p) => (
                <tr key={p.id} className="border-t border-neutral-100 align-top">
                  <td className="py-1 pr-2 font-mono text-xs whitespace-nowrap">{p.due_date}</td>
                  <td className="py-1 pr-2 text-xs">{p.scenario}</td>
                  <td className="py-1 pr-2">{p.claim}</td>
                  <td className="py-1 pr-2 text-neutral-600 text-xs">{p.measurable}</td>
                  <td className="py-1 pr-2 text-xs">
                    {p.outcome}
                    {p.grade_note ? ` — ${p.grade_note}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {!!Object.keys(c).length && (
        <Section title="Risk 비평">
          {!!c.verdict_rationale && (
            <p>
              <span className="font-semibold">{S(c.verdict)}</span> — {S(c.verdict_rationale)}
            </p>
          )}
          {!!c.pre_mortem && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">사전부검 (12개월 뒤 −70% 라면)</div>
              <Para text={c.pre_mortem} />
            </div>
          )}
          {!!c.base_rate_check && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">기저율</div>
              <Para text={c.base_rate_check} />
            </div>
          )}
          {!!Object.keys(obj(c.financing_and_dilution)).length && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">
                자금조달·희석 <Sev s={S(obj(c.financing_and_dilution).severity)} /> · ATM/Shelf {S(obj(c.financing_and_dilution).atm_or_shelf_active)} · 다음 조달까지 {S(obj(c.financing_and_dilution).months_to_next_raise_estimate)}
              </div>
              <Para text={obj(c.financing_and_dilution).assessment} />
            </div>
          )}
          {!!arr(c.unsupported_claims).length && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">근거 없는 주장</div>
              <ul className="list-disc pl-5">
                {arr<Any>(c.unsupported_claims).map((x, i) => (
                  <li key={i}>
                    {S(x.claim)} <span className="text-neutral-500">({S(x.where)}) — {S(x.why)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!!arr(c.insider_signal_caveats).length && (
            <div>
              <div className="text-xs font-semibold text-neutral-500">내부자 신호 주의점</div>
              <ul className="list-disc pl-5">
                {arr<string>(c.insider_signal_caveats).map((x, i) => (
                  <li key={i}>{S(x)}</li>
                ))}
              </ul>
            </div>
          )}
          {!!Object.keys(obj(c.binary_event_exposure)).length && (
            <p>
              <span className="text-neutral-500">바이너리 이벤트:</span> {arr<string>(obj(c.binary_event_exposure).events).join(" · ")} — {S(obj(c.binary_event_exposure).assessment)}
            </p>
          )}
          {!!Object.keys(obj(c.liquidity)).length && (
            <p>
              <span className="text-neutral-500">유동성:</span> {S(obj(c.liquidity).assessment)}
            </p>
          )}
          {!!arr(c.what_would_change_my_mind).length && (
            <p>
              <span className="text-neutral-500">생각이 바뀌려면:</span> {arr<string>(c.what_would_change_my_mind).join(" · ")}
            </p>
          )}
        </Section>
      )}

      {!!Object.keys(obj(b.market_context)).length && (
        <Section title="시장 맥락">
          {(["macro", "sector", "theme", "what_market_believes"] as const).map((k) => (
            <div key={k}>
              <div className="text-xs font-semibold text-neutral-500">{{ macro: "매크로", sector: "섹터", theme: "테마", what_market_believes: "시장이 믿고 있는 것" }[k]}</div>
              <Para text={obj(b.market_context)[k]} />
            </div>
          ))}
        </Section>
      )}

      {!!Object.keys(obj(b.business_change)).length && (
        <Section title="사업구조 변화·경쟁">
          <Para text={obj(b.business_change).revenue_and_model} />
          {!!arr(obj(b.business_change).competitors).length && (
            <table className="w-full text-sm">
              <tbody>
                {arr<Any>(obj(b.business_change).competitors).map((x, i) => (
                  <tr key={i} className="border-t border-neutral-100 align-top">
                    <td className="py-1 pr-2 whitespace-nowrap font-medium">
                      {S(x.name)} {x.ticker ? <span className="font-mono text-xs">({S(x.ticker)})</span> : null}
                    </td>
                    <td className="py-1 pr-2">
                      {S(x.position_vs_company)} <Url u={x.source} label="출처" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!!obj(b.business_change).moat_or_edge && (
            <p>
              <span className="text-neutral-500">엣지:</span> {S(obj(b.business_change).moat_or_edge)}
            </p>
          )}
        </Section>
      )}

      {!!Object.keys(obj(b.price_context)).length && (
        <Section title="주가 맥락">
          <Para text={obj(b.price_context).narrative} />
          <p>
            <span className="text-neutral-500">이미 반영:</span> {S(obj(b.price_context).already_priced_in)}
          </p>
          <p>
            <span className="text-neutral-500">미반영 (가설):</span> {S(obj(b.price_context).not_priced_in)}
          </p>
        </Section>
      )}

      {(!!Object.keys(obj(b.history)).length || !!Object.keys(obj(b.current_state)).length) && (
        <Section title="히스토리와 현재">
          <Para text={obj(b.history).narrative} />
          {!!arr(obj(b.history).turning_points).length && (
            <ul className="list-disc pl-5">
              {arr<Any>(obj(b.history).turning_points).map((x, i) => (
                <li key={i}>
                  <span className="font-mono text-xs">{S(x.when)}</span> {S(x.what)} <span className="text-neutral-500">— {S(x.so_what)}</span>
                </li>
              ))}
            </ul>
          )}
          <Para text={obj(b.current_state).narrative} />
          {!!arr(obj(b.current_state).key_numbers).length && (
            <div className="flex flex-wrap gap-2">
              {arr<Any>(obj(b.current_state).key_numbers).map((x, i) => (
                <span key={i} className="border border-neutral-200 rounded px-2 py-0.5 text-xs">
                  {S(x.label)}: <span className="font-mono">{S(x.value)}</span>
                </span>
              ))}
            </div>
          )}
        </Section>
      )}

      {(!!arr(r.recent_news).length || !!arr(r.upcoming_events).length || !!arr(r.competitors).length) && (
        <Section title="리서치 (웹 검색)" sub={`검색 ${S(usage.web_searches) || 0}회 · 신뢰도 low 는 근거로 쓰지 않음`}>
          {!!arr(r.recent_news).length && (
            <ul className="list-disc pl-5">
              {arr<Any>(r.recent_news).map((x, i) => (
                <li key={i}>
                  <span className="font-mono text-xs">{S(x.date)}</span> {S(x.headline)} <span className="text-neutral-500">— {S(x.implication)}</span> <Url u={x.source_url} label="출처" /> <span className="text-xs text-neutral-400">{S(x.reliability)}</span>
                </li>
              ))}
            </ul>
          )}
          {!!arr(r.upcoming_events).length && (
            <p>
              <span className="text-neutral-500">예정 이벤트:</span>{" "}
              {arr<Any>(r.upcoming_events).map((x, i) => (
                <span key={i} className="mr-3">
                  <span className="font-mono text-xs">{S(x.window)}</span> {S(x.event)}
                </span>
              ))}
            </p>
          )}
          {!!arr(r.open_questions).length && (
            <p className="text-neutral-500 text-xs">열린 질문: {arr<string>(r.open_questions).join(" · ")}</p>
          )}
        </Section>
      )}

      {!!arr(b.hard_data).length && (
        <Section title="하드데이터 링크">
          <ul className="list-disc pl-5 text-xs">
            {arr<Any>(b.hard_data).map((x, i) => (
              <li key={i}>
                {S(x.label)} <Url u={x.url} />
              </li>
            ))}
          </ul>
          {!!arr(b.data_gaps).length && <p className="text-xs text-neutral-500">데이터 공백: {arr<string>(b.data_gaps).join(" · ")}</p>}
        </Section>
      )}

      <details className="border border-neutral-200 rounded bg-white p-3 text-xs">
        <summary className="cursor-pointer">
          데이터팩 요약 · 비용 ${fmtNum(usage.cost_usd, 3)} · 토큰 in {fmtNum(usage.input_tokens)} / out {fmtNum(usage.output_tokens)} · {fmtDate(row.created_at)}
        </summary>
        <pre className="mt-2 whitespace-pre-wrap break-all">{JSON.stringify({ datapack_summary: dps, usage: row.usage, research: r }, null, 1)}</pre>
      </details>
    </div>
  );
}

function pct(v: unknown): string {
  const n = Number(v);
  if (v === null || v === undefined || !Number.isFinite(n)) return "–";
  return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;
}
