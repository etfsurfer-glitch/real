#!/usr/bin/env bash
# 콕집 일일 백업 — /opt/koczip/data 의 SQLite DB + 사용자 업로드를
# 전용 백업 디스크(/mnt/backup, 100GB 블록스토리지 LABEL=koczip-backup)에 보관.
#
# 설계:
#  · DB는 sqlite3 ".backup"(온라인 일관 스냅샷 — WAL 포함, 라이브 수집 중에도 안전).
#    단순 cp는 WAL모드에서 깨질 수 있어 금지.
#  · 각 백업본 quick_check 무결성 검증 → 실패 시 그 DB는 직전 스냅샷 유지, 알림.
#  · 임시 디렉터리에 완성 후 원자적 mv → 부분/실패 백업이 정상본 행세 못 함.
#  · 5일 순환(오늘 포함). 새 백업 쓰기 전 오래된 것부터 정리.
#  · ★최신 1벌만 원본 그대로, 나머지는 zstd 압축(실측 7~9배). 장애 때는 최신본을
#    압축 해제 없이 바로 갖다 쓰고, 과거분은 되돌릴 때만 풀면 된다.
#      복원:  zstd -d /mnt/backup/2026-07-30/db/naverreal.sqlite.zst -o /경로/naverreal.sqlite
#  · 압축은 '파일 하나 압축 → 검증 → 원본 삭제'를 크기 작은 것부터 반복한다.
#    한꺼번에 압축하면 원본+압축본이 동시에 존재해 디스크가 터진다(전환 당시 여유 2.6GB).
#  · archive/ 는 제외 — 이미 nfind 오프박스로 복제됨(naverreal-offbox-archive).
#  · ★마운트 가드: /mnt/backup 이 실제 마운트가 아니면 즉시 중단(root 디스크 87% 보호).
# 크론 06:00(02시 daily_run 완료 후, 11시 수집 전 조용한 시간).
set -u
DATA=/opt/koczip/data
DEST=/mnt/backup
KEEP=5                      # 보관할 일자 스냅샷 수(오늘 포함)
BIG=2147483648             # 2GB↑ DB는 quick_check(전 페이지 검사, 23GB=3h+) 대신 빠른 구조검증
LOG=/tmp/backup_daily.log
STAMP=$(date '+%F')
TS() { date '+%F %T'; }
say() { echo "[$(TS)] $*" >> "$LOG"; }
alert() {
  say "ALERT: $*"
  cd /opt/koczip && .venv/bin/python scripts/tg_notify.py "백업 경고: $*" >/dev/null 2>&1 || true
}

# ── 과거 스냅샷 압축 ─────────────────────────────────────
# 파일 하나씩: 압축 → zstd -t 검증 → 원본 삭제. 검증 실패면 압축본만 버리고 원본 유지.
compress_dir() {
  local dir="$1" f out before after
  [ -d "$dir/db" ] || return 0
  # 작은 파일부터(먼저 압축해 확보한 공간으로 큰 파일을 압축할 수 있다)
  while IFS= read -r f; do
    [ -e "$f" ] || continue
    out="$f.zst"
    before=$(stat -c%s "$f")
    # -f: 중단된 이전 시도의 잔여 .zst 를 덮어쓴다(없으면 재실행이 영영 막힌다)
    if ! nice -n19 ionice -c3 zstd -3 -T2 -q -f -o "$out" "$f" 2>>"$LOG"; then
      say "compress fail(생성): $f"; rm -f "$out"; continue
    fi
    if ! zstd -t "$out" >/dev/null 2>&1; then
      alert "압축본 검증 실패 — 원본 유지: $f"; rm -f "$out"; continue
    fi
    after=$(stat -c%s "$out")
    rm -f "$f"
    say "compressed: $(basename "$f") $((before/1048576))MB → $((after/1048576))MB"
  done < <(find "$dir/db" -maxdepth 1 -name '*.sqlite' -printf '%s\t%p\n' | sort -n | cut -f2)
}

# 전부 압축(최신본까지) — 공간이 부족할 때만. 즉시복구용 원본이 잠시 사라진다.
compress_all() {
  ls -1d "$DEST"/20*/ 2>/dev/null | while read -r d; do compress_dir "${d%/}"; done
}

# 최신 스냅샷 하나만 원본으로 두고 나머지를 압축
compress_old() {
  local newest
  newest=$(ls -1d "$DEST"/20*/ 2>/dev/null | sort | tail -1)
  ls -1d "$DEST"/20*/ 2>/dev/null | sort | while read -r d; do
    [ "$d" = "$newest" ] && continue
    compress_dir "${d%/}"
  done
}

# ── 단일 실행 보장(크론×수동, 이전 런 초과 시 충돌 방지) ──
exec 9>/var/lock/koczip-backup.lock
if ! flock -n 9; then
  say "다른 백업이 실행 중 — 이번 실행 건너뜀(중복 방지)."
  exit 0
fi

if [ "${1:-}" = "--compress-old" ]; then
  if ! mountpoint -q "$DEST"; then say "$DEST 미마운트 — 중단"; exit 1; fi
  say "===== compress-old only ====="
  compress_old
  say "compress-old 완료 · disk_avail=$(df -h "$DEST" | awk 'NR==2{print $4}')"
  exit 0
fi

say "===== backup start ($STAMP) ====="

# ── 마운트 가드(최우선) ──────────────────────────────────
if ! mountpoint -q "$DEST"; then
  alert "$DEST 미마운트 — 백업 중단(root 디스크 보호). 블록스토리지 확인 필요."
  exit 1
fi

# DB 백업본 검증: 2GB↑=빠른 구조검증(헤더+스키마 b-tree, .backup이 일관성 보장하므로 충분),
# 미만=full quick_check. 성공 시 "ok" 출력.
validate_db() {
  local f="$1" sz
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -ge "$BIG" ]; then
    if sqlite3 "$f" "PRAGMA schema_version; SELECT count(*) FROM sqlite_master;" >/dev/null 2>&1; then
      echo ok
    else
      echo "malformed"
    fi
  else
    sqlite3 "$f" "PRAGMA quick_check" 2>/dev/null | head -1
  fi
}

# ── 공간 점검: 이번 백업이 들어갈 자리가 있는지 먼저 본다 ──
#   못 들어가면 (1)과거분 압축 → (2)그래도 모자라면 최신본까지 압축.
#   DB가 커질수록 '원본 1벌 + 새 백업'이 볼륨을 넘어설 수 있어 이 단계가 필요하다.
need_kb=$(du -sk --exclude=archive "$DATA" 2>/dev/null | cut -f1)
need_kb=$((need_kb + need_kb / 10))                  # 10% 여유
free_kb=$(df -Pk "$DEST" | awk 'NR==2{print $4}')
if [ "$free_kb" -lt "$need_kb" ]; then
  say "공간 부족(여유 $((free_kb/1048576))GB < 필요 $((need_kb/1048576))GB) — 과거분 압축"
  compress_old
  free_kb=$(df -Pk "$DEST" | awk 'NR==2{print $4}')
fi
if [ "$free_kb" -lt "$need_kb" ]; then
  say "여전히 부족 — 최신본까지 압축(즉시복구본은 이번 백업 완료 시 재생성)"
  compress_all
  free_kb=$(df -Pk "$DEST" | awk 'NR==2{print $4}')
fi
if [ "$free_kb" -lt "$need_kb" ]; then
  alert "백업 공간 부족: 여유 $((free_kb/1048576))GB, 필요 $((need_kb/1048576))GB — 보관일수(KEEP=$KEEP) 축소나 볼륨 증설 필요"
  exit 1
fi

BUILD="$DEST/.building"
rm -rf "$BUILD"; mkdir -p "$BUILD/db" "$BUILD/files"

# ── 공간 확보: 새 백업 전에 오래된 스냅샷부터 정리(KEEP-1 남기고) ──
ls -1d "$DEST"/20*/ 2>/dev/null | sort | head -n -$((KEEP-1)) | while read -r old; do
  say "prune old: $old"; rm -rf "$old"
done

# ── DB 온라인 일관 백업 + 무결성 검증 ──────────────────────
fail=0; ndb=0
for src in "$DATA"/*.sqlite; do
  [ -e "$src" ] || continue
  name=$(basename "$src")
  out="$BUILD/db/$name"
  if sqlite3 -cmd ".timeout 60000" "file:$src?mode=ro" ".backup '$out'" 2>>"$LOG"; then
    chk=$(validate_db "$out")
    if [ "$chk" = "ok" ]; then
      ndb=$((ndb+1))
    else
      alert "$name 무결성 실패($chk) — 이 DB 제외"; rm -f "$out"; fail=$((fail+1))
    fi
  else
    alert "$name .backup 실패 — 이 DB 제외"; rm -f "$out"; fail=$((fail+1))
  fi
done

# ── 사용자 업로드(재생성 불가) ────────────────────────────
for d in homepage_images realtor_docs; do
  [ -d "$DATA/$d" ] && rsync -a --delete "$DATA/$d/" "$BUILD/files/$d/" 2>>"$LOG"
done

# ── 매니페스트 ───────────────────────────────────────────
{
  echo "backup: $STAMP  host=$(hostname)  taken=$(TS)  path=$DEST/$STAMP"
  echo "dbs_ok=$ndb  dbs_failed=$fail"
  echo "--- sizes ---"; (cd "$BUILD" && du -sh db/* files/* 2>/dev/null)
  echo "--- total ---"; du -sh "$BUILD" | sed "s#$BUILD#(total)#"
} > "$BUILD/MANIFEST.txt"

# ── DB가 하나도 안 백업됐으면 실패 처리(원자적 확정 안 함) ──
if [ "$ndb" -eq 0 ]; then
  alert "백업된 DB 0개 — 확정 취소"; rm -rf "$BUILD"; exit 2
fi

# ── 원자적 확정 + latest 갱신 ─────────────────────────────
rm -rf "$DEST/$STAMP"
mv "$BUILD" "$DEST/$STAMP"
ln -sfn "$STAMP" "$DEST/latest"
total=$(du -sh "$DEST/$STAMP" | cut -f1)

# ── 과거 스냅샷 압축(최신 1벌은 원본 유지) ────────────────
compress_old

avail=$(df -h "$DEST" | awk 'NR==2{print $4}')
say "backup OK: $STAMP  dbs=$ndb failed=$fail  size=$total  disk_avail=$avail"
[ "$fail" -gt 0 ] && exit 3 || exit 0
