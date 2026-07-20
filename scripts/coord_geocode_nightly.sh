#!/bin/bash
# 비단지 좌표 → 지번주소 역지오코딩 야간 배치 (build_coord_addr.py).
# VWorld 지오코더는 키당 일일한도(약 4만, OVER_REQUEST_LIMIT)라 하루치만 처리되고 멈춘다.
# 키 5개를 순회하며 하루 최대 ~20만 처리 → 최초 51.6만 건은 3일이면 완료.
# 이후에는 수집이 새로 만든 좌표만 남으므로 매일 소량(수천)만 돌고 끝난다. pending 0 이면 즉시 종료.
cd /opt/koczip || exit 1
LOG=data/coord_addr.log

# 중복 실행 방지 — 최초 백필(수십시간)이 다음날 크론과 겹치면 같은 pending 을 두 프로세스가
# 동시에 처리해 호출만 두 배로 낭비된다. 이미 돌고 있으면 조용히 종료.
exec 9>/tmp/koczip_coord_geocode.lock
flock -n 9 || { echo "[$(date '+%F %T')] 이미 실행중 — skip" >> "$LOG"; exit 0; }

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
LEFT=$(sqlite3 data/coord_addr.sqlite "SELECT COUNT(*) FROM coord_addr WHERE status IN ('pending','error')")
echo "[$(date '+%F %T')] nightly done — 남은 ${LEFT}" >> "$LOG"

# 전량 완료 시 1회만 텔레그램 알림(플래그 파일로 중복 발송 방지)
if [ "${LEFT:-1}" -eq 0 ] && [ ! -f data/.coord_addr_done ]; then
  OK=$(sqlite3 data/coord_addr.sqlite "SELECT COUNT(*) FROM coord_addr WHERE status='ok'")
  NF=$(sqlite3 data/coord_addr.sqlite "SELECT COUNT(*) FROM coord_addr WHERE status='notfound'")
  .venv/bin/python scripts/tg_notify.py "✅ 비단지 지번주소 역지오코딩 완료
좌표 ${OK} 확보 · 미확인 ${NF}
매물장·중개사 매물 주소가 '서울 강남구 역삼동 813-14' 형태로 표시됩니다." >> "$LOG" 2>&1
  touch data/.coord_addr_done
fi
