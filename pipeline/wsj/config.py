"""환경변수 → Settings. .env는 pipeline/ 디렉터리 기준으로 읽는다."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PIPELINE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PIPELINE_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # store
    wsj_store: Literal["postgrest", "sqlite"] = "postgrest"
    wsj_sqlite_path: Path = PIPELINE_DIR / "data" / "wsj.sqlite"
    supabase_url: str = ""
    supabase_secret_key: str = ""

    # sources
    sec_user_agent: str = "WSJ-investment research contact@example.com"
    openfda_api_key: str = ""
    dart_api_key: str = ""  # 한국 DART OpenAPI (선택) — 없으면 한국 기업은 뉴스로만 본다
    openalex_api_key: str = ""  # 논문 백필 (wsj.ecosystems.techdocs papers)
    openalex_mailto: str = ""

    # briefs (Analyst / Risk)
    anthropic_api_key: str = ""
    wsj_brief_model: str = "haiku"  # 기본 저비용 분석; 중요한 후보만 sonnet

    # 선별 에이전트 (python -m wsj screen) — 실행당 상한을 넘을 것 같으면 묶음을 더 보내지 않는다
    screen_model: str = "claude-sonnet-5-5"
    screen_max_input_tokens: int = 400_000
    screen_max_usd: float = 2.0
    screen_report_rpc: str = "put_reports"   # 'put_reports' 또는 'schema.put_reports'. 없으면 research → ideas → public 순으로 찾는다
    screen_body_chars: int = 4000            # 단서 본문은 앞부분만
    screen_batch_tokens: int = 60_000        # 묶음 하나의 입력(추정) 상한
    screen_effort: str = "medium"            # 빈 값이면 effort 를 보내지 않는다

    # misc
    wsj_log_level: str = "INFO"
    wsj_data_dir: Path = PIPELINE_DIR / "data"

    def require_supabase(self) -> None:
        if self.wsj_store == "postgrest" and not (self.supabase_url and self.supabase_secret_key):
            raise SystemExit(
                "SUPABASE_URL / SUPABASE_SECRET_KEY 가 없습니다. pipeline/.env 를 채우거나 "
                "WSJ_STORE=sqlite 로 로컬 검증을 실행하세요."
            )


def load_settings() -> Settings:
    return Settings()
