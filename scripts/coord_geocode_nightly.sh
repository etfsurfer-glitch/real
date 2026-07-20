#!/bin/bash
# 비단지 좌표 → 지번주소 역지오코딩 야간 배치 (build_coord_addr.py).
# VWorld 지오코더는 키당 일일한도(약 4만, OVER_REQUEST_LIMIT)라 하루치만 처리되고 멈춘다.
# 키 5개를 순회하며 하루 최대 ~20만 처리 → 최초 51.6만 건은 3일이면 완료.
# 이후에는 수집이 새로 만든 좌표만 남으므로 매일 소량(수천)만 돌고 끝난다. pending 0 이면 즉시 종료.
cd /opt/koczip || exit 1
LOG=data/coord_addr.log

# 1) 신규 좌표 적재(API 호출 없음) — 그날 수집분에서 처음 보는 좌표만 pending 으로 들어온다
.venv/bin/python -u scripts/build_coord_addr.py --scan >> "$LOG" 2>&1

PEND=$(sqlite3 data/coord_addr.sqlite "SELECT COUNT(*) FROM coord_addr WHERE status IN ('pending','error')")
echo "[$(date '+%F %T')] nightly start — pending+error=${PEND:-?}" >> "$LOG"
[ "${PEND:-0}" -eq 0 ] && { echo "  완료됨 — skip" >> "$LOG"; exit 0; }

for N in "" 2 3 4 5; do
  K=$(grep "^VWORLD_KEY${N}=" .env | cut -d= -f2)
  [ -z "$K" ] && continue
  REMAIN=$(sqlite3 data/coord_addr.sqlite "SELECT COUNT(*) FROM coord_addr WHERE status IN ('pending','error')")
  [ "${REMAIN:-0}" -eq 0 ] && break
  echo "  -- VWORLD_KEY${N} (남은 ${REMAIN})" >> "$LOG"
  .venv/bin/python -u scripts/build_coord_addr.py --geocode --key "$K" --concurrency 8 >> "$LOG" 2>&1
done
echo "[$(date '+%F %T')] nightly done — 남은 $(sqlite3 data/coord_addr.sqlite "SELECT COUNT(*) FROM coord_addr WHERE status IN ('pending','error')")" >> "$LOG"
