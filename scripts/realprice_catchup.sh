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

# ── 발동 조건 ──────────────────────────────────────────────
# 예전엔 마커(날짜)와 오늘 날짜만 비교했는데, 자정에 날짜가 넘어가는 순간
# '오늘 아직 안 받았다'가 되어 **daily_run 이 돌기도 전에** 전량 수집을 시작했다.
# 실측(2026-07-23): 매일 00:00 에 발동해 1시간 8분간 daily 와 같은 일을 중복 수행.
#
# 그래서 두 가지로 판단한다:
#   ① daily_run 이 끝났어야 할 시각(DAILY_DONE_BY)이 지났는가 — 그 전이면 daily 차례를 기다린다
#   ② 마지막 성공이 STALE_HOURS 넘게 오래됐는가 — 그래야 '실패'로 본다
# 이러면 실제 장애(daily 가 API DOWN 으로 못 받은 날)에만 나선다.
# catchup 은 '오늘 daily 가 실거래를 못 받았다'만 메운다.
# 낮 시간대의 정기 보충은 realprice_refresh(08·15·18시)가 따로 맡으므로,
# 여기서 '오래됐다'를 시간 길이로만 재면 정상일 오후에도 오발동한다(9시간 경과 등).
# → 판정은 '오늘 daily 성공 기록이 있는가'로 하되, 그 시각이 daily 예정 시각 이후여야 한다.
DAILY_DONE_BY="06:00"   # daily_run 00:30 시작 + 소요 5h15m + 여유

now_s=$(date +%s)
gate_s=$(date -d "today $DAILY_DONE_BY" +%s)
if [ "$now_s" -lt "$gate_s" ]; then
  exit 0                      # 아직 daily 차례 — 나서지 않는다
fi

# 마커는 ISO 시각(2026-07-23T05:17:03). 옛 형식(날짜만)도 읽어 그날 00:00 으로 본다
# → 보수적으로 '오래됨' 판정이 나와 한 번 돌고 나면 새 형식으로 자동 교체된다.
last_raw=$(cat "$MARKER" 2>/dev/null || true)
last_s=0
if [ -n "$last_raw" ]; then
  last_s=$(date -d "$(echo "$last_raw" | tr 'T' ' ')" +%s 2>/dev/null || echo 0)
fi
# 오늘(KST) 안에 찍힌 마커면 daily 가 성공한 것 — 나설 일 없다.
today_start_s=$(date -d "today 00:00" +%s)
if [ "$last_s" -ge "$today_start_s" ]; then
  exit 0
fi
age_h=$(( (now_s - last_s) / 3600 ))
log "catchup 발동: 오늘 daily 실거래 성공 기록 없음(마지막 ${age_h}시간 전, 마커=${last_raw:-없음})"

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
  date +%FT%H:%M:%S > "$MARKER"
  log "=== catchup 완료 (마커=$(cat "$MARKER")) ==="
else
  log "catchup: 수집 중 data.go.kr 재DOWN → 마커 미기록, 다음 틱 재시도"
fi
