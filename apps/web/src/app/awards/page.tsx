import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtUsd } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Awards({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const agency = param(sp, "agency");
  const page = pageOf(sp);

  let query = db("raw").from("gov_awards").select("*", { count: "exact" });
  if (agency) query = query.ilike("awarding_agency", `%${agency}%`);
  if (q) query = query.or(`recipient_name.ilike.%${q}%,search_text.ilike.%${q}%,description.ilike.%${q}%`);
  const [from, to] = range(page);
  const { data, count, error } = await query.order("last_modified_date", { ascending: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;

  return (
    <div>
      <h1 className="text-lg font-semibold mb-1">연방 계약 (USAspending, 최종 수정일 기준)</h1>
      <p className="text-neutral-500 mb-2">국방부 계약은 FPDS 90일 지연. search_text 는 어떤 유니버스 회사명으로 검색돼 잡혔는지.</p>
      <Toolbar
        path="/awards"
        params={{ q, agency }}
        fields={[
          { name: "q", placeholder: "수신자/검색어/설명" },
          { name: "agency", placeholder: "기관" },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "last_modified_date", label: "수정일", render: (r) => fmtDate(r.last_modified_date) },
          { key: "recipient_name", label: "수신자" },
          { key: "search_text", label: "검색어" },
          { key: "award_amount", label: "계약액", num: true, render: (r) => fmtUsd(r.award_amount) },
          { key: "total_outlays", label: "집행액", num: true, render: (r) => fmtUsd(r.total_outlays) },
          { key: "awarding_agency", label: "기관" },
          { key: "awarding_sub_agency", label: "하위기관" },
          { key: "contract_award_type", label: "유형" },
          { key: "start_date", label: "시작", render: (r) => fmtDate(r.start_date) },
          { key: "end_date", label: "종료", render: (r) => fmtDate(r.end_date) },
          { key: "naics_code", label: "NAICS" },
          { key: "description", label: "설명", render: (r) => String(r.description ?? "").slice(0, 100) },
          {
            key: "award_id",
            label: "링크",
            render: (r) => (
              <a className="underline" href={`https://www.usaspending.gov/award/${r.generated_internal_id}`} target="_blank" rel="noreferrer">
                {String(r.award_id ?? "")}
              </a>
            ),
          },
        ]}
      />
    </div>
  );
}
