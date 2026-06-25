"""Daily Naver real-estate snapshot collector — generalized.

Examples:
    # 특정 동만
    python scripts/run_collect.py --cortar 1165010800

    # 시군구 전체 (서초구)
    python scripts/run_collect.py --ancestor 1165000000

    # 시도 전체 (서울)
    python scripts/run_collect.py --ancestor 1100000000

    # 전국 (default: Phase 1 cached up to 14 days)
    python scripts/run_collect.py --all

    # 전국 — force a fresh Phase 1 (use weekly)
    python scripts/run_collect.py --all --listing-max-age 0

Phase 1 (Naver region→complex listing) is skipped automatically when the
cached complex list is younger than --listing-max-age days (default 14).
Single-Naver-API-call-per-dong adds up to ~55 min for nationwide, so
skipping it on regular daily runs is the default; the listing self-
refreshes every ~14 days inside an otherwise normal daily run.

Resumable: re-running on the same day skips (complex, trade) pairs already
logged as successful. Use --reset-today to force re-collection.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import regions, storage  # noqa: E402
from collector.config import settings  # noqa: E402
from collector.creds import ensure_creds  # noqa: E402
from collector.naver import (  # noqa: E402
    TRADE_TYPES,
    articles_for_complex,
    complexes_in_region,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--cortar", nargs="+", help="specific leaf 동 cortarNo(s)")
    g.add_argument("--ancestor", help="all 동 under this cortarNo (시도 or 시군구)")
    g.add_argument("--all", action="store_true", help="all 동 in saved region tree")
    p.add_argument("--limit", type=int, default=0, help="cap 동 count (debug)")
    p.add_argument("--shuffle", action="store_true", help="randomize 동 order")
    p.add_argument("--reset-today", action="store_true",
                   help="ignore today's collection_log and re-collect everything")
    p.add_argument("--listing-max-age", type=int, default=14,
                   help="skip Phase 1 if cached complex listing is younger than N days "
                        "(default 14; 0 forces refresh)")
    p.add_argument("--keep-log-days", type=int, default=7,
                   help="retain success rows in collection_log for N days "
                        "(errors kept indefinitely; default 7)")
    return p.parse_args()


def resolve_dongs(conn, args) -> list[str]:
    if args.cortar:
        return list(args.cortar)
    if args.ancestor:
        return regions.dong_cortar_nos_under(conn, args.ancestor)
    return regions.dong_cortar_nos(conn)


def _should_refresh_listing(conn, max_age_days: int) -> tuple[bool, str]:
    """Decide whether to run Phase 1 (Naver listing) vs use cached complexes."""
    if max_age_days <= 0:
        return True, "max_age=0 forces refresh"
    cur = conn.execute("SELECT MAX(last_seen_date) FROM complexes")
    row = cur.fetchone()
    if not row or not row[0]:
        return True, "no cached complexes in DB"
    from datetime import date as _date, datetime as _dt
    try:
        last = _dt.strptime(row[0], "%Y-%m-%d").date()
    except ValueError:
        return True, f"cannot parse last_seen_date={row[0]!r}"
    age = (_date.today() - last).days
    if age > max_age_days:
        return True, f"cache age {age}d > max_age {max_age_days}d"
    return False, f"cache age {age}d ≤ {max_age_days}d"


def _cached_complex_nos(conn, dongs: list[str]) -> list[str]:
    """Load complex_no list for the given dongs from the local complexes table."""
    if not dongs:
        return []
    BATCH = 500  # below SQLite SQLITE_MAX_VARIABLE_NUMBER on any modern build
    out: list[str] = []
    for i in range(0, len(dongs), BATCH):
        chunk = dongs[i:i + BATCH]
        ph = ",".join("?" * len(chunk))
        cur = conn.execute(
            f"SELECT complex_no FROM complexes WHERE cortar_no IN ({ph})",
            chunk,
        )
        out.extend(r[0] for r in cur.fetchall())
    return out


# ── 단일 실행 잠금 (수동/예약 수집 동시 실행 충돌 방지) ──────────────────────
# OS 배타적 파일락 — 프로세스가 죽으면(크래시/강제종료 포함) 락이 자동 해제돼
# stale lock 문제가 없다. 이미 수집이 돌고 있으면 두 번째 인스턴스는 즉시 종료.
_LOCK_PATH = Path(settings.local_db_path).resolve().parent / "run_collect.lock"
_lock_handle = None  # 프로세스 수명 동안 유지(GC 방지) — 락 유지용


def _acquire_singleton_lock() -> bool:
    """이미 수집이 실행 중이면 False, 락 획득에 성공하면 True."""
    global _lock_handle
    f = None
    try:
        f = open(_LOCK_PATH, "a+")
        if sys.platform.startswith("win"):
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if f is not None:
            try: f.close()
            except Exception: pass
        return False
    try:
        f.seek(0)
        f.write(f"{os.getpid()}\n")
        f.flush()
    except Exception:
        pass
    _lock_handle = f  # 닫지 않고 보관 → 프로세스 끝날 때까지 락 유지
    return True


# ── 완결성 게이트 (부분 수집이 '완전한 하루'로 집계/발행되는 것을 방지) ──────
COMPLETENESS_THRESHOLD = 0.97   # 이번 run 성공 task 비율 하한
COVERAGE_THRESHOLD = 0.90       # task 수가 직전 최다수집일 대비 이 비율 미만이면 불완전(Phase1 누락)


def _recent_task_baseline(conn: sqlite3.Connection, run_date: str) -> int:
    """직전 날짜들 중 '가장 많이 수집된 날'의 성공 task 수 — 정상 수집 규모 기준선."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM collection_log "
        "WHERE status='success' AND run_date < ? GROUP BY run_date ORDER BY n DESC LIMIT 1",
        (run_date,),
    ).fetchone()
    return row[0] if row else 0


RESUME_MAX_AGE_DAYS = 2   # 미완 수집을 며칠 전까지 이어받을지 상한


def _pick_run_date(conn: sqlite3.Connection) -> str:
    """수집 대상 snapshot_date 결정.

    자정을 넘겨 재시작하면 date.today() 기준으론 '새 날짜'로 새 스냅샷을 시작해
    직전(크래시된) 날의 부분 데이터가 고아가 된다. 그래서 가장 최근 run 이
    '명백히 미완'(성공 task 가 정상 규모의 COVERAGE_THRESHOLD 미만)이고 최근
    RESUME_MAX_AGE_DAYS 일 이내면 그 날짜를 이어받아 같은 스냅샷으로 완주한다.
    """
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT run_date, COUNT(*) AS n FROM collection_log WHERE status='success' "
        "GROUP BY run_date ORDER BY run_date DESC LIMIT 1"
    ).fetchone()
    if not row:
        return today
    last_date, last_n = row[0], row[1]
    if last_date >= today:
        return today  # 오늘 것 이미 진행/완료 중
    baseline = conn.execute(
        "SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM collection_log "
        "WHERE status='success' GROUP BY run_date)"
    ).fetchone()[0] or 0
    from datetime import date as _date
    gap = (_date.fromisoformat(today) - _date.fromisoformat(last_date)).days
    if baseline and last_n < baseline * COVERAGE_THRESHOLD and gap <= RESUME_MAX_AGE_DAYS:
        print(f"[resume] 직전 미완 수집 {last_date} (성공 {last_n:,}/{baseline:,}) 이어받기 "
              f"— 새 스냅샷 대신 같은 날로 완주")
        return last_date
    return today


def main() -> int:
    args = parse_args()
    if not _acquire_singleton_lock():
        print(f"[lock] 이미 다른 수집이 실행 중입니다 ({_LOCK_PATH}) — 이 인스턴스는 종료합니다.")
        return 3
    t_start = time.time()

    conn = storage.open_db(settings.local_db_path)
    storage.init_schema(conn)
    # snapshot_date 결정 — reset-today 면 무조건 오늘, 아니면 직전 미완 수집 이어받기.
    run_date = date.today().isoformat() if args.reset_today else _pick_run_date(conn)
    creds = ensure_creds()

    dongs = resolve_dongs(conn, args)
    if args.shuffle:
        random.shuffle(dongs)
    if args.limit:
        dongs = dongs[: args.limit]

    refresh_listing, refresh_reason = _should_refresh_listing(conn, args.listing_max_age)
    _ips = [s.strip() for s in settings.naver_source_ips.split(",") if s.strip()]
    print(f"[*] run_date={run_date}  dongs={len(dongs)}  "
          f"concurrency={settings.naver_concurrency}×{max(1,len(_ips))}IP={settings.naver_concurrency*max(1,len(_ips))}  "
          f"jitter≤{settings.naver_delay_ms}ms  src_ips={_ips or 'default'}")
    print(f"[*] Phase 1: {'REFRESH' if refresh_listing else 'SKIP (use cache)'} ({refresh_reason})")
    if not dongs:
        print("[!] no dongs to process — did you run build_region_tree.py?")
        return 1

    all_tasks: list[tuple[str, str]] = []
    list_errors = 0

    if refresh_listing:
        # Phase 1 — list complexes per dong via Naver API (sequential, ~1 req/dong)
        print("\n[1/3] complex listing per dong (Naver API)")
        for i, dno in enumerate(dongs, 1):
            try:
                cps = complexes_in_region(dno, creds)
            except Exception as e:  # noqa: BLE001
                print(f"  [{i}/{len(dongs)}] {dno} LIST_ERR: {str(e)[:80]}")
                list_errors += 1
                continue
            for c in cps:
                storage.upsert_complex(conn, c)
                for trade in TRADE_TYPES:
                    all_tasks.append((str(c["complexNo"]), trade))
            if i % 100 == 0 or i == len(dongs):
                elapsed = time.time() - t_start
                print(f"  [{i}/{len(dongs)}] tasks={len(all_tasks)}  "
                      f"list_err={list_errors}  ({elapsed:.0f}s)")
    else:
        # Phase 1 skipped — load cached complex list from local DB
        print("\n[1/3] complex listing — using cached complexes from DB")
        cnos = _cached_complex_nos(conn, dongs)
        all_tasks = [(cno, t) for cno in cnos for t in TRADE_TYPES]
        elapsed = time.time() - t_start
        print(f"  cached complexes: {len(cnos)}  tasks={len(all_tasks)}  ({elapsed:.1f}s)")

    # Resume support
    if args.reset_today:
        done: set[tuple[str, str]] = set()
        print("  [reset-today] ignoring previous completion log")
    else:
        done = storage.get_completed_for_run(conn, run_date)
    remaining = [t for t in all_tasks if t not in done]
    print(f"\n[2/3] articles  total_tasks={len(all_tasks)}  "
          f"already_done={len(done)}  remaining={len(remaining)}")

    if not remaining:
        print("  nothing to do")
    else:
        prog = {"n": 0, "items": 0, "errs": 0}
        plock = threading.Lock()

        # 멀티 IP 병렬: NAVER_SOURCE_IPS 에 소스 IP 들을 주면 task 를 IP 에 round-robin
        # 분산하고 각 요청을 그 IP 로 바인딩(interface=). IP당 naver_concurrency 워커.
        # 데이터 정확성은 그대로 — 같은 단지는 어느 IP로 받아도 동일 응답, 쓰기는
        # storage._LOCK 으로 직렬화. 비어있으면 단일(interface=None, 기존 동작).
        src_ips = [s.strip() for s in settings.naver_source_ips.split(",") if s.strip()]
        n_ip = max(1, len(src_ips))

        def worker(cno: str, trade: str, ip: str | None) -> tuple[str, str, int, str | None]:
            try:
                items = list(articles_for_complex(cno, trade, creds, interface=ip))
                storage.save_articles(conn, cno, trade, items, run_date)
                storage.log_completion(conn, run_date, cno, trade, len(items), "success", None)
                return cno, trade, len(items), None
            except Exception as e:  # noqa: BLE001
                storage.log_completion(conn, run_date, cno, trade, 0, "error", str(e)[:300])
                return cno, trade, 0, f"{type(e).__name__}: {str(e)[:80]}"

        with ThreadPoolExecutor(max_workers=settings.naver_concurrency * n_ip) as exe:
            futs = [
                exe.submit(worker, c, t, (src_ips[i % n_ip] if src_ips else None))
                for i, (c, t) in enumerate(remaining)
            ]
            for fut in as_completed(futs):
                cno, trade, n, err = fut.result()
                with plock:
                    prog["n"] += 1
                    if err:
                        prog["errs"] += 1
                    else:
                        prog["items"] += n
                    n_done = prog["n"]
                    if n_done % 200 == 0 or err or n_done == len(remaining):
                        elapsed = time.time() - t_start
                        rate = n_done / max(elapsed, 0.001)
                        line = f"  [{n_done}/{len(remaining)}] {cno}/{trade}"
                        if err:
                            line += f" ERR {err[:60]}"
                        else:
                            line += f" +{n}"
                        line += f"  ({rate:.1f}/s  items={prog['items']}  errs={prog['errs']})"
                        print(line)

    # ── 완결성 게이트 ──────────────────────────────────────────────
    # 부분 수집분이 집계(complex/region_daily_agg)로 새어나가면 홈페이지가 '가짜
    # 폭락'을 표시한다. 성공 task 비율과 수집 규모가 충분할 때만 Phase 3 진행.
    # 불완전이면 직전 완전 스냅샷을 그대로 두고 exit 2 (daily_run.ps1 이 업로드/
    # 아카이브를 건너뛰는 신호). 같은 날 재실행하면 resume 으로 이어서 완성.
    n_success = len(storage.get_completed_for_run(conn, run_date))
    n_expected = len(all_tasks)
    ratio = n_success / n_expected if n_expected else 0.0
    baseline = _recent_task_baseline(conn, run_date)
    coverage = (n_expected / baseline) if baseline else 1.0
    complete = (n_expected > 0 and ratio >= COMPLETENESS_THRESHOLD
                and coverage >= COVERAGE_THRESHOLD)
    print(f"\n[gate] 성공 {n_success}/{n_expected} = {ratio:.1%}  "
          f"규모 {n_expected} vs 기준 {baseline} = {coverage:.0%}  list_err={list_errors}")
    if not complete:
        reason = ("성공률 부족" if ratio < COMPLETENESS_THRESHOLD
                  else "수집 규모 부족(Phase1 누락 의심)")
        print(f"[gate] 불완전({reason}) — 집계/삭제/발행을 건너뜁니다. "
              f"직전 완전 스냅샷 유지. 같은 날 재실행하면 이어서 수집합니다.")
        elapsed = time.time() - t_start
        print(f"[done-incomplete] {elapsed:.0f}s  success={ratio:.1%}")
        return 2

    # Phase 3 — DELISTED detection + aggregates + log trim (완전 수집일에만)
    print("\n[3/3] aggregates + deletions")
    n_delisted = storage.finalize_deletions(conn, run_date)
    print(f"  articles delisted today: {n_delisted}")
    n_complex = storage.compute_complex_daily_agg(conn, run_date)
    n_region = storage.compute_region_daily_agg(conn, run_date)
    print(f"  complex_daily_agg rows: {n_complex}")
    print(f"  region_daily_agg rows: {n_region}")
    n_trimmed = storage.trim_collection_log(conn, keep_success_days=args.keep_log_days)
    print(f"  collection_log trimmed: {n_trimmed} old success rows "
          f"(keep_success_days={args.keep_log_days}, errors retained)")

    elapsed = time.time() - t_start
    print(f"\n[done] {elapsed:.0f}s  list_err={list_errors}  "
          f"items={prog.get('items', 0) if remaining else 0}  "
          f"errs={prog.get('errs', 0) if remaining else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
