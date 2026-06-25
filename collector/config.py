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
    naver_source_ips: str  # 멀티 IP 병렬 수집용 소스 IP(쉼표구분). 비면 단일(기본 라우팅).
    local_db_path: Path
    snapshot_dir: Path
    data_go_kr_service_key: str
    admin_emails: str   # 관리자 카카오 로그인 이메일(쉼표구분). 관리자 페이지 접근 허용 목록.
    admin_user_ids: str  # 관리자 user_id(uid) 쉼표구분 — 글·리뷰에 '관리자' 표시용(타인에게 노출)
    aligo_api_key: str  # 알리고 SMS API 키 (전화번호 인증). 미설정 시 dev 모드(코드 응답 노출).
    aligo_user_id: str  # 알리고 계정 아이디
    aligo_sender: str   # 알리고 발신번호(사전등록 필요)

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
            naver_source_ips=os.getenv("NAVER_SOURCE_IPS", ""),
            local_db_path=_resolve("LOCAL_DB_PATH", "./data/naverreal.sqlite"),
            snapshot_dir=_resolve("SNAPSHOT_DIR", "./data/snapshots"),
            data_go_kr_service_key=os.getenv("DATA_GO_KR_SERVICE_KEY", ""),
            admin_emails=os.getenv("ADMIN_EMAILS", ""),
            admin_user_ids=os.getenv(
                "ADMIN_USER_IDS", "434bd1e7-2b64-4c48-a30e-762d254582c8"),
            aligo_api_key=os.getenv("ALIGO_API_KEY", ""),
            aligo_user_id=os.getenv("ALIGO_USER_ID", ""),
            aligo_sender=os.getenv("ALIGO_SENDER", ""),
        )


settings = Settings.load()
