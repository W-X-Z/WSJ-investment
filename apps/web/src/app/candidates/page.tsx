import Link from "next/link";
import { Toolbar } from "@/components/Toolbar";
import { fmtDate, fmtNum, fmtUsd } from "@/lib/format";
import { db, PAGE_SIZE, pageOf, param, range, type SearchParams } from "@/lib/supabase";

export const dynamic = "force-dynamic";

type Sig = { family: string; kind: string; date: string; strength?: number; summary: string; url?: string | null };
type Cand = {
  cik: number; ticker: string | null; name: string; sector_bucket: string | null; public_float: number | null;
  as_of: string; score: number; families: string[]; family_count: number; signal_count_90d: number; risk_count_90d: number;
  first_signal_date: string | null; last_signal_date: string | null; top_signals: Sig[] | null; risks: Sig[] | null;
  status: string; notes: string | null;
};

const FAMILY_LABEL: Record<string, string> = {
  insider: "내부자", contract: "계약", clinical: "임상", fda: "FDA", gov: "정부계약", activist: "행동주의",
  institution: "기관", dilution: "희석", flow: "수급",
};

function Pill({ fam }: { fam: string }) {
  return <span className="inline-block rounded px-1.5 py-0.5 text-xs bg-neutral-200 text-neutral-800 mr-1">{FAMILY_LABEL[fam] ?? fam}</span>;
}

export default async function Candidates({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const bucket = param(sp, "bucket");
  const status = param(sp, "status");
  const minFam = param(sp, "minfam", "2");
  const page = pageOf(sp);

  let query = db("public").from("v_candidates").select("*", { count: "exact" });
  if (bucket) query = query.eq("sector_bucket", bucket);
  if (status) query = query.eq("status", status);
  if (minFam) query = query.gte("family_count", parseInt(minFam, 10) || 1);
  const [from, to] = range(page);
  const { data, count, error } = await query.order("score", { ascending: false }).range(from, to);
  if (error) return <pre className="text-red-600">{error.message}</pre>;
  const rows = (data ?? []) as Cand[];

  return (
    <div>
      <h1 className="text-lg font-semibold mb-1">오늘의 후보 (core.candidates)</h1>
      <p className="text-neutral-500 mb-2">
        90일 창에서 서로 독립적인 신호 계열이 겹친 종목. 점수 = 계열별 최대 세기 합 + 2×(계열수−1) − 0.5×리스크 수. 클러스터 매수는 단독으로도 후보.
      </p>
      <Toolbar
        path="/candidates"
        params={{ bucket, status, minfam: minFam }}
        fields={[
          { name: "bucket", placeholder: "섹터(전체)", options: ["biotech", "medtech", "gov_procurement", "energy", "ai_software", "semis"] },
          { name: "status", placeholder: "상태(전체)", options: ["new", "watch", "briefed", "dismissed"] },
          { name: "minfam", placeholder: "최소 계열 수", options: ["1", "2", "3"] },
        ]}
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
      />
      {!rows.length && <p className="text-neutral-500 py-6">후보 없음 — `python -m wsj signals build` 실행 후 다시 확인</p>}
      <div className="space-y-3">
        {rows.map((c) => (
          <div key={c.cik} className="border border-neutral-200 rounded bg-white p-3">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-base font-semibold">
                <Link className="underline" href={`/signals?q=${c.ticker ?? ""}`}>{c.ticker ?? c.cik}</Link> · {c.name}
              </span>
              <span className="text-neutral-500">{c.sector_bucket} · 공개유동 {fmtUsd(c.public_float)}</span>
              <span className="ml-auto font-mono">score {fmtNum(c.score, 1)}</span>
              <span className="text-xs rounded px-1.5 py-0.5 border">{c.status}</span>
            </div>
            <div className="mt-1">
              {(c.families ?? []).map((f) => <Pill key={f} fam={f} />)}
              <span className="text-neutral-500 text-xs">
                신호 {c.signal_count_90d} · 리스크 {c.risk_count_90d} · {fmtDate(c.first_signal_date)} ~ {fmtDate(c.last_signal_date)}
              </span>
            </div>
            <ul className="mt-2 space-y-0.5">
              {(c.top_signals ?? []).map((s, i) => (
                <li key={i} className="text-sm">
                  <span className="text-neutral-400 font-mono mr-2">{s.date}</span>
                  <Pill fam={s.family} />
                  {s.summary}
                  {s.url && (
                    <a className="underline text-neutral-500 ml-2" href={s.url} target="_blank" rel="noreferrer">원문</a>
                  )}
                </li>
              ))}
            </ul>
            {!!(c.risks ?? []).length && (
              <ul className="mt-2 space-y-0.5 border-t border-dashed pt-2">
                {(c.risks ?? []).map((s, i) => (
                  <li key={i} className="text-sm text-red-700">
                    <span className="text-neutral-400 font-mono mr-2">{s.date}</span>
                    <Pill fam={s.family} />
                    {s.summary}
                    {s.url && (
                      <a className="underline text-neutral-500 ml-2" href={s.url} target="_blank" rel="noreferrer">원문</a>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {c.notes && <p className="mt-2 text-sm text-neutral-600">메모: {c.notes}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
