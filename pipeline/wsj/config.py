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

    # briefs (Analyst / Risk)
    anthropic_api_key: str = ""
    wsj_brief_model: str = "haiku"  # 기본 저비용 분석; 중요한 후보만 sonnet

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
