"""수집·집계 실패 감시 — 로그를 훑어 실패를 잡아 알린다.

왜 필요한가
  2026-09-23 수집에서 `sqlite3.OperationalError: database or disk is full` 로
  compute_complex_daily_agg 가 죽었는데 아무도 3일간 몰랐다. 그 사이 일별집계
  3일치가 비었다(복구에 수 시간 소요). systemd 는 start/end 만 보내고,
  collect_listings.sh 내부에는 실패 알림 호출이 하나도 없다.

왜 로그 스캔인가
  단계별 실패(`step N: xxx: exit=1`)는 래퍼가 계속 진행하므로 유닛은 성공으로 끝난다.
  즉 systemd OnFailure 로는 안 잡힌다. 핵심 수집 스크립트를 고치는 건 위험이 커서,
  바깥에서 로그를 읽는 방식을 택했다.

설계
  · 최근 N시간 내 수정된 daily_*/listings_*/catchup_* 로그를 훑는다.
  · 실패 신호: `exit=<0 아닌 값>`, `Traceback`, `disk is full`, `[done-incomplete]`,
    `ALERT`, `malformed`
  · 이미 알린 건 다시 알리지 않는다(로그파일+신호 해시를 상태로 보관).
  · 한 번에 최대 8줄만 요약해 보낸다.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

LOGDIR = Path("/opt/koczip/logs")
STATE = Path("/opt/koczip/maint/collect_watch_state.json")
WINDOW_H = 26                      # 최근 26시간 로그만 (하루치 + 여유)
PATTERNS = [
    (re.compile(r"step \d+: [\w_]+: exit=(?!0)\d+"), "단계 실패"),
    (re.compile(r"sqlite3\.\w*Error: .*"), "DB 오류"),
    (re.compile(r"disk is full"), "디스크 풀"),
    (re.compile(r"\[done-incomplete\]"), "불완전 수집"),
    (re.compile(r"^ALERT|malformed"), "경고"),
]
TEST = "--test" in sys.argv


def notify(msg):
    try:
        subprocess.run(["/opt/koczip/.venv/bin/python", "scripts/tg_notify.py", msg],
                       cwd="/opt/koczip", timeout=30, check=False)
    except Exception as e:
        print("알림 실패:", e, file=sys.stderr)


def main():
    if TEST:
        notify("[테스트] 수집 실패 감시 동작 확인")
        print("테스트 알림 전송")
        return 0

    STATE.parent.mkdir(parents=True, exist_ok=True)
    try:
        seen = set(json.loads(STATE.read_text()))
    except Exception:
        seen = set()

    cutoff = time.time() - WINDOW_H * 3600
    hits = []
    new_keys = []
    for f in sorted(LOGDIR.glob("*.log")):
        if f.stat().st_mtime < cutoff:
            continue
        if not re.match(r"(daily|listings|catchup)_", f.name):
            continue
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        for rx, label in PATTERNS:
            for m in rx.finditer(text):
                line = m.group(0).strip()[:160]
                key = hashlib.md5(("%s|%s" % (f.name, line)).encode()).hexdigest()
                if key in seen:
                    continue
                new_keys.append(key)
                hits.append("· [%s] %s: %s" % (f.name.replace(".log", ""), label, line))

    if hits:
        head = "🔴 수집/집계 실패 %d건 감지" % len(hits)
        body = "\n".join(hits[:8])
        if len(hits) > 8:
            body += "\n… 외 %d건" % (len(hits) - 8)
        notify("%s\n%s" % (head, body))
        print(head)
        for h in hits[:8]:
            print(" ", h)
        seen.update(new_keys)
        # 상태가 무한히 커지지 않게 최근 2000건만 유지
        STATE.write_text(json.dumps(list(seen)[-2000:]))
    else:
        print("실패 없음 (최근 %d시간)" % WINDOW_H)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
