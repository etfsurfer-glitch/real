"""알리고 문자 잔액 확인 — 100건 미만이면 텔레그램으로 알린다(daily_run step 11g).

2026-11-10 잔액 0건인 채로 하루 넘게 있어 신규 회원의 휴대폰 인증 문자가 조용히 실패했다(502 ×3).
실행: python scripts/aligo_remain_check.py [--min 100]
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=100)
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass
    key, uid = os.getenv("ALIGO_API_KEY", ""), os.getenv("ALIGO_USER_ID", "")
    if not key or not uid:
        print("aligo 미설정"); return 0
    data = urllib.parse.urlencode({"key": key, "user_id": uid}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("https://apis.aligo.in/remain/", data=data, headers={"User-Agent": "koczip/1.0"}), timeout=10) as r:
            j = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print("remain 조회 실패:", str(e)[:120]); return 0
    sms, lms = int(j.get("SMS_CNT") or 0), int(j.get("LMS_CNT") or 0)
    print(f"aligo remain SMS {sms} LMS {lms}")
    if sms < a.min:
        try:
            from scripts.tg_notify import tg_send
            tg_send(f"📵 알리고 문자 잔액 {sms}건(LMS {lms}) — {a.min}건 미만. 충전하지 않으면 회원 휴대폰 인증·알림 문자가 실패해요.")
        except Exception as e:  # noqa: BLE001
            print("tg 실패:", str(e)[:80])
    return 0


if __name__ == "__main__":
    sys.exit(main())
