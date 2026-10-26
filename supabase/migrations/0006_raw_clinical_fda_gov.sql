-- 0006: raw.ct_* (ClinicalTrials.gov v2), raw.fda_* (openFDA), raw.gov_awards (USAspending)

-- ClinicalTrials: 현재 스냅샷. 이력 API가 없으므로 매 수집 시 diff를 ct_study_changes에 남긴다.
create table if not exists raw.ct_studies (
  nct_id                    text primary key,
  brief_title               text,
  lead_sponsor_name         text,
  overall_status            text,
  why_stopped               text,
  status_verified_date      text,          -- 'YYYY-MM'
  start_date                text,          -- 'YYYY-MM-DD' 또는 'YYYY-MM' (소스가 섞어 씀)
  primary_completion_date   text,
  completion_date           text,
  study_first_post_date     date,
  last_update_submit_date   date,
  last_update_post_date     date,
  phases                    text[],
  enrollment_count          integer,
  enrollment_type           text,
  study_type                text,
  conditions                text[],
  interventions             text[],
  payload                   jsonb,
  first_seen_at             timestamptz not null default now(),
  snapshot_at               timestamptz not null default now()
);
create index if not exists ct_studies_sponsor_idx on raw.ct_studies (lead_sponsor_name);
create index if not exists ct_studies_status_idx  on raw.ct_studies (overall_status);

-- 변경 이벤트: 이전 스냅샷 대비 달라진 필드
create table if not exists raw.ct_study_changes (
  id            bigint generated always as identity primary key,
  nct_id        text not null references raw.ct_studies (nct_id) on delete cascade,
  detected_at   timestamptz not null default now(),
  field         text not null,        -- overall_status | primary_completion_date | enrollment_count | ...
  old_value     text,
  new_value     text,
  unique (nct_id, detected_at, field)
);
create index if not exists ct_study_changes_detected_idx on raw.ct_study_changes (detected_at desc);
create index if not exists ct_study_changes_nct_idx on raw.ct_study_changes (nct_id);

-- openFDA drugsfda: 승인 신청(NDA/BLA/ANDA)과 제출 이력
create table if not exists raw.fda_drug_applications (
  application_number  text primary key,
  sponsor_name        text,
  brand_names         text[],
  generic_names       text[],
  product_count       integer,
  latest_submission_status       text,
  latest_submission_status_date  date,
  latest_submission_type         text,
  latest_submission_class        text,
  submissions         jsonb,         -- 전체 제출 이력
  products            jsonb,
  payload             jsonb,
  ingested_at         timestamptz not null default now()
);
create index if not exists fda_drug_apps_sponsor_idx on raw.fda_drug_applications (sponsor_name);
create index if not exists fda_drug_apps_status_date_idx on raw.fda_drug_applications (latest_submission_status_date desc);

-- openFDA device/510k
create table if not exists raw.fda_device_510k (
  k_number          text primary key,
  applicant         text,
  device_name       text,
  product_code      text,
  decision_code     text,
  decision_date     date,
  date_received     date,
  clearance_type    text,
  advisory_committee text,
  third_party_flag  text,
  payload           jsonb,
  ingested_at       timestamptz not null default now()
);
create index if not exists fda_510k_applicant_idx on raw.fda_device_510k (applicant);
create index if not exists fda_510k_decision_idx  on raw.fda_device_510k (decision_date desc);

-- USAspending: 계약 awards (수신자명 검색 기반). generated_internal_id가 자연키.
create table if not exists raw.gov_awards (
  generated_internal_id       text primary key,
  award_id                    text,
  recipient_name              text,
  recipient_uei               text,
  award_amount                numeric,
  total_outlays               numeric,
  description                 text,
  start_date                  date,
  end_date                    date,
  base_obligation_date        date,
  last_modified_date          timestamptz,
  awarding_agency             text,
  awarding_sub_agency         text,
  naics_code                  text,
  naics_description           text,
  psc_code                    text,
  psc_description             text,
  contract_award_type         text,
  def_codes                   text[],
  search_text                 text,            -- 어떤 검색어로 잡혔는지
  payload                     jsonb,
  ingested_at                 timestamptz not null default now()
);
create index if not exists gov_awards_recipient_idx on raw.gov_awards (recipient_name);
create index if not exists gov_awards_uei_idx       on raw.gov_awards (recipient_uei);
create index if not exists gov_awards_modified_idx  on raw.gov_awards (last_modified_date desc);

alter table raw.ct_studies            enable row level security;
alter table raw.ct_study_changes      enable row level security;
alter table raw.fda_drug_applications enable row level security;
alter table raw.fda_device_510k       enable row level security;
alter table raw.gov_awards            enable row level security;
create policy "read raw" on raw.ct_studies            for select to anon, authenticated using (true);
create policy "read raw" on raw.ct_study_changes      for select to anon, authenticated using (true);
create policy "read raw" on raw.fda_drug_applications for select to anon, authenticated using (true);
create policy "read raw" on raw.fda_device_510k       for select to anon, authenticated using (true);
create policy "read raw" on raw.gov_awards            for select to anon, authenticated using (true);
