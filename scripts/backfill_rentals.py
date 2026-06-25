"""전월세 실거래가 백필: 시군구 × 월 단위로 fetch + 매칭 + rentals 저장.

거의 backfill_realprice.py(매매)와 동일하지만 endpoint와 storage가 다름.

Examples:
    python scripts/backfill_rentals.py --lawd 11650 --month 202604
    python scripts/backfill_rentals.py --sido 11 --months 12
    python scripts/backfill_rentals.py --all --months 6

Daily 한도 10,000 calls. 전국 1개월 ≈ 255 calls.
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
    g.add_argument("--lawd", help="시군구 5자리 코드")
    g.add_argument("--sido", help="시도 2자리 코드")
    g.add_argument("--all", action="store_true", help="전국 시군구")
    p.add_argument("--month", help="단일 월 (YYYYMM)")
    p.add_argument("--months", type=int, default=1,
                   help="과거 N개월 (현재 월 포함 backward)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--concurrency", type=int, default=4)
    return p.parse_args()


def resolve_sggs(conn, args) -> list[tuple[str, str]]:
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
                  conn: sqlite3.Connection, dry_run: bool) -> dict:
    result = {"items": 0, "matched": 0, "unmatched": 0, "api_err": None}
    try:
        items = list(rp_api.fetch_all(lawd_cd, ymd, endpoint=rp_api.ENDPOINT_RENT))
    except rp_api.APIError as e:
        result["api_err"] = str(e)
        return result
    if not items:
        return result

    match_results = {}
    for tx in items:
        rid = rp_storage.make_rental_id(tx)
        trace = rp_match.match_one_with_trace(tx, index, keep_top=3)
        match_results[rid] = trace
        if trace["chosen"]:
            result["matched"] += 1
        else:
            result["unmatched"] += 1
    result["items"] = len(items)

    if not dry_run:
        rp_storage.upsert_rentals(conn, items, match_results)
    return result


def main() -> int:
    args = parse_args()
    t_start = time.time()
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    rp_storage.init_schema(conn)

    sggs = resolve_sggs(conn, args)
    months = resolve_months(args)
    total_tasks = len(sggs) * len(months)
    print(f"[*] {len(sggs)} 시군구 × {len(months)} months = {total_tasks} tasks  "
          f"concurrency={args.concurrency}  (전월세)")
    if args.dry_run:
        print("[*] dry-run mode (no DB writes)")

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
    if grand["items"]:
        print(f"  matched:   {grand['matched']:,}  ({grand['matched']*100/grand['items']:.1f}%)")
    print(f"  unmatched: {grand['unmatched']:,}")

    if not args.dry_run:
        n_jeonse = conn.execute("SELECT COUNT(*) FROM rentals WHERE monthly_rent=0").fetchone()[0]
        n_wolse = conn.execute("SELECT COUNT(*) FROM rentals WHERE monthly_rent>0").fetchone()[0]
        dr = conn.execute("SELECT MIN(deal_ymd), MAX(deal_ymd) FROM rentals").fetchone()
        print(f"\n[stats] rentals table:")
        print(f"  jeonse(전세):  {n_jeonse:,}")
        print(f"  wolse (월세):  {n_wolse:,}")
        print(f"  date range:    {dr[0]} ~ {dr[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
