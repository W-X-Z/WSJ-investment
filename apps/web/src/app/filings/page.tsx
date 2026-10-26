import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtList } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

const ITEM_LABEL: Record<string, string> = {
  "1.01": "중요 계약",
  "1.02": "계약 종료",
  "2.01": "자산 인수/처분",
  "2.02": "실적",
  "2.03": "채무 발생",
  "3.02": "미등록 증권 판매",
  "5.02": "임원/이사 변경",
  "7.01": "Reg FD",
  "8.01": "기타",
  "9.01": "첨부",
};

export default async function Filings({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const form = param(sp, "form");
  const item = param(sp, "item");
  const page = pageOf(sp);

  let query = db("raw").from("sec_filings").select("*", { count: "exact" });
  if (form) query = query.eq("form", form);
  if (item) query = query.contains("items", [item]);
  if (q) query = query.ilike("display_names", `%${q}%`);
  const [from, to] = range(page);
  const { data, count, error } = await query.order("file_date", { ascending: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;

  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">공시 인덱스 (raw.sec_filings)</h1>
      <Toolbar
        path="/filings"
        params={{ q, form, item }}
        fields={[
          { name: "q", placeholder: "발행인" },
          { name: "form", placeholder: "폼(전체)", options: ["8-K", "10-K", "10-Q", "SCHEDULE 13D", "SCHEDULE 13G", "S-1", "S-3", "424B5", "DEF 14A"] },
          { name: "item", placeholder: "8-K 항목(전체)", options: Object.keys(ITEM_LABEL) },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "file_date", label: "공시일", render: (r) => fmtDate(r.file_date) },
          { key: "form", label: "폼" },
          {
            key: "items",
            label: "항목",
            render: (r) => (r.items as string[]).map((i) => `${i} ${ITEM_LABEL[i] ?? ""}`.trim()).join(" · "),
          },
          { key: "display_names", label: "발행인", render: (r) => fmtList(r.display_names, 2) },
          { key: "period_ending", label: "기간말", render: (r) => fmtDate(r.period_ending) },
          { key: "sics", label: "SIC", render: (r) => fmtList(r.sics) },
          {
            key: "file_url",
            label: "링크",
            render: (r) => (
              <a className="underline" href={String(r.file_url)} target="_blank" rel="noreferrer">
                EDGAR
              </a>
            ),
          },
        ]}
      />
    </div>
  );
}
