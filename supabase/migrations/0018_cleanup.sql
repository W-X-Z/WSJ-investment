-- 0018: 데이터 정리 (0017 이후). ADR-0015 개정 1 · ADR-0016.

-- 1) 데이터 없는 옛 지표 정의
delete from ideas.indicators where indicator_id like 'fred:PCU%' or indicator_id = 'bls:PCU335921335921';

-- 2) 목적 밖 유니버스 정리 (원자료는 보존): 피벗 전 SIC 버킷은 신호·브리프 대상에서 내린다
update core.companies set in_universe = false, universe_reason = 'retired:legacy-sic-bucket', updated_at = now()
where in_universe and coalesce(universe_reason, '') not like 'ontology%';

-- 3) 세션 큐레이션 이슈 잠금, 중복 병합, 자동 실행에 덮인 큐레이션 1건 복원
update ideas.supply_chain_issues set locked = true, method = 'curated' where model like 'claude-opus%';
update ideas.supply_chain_issues set status = 'merged',
  merged_into = (select issue_key from ideas.supply_chain_issues where title like 'HBM4 사양 하향%' and status = 'active' order by importance desc limit 1)
where title like 'Samsung, NVIDIA용 HBM 베이스다이%' and status = 'active'
  and exists (select 1 from ideas.supply_chain_issues where title like 'HBM4 사양 하향%' and status = 'active');
update ideas.supply_chain_issues set
  title = 'MaxLinear 3분기 매출 +72%, 1.6T·AEC 로 확장',
  summary = 'MaxLinear 3분기 매출은 2억 1,810만 달러로 전년 대비 72%, 인프라 부문은 210% 늘었다(8-K EX-99.1). 회사는 Keystone PAM4 DSP 양산 확대와 1.6T 대응 Rushmore·Annapurna 제품군을 성장 동력으로 꼽았다. 같은 주 MaxLinear 가 AEC(능동 전기 케이블) 시장 진출을 밝히자 Credo 주가가 하루 약 10% 하락했다는 보도가 나왔다.',
  why_it_matters = '광 DSP 는 800G→1.6T 전환의 핵심 칩이고, 소형사 MaxLinear 가 Marvell·Broadcom 이 쥔 영역에서 매출로 확인되기 시작했다. AEC 진입은 Credo 의 독점적 지위에 대한 첫 경쟁 신호다.',
  event_type = 'earnings', ecosystem = 'optics', importance = 8,
  importance_rationale = '1차 출처(8-K) + 독립 출판사 6곳 이상, 소형 공급사의 실적으로 확인된 병목 진입, 경쟁사(Credo) 영향까지 포함.',
  nodes = array['component:optical_dsp','gen:1p6t','component:aec','product:credo_aec'],
  companies = '[{"company_id":"company:mxl","direction":"+","basis":"Q3 매출 YoY +72%, 인프라 +210%, Keystone PAM4 DSP 양산 확대 (8-K)"},{"company_id":"company:crdo","direction":"-","basis":"MaxLinear 가 Credo 주력 AEC 시장 진출을 밝혔다는 보도"}]'::jsonb,
  method = 'curated', model = 'claude-opus-5-5 (session curation)', locked = true
where issue_key = '3fcc15c9b7c92474b124';
