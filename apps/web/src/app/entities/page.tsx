import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Entities({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const source = param(sp, "source");
  const view = param(sp, "view", "aliases");
  const page = pageOf(sp);
  const [from, to] = range(page);
  const fields = [
    { name: "q", placeholder: "별칭" },
    { name: "source", placeholder: "소스(전체)", options: ["clinicaltrials", "fda", "usaspending", "sec"] },
    { name: "view", placeholder: "보기", options: ["aliases", "unresolved"] },
  ];

  if (view === "unresolved") {
    let query = db("core").from("entity_unresolved").select("*", { count: "exact" });
    if (source) query = query.eq("source", source);
    if (q) query = query.ilike("alias", `%${q}%`);
    const { data, count, error } = await query.order("seen_count", { ascending: false }).range(from, to);
    if (error) return <pre className="text-red-600">{error.message}</pre>;
    return (
      <div>
        <h1 className="text-lg font-semibold mb-1">미매칭 큐 (core.entity_unresolved)</h1>
        <p className="text-neutral-500 mb-2">정규화 정확 일치는 실패했지만 후보가 있는 이름. 사람이 확인해 entity_aliases 로 옮긴다 (method=manual).</p>
        <Toolbar path="/entities" params={{ q, source, view }} fields={fields} page={page} count={count} pageSize={PAGE_SIZE} />
        <DataTable
          rows={data ?? []}
          columns={[
            { key: "source", label: "소스" },
            { key: "alias_type", label: "유형" },
            { key: "alias", label: "원문" },
            {
              key: "candidates",
              label: "후보 (cik · 이름 · 티커)",
              render: (r) =>
                ((r.candidates as { cik: number; name: string; ticker?: string; in_universe?: boolean }[]) ?? [])
                  .map((c) => `${c.cik} · ${c.name}${c.ticker ? ` (${c.ticker})` : ""}${c.in_universe ? " ★" : ""}`)
                  .join(" | "),
            },
            { key: "last_seen", label: "최근", render: (r) => fmtDate(r.last_seen) },
          ]}
        />
      </div>
    );
  }

  let query = db("core").from("entity_aliases").select("*, companies(name, ticker, in_universe)", { count: "exact" });
  if (source) query = query.eq("source", source);
  if (q) query = query.ilike("alias", `%${q}%`);
  const { data, count, error } = await query.order("created_at", { ascending: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;
  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">엔티티 별칭 (core.entity_aliases)</h1>
      <Toolbar path="/entities" params={{ q, source, view }} fields={fields} page={page} count={count} pageSize={PAGE_SIZE} />
      <DataTable
        rows={(data ?? []) as Record<string, unknown>[]}
        columns={[
          { key: "source", label: "소스" },
          { key: "alias_type", label: "유형" },
          { key: "alias", label: "원문" },
          { key: "cik", label: "CIK" },
          { key: "company", label: "회사", render: (r) => String((r.companies as Record<string, unknown>)?.name ?? "") },
          { key: "ticker", label: "티커", render: (r) => String((r.companies as Record<string, unknown>)?.ticker ?? "") },
          { key: "method", label: "방법" },
          { key: "confidence", label: "신뢰도", num: true },
          { key: "created_at", label: "생성", render: (r) => fmtDate(r.created_at) },
        ]}
      />
    </div>
  );
}
