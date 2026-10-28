# ADR-0021: 시장 범위 — 아이디어의 주 기업은 미국·한국 상장사

상태: accepted (2026-10-29). 사용자: "주식 접근성이 좋은 미국, 한국 기업 위주로 해도 될 것 같아."

## 문제
첫 수동 실행(10/29)의 활성 아이디어 12건 중 6건의 주 기업이 대만(TWSE·TPEx)·독일(Xetra)·프랑스(Euronext)·일본(TSE) 상장사였다.
사용자가 바로 거래할 수 없는 시장이고, 그 시장의 가격·주식수·재무 출처도 없어 절반은 가치평가조차 못 했다(AIXTRON·Soitec·SUSS·Mitsui).
반면 공급망의 변화는 그 시장의 기업(TSMC·Unimicron·力成·群翊)에서 자주 시작된다 — 그 소식은 신호로 꼭 필요하다.

## 결정
1. **주 기업(primary)은 미국(NYSE·Nasdaq·NYSE American)·한국(KRX·KOSDAQ) 상장사만** (`wsj.ecosystems.scope.IDEA_EXCHANGES`).
   미국 거래소의 ADR(TSM·ASX 등)은 범위 안, OTC 는 밖.
2. 다른 시장의 기업은 그래프에서 빼지 않는다. 그 소식·월매출·가동률은 신호(E)와 근거로 계속 쓰고, companies 에 고객·경쟁·동종 역할로 들어간다.
   후보(candidates)·단서(leads: company_leads·uncovered·price_leads·second_order)는 범위 안 기업만, 동종사(peers)에는 '범위 밖(거래소)' 표시.
3. 검증기: 범위 밖 주 기업의 새 아이디어·갱신은 거부. 기존 아이디어의 주 기업이 범위 밖이면 keep·weaken 을 close 로 바꾼다(사유 "시장 범위 밖 — ADR-0021").
   update 가 범위 안 기업으로 옮기면 받는다.
4. 프롬프트·일일 지침: 변화가 범위 밖 기업에서 시작됐으면 같은 경로의 미국·한국 고리(그 기업의 고객·장비·소재 공급사, 같은 부품의 미국·한국 동종사,
   대체·보완 기술의 미국·한국 기업)를 찾고, 없으면 아이디어를 만들지 않고 states·leads 로만 남긴다.

## 결과
- 10/29 범위 밖 활성 아이디어 6건(力成·群翊·AIXTRON·Soitec·SUSS·Mitsui Kinzoku)을 같은 사유로 종료. 활성 6건(유니테스트·테크윙·MaxLinear·Ideal Power·AXT·Methode).
- 유럽 가격·일본·중국 재무 수집은 하지 않는다(ADR-0019 의 남은 일에서 제외). 대만 월매출·재무 수집은 신호·관측치용으로 유지.
- 범위를 넓히려면 `IDEA_EXCHANGES` 한 줄과 이 ADR 의 후속으로.
