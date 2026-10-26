# SIGNAL ATLAS — 기술 생태계 기반 투자 리서치 워크스페이스

- 상태: **Phase 1 UI 구현 + DB schema 제안** (2026-10-26)
- 대상 리포지토리: `W-X-Z/WSJ-investment` / Next.js 16 / Vercel
- 기반 데이터: 기존 Supabase `public.v_briefs`, `public.v_signals`, `public.v_candidates` (읽기 전용) + 소스가 확인된 기술 지식 그래프 2026-10-26 시드
- 운영 DB 마이그레이션: **아직 적용하지 않음**. 초기 UI는 기술 시드 + 기존 조회 가능한 DB의 기업 신호를 조합

## 1. 제품 목표
투자자는 SEC/FDA 등 각 테이블이 몇 행 적재됐는지보다는 다음에 답해야 한다.

1. **지금 무엇이 달라지고 있나?** 산업별 중요한 기술 변화와 원문
2. **왜 변화가 중요한가?** 성능 요구 -> 기술 병목 -> 해결 소재·부품·공정 -> 잠재 공급기업
3. **누가 실제 가치를 얻을 수 있나?** 기술 적합성과 실제 qualification/납품/매출의 구별
4. **다음에 무엇이 일어나야 하는가?** 구체적인 감시 조건과 반증 항목
5. **과거 주장과 무엇이 다른가?** 날짜·출처별 기술적 증거, 가설 강화/약화 이력

주가/매매는 결과 또는 별도 판단 레이어이며 **투자 아이디어 발굴의 입력이 아님**.

## 2. 정보 구조
```text
SIGNAL ATLAS  [sidebar]
├─ 인사이트 홈                         /
│  ├─ 3개 기술 생태계 카드
│  ├─ 주요 이슈 · 기업 투자 가설
│  ├─ 공급망 Impact Map 미리보기
│  └─ 기존 DB 데이터 접속 상태
├─ 기술 생태계                         /ecosystems
│  └─ HBM, 1.6T Optics, 800VDC       /ecosystems/[slug]
│     ├─ 기술 로드맵 + 정량 지표
│     ├─ 인과 관계 노드 선택 / 근거 패널
│     ├─ 최근 관련 사건·감시 규칙
│     └─ 관련 기업 / 출처
├─ 이슈 피드                            /feed
│  └─ 이슈 근거·영향 상세               /feed/[id]
├─ 투자 가설                            /ideas
│  └─ 기업/기술 가설 상세               /ideas/[id]
├─ 트리거 추적                          /triggers
├─ 통합 검색 (Ctrl/⌘ K)                /search?q=
└─ 데이터 워크스페이스 (2-depth 이하)   /data
   ├─ 적재 모니터링                     /data/collectors
   ├─ 기존 브리프·후보·신호             /briefs, /candidates, /signals
   └─ 원천 데이터                       /filings, /fda, /finra, ...
```

## 3. 주요 화면 설계 원칙
- **Top 1:** 세 도메인의 핵심 기술 요구와 병목, 최신 업데이트가 한눈에 보인다.
- **Top 2:** 정량화된 관측 자료는 사건 카드 / 영향 그래프 / 회사 가설로 연결된다.
- **2-depth:** 현업 연구를 뒷받침하는 원본 수집 상태·Raw tables는 유지하지만 주메뉴에서는 숨긴다.
- **Graph:** node types, edge predicate, polarity, epistemic state, evidence source를 분리한다. Edge를 클릭/Node를 선택하면 우측 inspector에 관계와 문서 확인 경로를 보여준다.
- **Feed:** 원문 발행일 기준 시계열, ecosystem/importance/query 필터, 클릭하면 원문 근거와 관련 기술 경로. 운영 DB 신호는 '기업 신호', 기술 시드는 '큐레이션'으로 구분.
- **Idea:** 투자 가설, 검증 단계, 반대 가설, 다음 이벤트, 공개 근거. 수익률 예측은 제거.
- **Search:** 통합 키워드/티커/정량 변수, 기술 노드/피드/가설/생태계의 초기 소규모 검색. 차후 서버측 text search + GIN + Korean analyzer로 고도화.
- **Visual language:** 논리적 정보 위계를 우선한 금융 리서치 워크스페이스. 어두운 업무 네비게이션, 중립 화이트/슬레이트 본문, 기술 종류별 보조색, 가설 단계/중요도 배지.
- **Responsive:** desktop 4-stage graph + inspector / mobile horizontal graph scrolling + stacked inspector. Sidebar mobile overlay, 검색 Ctrl/⌘ K.
- **A11y:** native link/button/heading, visible focus, aria label, URL 기반 필터, 폼 제출.

## 4. 데이터 계약/DB 설계
- 구현 제안: `supabase/migrations/0011_technology_intelligence.sql` (운영 미적용)
- `core.tech_ecosystems`: ecosystem slug, wiki ref, lifecycle
- `core.tech_nodes`: typed concept (equipment, material, component, bottleneck, etc)
- `core.tech_edges`: typed, dated, directional relationship; confidence, polarity, supersession
- `raw.tech_sources`: original source revision/hash/publisher/publication/first-seen, licensing
- `raw.tech_claims`: atomic claim, measured value+unit+conditions, quote locator, epistemic status
- `core.tech_edge_evidence`: edges ↔ claims, supports/contradicts
- `core.tech_company_exposures`: CIK/company mapping, **candidate vs verified qualification/shipments/revenue**
- `core.tech_events`: normalized new evidence or quantitative delta
- `ideas.tech_hypotheses` + `ideas.tech_hypothesis_evidence`: versioned investment thesis and contradiction
- `ops.tech_watch_rules/runs/alerts`: trigger configuration, checkpoints, dedupe, review/notify lifecycle

### Source-of-truth & cache policy
- 초기 기술 그래프 원본: `research/ecosystems/seed_graph.json`, 앱용 복제: `apps/web/src/data/ecosystem-seed.json`
- `python3 apps/web/scripts/sync_ecosystem_seed.py`로 동기화, `--check`는 CI 실패 처리.
- 민감한 사내 해석·비공개 사용자 판단은 공개 publishable/anon key로 가져오지 않는다.
- **현재 UI에서 표시되는 기술 이벤트는 연구용 시드**이며, 별도 GitHub 모니터의 신규 수집 결과가 자동으로 반영되는 DB 엔드포인트는 아직 없다.
- 웹에서 legacy `v_briefs`, `v_signals`, `v_candidates`를 안전하게 읽을 수 없으면 새 UI가 무너지지 않도록 시드 데이터로 표시한다.
- 운영 스케줄, 미확인 9개 watch rule의 발화(Trigger firing)와 푸시는 이 PR에 포함되지 않는다. 기존 원천 수집 파이프라인은 건드리지 않는다.

## 5. 신규 그래프 DB 실제 적용 조건
1. 인증 및 정책을 먼저 확정: 현재 기존 앱의 익명 조회 정책을 그대로 확장하면 가설·추정치가 공개될 수 있다.
2. `0011` 마이그레이션을 개발/스테이징 DB에서 검증하고, 부여된 schema grants/기본 RLS를 확인.
3. 추적할 원천 및 assertion 각 row에 first_seen_at, original_published_at, ingestion timestamp, content hash를 별도 확보.
4. 기존 Python collector에 새로운 tech_sources/claims upsert 제공, raw→graph 검증 파이프라인.
5. **공개 가능한 리서치만** 명시적으로 projection하는 읽기 전용 서버 API 또는 security-invoker view 작성; 이때는 사이트 인증 및 policy 동시 적용.
6. `data_version` 기준으로 UI seed를 live tech graph로 점진 교체. 사용자 화면에 refresh metadata 명시.
7. alert candidate→human validated→notification 과정 및 알림 피로도 테스트.

## 6. 확인할 시나리오
1. 모바일/데스크톱 홈에서 3 생태계의 기술적 변화와 최근 이슈 인지가 가능
2. 그래프에서 미세 접합 병목 → 검사 기술 → CAMT, 또는 800VDC → SiC → AEHR 경로 탐색 시 **미검증** 표시
3. 원문 없는 공급 관계를 계약/매출이라고 표시하지 않음
4. `/search?q=HBM`, `/search?q=POET`, `/search?q=800V` 검색 결과
5. 피드의 기술/중요도 필터와 상세 원문 클릭
6. 가설 반대 근거/다음 트리거를 해당 페이지에서 확인
7. `/data` → `/data/collectors`에서 기존 수집 테이블 확인
8. DB/API 오류 또는 빈 데이터에도 UI가 연구 시드와 출처로 정상 렌더링
9. `npm run typecheck`, `npm run build`, 시드 `--check` 통과
10. SSO 보호 프리뷰에서 접근 확인 후 production 병합/배포

## 7. 향후 구축 우선순위
- **P1** 읽기·검색·시각화와 도메인 seed, 검증 가능한 링크 (이번 PR)
- **P2** 인증된 기술 그래프 DB와 evidence ingestion, 정규화된 사건·정량 속성 조회
- **P3** 신규 버전 비교/원문 diff·독립 검증 후 알림, trigger 상태 변화
- **P4** 장기 추적성과 회고 학습, 공급망 대체 영향·매출 전환 밴드 분석
