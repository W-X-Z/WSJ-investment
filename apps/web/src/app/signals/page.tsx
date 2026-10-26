import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtNum } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Signals({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const family = param(sp, "family");
  const dir = param(sp, "dir");
  const page = pageOf(sp);

  let query = db("public").from("v_signals").select("*", { count: "exact" });
  if (family) query = query.eq("family", family);
  if (dir) query = query.eq("direction", parseInt(dir, 10));
  if (q) query = query.or(`ticker.ilike.${q}%,name.ilike.%${q}%`);
  const [from, to] = range(page);
  const { data, count, error } = await query.order("signal_date", { ascending: false }).order("strength", { ascending: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;

  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">신호 (core.signals)</h1>
      <Toolbar
        path="/signals"
        params={{ q, family, dir }}
        fields={[
          { name: "q", placeholder: "티커/이름" },
          { name: "family", placeholder: "계열(전체)", options: ["insider", "contract", "clinical", "fda", "gov", "activist", "institution", "dilution", "flow"] },
          { name: "dir", placeholder: "방향(전체)", options: ["1", "-1", "0"] },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "signal_date", label: "날짜", render: (r) => fmtDate(r.signal_date) },
          { key: "ticker", label: "티커" },
          { key: "name", label: "회사" },
          { key: "family", label: "계열" },
          { key: "kind", label: "종류" },
          {
            key: "direction",
            label: "방향",
            render: (r) => (r.direction === 1 ? <span className="text-green-700">+</span> : r.direction === -1 ? <span className="text-red-700">−</span> : "·"),
          },
          { key: "strength", label: "세기", num: true, render: (r) => fmtNum(r.strength, 1) },
          { key: "summary", label: "요약", render: (r) => <span className="whitespace-normal inline-block max-w-2xl">{String(r.summary)}</span> },
          {
            key: "url",
            label: "원문",
            render: (r) => (r.url ? <a className="underline" href={String(r.url)} target="_blank" rel="noreferrer">링크</a> : ""),
          },
        ]}
      />
    </div>
  );
}
