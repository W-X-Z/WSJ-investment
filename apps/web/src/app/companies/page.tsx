import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtUsd } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Companies({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const bucket = param(sp, "bucket");
  const universe = param(sp, "universe", "1");
  const page = pageOf(sp);

  let query = db("core").from("companies").select("*", { count: "exact" });
  if (universe === "1") query = query.eq("in_universe", true);
  if (bucket) query = query.eq("sector_bucket", bucket);
  if (q) query = query.or(`name.ilike.%${q}%,ticker.ilike.${q}%`);
  const [from, to] = range(page);
  const { data, count, error } = await query.order("public_float", { ascending: false, nullsFirst: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;

  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">유니버스 (core.companies)</h1>
      <Toolbar
        path="/companies"
        params={{ q, bucket, universe }}
        fields={[
          { name: "q", placeholder: "이름/티커" },
          { name: "bucket", placeholder: "섹터", options: ["biotech", "medtech", "gov_procurement", "other"] },
          { name: "universe", placeholder: "유니버스만", options: ["1", "0"] },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "ticker", label: "티커" },
          { key: "name", label: "이름" },
          { key: "exchange", label: "거래소" },
          { key: "sector_bucket", label: "섹터" },
          { key: "sic", label: "SIC" },
          { key: "sic_description", label: "SIC 설명" },
          { key: "public_float", label: "공개유동", num: true, render: (r) => fmtUsd(r.public_float) },
          { key: "public_float_asof", label: "기준일", render: (r) => fmtDate(r.public_float_asof) },
          { key: "business_state", label: "주" },
          { key: "filer_category", label: "필러 구분", render: (r) => String(r.filer_category ?? "").replace("<br>", " / ") },
          { key: "cik", label: "CIK" },
        ]}
      />
    </div>
  );
}
