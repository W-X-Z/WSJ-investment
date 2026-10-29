# JSON 그래프 패치 (ADR-0027)

매일 발굴 작업(`docs/agents/daily/discover.md`)이 작은 테제(micro)의 소형·중형 공급사와 그 근거 간선을 그래프에 넣는 곳이다.
예약작업은 파이프라인 코드를 바꾸지 않으므로 파이썬 패치(`pipeline/wsj/ecosystems/graph_patches/p*.py`) 대신 여기 데이터로 적는다.

- 파일: `YYYYMMDD_discover.json` — 형식은 `pipeline/wsj/ecosystems/graph_patches/from_json.py` 맨 위 설명.
- 적용: `cd pipeline && .venv/bin/python -m wsj.ecosystems.graph_patches.from_json ../research/ecosystems/patches/<file>.json && .venv/bin/python -m wsj.ecosystems.export_web`
- 규칙: 기업은 상장사만(ticker·exchange), 간선마다 https 원문 근거 1개 이상, 원문에서 읽은 것만. 멱등이라 다시 적용해도 같다. 온톨로지 검증이 실패하면 그래프를 쓰지 않는다.
- 병합: 바뀐 파일이 `research/` 와 `apps/web/src/data/` 안뿐이고 CI 가 모두 통과하면 발굴 작업이 스스로 병합한다 (그 밖이 바뀌면 병합하지 않는다).
