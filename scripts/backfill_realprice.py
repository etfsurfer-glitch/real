"""실거래가 백필: 시군구 × 월 단위로 fetch + 매칭 + transactions 저장.

Examples:
    # 서초구 1개월
    python scripts/backfill_realprice.py --lawd 11650 --month 202604

    # 서울 전체 (시군구 25개) × 최근 12개월
    python scripts/backfill_realprice.py --sido 11 --months 12

    # 전국 × 36개월 (Phase B 본 백필)
    python scripts/backfill_realprice.py --all --months 36

Daily 한도 10,000 calls. 가장 큰 작업도 9,180 calls 정도라 1일치 한도 내 끝.
"""
from __future__ import annotations

import argparse
import sqlite3
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

from collector.config import settings  # noqa: E402
from collector.realprice import api as rp_api  # noqa: E402
from collector.realprice import matching as rp_match  # noqa: E402
from collector.realprice import storage as rp_storage  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lawd", help="시군구 5자리 코드 (예: 11650 서초구)")
    g.add_argument("--sido", help="시도 2자리 코드 (예: 11 서울). 산하 시군구 전체.")
    g.add_argument("--all", action="store_true", help="전국 시군구")
    p.add_argument("--month", help="단일 월 (YYYYMM). 지정 시 --months 무시")
    p.add_argument("--months", type=int, default=1,
                   help="과거 N개월 (현재 월 포함 backward)")
    p.add_argument("--dry-run", action="store_true",
                   help="API 호출만, DB 저장 X")
    p.add_argument("--concurrency", type=int, default=4,
                   help="(시군구,월) 작업 동시 실행 수. 기본 4")
    return p.parse_args()


def resolve_sggs(conn, args) -> list[tuple[str, str]]:
    """Return [(lawd_cd 5자리, label)]."""
    if args.lawd:
        cur = conn.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_no LIKE ? AND cortar_type='dvsn' LIMIT 1",
            (args.lawd + "%",),
        )
        row = cur.fetchone()
        label = row[1] if row else args.lawd
        return [(args.lawd, label)]
    if args.sido:
        cur = conn.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_no LIKE ? AND cortar_type='dvsn' ORDER BY cortar_no",
            (args.sido + "%",),
        )
        return [(r[0][:5], r[1]) for r in cur.fetchall()]
    # --all
    cur = conn.execute(
        "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn' ORDER BY cortar_no"
    )
    return [(r[0][:5], r[1]) for r in cur.fetchall()]


def resolve_months(args) -> list[str]:
    if args.month:
        return [args.month]
    today = date.today()
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(args.months):
        months.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return months


def _process_task(lawd_cd: str, ymd: str, index: rp_match.ComplexIndex,
                  conn: sqlite3.Connection, dry_run: bool
                  ) -> dict:
    """Single (시군구, month) unit: fetch + match + upsert. Thread-safe via
    storage._LOCK for the DB write."""
    result = {"items": 0, "matched": 0, "unmatched": 0, "api_err": None}
    try:
        items = list(rp_api.fetch_all(lawd_cd, ymd))
    except rp_api.APIError as e:
        result["api_err"] = str(e)
        return result
    if not items:
        return result

    match_results = {}
    for tx in items:
        deal_id = rp_storage.make_deal_id(tx)
        trace = rp_match.match_one_with_trace(tx, index, keep_top=3)
        match_results[deal_id] = trace
        if trace["chosen"]:
            result["matched"] += 1
        else:
            result["unmatched"] += 1
    result["items"] = len(items)

    if not dry_run:
        rp_storage.upsert_transactions(conn, items, match_results)
    return result


def main() -> int:
    args = parse_args()
    t_start = time.time()
    # Allow cross-thread connection use; storage uses its own lock to serialize writes.
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA journal_size_limit=1073741824")  # WAL 상한 1GB(체크포인트 후 자동 축소)
    conn.execute("PRAGMA synchronous=NORMAL")
    rp_storage.init_schema(conn)

    sggs = resolve_sggs(conn, args)
    months = resolve_months(args)
    total_tasks = len(sggs) * len(months)
    print(f"[*] {len(sggs)} 시군구 × {len(months)} months = {total_tasks} tasks  "
          f"concurrency={args.concurrency}")
    if args.dry_run:
        print("[*] dry-run mode (no DB writes)")

    # Pre-build per-시군구 indexes (shared across worker threads)
    print(f"[1] building indexes for {len(sggs)} 시군구 ...")
    indexes: dict[str, rp_match.ComplexIndex] = {}
    for lawd_cd, _ in sggs:
        if lawd_cd not in indexes:
            complexes = rp_match.load_complexes(conn, cortar_prefix=lawd_cd)
            indexes[lawd_cd] = rp_match.ComplexIndex(complexes)
    print(f"    {len(indexes)} indexes built ({time.time()-t_start:.1f}s)")

    print(f"\n[2] running tasks ...")
    grand = {"items": 0, "matched": 0, "unmatched": 0,
             "api_calls": 0, "api_errs": 0}
    plock = threading.Lock()
    done = 0
    tasks = [(lawd_cd, label, ymd) for (lawd_cd, label) in sggs for ymd in months]

    def worker(lawd_cd, label, ymd):
        return label, lawd_cd, ymd, _process_task(lawd_cd, ymd, indexes[lawd_cd],
                                                    conn, args.dry_run)

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = [exe.submit(worker, *t) for t in tasks]
        for fut in as_completed(futs):
            label, lawd_cd, ymd, r = fut.result()
            with plock:
                done += 1
                grand["api_calls"] += 1
                if r["api_err"]:
                    grand["api_errs"] += 1
                grand["items"] += r["items"]
                grand["matched"] += r["matched"]
                grand["unmatched"] += r["unmatched"]
                if done % 50 == 0 or r["api_err"] or done == total_tasks:
                    elapsed = time.time() - t_start
                    rate = done / max(elapsed, 0.001)
                    line = (f"  [{done}/{total_tasks}] {label}({lawd_cd}) {ymd}: "
                            f"items={r['items']} matched={r['matched']} "
                            f"unmatched={r['unmatched']}")
                    if r["api_err"]:
                        line += f"  API_ERR: {r['api_err'][:60]}"
                    line += f"  ({rate:.1f} tasks/s)"
                    print(line)

    elapsed = time.time() - t_start
    print(f"\n[done] {elapsed:.0f}s")
    print(f"  api_calls: {grand['api_calls']:,}  api_errs: {grand['api_errs']}")
    print(f"  items:     {grand['items']:,}")
    print(f"  matched:   {grand['matched']:,}  ({grand['matched']*100/grand['items']:.1f}%)" if grand["items"] else "")
    print(f"  unmatched: {grand['unmatched']:,}")

    if not args.dry_run:
        s = rp_storage.stats(conn)
        print(f"\n[stats] transactions table:")
        print(f"  total rows: {s['total']:,}")
        print(f"  date range: {s['date_range'][0]} ~ {s['date_range'][1]}")
        for method, n in s["by_method"]:
            print(f"  {(method or 'unmatched'):<22} {n:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
