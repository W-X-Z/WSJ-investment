export function fmtNum(v: unknown, digits = 0): string {
  if (v === null || v === undefined || v === "") return "";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function fmtUsd(v: unknown): string {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return "";
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(2)}`;
}

export function fmtDate(v: unknown): string {
  if (!v) return "";
  const s = String(v);
  return s.length > 10 ? s.slice(0, 16).replace("T", " ") : s;
}

export function fmtList(v: unknown, max = 3): string {
  if (!Array.isArray(v)) return v ? String(v) : "";
  return v.slice(0, max).join(", ") + (v.length > max ? ` +${v.length - max}` : "");
}
