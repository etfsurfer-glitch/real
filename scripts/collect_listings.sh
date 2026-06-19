#!/usr/bin/env bash
# 매물 전용 수집 루틴 (하루 3회 중 11:00·19:00 — data.go.kr 실거래 제외).
# 02:00 전체 run(daily_run.sh)은 매물+실거래 모두. 이 스크립트는 실거래 backfill·rollup을
# 빼고 매물(naver)만 재수집 → 쿼터 무관, 종일 변하는 매물만 갱신. pipeline.lock 공유로
# daily_run/catchup 과 동시 DB writer 0 보장. (A안: 매물 3회 + 실거래 1회)
set -u
ROOT=/opt/koczip
PY="$ROOT/.venv/bin/python"
mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/listings_$(date +%Y%m%d_%H%M).log"
export PYTHONUNBUFFERED=1
cd "$ROOT" || exit 1

# daily_run·catchup 과 동일한 단일 락 — 동시 실행 금지(동시 writer 0)
exec 9>"$ROOT/data/pipeline.lock"
flock -w 1800 9 || { echo "lock busy 30m+ — exit"; exit 0; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
step() { local label="$1"; shift; log "$label"; "$@" >>"$LOG" 2>&1; log "$label: exit=$?"; }

log "listings-only run start (intraday 3x)"

# 1) 매물 재수집 — --reset-today 로 같은 날에도 강제 재수집(collection_log 무시).
$PY -u scripts/run_collect.py --all --reset-today >>"$LOG" 2>&1
collect_exit=$?
log "step 1: run_collect(--reset-today) exit=$collect_exit"
if [ "$collect_exit" -eq 3 ]; then
  log "another collection holds the lock (exit=3) — skipping rest"; exit 0
fi

# 2~3) 신규 단지/중개사 보강 (소량, --only-missing)
step "step 2: fetch_complex_detail"   $PY -u scripts/fetch_complex_detail.py --only-missing --parallel 8
step "step 3: fetch_naver_realtors"   $PY -u scripts/fetch_naver_realtors_direct.py --only-missing --parallel 8
# 4) 중개사 매칭 + 전화 인덱스 (신규 realtor 반영)
step "step 4: match_clean"            $PY -u scripts/match_clean.py
step "step 5: build_vworld_phone_index" $PY -u scripts/build_vworld_phone_index.py
# 6) 중개사 일별 매물수 (매물 변화 추적)
step "step 6: realtor_daily_count"    $PY -u scripts/realtor_daily_count.py
# 7) 캐시 갱신 (새 매물 반영) — 실거래 rollup은 02:00 run에서만(여기선 불변)
step "step 7: build_api_cache"        $PY -u scripts/build_api_cache.py --default-only

log "listings-only run done collect=$collect_exit"
