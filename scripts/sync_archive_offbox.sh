#!/usr/bin/env bash
# 매물 parquet 아카이브 오프박스 동기화 — koczip 박스(디스크 87%) → nfind 박스(42G 여유).
# 대상: /opt/koczip/data/archive/ 전체(아파트 listings 85MB/일 + 비단지 10종 35MB/일).
# 격리: nfind 쪽은 /opt/koczip-archive/ 전용 디렉터리만 사용(nfind 서비스 무접촉).
# 성공 시에만 로컬 30일 초과 parquet 삭제(최근 30일은 양쪽 보관, 그 이전은 nfind에만).
# 크론 22:30 nonresi 체인 뒤에 붙음. 실패 시 텔레그램 알림.
set -u
SRC=/opt/koczip/data/archive/
DST=root@115.68.177.72:/opt/koczip-archive/archive/
LOG=/tmp/archive_sync.log

echo "[$(date '+%F %T')] sync start" >> "$LOG"
rsync -a --timeout=600 "$SRC" "$DST" >> "$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] rsync FAIL rc=$rc" >> "$LOG"
  cd /opt/koczip && .venv/bin/python scripts/tg_notify.py \
    "아카이브 오프박스 동기화 실패(rc=$rc) — nfind 박스 확인 필요. 로컬 삭제는 건너뜀(안전)." || true
  exit $rc
fi
# 동기화 성공 → 30일 초과 로컬 parquet 정리(디스크 회수)
purged=$(find "$SRC" -name '*.parquet' -mtime +30 -print -delete | wc -l)
echo "[$(date '+%F %T')] sync OK, purged_local=$purged" >> "$LOG"
