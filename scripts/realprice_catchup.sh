#!/usr/bin/env bash
# 실거래 catch-up — data.go.kr 장애로 nightly run에서 실거래를 못 받았을 때,
# 서버가 회복되면 당일 실거래를 채운다. systemd timer(koczip-catchup.timer, 30분)로 실행.
#
# 무결성(DB 안 꼬임) 원칙:
#  · 단일 락(pipeline.lock) — nightly daily_run·다른 catchup과 절대 동시 실행 금지(동시 writer 0).
#  · 헬스게이트 — data.go.kr UP일 때만 수집. DOWN이면 손도 안 댐(헛돌기·부분수집 방지).
#  · 성공마커 — 수집 전후 모두 UP이어야 '오늘 성공'으로 기록. 중간에 죽었으면 마커 미기록 →
#    다음 틱에 재시도(backfill은 deal_id 중복제거라 재실행 안전).
set -u
ROOT=/opt/koczip
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/logs/catchup_$(date +%Y%m%d).log"
MARKER="$ROOT/data/realprice_done.date"
TODAY=$(date +%F)
mkdir -p "$ROOT/logs"
log(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }

# 단일 락 — 못 잡으면(다른 파이프라인 작동중) 조용히 종료
exec 9>"$ROOT/data/pipeline.lock"
flock -n 9 || { log "catchup: pipeline busy → skip"; exit 0; }

cd "$ROOT" || exit 1
# 오늘 이미 실거래 수집 성공이면 종료
[ "$(cat "$MARKER" 2>/dev/null)" = "$TODAY" ] && exit 0

# data.go.kr 헬스 게이트
if ! $PY scripts/dgk_health.py >>"$LOG" 2>&1; then
  exit 0   # DOWN — 조용히 대기(다음 틱)
fi

log "=== catchup 시작: data.go.kr UP + 오늘 실거래 미수집 → 수집 ==="
$PY -u scripts/backfill_realprice.py --all --months 6 >>"$LOG" 2>&1; r1=$?
$PY -u scripts/backfill_rentals.py   --all --months 6 >>"$LOG" 2>&1; r2=$?
$PY -u scripts/backfill_offi.py      --all --months 6 >>"$LOG" 2>&1; r3=$?
$PY -u scripts/backfill_silv.py      --all --months 6 >>"$LOG" 2>&1; r4=$?
# 비단지 실거래도 catchup에 포함 — daily가 어떤 이유로 스킵돼도 아파트류처럼 복원력 확보.
$PY -u scripts/backfill_villa.py     --all --months 6 >>"$LOG" 2>&1; r5=$?
$PY -u scripts/backfill_nonresi.py --kind house --all --months 6 >>"$LOG" 2>&1; r6=$?
$PY -u scripts/backfill_nonresi.py --kind comm  --all --months 6 >>"$LOG" 2>&1; r7=$?
log "backfill exit: realprice=$r1 rentals=$r2 offi=$r3 silv=$r4 villa=$r5 house=$r6 comm=$r7"

# 수집 직후 재확인 — 중간에 죽었으면(부분수집) 마커 미기록
if $PY scripts/dgk_health.py >>"$LOG" 2>&1; then
  log "롤업·캐시 재빌드(신규 실거래 반영)"
  $PY -u scripts/build_tx_rollups.py >>"$LOG" 2>&1
  $PY -u scripts/build_api_cache.py --default-only >>"$LOG" 2>&1
  bash "$ROOT/scripts/warm_api.sh" >>"$LOG" 2>&1 || true
  echo "$TODAY" > "$MARKER"
  log "=== catchup 완료 (마커=$TODAY) ==="
else
  log "catchup: 수집 중 data.go.kr 재DOWN → 마커 미기록, 다음 틱 재시도"
fi
