#!/usr/bin/env bash
# 박스(iwinv) 일일 수집·집계 파이프라인. daily_run.ps1 의 리눅스 포팅.
# 차이: ① Supabase 업로드 없음(폐기) ② 시군구 급매캐시(12b) 없음(quick-deals
# 쿼리 최적화로 라이브 <3s, 캐시 불필요) ③ Windows 절전코드 없음 ④ 매물 수집은
# NAVER_SOURCE_IPS(.env) 로 2-IP 병렬. systemd timer(koczip-daily.timer)로 실행.
set -u
ROOT=/opt/koczip
PY="$ROOT/.venv/bin/python"
mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/daily_$(date +%Y%m%d_%H%M).log"
export PYTHONUNBUFFERED=1
cd "$ROOT" || exit 1

# 단일 락 — catchup·다른 daily_run 과 동시 실행 금지(동시 DB writer 0 → 꼬임 방지)
exec 9>"$ROOT/data/pipeline.lock"
flock -n 9 || { echo "another pipeline holds the lock — exit"; exit 0; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
step() {  # step "label" cmd...
  local label="$1"; shift
  log "$label"
  "$@" >>"$LOG" 2>&1
  local ec=$?
  log "$label: exit=$ec"
  return $ec
}

log "daily run start (box, 2-IP collect)"

# 1) 매물 수집 (resumable, 단일실행 락, 완결성 게이트). NAVER_SOURCE_IPS 로 2-IP.
$PY -u scripts/run_collect.py --all >>"$LOG" 2>&1
collect_exit=$?
log "step 1: run_collect exit=$collect_exit"

# 다른 수집이 락을 쥔 경우(exit 3) → 중복 처리 방지 위해 전체 중단
if [ "$collect_exit" -eq 3 ]; then
  log "another collection holds the lock (exit=3) — skipping rest"
  exit 0
fi

# 완결성 게이트: 완전 수집(exit 0)일 때만 archive. 부분(exit 2)이면 발행 안 함.
if [ "$collect_exit" -eq 0 ]; then
  step "step 2: archive_listings (parquet)" $PY -u scripts/archive_listings.py; archive_exit=$?
else
  archive_exit=-1
  log "step 2: SKIPPED (collect exit=$collect_exit, partial snapshot)"
fi

# 3~5) 실거래 증분 (data.go.kr 4 endpoint — 키-TPS 제한이라 IP 무관, 단일)
step "step 3: backfill_realprice (매매)"  $PY -u scripts/backfill_realprice.py --all --months 6; realprice_exit=$?
step "step 4: backfill_rentals (전월세)"   $PY -u scripts/backfill_rentals.py   --all --months 6; rentals_exit=$?
step "step 5: backfill_offi (오피스텔)"     $PY -u scripts/backfill_offi.py      --all --months 6; offi_exit=$?
step "step 5b: backfill_silv (분양권/입주권)" $PY -u scripts/backfill_silv.py      --all --months 6; silv_exit=$?
step "step 5c: backfill_villa (빌라 매매·전월세)" $PY -u scripts/backfill_villa.py    --all --months 6; villa_exit=$?

# 실거래 성공 마커 — backfill 후 data.go.kr 이 살아있으면 '오늘 실거래 수집됨' 기록.
# DOWN(장애)이면 미기록 → catchup(koczip-catchup.timer)이 낮에 회복 시 채운다.
if $PY scripts/dgk_health.py >>"$LOG" 2>&1; then
  date +%F > "$ROOT/data/realprice_done.date"
  log "실거래 마커 기록(오늘 수집 성공)"
else
  log "실거래 미수집(data.go.kr DOWN) — 마커 미기록, catchup이 회복 시 채움"
fi

# 6~8) 보조 수집 (Naver, --only-missing 소량)
step "step 6: refresh_supply_area"         $PY -u scripts/refresh_supply_area.py; supply_exit=$?
step "step 7: fetch_complex_detail"        $PY -u scripts/fetch_complex_detail.py --only-missing --parallel 8; cdetail_exit=$?
step "step 8: fetch_naver_realtors"        $PY -u scripts/fetch_naver_realtors_direct.py --only-missing --parallel 8; nrealtor_exit=$?

# 9~10) 매칭 (시군구-local 안전 병렬)
step "step 9: match_clean (realtor)"       $PY -u scripts/match_clean.py; match_exit=$?
step "step 9b: build_realtor_dong (우리동네)" $PY -u scripts/build_realtor_dong.py; rdong_exit=$?
step "step 10: rematch_all_realprice"      $PY -u scripts/rematch_all_realprice.py --tables apt rent offi offi_rent --concurrency 4; rematch_exit=$?

# 11) 롤업 (매칭 후, 캐시 전)
step "step 11: build_tx_rollups"           $PY -u scripts/build_tx_rollups.py; rollup_exit=$?

# 12) 캐시 (기본화면만 — quick-deals 최적화로 시군구 급매캐시 불필요)
step "step 12: build_api_cache --default-only" $PY -u scripts/build_api_cache.py --default-only; cache_exit=$?

# 12b) 매물가격추이 시군구 캐시 백필 — step12(default-only)는 전국+시도만 캐시하므로
#      시군구 avg-price-trend/changes/summary(asset apt/offi)를 덧쌓는다(no-wipe).
#      재개가능(이미 캐시된 키 skip)+주기커밋+3워커(gentle). step()은 비치명적이라
#      실패/지연돼도 step12 캐시는 그대로 남아 안전.
step "step 12b: backfill_trend_cache (시군구 호가추이)" $PY -u scripts/backfill_trend_cache.py --workers 3; trendcache_exit=$?

# 13) 비단지 매물(11종) 전국 멀티IP — ★별도 DB에만 기록(naverreal 무접근).
#     step()은 exit만 로깅(비치명적) → 실패/지연돼도 위 전체수집·발행 무영향. A안: 3회 다 전국.
step "step 13: region_listings(비단지 전국)" $PY -u scripts/collect_region_listings.py --all; region_exit=$?
# 13b) 비단지 수집(step13) 후 중개사 집계 재빌드 — step9b는 region 전이라 당일 비단지 미반영이므로,
#      여기서 한 번 더 돌려 realtor_region_counts·랭킹·우리동네에 오늘 비단지까지 반영(재발방지).
step "step 13b: build_realtor_dong (비단지 반영)" $PY -u scripts/build_realtor_dong.py; rdong2_exit=$?

log "daily run done  collect=$collect_exit archive=${archive_exit:-NA} realprice=${realprice_exit:-NA} rentals=${rentals_exit:-NA} offi=${offi_exit:-NA} silv=${silv_exit:-NA} villa=${villa_exit:-NA} supply=${supply_exit:-NA} cdetail=${cdetail_exit:-NA} nrealtor=${nrealtor_exit:-NA} match=${match_exit:-NA} rematch=${rematch_exit:-NA} rollup=${rollup_exit:-NA} cache=${cache_exit:-NA} trendcache=${trendcache_exit:-NA} region=${region_exit:-NA}"
