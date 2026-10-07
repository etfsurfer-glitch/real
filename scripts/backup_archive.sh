#!/usr/bin/env bash
# 아카이브 백업 — /mnt/backup/archive.sqlite 를 /mnt/cold 로 압축 보관.
#
# 왜 필요한가
#   archive.sqlite 는 계층화로 옮겨진 '재생성 불가' 원장이다(articles 비활성·
#   article_events·complex_daily_agg 과거분). 그런데 backup_daily.sh 는
#   /opt/koczip/data/*.sqlite 만 백업하므로 아카이브는 백업 대상 밖이었다.
#   사본이 하나도 없으면 vdb 장애 = 영구 소실.
#
# 설계
#   · sqlite3 ".backup" 으로 일관 스냅샷(라이브 쓰기 중에도 안전). cp 금지.
#   · zstd 압축(실측 5배 이상) → vdc 49GB 로 수년 보관 가능.
#   · 임시파일에 완성 후 원자적 mv. 검증 실패 시 기존 사본 유지.
#   · 2벌 순환.
#   · 마운트 가드: /mnt/cold 가 실제 마운트가 아니면 중단(root 디스크 보호).
set -u
ARC=/mnt/backup/archive.sqlite
DEST=/mnt/cold/archive_backup
KEEP=2
STAMP=$(date '+%F')
LOG=/tmp/backup_archive.log
say() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
alert() {
  say "ALERT: $*"
  cd /opt/koczip && .venv/bin/python scripts/tg_notify.py "아카이브 백업 경고: $*" >/dev/null 2>&1 || true
}

exec 9>/var/lock/koczip-archive-backup.lock
flock -n 9 || { say "다른 실행 중 — 건너뜀"; exit 0; }

say "===== archive backup start ($STAMP) ====="
[ -f "$ARC" ] || { say "아카이브 없음 — 건너뜀"; exit 0; }
mountpoint -q /mnt/cold || { alert "/mnt/cold 미마운트 — 중단"; exit 1; }
mkdir -p "$DEST"

TMP="$DEST/.building_$STAMP.sqlite"
OUT="$DEST/archive_$STAMP.sqlite.zst"
rm -f "$TMP" "$TMP.zst"

# 1) 일관 스냅샷
if ! sqlite3 -cmd ".timeout 60000" "file:$ARC?mode=ro" ".backup '$TMP'" 2>>"$LOG"; then
  alert ".backup 실패"; rm -f "$TMP"; exit 1
fi
# 2) 무결성 (2GB 이상은 구조검증 — .backup 이 일관성을 보장하므로 충분)
sz=$(stat -c%s "$TMP")
if [ "$sz" -ge 2147483648 ]; then
  chk=$(sqlite3 "$TMP" "PRAGMA schema_version; SELECT count(*) FROM sqlite_master;" >/dev/null 2>&1 && echo ok || echo bad)
else
  chk=$(sqlite3 "$TMP" "PRAGMA quick_check" 2>/dev/null | head -1)
fi
[ "$chk" = "ok" ] || { alert "무결성 실패($chk) — 기존 사본 유지"; rm -f "$TMP"; exit 1; }

# 3) 압축 + 검증 후 원자적 확정
if ! nice -n19 ionice -c3 zstd -3 -T2 -q -f -o "$TMP.zst" "$TMP" 2>>"$LOG"; then
  alert "압축 실패"; rm -f "$TMP" "$TMP.zst"; exit 1
fi
zstd -t "$TMP.zst" >/dev/null 2>&1 || { alert "압축본 검증 실패"; rm -f "$TMP" "$TMP.zst"; exit 1; }
rm -f "$TMP"
mv "$TMP.zst" "$OUT"

# 4) 순환
ls -1t "$DEST"/archive_*.sqlite.zst 2>/dev/null | tail -n +$((KEEP+1)) | while read -r old; do
  say "prune old: $old"; rm -f "$old"
done

say "archive backup OK: $(basename "$OUT")  $((sz/1048576))MB → $(( $(stat -c%s "$OUT") /1048576 ))MB  cold_avail=$(df -h /mnt/cold | awk 'NR==2{print $4}')"
exit 0
