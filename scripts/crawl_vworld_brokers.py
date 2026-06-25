"""V-WORLD 부동산중개업 정보 크롤러.

두 단계:
  --list        시군구별 list 크롤 (등록번호/상호/주소/대표자/상태).
                기존 데이터는 UPSERT, list_fetched_at 갱신.
  --detail      list로 수집한 사무소 중 phone이 비어있는 항목의 detail 페이지
                fetch해서 전화번호 채움.

사용:
  python scripts/crawl_vworld_brokers.py --list           # 전국 모든 시군구
  python scripts/crawl_vworld_brokers.py --list --sido 11 # 서울만
  python scripts/crawl_vworld_brokers.py --detail --limit 500
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.vworld import (  # noqa: E402
    BrokerListItem,
    EmployeeRow,
    fetch_detail,
    fetch_employees_page,
    iter_employees_sigungu,
    iter_sigungu,
    new_session,
)


def open_db() -> sqlite3.Connection:
    # busy_timeout=30s: 동시에 daily_run이 쓰는 동안 락 잡힐 때 즉시 에러 대신 대기.
    # check_same_thread=False: --parallel 모드에서 워커 스레드가 같은 conn으로 upsert.
    #   대신 _db_lock 으로 직렬화.
    c = sqlite3.connect(
        settings.local_db_path, timeout=30.0, check_same_thread=False
    )
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout = 30000")
    return c


def list_sigungus(
    conn: sqlite3.Connection, sido_filter: str | None
) -> list[tuple[str, str, str]]:
    """Returns [(sido_cd, sigungu_cd, name)] from regions table."""
    q = "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn'"
    params: list = []
    if sido_filter:
        q += " AND substr(cortar_no,1,2)=?"
        params.append(sido_filter)
    q += " ORDER BY cortar_no"
    rows = conn.execute(q, params).fetchall()
    return [(c[:2], c[:5], n) for c, n in rows]


def upsert_list_item(conn: sqlite3.Connection, it: BrokerListItem, now: str) -> None:
    conn.execute(
        """
        INSERT INTO vworld_brokers
            (sys_regno, ra_regno, sgg_cd, business_name, address,
             representative, registered_ymd, status, list_fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sys_regno) DO UPDATE SET
            ra_regno=excluded.ra_regno,
            sgg_cd=excluded.sgg_cd,
            business_name=excluded.business_name,
            address=excluded.address,
            representative=excluded.representative,
            registered_ymd=excluded.registered_ymd,
            status=excluded.status,
            list_fetched_at=excluded.list_fetched_at
        """,
        (
            it.sys_regno, it.ra_regno, it.sgg_cd, it.business_name, it.address,
            it.representative, it.registered_ymd, it.status, now,
        ),
    )


_db_lock = threading.Lock()


def _crawl_one_sigungu(client, sido, sgg, args, conn, now) -> tuple[int, int]:
    """Returns (total, rows). Commits after each row so the writer doesn't
    hold the lock through HTTP waits. _db_lock 으로 스레드간 직렬화."""
    from collector.vworld import fetch_list_page
    rows = 0
    total = 0
    for it in iter_sigungu(
        client, sido, sgg,
        page_size=args.page_size,
        sleep_s=args.sleep,
        max_pages=args.max_pages,
    ):
        with _db_lock:
            upsert_list_item(conn, it, now)
            conn.commit()
        rows += 1
    total, _ = fetch_list_page(client, sido, sgg, 1, args.page_size)
    return total, rows


def crawl_list(args: argparse.Namespace) -> int:
    conn = open_db()
    sgs = list_sigungus(conn, args.sido)
    print(f"[*] sigungus to crawl: {len(sgs)}  parallel={args.parallel}", flush=True)
    grand_total = 0
    started = time.time()

    pending: list[tuple[int, str, str, str]] = []
    for i, (sido, sgg, name) in enumerate(sgs, 1):
        if args.skip_done:
            row = conn.execute(
                "SELECT total_count, rows_seen FROM vworld_crawl_log WHERE sgg_cd=?",
                (sgg,),
            ).fetchone()
            if row and row[0] and row[1] and row[1] >= row[0]:
                print(f"  [{i}/{len(sgs)}] {sgg} {name}  SKIP (done {row[1]}/{row[0]})", flush=True)
                continue
        pending.append((i, sido, sgg, name))

    def _work(item) -> tuple[int, str, str, int, int, float, str | None]:
        i, sido, sgg, name = item
        client = new_session()
        t0 = time.time()
        now = datetime.now().isoformat(timespec="seconds")
        rows = 0
        total = 0
        err = None
        try:
            total, rows = _crawl_one_sigungu(client, sido, sgg, args, conn, now)
            if rows == 0 and total == 0:
                client = new_session()
                total, rows = _crawl_one_sigungu(client, sido, sgg, args, conn, now)
        except Exception as e:
            err = str(e)[:200]
        return i, sgg, name, total, rows, time.time() - t0, err

    if args.parallel <= 1:
        for item in pending:
            i, sgg, name, total, rows, elapsed, err = _work(item)
            with _db_lock:
                _write_log_row(conn, sgg, total, rows, err)
                conn.commit()
            grand_total += rows
            tag = f"ERROR: {err}" if err else f"rows={rows}/{total}"
            print(f"  [{i}/{len(sgs)}] {sgg} {name}  {tag}  ({elapsed:.1f}s)  total_so_far={grand_total}", flush=True)
        print(f"\n[*] list crawl done. {grand_total} rows in {time.time()-started:.0f}s", flush=True)
        return 0

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = {pool.submit(_work, item): item for item in pending}
        for fut in as_completed(futs):
            i, sgg, name, total, rows, elapsed, err = fut.result()
            with _db_lock:
                _write_log_row(conn, sgg, total, rows, err)
                conn.commit()
            grand_total += rows
            tag = f"ERROR: {err}" if err else f"rows={rows}/{total}"
            print(f"  [{i}/{len(sgs)}] {sgg} {name}  {tag}  ({elapsed:.1f}s)  total_so_far={grand_total}", flush=True)
    print(f"\n[*] list crawl done. {grand_total} rows in {time.time()-started:.0f}s", flush=True)
    return 0


def _write_log_row(conn, sgg, total, rows, err) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    note = f"err: {err}" if err else None
    conn.execute(
        """
        INSERT INTO vworld_crawl_log(sgg_cd, last_listed_at, total_count, rows_seen, note)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(sgg_cd) DO UPDATE SET
            last_listed_at=excluded.last_listed_at,
            total_count=excluded.total_count,
            rows_seen=excluded.rows_seen,
            note=excluded.note
        """,
        (sgg, now, total or 0, rows, note),
    )


def crawl_detail(args: argparse.Namespace) -> int:
    conn = open_db()
    where = "phone IS NULL"
    if args.status_filter:
        where += " AND status = ?"
        params: list = [args.status_filter]
    else:
        params = []
    q = f"SELECT sgg_cd, ra_regno, sys_regno FROM vworld_brokers WHERE {where}"
    if args.limit:
        q += f" LIMIT {int(args.limit)}"
    rows = conn.execute(q, params).fetchall()
    print(f"[*] details to fetch: {len(rows)}  parallel={args.parallel}", flush=True)
    started = time.time()
    ok = 0
    fail = 0
    counter = {"i": 0}
    counter_lock = threading.Lock()
    # 각 워커가 자체 세션을 갖되, vworld는 같은 IP에서 동시 많은 요청 시 disconnect.
    # 따라서 parallel은 작게 (3) 유지 권장.
    sessions: list = [new_session() for _ in range(max(1, args.parallel))]

    def _do_one(idx_session: tuple[int, tuple]) -> tuple[bool, str | None]:
        ses_i, (sgg, ra, sys_regno) = idx_session
        client = sessions[ses_i % len(sessions)]
        try:
            d = fetch_detail(client, sgg, ra, sys_regno)
            with _db_lock:
                conn.execute(
                    """
                    UPDATE vworld_brokers
                    SET phone=?, classification=?, detail_fetched_at=?
                    WHERE sys_regno=?
                    """,
                    (d.phone, d.classification, datetime.now().isoformat(timespec="seconds"), sys_regno),
                )
                conn.commit()
            return True, None
        except Exception as e:
            return False, f"{sys_regno}: {str(e)[:100]}"

    def _worker(i_row):
        i, row = i_row
        ses_i = i % len(sessions)
        ok_b, err = _do_one((ses_i, row))
        with counter_lock:
            counter["i"] += 1
            cur = counter["i"]
        return ok_b, err, cur

    if args.parallel <= 1:
        for i, row in enumerate(rows, 1):
            ok_b, err = _do_one((0, row))
            if ok_b:
                ok += 1
            else:
                fail += 1
                if fail <= 5 and err:
                    print(f"  fail {err}", flush=True)
            if i % 100 == 0:
                elapsed = time.time() - started
                rate = i / max(elapsed, 0.001)
                eta = (len(rows) - i) / max(rate, 0.001)
                print(
                    f"  [{i}/{len(rows)}]  ok={ok} fail={fail}  "
                    f"{rate:.1f}/s  ETA {eta/60:.1f}m",
                    flush=True,
                )
            time.sleep(args.sleep)
    else:
        # 병렬 모드: parallel-row 큐.
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futs = []
            for i, row in enumerate(rows, 1):
                futs.append(pool.submit(_worker, (i, row)))
            for fut in as_completed(futs):
                ok_b, err, cur = fut.result()
                if ok_b:
                    ok += 1
                else:
                    fail += 1
                    if fail <= 5 and err:
                        print(f"  fail {err}", flush=True)
                if cur % 200 == 0:
                    elapsed = time.time() - started
                    rate = cur / max(elapsed, 0.001)
                    eta = (len(rows) - cur) / max(rate, 0.001)
                    print(
                        f"  [{cur}/{len(rows)}]  ok={ok} fail={fail}  "
                        f"{rate:.1f}/s  ETA {eta/60:.1f}m",
                        flush=True,
                    )
    conn.commit()
    print(f"\n[*] detail crawl done. ok={ok} fail={fail} in {time.time()-started:.0f}s", flush=True)
    return 0


def upsert_employee(conn: sqlite3.Connection, it: EmployeeRow, now: str) -> None:
    conn.execute(
        """
        INSERT INTO vworld_employees
            (sys_regno, sgg_cd, ra_regno, business_name, employee_name,
             role, position, status, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sys_regno, employee_name, role, position) DO UPDATE SET
            business_name=excluded.business_name,
            status=excluded.status,
            fetched_at=excluded.fetched_at
        """,
        (it.sys_regno, it.sgg_cd, it.ra_regno, it.business_name,
         it.employee_name, it.role, it.position, it.status, now),
    )


def _crawl_employees_one_sigungu(client, sido, sgg, args, conn, now) -> tuple[int, int]:
    rows = 0
    total = 0
    for it in iter_employees_sigungu(
        client, sido, sgg,
        page_size=args.page_size,
        sleep_s=args.sleep,
        max_pages=args.max_pages,
    ):
        with _db_lock:
            upsert_employee(conn, it, now)
            conn.commit()
        rows += 1
    total, _ = fetch_employees_page(client, sido, sgg, 1, args.page_size)
    return total, rows


def crawl_employees(args: argparse.Namespace) -> int:
    conn = open_db()
    sgs = list_sigungus(conn, args.sido)
    # skip-done: 이미 employees가 어느정도 수집된 sgg는 건너뜀
    done_sggs: set[str] = set()
    if args.skip_done:
        for r in conn.execute("SELECT sgg_cd, COUNT(*) FROM vworld_employees GROUP BY sgg_cd HAVING COUNT(*) > 0"):
            done_sggs.add(r[0])
    pending_sgs = [(i, sido, sgg, name) for i, (sido, sgg, name) in enumerate(sgs, 1) if sgg not in done_sggs]
    skipped = len(sgs) - len(pending_sgs)
    print(f"[*] sigungus to crawl (employees): {len(pending_sgs)}/{len(sgs)}  skipped={skipped}  parallel={args.parallel}", flush=True)
    grand_total = 0
    started = time.time()

    def _work(item) -> tuple[int, str, str, int, int, float, str | None]:
        i, sido, sgg, name = item
        t0 = time.time()
        now = datetime.now().isoformat(timespec="seconds")
        rows = 0
        total = 0
        err = None
        # new_session()도 ConnectTimeout 던질 수 있어서 try 안에서 호출.
        try:
            client = new_session()
            total, rows = _crawl_employees_one_sigungu(client, sido, sgg, args, conn, now)
            if rows == 0 and total == 0:
                client = new_session()
                total, rows = _crawl_employees_one_sigungu(client, sido, sgg, args, conn, now)
        except Exception as e:
            err = str(e)[:200]
        return i, sgg, name, total, rows, time.time() - t0, err

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futs = {pool.submit(_work, item): item for item in pending_sgs}
        for fut in as_completed(futs):
            try:
                i, sgg, name, total, rows, elapsed, err = fut.result()
            except Exception as e:
                print(f"  worker crashed: {e}", flush=True)
                continue
            grand_total += rows
            tag = f"ERROR: {err}" if err else f"rows={rows}/{total}"
            print(f"  [{i}/{len(sgs)}] {sgg} {name}  {tag}  ({elapsed:.1f}s)  total_so_far={grand_total}", flush=True)
    print(f"\n[*] employees crawl done. {grand_total} rows in {time.time()-started:.0f}s", flush=True)
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true", help="시군구별 사무소 목록 크롤")
    p.add_argument("--detail", action="store_true", help="phone NULL인 사무소의 detail fetch")
    p.add_argument("--employees", action="store_true", help="시군구별 직원/공인중개사 목록 크롤")
    p.add_argument("--sido", help="시도코드 2자리 (예: 11=서울)")
    p.add_argument("--page-size", type=int, default=50, help="한 페이지당 행 수 (10/20/50)")
    p.add_argument("--max-pages", type=int, default=200)
    p.add_argument("--sleep", type=float, default=0.4, help="요청 간 sleep 초")
    p.add_argument("--limit", type=int, help="detail mode: max rows to process")
    p.add_argument("--status-filter", help="detail mode: 특정 status만 (예: 영업)")
    p.add_argument("--skip-done", action="store_true",
                   help="list mode: log상 완료된 시군구는 건너뜀")
    p.add_argument("--parallel", type=int, default=1,
                   help="list mode: 시군구 단위 병렬 워커 수 (각자 자체 세션). 권장 3")
    args = p.parse_args()
    if not (args.list or args.detail or args.employees):
        p.error("--list / --detail / --employees 중 하나 필요")
    if args.list:
        return crawl_list(args)
    if args.employees:
        return crawl_employees(args)
    return crawl_detail(args)


if __name__ == "__main__":
    sys.exit(main())
