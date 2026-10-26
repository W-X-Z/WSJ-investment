import { createClient } from "@supabase/supabase-js";

/** 서버 컴포넌트용 읽기 전용 클라이언트. publishable 키 + RLS(SELECT) 로만 접근한다. */
export function db(schema: "public" | "raw" | "core" | "ops" | "ideas" = "public") {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_KEY;
  if (!url || !key) {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_KEY 가 없습니다 (.env.local)");
  }
  return createClient(url, key, {
    db: { schema },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export const PAGE_SIZE = 100;

export type SearchParams = Record<string, string | string[] | undefined>;

export function param(sp: SearchParams, key: string, fallback = ""): string {
  const v = sp[key];
  return (Array.isArray(v) ? v[0] : v) ?? fallback;
}

export function pageOf(sp: SearchParams): number {
  const n = parseInt(param(sp, "page", "1"), 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

export function range(page: number): [number, number] {
  return [(page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1];
}
