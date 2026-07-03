"""동시사용자 감시 → 텔레그램 (1분 주기 타이머).

최근 5분 활성 사용자(로그인 user_id 또는 IP, 내부 워밍 제외)가 30명을 넘으면 알림,
이후 10명 구간(40·50·60…)을 새로 넘을 때마다 알림. 30 아래로 내려오면 구간 리셋
(다음 피크 때 다시 30부터 알림). 상태는 data/tg_users_tier.txt 에 기억.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "tg_users_tier.txt"

import sys
sys.path.insert(0, str(ROOT))
from scripts.tg_notify import tg_send  # noqa: E402


def active_users() -> int:
    with sqlite3.connect(f"file:{ROOT}/data/logs.sqlite?mode=ro", uri=True) as c:
        return c.execute(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(user_id,''), ip)) FROM event_log "
            "WHERE ts >= datetime('now', '-5 minutes') AND ip != '127.0.0.1'"
        ).fetchone()[0]


def main() -> None:
    n = active_users()
    last = 0
    try:
        last = int(STATE.read_text().strip() or 0)
    except Exception:
        pass
    tier = (n // 10) * 10 if n >= 30 else 0
    if tier > last:
        tg_send(f"🔥 동시사용자 {n}명 (최근 5분) — {tier}명 구간 진입")
        STATE.write_text(str(tier))
    elif tier == 0 and last:
        STATE.write_text("0")   # 피크 해소 — 조용히 리셋


if __name__ == "__main__":
    main()
