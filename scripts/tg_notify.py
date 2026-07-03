"""콕집 텔레그램 운영 알림 — 공용 발송 모듈 + CLI.

설정: data/telegram.json {"token": "...", "chat_id": ...}
사용: python scripts/tg_notify.py "메시지"  또는  from scripts.tg_notify import tg_send
실패는 조용히 무시(알림이 본 기능을 깨면 안 됨).
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_CFG = Path(__file__).resolve().parent.parent / "data" / "telegram.json"


def tg_send(text: str) -> bool:
    try:
        cfg = json.loads(_CFG.read_text())
        token, chat = cfg.get("token"), cfg.get("chat_id")
        if not token or not chat:
            return False
        data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def tg_send_async(text: str) -> None:
    """API 핸들러용 — 스레드로 발송해 응답 지연 없음."""
    import threading
    threading.Thread(target=tg_send, args=(text,), daemon=True).start()


if __name__ == "__main__":
    ok = tg_send(" ".join(sys.argv[1:]) or "(빈 메시지)")
    sys.exit(0 if ok else 1)
