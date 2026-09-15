#!/bin/bash
# 지번복원 데몬 감시 — 크론 매일 07:10.
# ① 죽었는데 잔여 있으면 재시작(크래시/재부팅 복원력)
# ② 전량 완료 감지 시: 복원지번 지오코딩 1회 → 자산별 최종 커버리지 → 텔레그램 보고(1회)
cd /opt/koczip || exit 1
LOG=data/ledger_recover_watch.log
DONE_FLAG=data/.ledger_recover_done

[ -f "$DONE_FLAG" ] && exit 0

REMAIN=$(.venv/bin/python - <<'PYEOF'
import sqlite3
nv = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
nv.execute("PRAGMA busy_timeout=60000")
try:
    lr = sqlite3.connect("file:/opt/koczip/data/ledger_recover.sqlite?mode=ro", uri=True)
    done = set(r[0] for r in lr.execute("SELECT deal_id FROM recovered"))
except Exception:
    done = set()
n = 0
for t, w in (("nrg_transactions", "jibun LIKE '%*%' AND building_ar>0 AND build_year>0"),
             ("sh_transactions", "total_floor_ar>0 AND build_year>0")):
    for (did,) in nv.execute(f"SELECT deal_id FROM {t} WHERE is_cancelled=0 AND {w}"):
        if did not in done:
            n += 1
print(n)
PYEOF
)

if [ "${REMAIN:-1}" -gt 0 ]; then
  if ! pgrep -f "ledger_jibun_recove[r]" >/dev/null; then
    echo "[$(date '+%F %T')] 데몬 죽음(잔여 ${REMAIN}) — 재시작" >> "$LOG"
    nohup .venv/bin/python -u scripts/ledger_jibun_recover.py >> /tmp/ledger_recover.log 2>&1 &
  else
    echo "[$(date '+%F %T')] 진행중 — 잔여 ${REMAIN}" >> "$LOG"
  fi
  exit 0
fi

# 완료 — 데몬 정리, 복원지번 좌표 확보 후 최종 검증·보고
echo "[$(date '+%F %T')] 전량 완료 — 최종 검증 시작" >> "$LOG"
pkill -f "ledger_jibun_recove[r]" 2>/dev/null
.venv/bin/python -u scripts/geocode_jibun.py --workers 4 --rps 10 >> "$LOG" 2>&1
.venv/bin/python -u scripts/tx_map_coverage.py --tg >> "$LOG" 2>&1
touch "$DONE_FLAG"
echo "[$(date '+%F %T')] 보고 완료" >> "$LOG"
