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

# 단일 락 — catchup·다른 daily_run 과 동시 실행 금지(동시 DB writer 0 → 꼬임 방지).
# ★대기(-w)로 획득: 비차단(-n)이면 catchup(*:0/30)과 daily(02:00)가 같은 초에 발동할 때
#   락경쟁에 져 daily 가 하루치를 통째로 건너뛰던 버그(2026-06-28 발생). catchup 은 보통
#   <1s, 길어야 당일 실거래 수집 ~30분 내 락을 푸므로, daily 는 끝나길 기다렸다 이어받는다.
#   여전히 순차 실행(동시 writer 0). 60분 내 못 잡으면(비정상) 로그 남기고 종료.
exec 9>"$ROOT/data/pipeline.lock"
flock -w 3600 9 || { echo "pipeline lock 60분 대기 초과 — 종료"; exit 0; }

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
step "step 5d: backfill_nonresi house (단독 매매·전월세)" $PY -u scripts/backfill_nonresi.py --kind house --all --months 6; house_exit=$?
step "step 5e: backfill_nonresi comm (상가/사무실 매매)"   $PY -u scripts/backfill_nonresi.py --kind comm  --all --months 6; comm_exit=$?

# 실거래 단계는 task 실패(API_ERR)가 있어도 exit=0 이다 — 8/26~10/31 동안 429 로
# 분양권·상가가 거의 전부 빠졌는데 아무 알림이 없었다. 실패 건수를 세서 알린다.
rp_err=$(awk '/step 3: backfill_realprice/{p=1} /step 5e: backfill_nonresi comm .*exit=/{p=0} p' "$LOG" | grep -c API_ERR)
log "실거래 API_ERR=$rp_err"
if [ "$rp_err" -gt 0 ]; then
  $PY scripts/tg_notify.py "⚠️ 실거래 수집 API 오류 ${rp_err}건 (step 3~5e) — $LOG" >/dev/null 2>&1
fi

# 실거래 성공 마커 — backfill 후 data.go.kr 이 살아있으면 '오늘 실거래 수집됨' 기록.
# DOWN(장애)이면 미기록 → catchup(koczip-catchup.timer)이 낮에 회복 시 채운다.
if $PY scripts/dgk_health.py >>"$LOG" 2>&1; then
  # 마커에 시각까지 남긴다 — catchup 이 '날짜가 같은가'가 아니라
  # '마지막 성공이 몇 시간 전인가'로 판단하도록(자정 오발동 방지).
  date +%FT%H:%M:%S > "$ROOT/data/realprice_done.date"
  log "실거래 마커 기록(오늘 수집 성공)"
else
  log "실거래 미수집(data.go.kr DOWN) — 마커 미기록, catchup이 회복 시 채움"
fi

# 6~8) 보조 수집 (Naver, --only-missing 소량)
step "step 6: refresh_supply_area"         $PY -u scripts/refresh_supply_area.py; supply_exit=$?
step "step 7: fetch_complex_detail"        $PY -u scripts/fetch_complex_detail.py --only-missing --parallel 8; cdetail_exit=$?
step "step 8: fetch_naver_realtors"        $PY -u scripts/fetch_naver_realtors_direct.py --only-missing --parallel 8; nrealtor_exit=$?
# 8b: 개설등록번호 공란 메우기. step 8 이 쓰는 /api/realtors 는 등록번호를 아예 안 주고,
#     등록번호를 주는 매물상세 경로는 '행이 이미 있으면' 건너뛴다. 그래서 개설 직후 번호 없이
#     수집된 사무소는 나중에 네이버에 번호를 넣어도 우리는 영영 공란이고, 번호가 없으니
#     자동매칭이 안 돼 사람이 손으로 잠그게 된다(2026-10-27 흑석 새봄 — 9/14 공란으로 굳어 있었음).
#     오래 안 본 사무소부터 하루 300곳씩 돌며 메운다(공란 7,061곳 기준 약 24일에 한 바퀴).
step "step 8b: regno 공란 메우기(일 300)" $PY -u scripts/fetch_naver_realtors.py --missing-regno --limit 300 --parallel 5; regnofill_exit=$?

# 9~10) 매칭 (시군구-local 안전 병렬)
step "step 8-pre-a: hidden 신규 검증(등록번호, 일 300그룹)" $PY -u scripts/build_hidden_realtor_map.py --limit 300 --workers 3
step "step 8-pre: hidden_realtor_map(숨김ID 귀속)" $PY -u scripts/apply_hidden_realtor_map.py

step "step 9: match_clean (realtor)"       $PY -u scripts/match_clean.py; match_exit=$?
# 9a: 미매칭 지역중개사 등록번호 매칭(매물상세 establishRegistrationNo→vworld). 자체번호 우선·전매물 일관·
#     대표 이중검증·오귀속0. 등록번호를 naver_realtors에 기록 → 이후 match_clean이 매일 자동 재도출(지속).
#     신규 미매칭만 점증 커버(30일 캐시), API 예산 위해 --limit.
step "step 9a: link_region_regno (미매칭 등록번호)" $PY -u scripts/link_region_realtors_regno.py --limit 200 --workers 6 --samples 5; linkregno_exit=$?
# 9a-2: 상호 변경 감시. step 8 은 --only-missing 이라 이미 있는 프로필을 영원히 건너뛴다 →
#   사무소가 개명해도 naver_realtors 가 안 바뀌어, 목록(옛 이름)과 상세(매물의 새 이름)가
#   서로 다르게 보였다(2026-10-16 제보로 발견, 3,215곳). 오늘 매물의 상호와 저장된 상호를
#   비교해 바뀐 곳만 모아 vworld 공부상 상호로 대조하고, 그 사무소 프로필만 다시 받는다.
#   반드시 9b(build_realtor_dong) **앞**이어야 realtor_names 가 새 상호를 싣는다.
step "step 9a-2: realtor_name_watch (상호 변경)" $PY -u scripts/realtor_name_watch.py --max-sgg 40; namewatch_exit=$?
# 9a-3: 사무소 승계 탐지. 대표가 바뀌면 같은 자리·같은 상호라도 새 등록번호로 다시 등록되는데,
#   우리 vworld 적재분에는 폐업 상태가 없어 옛 번호가 계속 '영업'으로 남는다. 계정이 옛 번호에
#   붙은 채 굳어 매칭이 조용히 틀어진다(2026-10-21 흑석 새봄 제보). 탐지만 하고 적용은 사람이 한다.
step "step 9a-3: detect_succession (승계 후보)" $PY -u scripts/detect_succession.py --save --limit 0; succession_exit=$?
# 9a-4: 도로명만 등록돼 동을 못 찾는 사무소의 주소를 VWorld 에 물어 법정동을 받아 둔다.
#   '우리동네 중개사'는 사무소 소재 동이 있어야 보이는데, 신축 상가처럼 도로명만 등록되고
#   네이버 매칭도 없으면 단서가 없어 통째로 빠졌다(2026-10-22 전국 대조 12,787곳).
#   받아 둔 값은 9b 가 4차 패스로 읽는다. 신규분만 점증(이미 물어본 건 건너뜀).
step "step 9a-4: geocode_broker_dong (사무소 법정동)" $PY -u scripts/geocode_broker_dong.py --limit 500; brokerdong_exit=$?
step "step 9b: build_realtor_dong (우리동네)" $PY -u scripts/build_realtor_dong.py; rdong_exit=$?
step "step 10: rematch_all_realprice"      $PY -u scripts/rematch_all_realprice.py --tables apt rent offi offi_rent --concurrency 4; rematch_exit=$?

# 10b) 등기 전 거래 동(棟) 추정 — 매칭(step 10) 뒤. 메인 DB 는 읽기만, 결과는 data/dong_estimates.sqlite.
#      새 거래 예비 추정 → 계약 +45일 최종 고정 → 등기 올라오면 정답 대조(로그) → 일요일 재학습(개선 시 승격).
step "step 10b: dong_estimate (등기 전 동 추정)" nice -n 10 $PY -u scripts/dong_estimate.py --daily; dongest_exit=$?

# 11) 롤업 (매칭 후, 캐시 전)
step "step 11: build_tx_rollups"           $PY -u scripts/build_tx_rollups.py; rollup_exit=$?

# 11b) 특수조건 매매 색인(주인전세·세안고·대출승계) — 매물 설명 기준이라 수집 직후 재생성.
#      전량 교체라 내려간 매물이 남지 않는다(4초).
step "step 11b: build_special_deals"       $PY -u scripts/build_special_deals.py; special_exit=$?
step "step 11d: build_quick_deals_cx (지도 동·구 급매 묶음)" nice -n 10 $PY -u scripts/build_quick_deals_cx.py; qdcx_exit=$?
# 11e) K-apt 관리비 — 연결 단지의 빠진 달 채우기(서비스별 일일 한도 안에서) + 최근 열린 단지 새로 연결
step "step 11e: kapt_fill (공동주택 관리비 공개자료)" nice -n 10 $PY -u scripts/kapt_fill.py; kapt_exit=$?
# 11f) 콕집매물 동기화 — 동의 사무소의 광고 중 매물을 수집 DB(읽기만)에서 콕집매물 DB(data/kok.sqlite)로 한 방향 복사.
#      안 보인 매물은 closed 표시(삭제 안 함), 상세(방·욕실·입주)는 여기서 받아 둔다. 화면은 kok.sqlite 만 읽는다.
step "step 11f: kok_sync (콕집매물 DB 동기화)" nice -n 10 $PY -u scripts/kok_sync.py; koksync_exit=$?
# 11g) 알리고 문자 잔액 — 100건 미만이면 텔레그램(잔액 0건으로 인증 문자가 조용히 실패한 2026-11-10 사고 재발 방지)
step "step 11g: aligo_remain_check (문자 잔액)" $PY -u scripts/aligo_remain_check.py; aligo_exit=$?
# 11h) 입주자·소유자 명단 — 올린 지 180일 지난 명단 삭제(고객원장과 별도 DB roster.sqlite)
step "step 11h: roster purge (만료 명단 삭제)" $PY -u scripts/roster.py --purge

# 11c) KST/UTC 정합 회귀검사 — SQLite date('now')는 UTC라 업무일자(deal_ymd 등)와
#      비교하면 매일 00~09시에 하루 밀린다(실측: 최근1일 실거래 684 vs 정상 213).
#      데이터 사이트에서 이런 오차는 조용히 지나가면 안 되므로 매일 확인한다.
step "step 11c: check_kst_dates"           $PY -u scripts/check_kst_dates.py; kst_exit=$?

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
step "step 13-pre: hidden_realtor_map(비단지 신규분 귀속)" $PY -u scripts/apply_hidden_realtor_map.py
step "step 13b: build_realtor_dong (비단지 반영)" $PY -u scripts/build_realtor_dong.py; rdong2_exit=$?

log "daily run done  collect=$collect_exit archive=${archive_exit:-NA} realprice=${realprice_exit:-NA} rentals=${rentals_exit:-NA} offi=${offi_exit:-NA} silv=${silv_exit:-NA} villa=${villa_exit:-NA} house=${house_exit:-NA} comm=${comm_exit:-NA} supply=${supply_exit:-NA} cdetail=${cdetail_exit:-NA} nrealtor=${nrealtor_exit:-NA} namewatch=${namewatch_exit:-NA} brokerdong=${brokerdong_exit:-NA} match=${match_exit:-NA} rematch=${rematch_exit:-NA} rollup=${rollup_exit:-NA} cache=${cache_exit:-NA} trendcache=${trendcache_exit:-NA} region=${region_exit:-NA}"
bash "$ROOT/scripts/warm_api.sh" >>"$LOG" 2>&1 || true   # 캐시 워밍(재빌드 후 첫 사용자도 빠르게)
