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
    data_go_kr_service_key: str

    @classmethod
    def load(cls) -> "Settings":
        # Resolve data paths relative to project ROOT, not CWD — collector
        # scripts may be launched from any directory.
        def _resolve(env_name: str, default: str) -> Path:
            p = Path(os.getenv(env_name, default))
            return p.resolve() if p.is_absolute() else (ROOT / p).resolve()

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
            local_db_path=_resolve("LOCAL_DB_PATH", "./data/naverreal.sqlite"),
            snapshot_dir=_resolve("SNAPSHOT_DIR", "./data/snapshots"),
            data_go_kr_service_key=os.getenv("DATA_GO_KR_SERVICE_KEY", ""),
        )


settings = Settings.load()
