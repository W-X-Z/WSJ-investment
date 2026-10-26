import { DataTable } from "@/components/DataTable";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtNum, fmtUsd } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function Finra({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const q = param(sp, "q").toUpperCase();
  const set = param(sp, "set", "short_interest");
  const page = pageOf(sp);
  const [from, to] = range(page);

  const toolbar = (count: number | null) => (
    <Toolbar
      path="/finra"
      params={{ q, set }}
      fields={[
        { name: "q", placeholder: "티커" },
        { name: "set", placeholder: "데이터셋", options: ["short_interest", "short_daily", "ats_weekly"] },
      ]}
      page={page}
      count={count}
      pageSize={PAGE_SIZE}
    />
  );

  if (set === "short_daily") {
    let query = db("raw").from("finra_short_daily").select("*", { count: "exact" });
    if (q) query = query.eq("symbol", q);
    const { data, count, error } = await query.order("trade_report_date", { ascending: false }).order("symbol").range(from, to);
    if (error) return <pre className="text-red-600">{error.message}</pre>;
    return (
      <div>
        <h1 className="text-lg font-semibold mb-2">일별 공매도 거래량 (regShoDaily, T+1)</h1>
        {toolbar(count)}
        <DataTable
          rows={data ?? []}
          columns={[
            { key: "trade_report_date", label: "거래일" },
            { key: "symbol", label: "티커" },
            { key: "market_code", label: "시장" },
            { key: "reporting_facility_code", label: "TRF" },
            { key: "short_par_quantity", label: "공매도", num: true, render: (r) => fmtNum(r.short_par_quantity) },
            { key: "total_par_quantity", label: "총거래", num: true, render: (r) => fmtNum(r.total_par_quantity) },
            {
              key: "ratio",
              label: "공매도 비율",
              num: true,
              render: (r) => (Number(r.total_par_quantity) ? `${((100 * Number(r.short_par_quantity)) / Number(r.total_par_quantity)).toFixed(1)}%` : ""),
            },
          ]}
        />
      </div>
    );
  }

  if (set === "ats_weekly") {
    let query = db("raw").from("finra_ats_weekly").select("*", { count: "exact" });
    if (q) query = query.eq("symbol", q);
    const { data, count, error } = await query
      .order("week_start_date", { ascending: false })
      .order("total_weekly_share_quantity", { ascending: false })
      .range(from, to);
    if (error) return <pre className="text-red-600">{error.message}</pre>;
    return (
      <div>
        <h1 className="text-lg font-semibold mb-2">ATS(다크풀) 주간 거래량 (weeklySummary)</h1>
        {toolbar(count)}
        <DataTable
          rows={data ?? []}
          columns={[
            { key: "week_start_date", label: "주 시작" },
            { key: "tier_identifier", label: "티어" },
            { key: "symbol", label: "티커" },
            { key: "market_participant_name", label: "ATS" },
            { key: "summary_type_code", label: "유형" },
            { key: "total_weekly_trade_count", label: "체결수", num: true, render: (r) => fmtNum(r.total_weekly_trade_count) },
            { key: "total_weekly_share_quantity", label: "주식수", num: true, render: (r) => fmtNum(r.total_weekly_share_quantity) },
            { key: "total_notional_sum", label: "금액", num: true, render: (r) => fmtUsd(r.total_notional_sum) },
          ]}
        />
      </div>
    );
  }

  let query = db("raw").from("finra_short_interest").select("*", { count: "exact" });
  if (q) query = query.eq("symbol", q);
  const { data, count, error } = await query
    .order("settlement_date", { ascending: false })
    .order("days_to_cover_quantity", { ascending: false, nullsFirst: false })
    .range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;
  return (
    <div>
      <h1 className="text-lg font-semibold mb-2">공매도 잔고 (consolidatedShortInterest, 월 2회)</h1>
      {toolbar(count)}
      <DataTable
        rows={data ?? []}
        columns={[
          { key: "settlement_date", label: "결제일", render: (r) => fmtDate(r.settlement_date) },
          { key: "symbol", label: "티커" },
          { key: "issue_name", label: "종목" },
          { key: "current_short_position_quantity", label: "잔고", num: true, render: (r) => fmtNum(r.current_short_position_quantity) },
          { key: "change_percent", label: "변화%", num: true, render: (r) => fmtNum(r.change_percent, 2) },
          { key: "average_daily_volume_quantity", label: "일평균 거래량", num: true, render: (r) => fmtNum(r.average_daily_volume_quantity) },
          { key: "days_to_cover_quantity", label: "Days to cover", num: true, render: (r) => fmtNum(r.days_to_cover_quantity, 2) },
          { key: "market_class_code", label: "시장" },
        ]}
      />
    </div>
  );
}
