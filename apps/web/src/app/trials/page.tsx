import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtList, fmtNum } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Trials({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const status = param(sp, "status");
  const view = param(sp, "view", "studies");
  const page = pageOf(sp);
  const [from, to] = range(page);

  if (view === "changes") {
    const { data, count, error } = await db("raw")
      .from("ct_study_changes")
      .select("*, ct_studies(brief_title, lead_sponsor_name)", { count: "exact" })
      .order("detected_at", { ascending: false })
      .range(from, to);
    if (error) return <pre className="text-red-600">{error.message}</pre>;
    return (
      <div>
        <h1 className="text-lg font-semibold mb-2">임상 변경 감지 (raw.ct_study_changes)</h1>
        <Toolbar path="/trials" params={{ q, status, view }} fields={[{ name: "view", placeholder: "보기", options: ["studies", "changes"] }]} page={page} count={count} pageSize={PAGE_SIZE} />
        <DataTable
          rows={(data ?? []) as Record<string, unknown>[]}
          columns={[
            { key: "detected_at", label: "감지", render: (r) => fmtDate(r.detected_at) },
            { key: "nct_id", label: "NCT" },
            { key: "sponsor", label: "스폰서", render: (r) => String((r.ct_studies as Record<string, unknown>)?.lead_sponsor_name ?? "") },
            { key: "field", label: "필드" },
            { key: "old_value", label: "이전" },
            { key: "new_value", label: "이후" },
            { key: "title", label: "제목", render: (r) => String((r.ct_studies as Record<string, unknown>)?.brief_title ?? "").slice(0, 80) },
          ]}
          empty="아직 변경이 감지되지 않았습니다 (두 번째 스냅샷부터 기록)"
        />
      </div>
    );
  }

  let query = db("raw").from("ct_studies").select("*", { count: "exact" });
  if (status) query = query.eq("overall_status", status);
  if (q) query = query.or(`lead_sponsor_name.ilike.%${q}%,brief_title.ilike.%${q}%,nct_id.eq.${q}`);
  const { data, count, error } = await query.order("last_update_post_date", { ascending: false, nullsFirst: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;

  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">임상 스냅샷 (raw.ct_studies)</h1>
      <Toolbar
        path="/trials"
        params={{ q, status, view }}
        fields={[
          { name: "q", placeholder: "스폰서/제목/NCT" },
          {
            name: "status",
            placeholder: "상태(전체)",
            options: ["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING", "COMPLETED", "TERMINATED", "SUSPENDED", "WITHDRAWN", "ENROLLING_BY_INVITATION"],
          },
          { name: "view", placeholder: "보기", options: ["studies", "changes"] },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "nct_id", label: "NCT", render: (r) => <a className="underline" href={`https://clinicaltrials.gov/study/${r.nct_id}`} target="_blank" rel="noreferrer">{String(r.nct_id)}</a> },
          { key: "lead_sponsor_name", label: "스폰서" },
          { key: "overall_status", label: "상태" },
          { key: "phases", label: "단계", render: (r) => fmtList(r.phases) },
          { key: "enrollment_count", label: "등록", num: true, render: (r) => fmtNum(r.enrollment_count) },
          { key: "primary_completion_date", label: "1차 완료" },
          { key: "last_update_post_date", label: "최근 갱신", render: (r) => fmtDate(r.last_update_post_date) },
          { key: "brief_title", label: "제목", render: (r) => String(r.brief_title ?? "").slice(0, 90) },
          { key: "conditions", label: "적응증", render: (r) => fmtList(r.conditions, 2) },
        ]}
      />
    </div>
  );
}
