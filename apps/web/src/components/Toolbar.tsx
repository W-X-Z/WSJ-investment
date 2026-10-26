import Link from "next/link";

/** GET 폼 기반 필터 + 페이지 이동. 상태 없음 — URL 이 전부. */
export function Toolbar({
  path,
  params,
  fields,
  page,
  count,
  pageSize,
}: {
  path: string;
  params: Record<string, string>;
  fields: { name: string; placeholder: string; type?: "text" | "date"; options?: string[] }[];
  page: number;
  count: number | null;
  pageSize: number;
}) {
  const qs = (overrides: Record<string, string>) => {
    const p = new URLSearchParams({ ...params, ...overrides });
    for (const [k, v] of [...p.entries()]) if (!v) p.delete(k);
    const s = p.toString();
    return s ? `${path}?${s}` : path;
  };
  const last = count ? Math.max(1, Math.ceil(count / pageSize)) : null;
  return (
    <form method="get" action={path} className="flex flex-wrap items-end gap-2 mb-3">
      {fields.map((f) =>
        f.options ? (
          <select key={f.name} name={f.name} defaultValue={params[f.name] ?? ""} className="border rounded px-2 py-1 bg-white">
            <option value="">{f.placeholder}</option>
            {f.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        ) : (
          <input
            key={f.name}
            name={f.name}
            type={f.type ?? "text"}
            placeholder={f.placeholder}
            defaultValue={params[f.name] ?? ""}
            className="border rounded px-2 py-1 bg-white w-44"
          />
        ),
      )}
      <button className="border rounded px-3 py-1 bg-neutral-900 text-white">조회</button>
      <span className="ml-auto flex items-center gap-2 text-neutral-500">
        {count !== null && <span>{count.toLocaleString()} rows</span>}
        <Link className={page <= 1 ? "pointer-events-none opacity-30" : "underline"} href={qs({ page: String(page - 1) })}>
          이전
        </Link>
        <span>
          {page}
          {last ? ` / ${last}` : ""}
        </span>
        <Link className={last && page >= last ? "pointer-events-none opacity-30" : "underline"} href={qs({ page: String(page + 1) })}>
          다음
        </Link>
      </span>
    </form>
  );
}
