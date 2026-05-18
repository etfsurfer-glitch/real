"""Thin curl_cffi wrapper that injects Naver-standard headers and applies
the 429 backoff prescribed by NAVER_API_PORTING.md §3.9.

curl_cffi (impersonate=chrome120) is required — plain `requests` is TLS-
fingerprint blocked. See porting guide §1.5.
"""
from __future__ import annotations

import random
import time
from typing import Any

from curl_cffi import requests as creq

from .config import settings
from .creds import random_ua

NAVER_BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://new.land.naver.com/",
}


def build_headers(creds: dict | None = None) -> dict[str, str]:
    h = dict(NAVER_BASE_HEADERS)
    h["User-Agent"] = random_ua()
    if creds:
        if creds.get("bearer"):
            h["Authorization"] = f"Bearer {creds['bearer']}"
        if creds.get("cookie"):
            h["Cookie"] = creds["cookie"]
    return h


def _jitter() -> None:
    time.sleep(random.uniform(0, settings.naver_delay_ms / 1000.0))


def _refresh_creds_inplace(creds: dict) -> bool:
    """Recapture Bearer/cookie, mutating creds dict in place. Returns success."""
    from . import creds as creds_mod  # local import: avoids cycle at module load

    try:
        new = creds_mod.capture(max_attempts=2)
    except Exception:  # noqa: BLE001
        return False
    creds.update(new)
    return True


def get_json(
    url: str,
    creds: dict,
    params: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> tuple[int, Any]:
    """GET with jitter + 429 backoff + one-shot 401 recapture.

    creds is mutated in-place on 401 so subsequent calls reuse the fresh token.
    Returns (status, parsed_json_or_text).
    """
    last_status = 0
    refreshed_once = False
    for attempt in range(max_retries):
        _jitter()
        r = creq.get(
            url,
            params=params,
            headers=build_headers(creds),
            impersonate="chrome120",
            timeout=settings.naver_timeout_sec,
        )
        last_status = r.status_code
        if r.status_code == 429:
            time.sleep(2 ** attempt + 1)
            continue
        if r.status_code in (401, 403) and not refreshed_once:
            refreshed_once = True
            if _refresh_creds_inplace(creds):
                continue
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, r.text
    return last_status, None


def get_raw(url: str, creds: dict, headers_extra: dict | None = None) -> tuple[int, bytes]:
    _jitter()
    h = build_headers(creds)
    if headers_extra:
        h.update(headers_extra)
    r = creq.get(url, headers=h, impersonate="chrome120", timeout=settings.naver_timeout_sec)
    return r.status_code, r.content
