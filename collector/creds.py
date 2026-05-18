"""Capture and cache the Naver `new.land` Bearer token + session cookies.

new.land issues a short-lived Bearer to the JS app on first page load. We
launch Playwright headless, intercept the Authorization header on any
outbound XHR, then snapshot the cookie jar. Both are saved to
data/naver_creds.json so subsequent runs reuse them until expiry.

See NAVER_API_PORTING.md §1 for the full v2 multi-entry design. This is the
simplified single-entry variant used for the spike.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .config import settings

CREDS_PATH = settings.snapshot_dir.parent / "naver_creds.json"
ENTRY_LIFETIME_SEC = 6 * 3600

# Linux is essential for KR IDC IPs (porting guide §3.1).
_UA_OS = [
    ("Macintosh; Intel Mac OS X 10_15_7", "Mac"),
    ("Windows NT 10.0; Win64; x64", "Win10"),
    ("Windows NT 11.0; Win64; x64", "Win11"),
    ("X11; Linux x86_64", "Linux"),
]
_UA_CHROME_VER = [
    "120.0.0.0", "121.0.0.0", "122.0.0.0", "123.0.0.0",
    "124.0.0.0", "125.0.0.0", "126.0.0.0", "127.0.0.0",
    "128.0.0.0", "129.0.0.0",
]
_NAVER_COOKIES = {
    "NNB", "NAC", "BUC", "REALESTATE",
    "PROP_TEST_KEY", "PROP_TEST_ID", "nid_inf",
}

_last_ua = ""


def random_ua() -> str:
    global _last_ua
    while True:
        os_tok, _ = random.choice(_UA_OS)
        ver = random.choice(_UA_CHROME_VER)
        ua = (
            f"Mozilla/5.0 ({os_tok}) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
        )
        if ua != _last_ua:
            _last_ua = ua
            return ua


def _load_from_disk() -> dict | None:
    if not CREDS_PATH.exists():
        return None
    try:
        data = json.loads(CREDS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    age = time.time() - data.get("captured_at", 0)
    if age > ENTRY_LIFETIME_SEC:
        return None
    if not data.get("bearer") or not data.get("cookie"):
        return None
    return data


def _save_to_disk(bearer: str, cookie: str) -> None:
    CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDS_PATH.write_text(
        json.dumps(
            {"bearer": bearer, "cookie": cookie, "captured_at": time.time()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def capture(timeout_ms: int = 25000, max_attempts: int = 3) -> dict:
    from playwright.sync_api import sync_playwright  # local import: heavy

    last_err: Exception | None = None
    with sync_playwright() as p:
        for attempt in range(1, max_attempts + 1):
            ua = random_ua()
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = browser.new_context(user_agent=ua, locale="ko-KR")
            page = ctx.new_page()
            bearer_holder = [""]

            def grab(route, request):
                if not bearer_holder[0]:
                    auth = request.headers.get("authorization", "")
                    if auth.startswith("Bearer "):
                        bearer_holder[0] = auth[len("Bearer "):]
                route.continue_()

            page.route("**/*", grab)
            try:
                page.goto(
                    "https://new.land.naver.com/",
                    wait_until="commit",
                    timeout=timeout_ms,
                )
                for _ in range(24):
                    if bearer_holder[0]:
                        break
                    page.wait_for_timeout(500)
                cookies = ctx.cookies()
                cookie_hdr = "; ".join(
                    f"{c['name']}={c['value']}"
                    for c in cookies
                    if c["name"] in _NAVER_COOKIES
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                ctx.close()
                browser.close()
                continue
            ctx.close()
            browser.close()

            if bearer_holder[0] and cookie_hdr:
                _save_to_disk(bearer_holder[0], cookie_hdr)
                return {
                    "bearer": bearer_holder[0],
                    "cookie": cookie_hdr,
                    "captured_at": time.time(),
                    "ua": ua,
                }
        raise RuntimeError(f"bearer capture failed after {max_attempts} attempts: {last_err}")


def ensure_creds(force: bool = False) -> dict:
    if not force:
        cached = _load_from_disk()
        if cached:
            return cached
    return capture()
