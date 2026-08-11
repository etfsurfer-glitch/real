#!/usr/bin/env python3
"""비단지 DB 조각 회수 — 운영 중에 돌려도 사고가 안 나게 만든 것.

**파일을 바꾸지 않는다.** 예전 판은 새 파일을 만들어 원본과 바꿔치기했는데, 그 사이에
다른 프로세스가 옛 파일에 쓰면 그 쓰기가 통째로 사라진다. 비단지 DB 를 건드리는
프로세스는 수집 말고도 다섯이나 있고(nonresi_daily_agg·archive_nonresi_listings·
build_realtor_dong·match_region_realtors·realtor_integrity_check) **그중 어느 것도
pipeline.lock 을 잡지 않는다** — 락만으로는 못 막는다.

그래서 SQLite 의 in-place VACUUM 을 쓴다. SQLite 가 배타 잠금을 잡고 트랜잭션으로
처리하므로 다른 쓰기는 기다릴 뿐 사라지지 않는다. 대신 그동안 읽기도 막히므로
**한 번에 한 DB 씩, 가장 한가한 시간에** 돌린다.

  python3 scripts/vacuum_nonresi.py            # 전부(회수 여지 5% 넘는 것만)
  python3 scripts/vacuum_nonresi.py sangga     # 지정
  python3 scripts/vacuum_nonresi.py --dry      # 검사만
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time

DATA = "/opt/koczip/data"
CATS = ["redev", "knowledge", "factory", "oneroom", "building", "land",
        "office", "villa", "house", "sangga"]
MIN_FREE_GB = 3.0          # 이 아래면 아예 시작하지 않는다
MIN_GAIN_PCT = 5.0         # 회수 여지가 이보다 작으면 건드리지 않는다
# 피해야 할 시간대(KST) — 비단지 DB 를 건드리는 것만 추린다.
#   collect_region_listings : 매물수집 11~14시·19~22시 안(step 7), daily_run 00:30~05:00 안(step 13)
#   nonresi_daily_agg + archive : 22:30      사무소귀속 23:15      빌라 지오코딩 23:30
#   백업(전 DB .backup) 07:30
# ⚠ 처음엔 새벽 01~03시를 안전하다고 뒀는데 그게 daily_run 한복판이었다
#   (실측: 매일 00:30 시작 → 05:00~05:13 종료). 그대로 뒀으면 수집 중에 VACUUM 이 걸렸다.
# 실제로 비는 창은 오전 09~10시와 오후 16~17시뿐이다.
SAFE_HOURS = (9, 10, 16, 17)
_SELF_LOCK = "/opt/koczip/data/vacuum_nonresi.lock"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def path_of(cat):
    return f"{DATA}/listings_{cat}.sqlite"


# ── 가드 ─────────────────────────────────────────────────────────────────────
def guard_single_instance():
    """자기 중복 실행 금지. 두 개가 같은 DB 를 잡으면 하나는 몇 분씩 멈춰 선다."""
    f = open(_SELF_LOCK, "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("✗ 이미 다른 회수 작업이 돌고 있다 — 중단")
        sys.exit(0)
    return f            # 프로세스가 살아 있는 동안 잡고 있어야 한다


def guard_busy_processes():
    """수집·집계가 도는 중이면 하지 않는다. VACUUM 이 그들을 몇 분 세운다."""
    pats = ("run_collect", "collect_region_listings", "collect_listings.sh",
            "nonresi_daily_agg", "archive_nonresi_listings", "build_realtor_dong",
            "match_region_realtors", "realtor_integrity_check", "daily_run")
    me = os.getpid()
    hits = []
    for pat in pats:
        try:
            out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True).stdout
        except Exception:  # noqa: BLE001
            continue
        for pid in out.split():
            # ★ 자기 자신과 자기 부모를 뺀다. 예전 판은 이걸 안 해서 스스로를 잡고
            #   '도는 중'이라 출력했다(그리고 멈추지도 않았다).
            if int(pid) in (me, os.getppid()):
                continue
            try:
                cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace")
            except OSError:
                continue
            if "vacuum_nonresi" in cmd:
                continue
            hits.append(f"{pid} {cmd.replace(chr(0), ' ')[:60]}")
    return hits


def guard_open_by_others(path):
    """이 파일을 연 프로세스 중 API 가 아닌 것이 있으면 위험하다."""
    try:
        out = subprocess.run(["fuser", path], capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001
        return []
    others = []
    for pid in out.split():
        pid = pid.strip().rstrip("cwrtme")
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace")
        except OSError:
            continue
        if "uvicorn" in cmd or "local_api" in cmd:
            continue        # API 는 읽기라 VACUUM 이 알아서 기다리게 한다
        others.append(f"{pid} {cmd.replace(chr(0), ' ')[:50]}")
    return others


def guard_wal(path):
    """WAL 에 안 합쳐진 내용이 있으면 먼저 합친다. 못 합치면 손대지 않는다."""
    wal = path + "-wal"
    if not os.path.exists(wal) or os.path.getsize(wal) == 0:
        return True
    c = sqlite3.connect(path, timeout=30)
    r = c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    c.close()
    left = os.path.getsize(wal) if os.path.exists(wal) else 0
    if r and r[0] == 0 and left == 0:
        return True
    log(f"  ✗ WAL 을 못 비웠다 (busy={r[0] if r else '?'}, 남은 {left}B) — 건너뛴다")
    return False


def free_gb(p=DATA):
    return shutil.disk_usage(p).free / 1073741824


# ── 지문 ─────────────────────────────────────────────────────────────────────
def fingerprint(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    fp = {"rows": c.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
          "by_date": dict(c.execute("SELECT snapshot_date, COUNT(*) FROM listings "
                                    "GROUP BY 1 ORDER BY 1").fetchall()),
          "sums": c.execute("SELECT COALESCE(SUM(deal_or_warrant_price),0),"
                            "COALESCE(SUM(rent_price),0),COALESCE(SUM(area2_m2),0) "
                            "FROM listings").fetchone()}
    h = hashlib.blake2b(digest_size=16)
    for r in c.execute("SELECT article_no,trade_type,deal_or_warrant_price,rent_price,"
                       "area2_m2,cortar_no,article_feature_desc,same_addr_min_price,"
                       "cp_name,snapshot_date FROM listings ORDER BY article_no"):
        h.update(("|".join("" if x is None else str(x) for x in r) + "\n").encode())
    fp["hash"] = h.hexdigest()
    for t in ("dong_daily", "region_daily", "collection_log"):
        try:
            fp[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            fp[t] = None
    c.close()
    return fp


def gain_pct(path):
    """회수 여지 — 빈 페이지 비율. 작으면 돌릴 이유가 없다."""
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    pc = c.execute("PRAGMA page_count").fetchone()[0]
    fl = c.execute("PRAGMA freelist_count").fetchone()[0]
    c.close()
    return (fl / pc * 100) if pc else 0.0


# ── 본체 ─────────────────────────────────────────────────────────────────────
def vacuum_one(cat, dry=False):
    path = path_of(cat)
    if not os.path.exists(path):
        return None
    before = os.path.getsize(path)
    g = gain_pct(path)
    log(f"[{cat}] {before/1048576:,.0f} MB · 빈 페이지 {g:.1f}%")
    if g < MIN_GAIN_PCT:
        log(f"  건너뜀 — 회수 여지 {MIN_GAIN_PCT}% 미만")
        return None

    others = guard_open_by_others(path)
    if others:
        log(f"  ✗ 다른 프로세스가 이 파일을 열고 있다 {others} — 건너뛴다")
        return None
    if not guard_wal(path):
        return None
    need = before / 1073741824 * 1.1
    if free_gb() < max(MIN_FREE_GB, need):
        log(f"  ✗ 여유 {free_gb():.1f} GB — 임시공간 {need:.1f} GB 가 필요하다. 건너뛴다")
        return None
    if dry:
        log("  (검사만 — 실행 안 함)")
        return None

    fp0 = fingerprint(path)
    t = time.time()
    c = sqlite3.connect(path, timeout=120)
    # 임시파일은 같은 디스크(빠름). 콜드에 두면 50MB/s 로 몇 배 오래 잠긴다.
    c.execute(f"PRAGMA temp_store_directory='{DATA}'")
    c.execute("VACUUM")
    ic = c.execute("PRAGMA integrity_check").fetchone()[0]
    c.close()
    after = os.path.getsize(path)
    fp1 = fingerprint(path)
    same = (fp1 == fp0)
    log(f"  VACUUM {time.time()-t:.0f}초 → {after/1048576:,.0f} MB "
        f"({(1-after/before)*100:.0f}% 감소) · integrity={ic} · 지문일치={same}")
    if ic != "ok" or not same:
        diff = [k for k in fp0 if fp0[k] != fp1.get(k)]
        log(f"  ★★ 어긋남 {diff} — 백업(/mnt/backup)에서 복구가 필요할 수 있다. 즉시 중단")
        sys.exit(2)
    return {"cat": cat, "before": before, "after": after}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    force = "--force" in sys.argv
    lock = guard_single_instance()       # noqa: F841  (프로세스 수명 동안 유지)

    hour = int(time.strftime("%H"))
    if not force and hour not in SAFE_HOURS:
        log(f"✗ 지금은 {hour}시 — 안전한 시간대가 아니다(허용 {SAFE_HOURS}시). "
            f"배치가 돌면 VACUUM 이 그것들을 몇 분 세운다. 정말 하려면 --force")
        return 0
    busy = guard_busy_processes()
    if busy:
        log(f"✗ 도는 작업이 있다 — 중단\n   " + "\n   ".join(busy))
        return 0
    if free_gb() < MIN_FREE_GB:
        log(f"✗ 여유 {free_gb():.1f} GB — {MIN_FREE_GB} GB 미만이라 시작하지 않는다")
        return 0

    log(f"시작 · 여유 {free_gb():.1f} GB")
    done = []
    for cat in (args or CATS):
        # ★ 매번 다시 본다. 처음 통과했어도 그사이 배치가 시작될 수 있다.
        busy = guard_busy_processes()
        if busy:
            log(f"✗ 작업이 시작됐다 — 여기서 멈춘다\n   " + "\n   ".join(busy))
            break
        r = vacuum_one(cat, dry=dry)
        if r:
            done.append(r)
    saved = sum(r["before"] - r["after"] for r in done)
    log(f"끝 · {len(done)}개 · 회수 {saved/1048576:,.0f} MB · 여유 {free_gb():.1f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── 참고: naverreal.sqlite 에서 지운 인덱스 ──────────────────────────────────
# article_events_date_idx (414 MB) — 2026-08-10 삭제.
# API·배치의 article_events 쿼리 9개를 전부 EXPLAIN 해 어느 것도 쓰지 않음을 확인했다.
# (event_type, event_date) 인덱스가 날짜 조건까지 커버하기 때문이다.
# 되돌리려면: data/DROPPED_INDEX_RESTORE.sql 을 실행한다(재생성 수 분).
