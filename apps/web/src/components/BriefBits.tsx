import type { ReactNode } from "react";

export const VERDICT: Record<string, string> = {
  proceed: "bg-emerald-100 text-emerald-900",
  watch: "bg-amber-100 text-amber-900",
  pass: "bg-rose-100 text-rose-900",
};

export type Probs = { bull?: number | null; base?: number | null; bear?: number | null } | undefined;

export function Prob({ p }: { p: Probs }) {
  if (!p) return null;
  const f = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${Math.round(v * 100)}%`);
  return (
    <span className="font-mono text-xs">
      ↑{f(p.bull)} ·{f(p.base)} ↓{f(p.bear)}
    </span>
  );
}

export function Section({ title, children, sub }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="border border-neutral-200 rounded bg-white p-4">
      <h2 className="font-semibold mb-1">{title}</h2>
      {sub && <p className="text-xs text-neutral-500 mb-2">{sub}</p>}
      <div className="text-sm leading-6 space-y-2">{children}</div>
    </section>
  );
}

/** LLM 이 쓴 문단 — \n 을 문단으로 */
export function Para({ text }: { text: unknown }) {
  if (text === null || text === undefined || text === "") return null;
  const s = typeof text === "string" ? text : JSON.stringify(text, null, 1);
  return (
    <>
      {s.split(/\n{1,}/).map((p, i) => (
        <p key={i} className="whitespace-pre-wrap">
          {p}
        </p>
      ))}
    </>
  );
}

export function Sev({ s }: { s: string | undefined }) {
  const cls = s === "high" ? "bg-rose-100 text-rose-900" : s === "medium" ? "bg-amber-100 text-amber-900" : "bg-neutral-100 text-neutral-700";
  return <span className={`text-xs rounded px-1.5 py-0.5 ${cls}`}>{s ?? "–"}</span>;
}

export function Url({ u, label }: { u: unknown; label?: string }) {
  if (!u || typeof u !== "string" || !/^https?:/.test(u)) return label ? <span>{label}</span> : null;
  return (
    <a className="underline text-neutral-600 break-all" href={u} target="_blank" rel="noreferrer">
      {label ?? u.replace(/^https?:\/\//, "").slice(0, 60)}
    </a>
  );
}
