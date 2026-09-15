#!/usr/bin/env bash
# 실거래 당일 재수집(top-up) — data.go.kr은 하루 종일 신고분을 발행하는데 nightly
# daily_run은 새벽 02시에 한 번만 수집해 '당일 신고분'을 놓친다(2026-07-14 서울 일별
# 현황이 경쟁사보다 훨씬 적게 보인 원인). 낮·저녁에 최근월만 다시 긁어 격차를 메운다.
#
# 무결성(realprice_catchup.sh와 동일 원칙):
#  · pipeline.lock 단일 락 — daily_run·catchup과 동시 실행(동시 writer) 금지.
#  · data.go.kr 헬스게이트 — UP일 때만. DOWN이면 손 안 댐.
#  · backfill은 deal_id 중복제거라 재실행 안전. 최근 2개월만(신규 신고가 떨어지는 구간).
#  · 성공 시 롤업·캐시 재빌드+워밍 → 통계/일별현황에 즉시 반영.
# 크론: 08:00, 15:00, 18:00 — 파이프라인 락이 비는 구간에만.
#   (02~05 daily_run / 11~14·19~22 매물수집 회피. 21:00은 상시 충돌해 폐기)
set -u
ROOT=/opt/koczip
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/logs/realprice_refresh_$(date +%Y%m%d).log"
MONTHS="${1:-2}"
mkdir -p "$ROOT/logs"
log(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }

exec 9>"$ROOT/data/pipeline.lock"
# 락 충돌은 조용히 넘어가면 안 된다 — 21:00 자리가 매물수집(19:00~22:06)과 겹쳐
# 매일 skip 되고 있었는데 아무도 몰랐다(2026-07-23 발견). 텔레그램으로 알린다.
flock -n 9 || {
  log "refresh: pipeline busy → skip"
  $PY scripts/tg_notify.py "실거래 top-up 건너뜀 — 파이프라인 락 점유(다른 수집 진행중). 시각=$(date +%H:%M)" 2>/dev/null || true
  exit 0; }

cd "$ROOT" || exit 1
if ! $PY scripts/dgk_health.py >>"$LOG" 2>&1; then
  log "refresh: data.go.kr DOWN → skip"; exit 0
fi

log "=== realprice refresh 시작 (months=$MONTHS) ==="
$PY -u scripts/backfill_realprice.py --all --months "$MONTHS" >>"$LOG" 2>&1; r1=$?
$PY -u scripts/backfill_rentals.py   --all --months "$MONTHS" >>"$LOG" 2>&1; r2=$?
$PY -u scripts/backfill_offi.py      --all --months "$MONTHS" >>"$LOG" 2>&1; r3=$?
log "backfill exit: realprice=$r1 rentals=$r2 offi=$r3"

# 신규 실거래 반영 — 롤업·캐시 재빌드
$PY -u scripts/build_tx_rollups.py >>"$LOG" 2>&1
$PY -u scripts/build_api_cache.py --default-only >>"$LOG" 2>&1
bash "$ROOT/scripts/warm_api.sh" >>"$LOG" 2>&1 || true
log "=== realprice refresh 완료 ==="
