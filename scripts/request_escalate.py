#!/usr/bin/env python3
"""콕집요청 무응답 자동 확대 — 크론이 10분마다 부른다.

제안이 한 건도 안 온 채 30분이 지난 요청을 찾아, 그 조건의 매물을 가진
다른 중개사무소 3곳에 더 보낸다(최대 3회, 총 12곳까지).
문자는 08~21시에만 나간다 — 새벽 문자는 민폐이고 신고 사유가 된다.

  */10 * * * * cd /opt/koczip && .venv/bin/python scripts/request_escalate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from scripts.local_api import escalate_due
    r = escalate_due()
    done = [x for x in r["results"] if x.get("ok")]
    if not r["checked"]:
        print("확대 대상 없음")
        return 0
    for x in r["results"]:
        state = f"+{x.get('added', 0)}곳(문자 {x.get('sms', 0)})" if x.get("ok") else x.get("reason")
        print(f"요청 #{x['id']}: {state}")
    print(f"대상 {r['checked']}건 · 확대 {len(done)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
