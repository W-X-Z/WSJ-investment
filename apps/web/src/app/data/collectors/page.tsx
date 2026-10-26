import { DataTable } from "@/components/DataTable";
import { fmtDate, fmtNum } from "@/lib/format";
import { db } from "@/lib/supabase";

export const dynamic = "force-dynamic";

type Overview = Record<string, unknown> & {
  collector: string;
  last_status: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_rows: number | null;
  last_error: string | null;
  watermark: Record<string, unknown> | null;
};

const TABLES = [
  "ideas.briefs",
  "ideas.predictions",
  "core.candidates",
  "core.signals",
  "core.companies",
  "core.entity_aliases",
  "core.entity_unresolved",
  "raw.sec_form4_filings",
  "raw.sec_form4_transactions",
  "raw.sec_filings",
  "raw.finra_short_daily",
  "raw.finra_short_interest",
  "raw.finra_ats_weekly",
  "raw.ct_studies",
  "raw.ct_study_changes",
  "raw.fda_drug_applications",
  "raw.fda_device_510k",
  "raw.gov_awards",
];

async function exactCount(table: string, filter?: Record<string, unknown>): Promise<number | null> {
  const [schema, name] = table.split(".") as ["raw" | "core" | "ops" | "ideas", string];
  let q = db(schema).from(name).select("*", { count: "exact", head: true });
  if (filter) q = q.match(filter);
  const { count, error } = await q;
  return error ? null : count;
}

export default async function Home() {
  const { data: runs } = await db("public").from("v_collector_overview").select("*").order("collector");
  const counts = await Promise.all(TABLES.map(async (t) => ({ table: t, rows: await exactCount(t) })));
  const universe = await exactCount("core.companies", { in_universe: true });
  const unresolved = await exactCount("core.entity_unresolved");

  return (
    <div className="space-y-6"><div className="page-head"><div><div className="page-kicker">DATA WORKSPACE / DEEP TOOL</div><h1>데이터 적재 현황</h1><p>기존 원천 데이터 콘솔을 보조 도구로 보존했습니다. 기술 인사이트 메인은 상단 탐색에서 확인할 수 있습니다.</p></div></div>
      <section>
        <h1 className="text-lg font-semibold mb-1">수집 현황 · 원천 데이터 콘솔</h1>
        <p className="text-neutral-500 mb-3">
          유니버스 {fmtNum(universe)} 종목 · 미매칭 엔티티 {fmtNum(unresolved)} 건
        </p>
        <DataTable<Overview>
          rows={(runs ?? []) as Overview[]}
          columns={[
            { key: "collector", label: "수집기" },
            {
              key: "last_status",
              label: "상태",
              render: (r) => (
                <span className={r.last_status === "failed" ? "text-red-600" : r.last_status === "succeeded" ? "text-green-700" : ""}>
                  {r.last_status ?? "-"}
                </span>
              ),
            },
            { key: "last_started_at", label: "시작", render: (r) => fmtDate(r.last_started_at) },
            { key: "last_finished_at", label: "종료", render: (r) => fmtDate(r.last_finished_at) },
            { key: "last_rows", label: "행", num: true, render: (r) => fmtNum(r.last_rows) },
            { key: "watermark", label: "워터마크", render: (r) => JSON.stringify(r.watermark ?? {}) },
            {
              key: "last_error",
              label: "메모/에러",
              render: (r) => <span className="whitespace-pre-wrap max-w-xl inline-block">{(r.last_error ?? "").slice(0, 300)}</span>,
            },
          ]}
          empty="아직 실행된 수집기가 없습니다. `python -m wsj run sec_universe` 부터."
        />
      </section>
      <section>
        <h2 className="text-base font-semibold mb-2">테이블 행 수</h2>
        <DataTable
          rows={counts}
          columns={[
            { key: "table", label: "테이블" },
            { key: "rows", label: "rows", num: true, render: (r) => fmtNum(r.rows) },
          ]}
        />
      </section>
    </div>
  );
}
