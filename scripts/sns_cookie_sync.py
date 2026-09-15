#!/usr/bin/env python3
"""콕집 SNS 쿠키 자동 동기화 — 내 PC(맥)에서 실행.

DevTools에서 쿠키를 손으로 복사·붙여넣던 것을 대체한다.
이미 로그인된 크롬(디버깅 모드)에 CDP로 붙어 Threads·Instagram·X 쿠키를 읽어
콕집 서버에 바로 저장한다. 세션이 만료되면 이 스크립트만 다시 돌리면 된다.

  python3 scripts/sns_cookie_sync.py            # 동기화(크롬 없으면 자동 실행)
  python3 scripts/sns_cookie_sync.py --check    # 로그인 상태만 확인(저장 안 함)
  python3 scripts/sns_cookie_sync.py --open     # 로그인용 크롬만 띄우기

처음 한 번은 열린 크롬 창에서 각 사이트에 직접 로그인해 두어야 한다.
그 세션은 디버깅 프로필(~/tmp/chrome-debug)에 남아 이후 계속 재사용된다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

API = os.environ.get("KOCZIP_API", "https://api.koczip.com")
KEY_FILE = Path.home() / ".koczip" / "sns_worker_key"
PROFILE = Path.home() / "tmp" / "chrome-debug"     # thread 프로젝트와 같은 디버깅 프로필 재사용
PORT = 9222
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SITES = {
    "threads": ["https://www.threads.com", "https://www.threads.net"],
    "instagram": ["https://www.instagram.com"],
    "x": ["https://x.com", "https://twitter.com"],
}
# 이 쿠키가 있어야 로그인된 세션으로 본다
REQUIRED = {"threads": ["sessionid"], "instagram": ["sessionid"], "x": ["auth_token", "ct0"]}


def worker_key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    k = os.environ.get("KOCZIP_SNS_KEY", "").strip()
    if k:
        return k
    sys.exit(f"워커 키가 없습니다. {KEY_FILE} 에 저장하거나 KOCZIP_SNS_KEY 환경변수를 쓰세요.")


def debug_alive() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2):
            return True
    except Exception:                                   # noqa: BLE001
        return False


def launch_chrome() -> bool:
    """디버깅 포트를 연 크롬 실행(기존 크롬 창과 별개 프로필이라 평소 사용에 영향 없음)."""
    if debug_alive():
        return True
    PROFILE.mkdir(parents=True, exist_ok=True)
    if not Path(CHROME).exists():
        print("크롬을 찾지 못했습니다:", CHROME)
        return False
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
         "--no-first-run", "--no-default-browser-check", "https://www.threads.com/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if debug_alive():
            return True
    return False


def collect() -> dict:
    """플랫폼별 쿠키 문자열 수집."""
    from playwright.sync_api import sync_playwright

    out: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        for plat, urls in SITES.items():
            try:
                cookies = ctx.cookies(urls)
            except Exception as e:                      # noqa: BLE001
                print(f"  {plat}: 쿠키 조회 실패 {e}")
                continue
            names = {c["name"] for c in cookies if c.get("value")}
            missing = [n for n in REQUIRED[plat] if n not in names]
            if missing:
                print(f"  {plat}: 로그인 안 됨 (없는 쿠키: {', '.join(missing)})")
                continue
            # 같은 이름이 도메인별로 여러 개면 마지막 것으로 정리
            merged: dict[str, str] = {}
            for c in cookies:
                if c.get("value"):
                    merged[c["name"]] = c["value"]
            out[plat] = "; ".join(f"{k}={v}" for k, v in merged.items())
            print(f"  {plat}: 로그인됨 · 쿠키 {len(merged)}개 ({len(out[plat])}자)")
    return out


def upload(cookies: dict) -> None:
    body = json.dumps({"key": worker_key(), "cookies": cookies}).encode()
    req = urllib.request.Request(f"{API}/sns/cookie-sync", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    saved = res.get("saved") or {}
    if saved:
        print("서버 저장 완료:", ", ".join(f"{k}({v}자)" for k, v in saved.items()))
    else:
        print("저장된 것이 없습니다(쿠키가 비었거나 형식 오류).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="상태만 확인, 서버 저장 안 함")
    ap.add_argument("--open", action="store_true", help="로그인용 크롬만 실행")
    a = ap.parse_args()

    if not launch_chrome():
        sys.exit("크롬 디버깅 모드를 실행하지 못했습니다.")
    if a.open:
        print(f"크롬을 열었습니다(프로필: {PROFILE}).")
        print("각 사이트에 로그인한 뒤 이 스크립트를 --open 없이 다시 실행하세요.")
        return

    print("로그인된 크롬에서 쿠키 수집 중...")
    got = collect()
    if not got:
        print("\n수집된 쿠키가 없습니다. 열린 크롬 창에서 각 사이트에 로그인한 뒤 다시 실행하세요.")
        print("  (threads.com · instagram.com · x.com)")
        sys.exit(2)
    if a.check:
        print("\n--check 모드라 서버에 저장하지 않았습니다.")
        return
    upload(got)


if __name__ == "__main__":
    main()
