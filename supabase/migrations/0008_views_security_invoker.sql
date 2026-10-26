-- 0008: 조회 뷰를 security_invoker 로 전환 (Supabase 보안 린터 0010 대응).
-- 뷰가 생성자(postgres) 권한이 아니라 조회자 권한·RLS 로 실행되게 한다.
-- anon 에는 raw/core/ops SELECT 정책이 있으므로 조회 화면은 그대로 동작한다.

alter view public.v_collector_overview   set (security_invoker = true);
alter view public.v_table_counts         set (security_invoker = true);
alter view public.v_insider_transactions set (security_invoker = true);
