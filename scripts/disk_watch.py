"""디스크 사용률 감시 — 90/95/98% 단계 알림.

왜 필요한가
  2026-09-25 디스크풀 사고는 며칠에 걸쳐 차오르는 동안 아무도 몰라서 커졌다.
  루트가 100%가 되자 API 크래시루프(502) + 일일백업 실패 + 집계 3일치 손실이
  한꺼번에 터졌다. 사전 경보가 있었다면 전부 막을 수 있었다.

설계
  · 90 / 95 / 98% 3단계. 단계가 올라갈 때만 알린다(같은 단계 반복 알림 없음).
  · 정상(90% 미만)으로 돌아오면 '해소' 1회 알림.
  · 상태는 /opt/koczip/maint/disk_watch_state.json 에 보관.
  · 여유 GB 를 함께 알린다 — %보다 실제 행동 판단에 쓸모 있다.
  · 감시 대상: / (루트 NVMe), /mnt/backup(vdb), /mnt/cold(vdc)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

MOUNTS = [("/", "루트(NVMe)"), ("/mnt/backup", "vdb"), ("/mnt/cold", "vdc")]
LEVELS = [98, 95, 90]          # 높은 단계부터 판정
STATE = Path("/opt/koczip/maint/disk_watch_state.json")
TEST = "--test" in sys.argv


def notify(msg):
    try:
        subprocess.run(["/opt/koczip/.venv/bin/python", "scripts/tg_notify.py", msg],
                       cwd="/opt/koczip", timeout=30, check=False)
    except Exception as e:
        print("알림 실패:", e, file=sys.stderr)


def usage(path):
    s = os.statvfs(path)
    total = s.f_blocks * s.f_frsize
    free = s.f_bavail * s.f_frsize
    used_pct = 100.0 * (total - free) / total if total else 0.0
    return used_pct, free / 2 ** 30, total / 2 ** 30


def level_of(pct):
    for lv in LEVELS:
        if pct >= lv:
            return lv
    return 0


def main():
    if TEST:
        lines = []
        for path, label in MOUNTS:
            if not os.path.ismount(path) and path != "/":
                continue
            pct, free_gb, total_gb = usage(path)
            lines.append("%s %.0f%% (여유 %.1fGB/%.0fGB)" % (label, pct, free_gb, total_gb))
        notify("[테스트] 디스크 감시 동작 확인\n" + "\n".join(lines))
        print("테스트 알림 전송:\n  " + "\n  ".join(lines))
        return 0

    STATE.parent.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(STATE.read_text())
    except Exception:
        state = {}

    changed = False
    for path, label in MOUNTS:
        if path != "/" and not os.path.ismount(path):
            continue
        pct, free_gb, total_gb = usage(path)
        lv = level_of(pct)
        prev = int(state.get(path, 0))

        if lv > prev:
            mark = "🔴" if lv >= 98 else ("🟠" if lv >= 95 else "🟡")
            notify("%s 디스크 %d%% 초과 — %s %.0f%% 사용, 여유 %.1fGB / %.0fGB"
                   % (mark, lv, label, pct, free_gb, total_gb))
            print("ALERT %s %.0f%% (단계 %d→%d)" % (label, pct, prev, lv))
        elif lv == 0 and prev > 0:
            notify("✅ 디스크 여유 회복 — %s %.0f%% 사용, 여유 %.1fGB" % (label, pct, free_gb))
            print("RECOVER %s %.0f%%" % (label, pct))
        if lv != prev:
            state[path] = lv
            changed = True

    if changed:
        STATE.write_text(json.dumps(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
