import Link from "next/link";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtNum } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";
import { Prob, VERDICT } from "@/components/BriefBits";

export const dynamic = "force-dynamic";

type Scores = {
  conviction?: number; asymmetry?: number; data_quality?: number; time_horizon_months?: number;
  final_conviction?: number | null; final_asymmetry?: number | null; verdict?: string | null;
  analyst_probabilities?: { bull?: number; base?: number; bear?: number };
  risk_probabilities?: { bull?: number | null; base?: number | null; bear?: number | null };
};
type Row = {
  id: number; cik: number; ticker: string | null; name: string; sector_bucket: string | null; as_of: string; version: number;
  status: string; title: string | null; scores: Scores | null; model: string | null; prompt_version: string | null;
  usage: { total?: { cost_usd?: number; web_searches?: number } } | null; error: string | null; created_at: string; prediction_count: number;
};


export default async function Briefs({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const status = param(sp, "status");
  const verdict = param(sp, "verdict");
  const q = param(sp, "q");
  const page = pageOf(sp);

  let query = db("public").from("v_briefs").select("*", { count: "exact" });
  if (status) query = query.eq("status", status);
  if (verdict) query = query.eq("scores->>verdict", verdict);
  if (q) query = query.or(`ticker.ilike.%${q}%,name.ilike.%${q}%`);
  const [from, to] = range(page);
  const { data, count, error } = await query.order("created_at", { ascending: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;
  const rows = (data ?? []) as Row[];

  return (
    <div>
      <h1 className="text-lg font-semibold mb-1">브리프 (ideas.briefs)</h1>
      <p className="text-neutral-500 mb-2">
        후보별 Analyst 종합 + Risk 비평. 실행마다 새 버전. 예측(predictions)은 due_date 에 사람이 채점한다 (ADR-0009).
      </p>
      <Toolbar
        path="/briefs"
        params={{ status, verdict, q }}
        fields={[
          { name: "q", placeholder: "티커/이름" },
          { name: "status", placeholder: "상태(전체)", options: ["final", "draft", "failed", "superseded"] },
          { name: "verdict", placeholder: "Risk 판정(전체)", options: ["proceed", "watch", "pass"] },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      {!rows.length && (
        <p className="text-neutral-500 py-6">
          브리프 없음 — `python -m wsj briefs build --top 3` (ANTHROPIC_API_KEY 필요) 또는 Actions `briefs` 워크플로 실행
        </p>
      )}
      <div className="space-y-2">
        {rows.map((b) => {
          const s = b.scores ?? {};
          return (
            <div key={b.id} className="border border-neutral-200 rounded bg-white p-3">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <Link className="text-base font-semibold underline" href={`/briefs/${b.id}`}>
                  {b.ticker ?? b.cik} · {b.name}
                </Link>
                <span className="text-neutral-500 text-xs">{b.sector_bucket} · {b.as_of} · v{b.version} · {b.model}</span>
                {s.verdict && <span className={`text-xs rounded px-1.5 py-0.5 ${VERDICT[s.verdict] ?? "bg-neutral-100"}`}>{s.verdict}</span>}
                {b.status !== "final" && <span className="text-xs rounded px-1.5 py-0.5 border">{b.status}</span>}
                <span className="ml-auto text-xs text-neutral-500 font-mono">
                  확신 {s.conviction ?? "–"}→{s.final_conviction ?? "–"} · 비대칭 {s.asymmetry ?? "–"}→{s.final_asymmetry ?? "–"} · 데이터 {s.data_quality ?? "–"} · {s.time_horizon_months ?? "–"}개월
                </span>
              </div>
              {b.title && <div className="mt-1">{b.title}</div>}
              <div className="mt-1 text-xs text-neutral-500 flex flex-wrap gap-x-4">
                <span>Analyst <Prob p={s.analyst_probabilities} /></span>
                <span>Risk <Prob p={s.risk_probabilities} /></span>
                <span>예측 {b.prediction_count}</span>
                <span>${fmtNum(b.usage?.total?.cost_usd, 2)} · 검색 {b.usage?.total?.web_searches ?? 0}</span>
                <span>{fmtDate(b.created_at)}</span>
              </div>
              {b.error && <pre className="mt-1 text-xs text-red-600 whitespace-pre-wrap">{b.error.slice(-400)}</pre>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
