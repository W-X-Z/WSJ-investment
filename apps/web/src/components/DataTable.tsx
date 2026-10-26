import type { ReactNode } from "react";

export type Column<T> = {
  key: string;
  label: string;
  num?: boolean;
  render?: (row: T) => ReactNode;
};

export function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
  empty = "데이터 없음",
}: {
  rows: T[];
  columns: Column<T>[];
  empty?: string;
}) {
  if (!rows.length) return <p className="text-neutral-500 py-6">{empty}</p>;
  return (
    <div className="overflow-auto border border-neutral-200 rounded bg-white max-h-[75vh]">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : ""}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? "num" : ""}>
                  {c.render ? c.render(r) : String(r[c.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
