#!/usr/bin/env bash
# vworld 중개업소 등록DB 월간 갱신 + 매칭 재실행.
# vworld_brokers는 자동갱신이 없어(마지막 수동 2026-06-19) 신규 개업 사무소가 누락 →
# ①CP매물 등록번호 귀속(office_region_attribution) 무매칭 ②중개사 매칭 공백 발생.
# 월 1회 크롤로 신규 사무소를 흡수한다. 크롤 후 매칭·귀속·우리동네를 재빌드.
#
# 무결성: daily_run(02시)·다른 파이프라인과 겹치지 않게 크론은 조용한 시간(매월 1일 08:30,
# 백업 07:30·daily 06:39 종료 후). vworld_brokers는 daily_run이 안 쓰므로 write 충돌 없음.
set -u
ROOT=/opt/koczip
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/logs/vworld_refresh_$(date +%Y%m).log"
mkdir -p "$ROOT/logs"
log(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }
cd "$ROOT" || exit 1

# 행정개편으로 신설된 시군구 코드. regions 는 옛 코드를 유지하는 정책이라 list_sigungus 가
# 이 코드들을 만들어내지 못한다. vworld 는 신설 코드로만 응답하므로 명시적으로 넘긴다.
#   · 2026-07-01 광주(29)+전남(46) → 12 통합
# 옛 코드로 요청하면 오류 없이 0건이 돌아와 조용히 누락되므로 반드시 유지할 것.
SGG_MERGED="12110,12130,12150,12170,12190,12210,12240,12270,12300,12330,12710,12720,12730,12740,12750,12760,12770,12780,12790,12800,12810,12820,12830,12840,12850,12860,12870"

log "=== vworld list 크롤 시작 ==="
$PY -u scripts/crawl_vworld_brokers.py --list --parallel 4 >>"$LOG" 2>&1; r1=$?
log "크롤(regions 기준) exit=$r1"
$PY -u scripts/crawl_vworld_brokers.py --list --sgg "$SGG_MERGED" --parallel 3 >>"$LOG" 2>&1
log "크롤(개편 신설코드) exit=$?"

# 소속직원 명단 — 2026-10-01 추가. 이전까지 --list 만 돌아 직원 데이터가 2026-05 에서 멈춰 있었다.
# upsert 전용이라 퇴사자가 지워지지 않으므로, 크롤 후 미갱신 행을 정리하는 래퍼를 쓴다.
log "=== 소속직원 크롤+정리 시작 ==="
$PY -u scripts/refresh_vworld_employees.py --parallel 3 >>"$LOG" 2>&1
log "직원 갱신 exit=$?"
$PY -u scripts/crawl_vworld_brokers.py --employees --sgg "$SGG_MERGED" --parallel 3 >>"$LOG" 2>&1
log "직원(개편 신설코드) exit=$?"

# 신규 사무소 반영 — 매칭(naver↔vworld) → 우리동네(동별 랭킹) → CP매물 등록번호 귀속
$PY -u scripts/match_clean.py                        >>"$LOG" 2>&1; log "match_clean exit=$?"
$PY -u scripts/build_realtor_dong.py                 >>"$LOG" 2>&1; log "build_realtor_dong exit=$?"
$PY -u scripts/build_region_office_attribution.py    >>"$LOG" 2>&1; log "office_attribution exit=$?"
$PY -u scripts/link_region_realtors.py >>"$LOG" 2>&1; log "link_region_realtors exit=$?"
$PY -u scripts/link_region_realtors_regno.py --workers 6 >>"$LOG" 2>&1; log "link_region_realtors_regno exit=$?"
$PY -u scripts/ensure_realtor_profiles.py --min 1 >>"$LOG" 2>&1; log "ensure_realtor_profiles exit=$?"
log "=== vworld refresh 완료 ==="

# 랭킹 캐시 무효화: 월간 체인은 naverreal.sqlite만 바꿔 _data_version(api_cache 기반)이 안 변함
# → 런타임 캐시가 다음 daily(06:39)까지 stale. 디스크 캐시 비우고 API 재시작(RAM 캐시)해 즉시 반영.
sqlite3 "$ROOT/data/runtime_cache.sqlite" "DELETE FROM mem_cache" 2>>"$LOG"; log "runtime_cache 클리어 exit=$?"
systemctl restart koczip-api; log "koczip-api 재시작 exit=$?"

# 실거래 지번 지오코딩 NOT_FOUND 월간 재시도 — VWorld가 행정개편(인천 신설구 등)을
# 반영하면 이전 실패 주소가 뒤늦게 풀린다. 마스킹(*) 지번은 스크립트가 즉시 fail 처리라 낭비 없음.
.venv/bin/python -u scripts/geocode_jibun.py --workers 4 --rps 10 --retry-fail >> data/coord_addr.log 2>&1
