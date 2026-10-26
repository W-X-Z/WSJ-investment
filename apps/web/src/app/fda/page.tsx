import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtList } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Fda({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const set = param(sp, "set", "drugs");
  const page = pageOf(sp);
  const [from, to] = range(page);
  const toolbar = (count: number | null) => (
    <Toolbar
      path="/fda"
      params={{ q, set }}
      fields={[
        { name: "q", placeholder: "스폰서/신청자/브랜드" },
        { name: "set", placeholder: "데이터셋", options: ["drugs", "510k"] },
      ]}
      page={page}
      count={count}
      pageSize={PAGE_SIZE}
    />
  );

  if (set === "510k") {
    let query = db("raw").from("fda_device_510k").select("*", { count: "exact" });
    if (q) query = query.or(`applicant.ilike.%${q}%,device_name.ilike.%${q}%`);
    const { data, count, error } = await query.order("decision_date", { ascending: false }).range(from, to);
    if (error) return <pre className="text-red-600">{error.message}</pre>;
    return (
      <div>
        <h1 className="text-lg font-semibold mb-2">의료기기 510(k) (월간 갱신)</h1>
        {toolbar(count)}
        <DataTable
          rows={data ?? []}
          columns={[
            { key: "decision_date", label: "결정일", render: (r) => fmtDate(r.decision_date) },
            { key: "k_number", label: "K번호" },
            { key: "applicant", label: "신청자" },
            { key: "device_name", label: "기기", render: (r) => String(r.device_name ?? "").slice(0, 80) },
            { key: "product_code", label: "제품코드" },
            { key: "decision_code", label: "결정" },
            { key: "clearance_type", label: "유형" },
            { key: "advisory_committee", label: "패널" },
            { key: "date_received", label: "접수", render: (r) => fmtDate(r.date_received) },
          ]}
        />
      </div>
    );
  }

  let query = db("raw").from("fda_drug_applications").select("*", { count: "exact" });
  if (q) query = query.or(`sponsor_name.ilike.%${q}%,brand_names.cs.{${q.toUpperCase()}}`);
  const { data, count, error } = await query.order("latest_submission_status_date", { ascending: false, nullsFirst: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;
  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">의약품 신청·제출 (drugsfda)</h1>
      {toolbar(count)}
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "latest_submission_status_date", label: "최근 제출일", render: (r) => fmtDate(r.latest_submission_status_date) },
          { key: "application_number", label: "신청번호" },
          { key: "sponsor_name", label: "스폰서" },
          { key: "brand_names", label: "브랜드", render: (r) => fmtList(r.brand_names) },
          { key: "generic_names", label: "성분", render: (r) => fmtList(r.generic_names, 2) },
          { key: "latest_submission_type", label: "유형" },
          { key: "latest_submission_class", label: "분류" },
          { key: "latest_submission_status", label: "상태" },
          { key: "product_count", label: "제품수", num: true },
        ]}
      />
    </div>
  );
}
