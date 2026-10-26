import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtNum, fmtUsd } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Insider({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const code = param(sp, "code", "P");
  const since = param(sp, "since");
  const page = pageOf(sp);

  let query = db("public").from("v_insider_transactions").select("*", { count: "exact" }).eq("row_type", "transaction");
  if (code) query = query.eq("transaction_code", code);
  if (since) query = query.gte("transaction_date", since);
  if (q) query = query.or(`issuer_ticker.ilike.${q}%,issuer_name.ilike.%${q}%,owner_name.ilike.%${q}%`);
  const [from, to] = range(page);
  const { data, count, error } = await query
    .order("transaction_date", { ascending: false })
    .order("accession_no", { ascending: false })
    .order("seq")
    .range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;

  return (
    <div>
      <h1 className="text-lg font-semibold mb-1">내부자 거래 (Form 4)</h1>
      <p className="text-neutral-500 mb-2">코드: P 공개시장 매수 · S 매도 · A 부여 · M 옵션 행사 · F 세금 원천 · G 증여</p>
      <Toolbar
        path="/insider"
        params={{ q, code, since }}
        fields={[
          { name: "q", placeholder: "티커/발행인/보고자" },
          { name: "code", placeholder: "거래 코드(전체)", options: ["P", "S", "A", "M", "F", "G", "D", "J", "X", "C"] },
          { name: "since", placeholder: "거래일 이후", type: "date" },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "transaction_date", label: "거래일", render: (r) => fmtDate(r.transaction_date) },
          { key: "issuer_ticker", label: "티커" },
          { key: "issuer_name", label: "발행인" },
          { key: "owner_name", label: "보고자" },
          {
            key: "role",
            label: "관계",
            render: (r) =>
              [r.is_director ? "Dir" : "", r.is_officer ? (r.officer_title as string) || "Officer" : "", r.is_ten_percent_owner ? "10%" : ""]
                .filter(Boolean)
                .join(" / "),
          },
          { key: "transaction_code", label: "코드" },
          { key: "acquired_disposed", label: "A/D" },
          { key: "shares", label: "주식수", num: true, render: (r) => fmtNum(r.shares) },
          { key: "price_per_share", label: "단가", num: true, render: (r) => fmtNum(r.price_per_share, 4) },
          { key: "value_usd", label: "금액", num: true, render: (r) => fmtUsd(r.value_usd) },
          { key: "shares_owned_following", label: "거래 후 보유", num: true, render: (r) => fmtNum(r.shares_owned_following) },
          { key: "ownership_nature", label: "D/I" },
          { key: "sector_bucket", label: "섹터" },
          { key: "public_float", label: "공개유동", num: true, render: (r) => fmtUsd(r.public_float) },
          { key: "file_date", label: "공시일", render: (r) => fmtDate(r.file_date) },
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
