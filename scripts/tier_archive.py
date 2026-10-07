"""누적 이력 계층화 — 오래된 파티션을 운영 DB에서 아카이브로 옮긴다(삭제 아님).

왜 필요한가
  articles(비활성)·article_events·complex_daily_agg 는 라이브 조회 범위가 짧은데도
  무한 누적되어 월 3.3GB 씩 NVMe 를 먹는다. 2026-09-25 디스크풀 사고의 근본 원인.
  → 오래된 파티션을 /mnt/backup/archive.sqlite 로 옮겨 전량 보존하고 NVMe 는 평평하게 유지.

왜 라이브 조회가 안 깨지나 (2026-09-25 코드 전수 확인)
  · articles          : local_api.py 에 참조 0곳. 수집기도 is_active=1 만 스캔.
  · article_events    : MAX(event_date) 1일 + 최근 피드 LIMIT 만 조회.
  · complex_daily_agg : 쿼리 9곳 전부 날짜 경계 있음(최대 92일 하드캡).
  보존일수는 이 한계보다 넉넉하게 잡는다.

안전 설계
  · 복사 → 검증 → 삭제 순서. 검증 실패 시 삭제하지 않는다(WAL 모드는 DB간 원자성이 없다).
  · 기준일은 시작 시 1회 계산해 리터럴로 고정 — 복사/삭제가 자정을 넘겨도 같은 조건.
  · 삭제는 배치 + 배치마다 WAL 체크포인트 + 디스크 여유 감시(부족하면 즉시 중단).
  · VACUUM 하지 않는다. 삭제로 생긴 빈 페이지를 다음 달 INSERT 가 재사용해 파일이 평평해진다.
  · 재등록(article_no 부활) 대비: 아카이브에 이미 있는 키는 건너뛰고, 핫에 있는 쪽을 정본으로 본다.
"""
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DB = Path(os.environ.get("KOCZIP_DB", "/opt/koczip/data/naverreal.sqlite"))
ARC = Path(os.environ.get("KOCZIP_ARCHIVE", "/mnt/backup/archive.sqlite"))
LOCK = "/var/lock/koczip-tier.lock"
BATCH = 200_000
MIN_FREE_MB = 1500          # 루트 여유가 이 밑이면 중단
DRY = "--dry-run" in sys.argv

# (테이블, 날짜컬럼, 보존일수, 추가조건)
TARGETS = [
    ("articles", "last_seen_date", 90, "is_active=0"),
    ("article_events", "event_date", 30, None),
    ("complex_daily_agg", "snapshot_date", 92, None),
]


def log(msg):
    print("[%s] %s" % (time.strftime("%F %T"), msg), flush=True)


def notify(msg):
    try:
        subprocess.run(["/opt/koczip/.venv/bin/python",
                        "/opt/koczip/scripts/tg_notify.py", "계층화: " + msg],
                       cwd="/opt/koczip", timeout=30, check=False)
    except Exception:
        pass


def free_mb(path="/"):
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize / 1048576


def main():
    if not DB.exists():
        log("운영 DB 없음: %s" % DB)
        return 1

    # 단일 실행 보장
    lock = open(LOCK, "w")
    try:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("다른 계층화가 실행 중 — 건너뜀")
        return 0

    con = sqlite3.connect(str(ARC), timeout=3600)
    con.execute("PRAGMA journal_mode=WAL")
    # 운영 DB 는 읽기 전용으로 붙인다 — 복사 단계에서 원본 쓰기를 물리적으로 차단
    con.execute("ATTACH DATABASE ? AS src", ("file:%s?mode=ro" % DB,))

    moved_total = 0
    plan = []
    for tbl, datecol, keep, extra in TARGETS:
        cutoff = con.execute(
            "SELECT date('now','+9 hours',?)", ("-%d days" % keep,)).fetchone()[0]
        cond = "%s < '%s'" % (datecol, cutoff)
        if extra:
            cond = "%s AND %s" % (extra, cond)
        n = con.execute("SELECT COUNT(*) FROM src.%s WHERE %s" % (tbl, cond)).fetchone()[0]
        plan.append((tbl, cond, cutoff, n))
        log("계획 %-18s 보존 %3d일(< %s)  이관대상 %s행" % (tbl, keep, cutoff, format(n, ",")))

    if DRY:
        log("DRY-RUN — 변경 없음")
        return 0

    # ── 1) 복사 + 검증 ─────────────────────────────────────
    for tbl, cond, cutoff, expect in plan:
        if expect == 0:
            continue
        exists = con.execute(
            "SELECT COUNT(*) FROM main.sqlite_master WHERE type='table' AND name=?",
            (tbl,)).fetchone()[0]
        if not exists:
            ddl = con.execute(
                "SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?",
                (tbl,)).fetchone()[0]
            con.execute(ddl)
            log("아카이브에 %s 생성" % tbl)
        before = con.execute("SELECT COUNT(*) FROM main.%s" % tbl).fetchone()[0]
        # 재등록 등으로 이미 있는 키는 건너뛴다(핫이 정본)
        con.execute("INSERT OR IGNORE INTO main.%s SELECT * FROM src.%s WHERE %s"
                    % (tbl, tbl, cond))
        con.commit()
        after = con.execute("SELECT COUNT(*) FROM main.%s" % tbl).fetchone()[0]
        added = after - before
        if added != expect:
            log("중단: %s 복사 %s행 != 대상 %s행 (중복키 가능) — 삭제하지 않음"
                % (tbl, format(added, ","), format(expect, ",")))
            notify("복사 행수 불일치(%s) — 삭제 중단" % tbl)
            return 2
        log("복사 %-18s %s행 (아카이브 %s행)" % (tbl, format(added, ","), format(after, ",")))
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()

    # ── 2) 삭제(배치 + 체크포인트 + 디스크 감시) ─────────────
    w = sqlite3.connect(str(DB), timeout=3600)
    w.execute("PRAGMA journal_mode=WAL")
    for tbl, cond, cutoff, expect in plan:
        if expect == 0:
            continue
        done = 0
        while True:
            if free_mb() < MIN_FREE_MB:
                log("중단: 루트 여유 %.0fMB < %dMB" % (free_mb(), MIN_FREE_MB))
                notify("디스크 여유 부족으로 삭제 중단(%s)" % tbl)
                w.close()
                return 3
            cur = w.execute(
                "DELETE FROM %s WHERE rowid IN (SELECT rowid FROM %s WHERE %s LIMIT %d)"
                % (tbl, tbl, cond, BATCH))
            n = cur.rowcount
            w.commit()
            w.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            done += n
            if n == 0:
                break
        log("삭제 %-18s %s행" % (tbl, format(done, ",")))
        moved_total += done
    fl = w.execute("PRAGMA freelist_count").fetchone()[0]
    ps = w.execute("PRAGMA page_size").fetchone()[0]
    log("빈 페이지 %.2fGB (다음 적재가 재사용 — VACUUM 불필요)" % (fl * ps / 2 ** 30))
    w.close()

    log("완료: 총 %s행 이관" % format(moved_total, ","))
    notify("완료 — %s행 이관, 루트 여유 %.1fGB" % (format(moved_total, ","), free_mb() / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
