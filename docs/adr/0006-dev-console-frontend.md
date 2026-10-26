# ADR-0006: 개발용 조회 화면은 Next.js 최소 구성

- 상태: accepted
- 날짜: 2026-10-26

## 맥락

"개발 단계를 위한 화면이니 공을 많이 들이지 않아도 된다"는 요구. 수집된 데이터를 테이블로 훑어보고 수집 상태를 확인하는 것이 전부다. 후보: Streamlit(Python), Next.js(Vercel), Supabase Studio만 쓰기.

## 결정

1. **Next.js App Router + supabase-js, 서버 컴포넌트에서 직접 조회.** 사용자가 이미 Vercel에 Next.js 프로토타입을 여러 개 올리고 있어 배포 경로가 익숙하다. Studio는 스키마별 조인·집계 뷰를 보기 불편하고, Streamlit은 호스팅이 하나 더 생긴다.
2. 스타일링은 Tailwind 기본값, 컴포넌트 라이브러리 없음. 페이지 = 테이블 + 필터 몇 개.
3. 읽기 전용. publishable key + RLS `SELECT` 정책(`raw`, `core`, `ops`)으로만 접근. 쓰기는 파이프라인만.
4. 페이지: 개요(수집기 상태·행 수·미매칭 건수), companies, insider(Form 4), filings(8-K), finra, trials, fda, awards.

## 결과

- 이 화면은 나중에 에이전트 작업물(ideas/proposals/decisions)을 보는 콘솔로 확장한다. 그때 디자인 투자.
- 배포는 Vercel에 `apps/web`를 루트로 연결. 지금은 로컬 `npm run dev`로 충분.
