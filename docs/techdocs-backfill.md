# 논문·특허 백필 — 사용자 PC 에서 한 번 돌리기

기술은 매출보다 몇 년 먼저 움직인다. 논문·특허의 긴 시계열을 한 번 채워 두면, 해석 작업이 단서를 읽을 때
`recall` 이 그 노드의 **연도별 흐름 · 최근 많이 낸 곳 · 새로 나타난 곳 · 대표 문서**를 함께 보여 준다.

- 특허: Google Patents 공개 데이터 (BigQuery `patents-public-data.patents.publications`) — 미국·한국·일본·대만·유럽·PCT, 2018년 이후 공개.
  키워드가 아니라 **CPC 분류**(research/techdocs/cpc_domains.json)로 먼저 고르고, 그래프 어휘로 노드를 붙인다. 같은 발명(패밀리)은 한 건.
- 논문: OpenAlex — **주제 분류**(research/techdocs/openalex_topics.json)별 연도 건수(2015~)와, **기업 소속 저자**가 있는 논문(2021~).
- 결과는 Supabase 의 `ideas.tech_series`(노드×분기 건수) · `ideas.tech_orgs`(노드×기간 상위 기관) · `ideas.tech_docs`(노드별 대표 문서).

## 0. 준비 (한 번)
1. **Supabase**: SQL 편집기에서 `supabase/migrations/0033_techdocs.sql` 실행.
2. **저장소**: `git pull` 후
   ```
   cd pipeline
   python -m venv .venv
   .venv\Scripts\activate          # macOS·Linux: source .venv/bin/activate
   pip install -e ".[techdocs]"
   ```
3. **Google Cloud (특허)** — 카드 등록 없는 BigQuery 샌드박스로 충분하다 (조회 무료 한도 월 1TB).
   - https://console.cloud.google.com 에서 프로젝트를 하나 만들고 BigQuery 를 연다 (샌드박스 안내가 뜬다). 프로젝트 ID 를 적어 둔다.
   - Google Cloud CLI 설치 후 `gcloud auth application-default login` (브라우저로 로그인).
4. **OpenAlex (논문)** — https://openalex.org 에서 무료 API 키를 받는다 (키가 없으면 하루 사용량이 아주 작다).
5. **pipeline/.env** (저장소에 올라가지 않는 파일):
   ```
   SUPABASE_URL=https://dcatgfivsvbktylmtvgf.supabase.co
   SUPABASE_SECRET_KEY=<Supabase 대시보드의 secret 키>
   OPENALEX_API_KEY=<OpenAlex 키>
   ```
   PowerShell 에서 OpenAlex 키는 `$env:OPENALEX_API_KEY="…"` 로 넣어도 된다.

## 1. 실행 (pipeline 폴더에서)
```
python -m wsj.ecosystems.techdocs patents --gcp-project <프로젝트ID> --dry-run   # 스캔 용량만 확인 — 1,000GB 아래인지
python -m wsj.ecosystems.techdocs patents --gcp-project <프로젝트ID>             # 30~60분, data/techdocs/raw/patents.jsonl.gz
python -m wsj.ecosystems.techdocs papers                                         # 20~40분, OpenAlex 하루 무료 한도 안
python -m wsj.ecosystems.techdocs build                                          # 몇 분, data/techdocs/out/ 와 summary.md
python -m wsj.ecosystems.techdocs upload --replace                               # Supabase 로
```
- `--dry-run` 에서 합계가 1,000GB 를 넘으면 `--since 2020-01-01` 이나 `--countries US,KR,JP` 로 줄인다 (기본 한도 `--max-gb 900`).
- 중국(CN) 특허는 양이 많아 기본에서 뺐다. 넣으려면 `--countries US,KR,JP,TW,EP,WO,CN`.
- 받는 것과 묶는 것이 나뉘어 있어서, 어휘(research/techdocs/patent_terms.json)를 고친 뒤에는 `build` → `upload --replace` 만 다시 돌리면 된다.

## 2. 확인
- `data/techdocs/out/summary.md` — 최근 2년에 가장 빨리 늘어난 노드, 2024년 이후 처음 나타난 기관.
- 실행 결과의 숫자(받은 특허 수, 노드가 붙은 문서 수, 올린 행 수)를 Claude 에게 알려 주면, 어휘가 빠진 노드나 이상한 태깅을 같이 고친다.
- 해석 작업에서는: `python -m wsj.ecosystems.recall --node component:tsv` 의 맨 아래 '논문·특허' 절.

## 3. 막히면
- `google.auth.exceptions.DefaultCredentialsError` → `gcloud auth application-default login` 을 다시.
- `403 ... BigQuery API has not been used` → 콘솔에서 그 프로젝트의 BigQuery API 사용 설정.
- OpenAlex `429` → 키를 넣었는지 확인. 하루 한도를 넘었으면 다음 날 `papers` 만 다시 (UTC 자정에 초기화).
- `upload` 에서 `relation "ideas.tech_docs" does not exist` → 0033 을 먼저.
