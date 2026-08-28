#!/usr/bin/env python3
"""만료 감시 — data/expiry.json 의 항목별 남은 일수를 계산해 임계일에 텔레그램 알림.

우리가 직접 챙겨야 하는 만료(자동 갱신 안 되는 것)를 한곳에서 관리한다:
  · Apple 로그인 클라이언트 시크릿(JWT, 6개월)  · 인증서·도메인·API 키 등

설정: data/expiry.json = [{"name","expires":"YYYY-MM-DD","note"?,"lead_days"?}]
  - lead_days: 이 일수 이내부터 임계 알림(기본 30)
동작: 임계일(30·14·7·3·1일 전, 당일, 초과)에 텔레그램 발송. 매일 1회 크론/타이머로 실행.
  python3 scripts/expiry_watch.py          # 임계일 알림
  python3 scripts/expiry_watch.py --list    # 전체 워치리스트 즉시 발송(확인·주간 다이제스트)
"""
import json, datetime, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tg_notify import tg_send  # 공용 텔레그램 모듈

CFG = Path(__file__).resolve().parent.parent / "data" / "expiry.json"
THRESHOLDS = {30, 14, 7, 3, 1}


def _load():
    if not CFG.exists():
        return []
    try:
        return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:
        return []


def _line(name, exp, days, note):
    if days < 0:
        head = f"🔴 만료됨({-days}일 지남): {name}"
    elif days == 0:
        head = f"🔴 오늘 만료: {name}"
    elif days <= 7:
        head = f"🟠 {days}일 후 만료: {name}"
    else:
        head = f"⏰ {days}일 후 만료: {name}"
    head += f"  [{exp}]"
    if note:
        head += f"\n    ↳ {note}"
    return head


def main(list_all: bool):
    items = _load()
    today = datetime.date.today()
    rows = []
    for it in items:
        try:
            exp = datetime.date.fromisoformat(str(it["expires"]))
        except Exception:
            continue
        days = (exp - today).days
        lead = int(it.get("lead_days", 30))
        name = it.get("name", "(무명)")
        note = it.get("note", "")
        if list_all:
            rows.append((days, _line(name, it["expires"], days, note)))
        else:
            fire = (days in THRESHOLDS and days <= lead) or days <= 0
            if fire:
                rows.append((days, _line(name, it["expires"], days, note)))
    if not rows:
        if list_all:
            tg_send("🗓 콕집 만료 워치리스트 — 등록된 항목이 없습니다. data/expiry.json 에 추가하세요.")
        return
    rows.sort(key=lambda r: r[0])   # 임박한 순
    title = "🗓 콕집 만료 워치리스트" if list_all else "🗓 콕집 만료 알림"
    tg_send(title + "\n\n" + "\n\n".join(r[1] for r in rows))


if __name__ == "__main__":
    main("--list" in sys.argv or "--test" in sys.argv)
