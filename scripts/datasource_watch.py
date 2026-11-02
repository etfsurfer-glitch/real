"""데이터 출처 신선도 매일 점검 — '점검 필요'(stale)가 있으면 텔레그램으로 알린다.

왜 필요한가
  관리자 '데이터 출처' 화면(/admin/data-sources)은 열어봐야만 보인다. 수집이 며칠째
  멈춰도 아무도 화면을 안 열면 모른다. 같은 판정(collector.data_sources)을 매일
  한 번 돌려, 점검 필요 항목이 있을 때만 보낸다(정상일 땐 조용히).

사용: python scripts/datasource_watch.py [--test]   (--test = 정상이어도 결과 발송)
cron: 매일 09:00 (새벽 daily_run 이 끝난 뒤)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from collector.config import settings          # noqa: E402
from collector.data_sources import check       # noqa: E402
from tg_notify import tg_send                  # noqa: E402

TEST = "--test" in sys.argv


def main() -> int:
    db = settings.local_db_path
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30) as c:
        rows = check(c, db.parent)

    stale = [r for r in rows if r["status"] == "stale"]
    delay = [r for r in rows if r["status"] == "delay"]

    def line(r):
        ago = "기록 없음" if r["days_ago"] is None else f"{r['days_ago']}일 전"
        return f"· {r['name']} — 마지막 수집 {r['last_collected'] or '-'} ({ago}, 주기 {r['cycle']})"

    print(f"checked {len(rows)}  stale={len(stale)}  delay={len(delay)}")
    if not stale and not TEST:
        return 0

    msg = [f"🔴 데이터 출처 점검 필요 {len(stale)}건" if stale else "✅ 데이터 출처 점검 — 모두 정상"]
    msg += [line(r) for r in stale]
    if delay:
        msg.append(f"\n🟡 지연 {len(delay)}건")
        msg += [line(r) for r in delay]
    msg.append("\nkoczip.com/admin → 데이터 출처")
    text = "\n".join(msg)
    print(text)
    tg_send(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
