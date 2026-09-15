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

log "=== vworld list 크롤 시작 ==="
$PY -u scripts/crawl_vworld_brokers.py --list --parallel 4 >>"$LOG" 2>&1; r1=$?
log "크롤 exit=$r1"

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
