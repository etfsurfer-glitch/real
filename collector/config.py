from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_secret_key: str
    supabase_anon_key: str
    naver_concurrency: int
    naver_delay_ms: int
    naver_timeout_sec: int
    naver_user_agent: str
    local_db_path: Path
    snapshot_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_secret_key=os.getenv("SUPABASE_SECRET_KEY", ""),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            naver_concurrency=int(os.getenv("NAVER_CONCURRENCY", "4")),
            naver_delay_ms=int(os.getenv("NAVER_REQUEST_DELAY_MS", "250")),
            naver_timeout_sec=int(os.getenv("NAVER_TIMEOUT_SEC", "15")),
            naver_user_agent=os.getenv(
                "NAVER_USER_AGENT",
                "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            ),
            local_db_path=Path(os.getenv("LOCAL_DB_PATH", "./data/naverreal.sqlite")).resolve(),
            snapshot_dir=Path(os.getenv("SNAPSHOT_DIR", "./data/snapshots")).resolve(),
        )


settings = Settings.load()
