import { STAR_LABEL } from "@/lib/research-client";

/** ★1~3. 판단 근거는 title 툴팁으로. */
export function Stars({ n, why, label = false }: { n: number; why?: string; label?: boolean }) {
  if (!n) return null;
  return <span className={`stars stars-${n}`} title={why} aria-label={`별 ${n}개 (3개 만점)${label ? ` · ${STAR_LABEL[n]}` : ""}`}>
    <span aria-hidden="true">{"★".repeat(n)}<i>{"★".repeat(3 - n)}</i></span>{label && <em>{STAR_LABEL[n]}</em>}
  </span>;
}
