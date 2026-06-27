"""연립다세대(빌라) 매매·전월세 실거래 백필. (RTMSDataSvcRHTrade / RHRent)

비단지 — 단지(complex) 매칭 안 함. 지번+건물명(mhouseNm)으로 rh_transactions / rh_rentals 저장.
시군구×월 단위로 매매·전월세를 동시에 받는다.

Examples:
    python scripts/backfill_villa.py --lawd 11680 --month 202505   # 강남구 5월
    python scripts/backfill_villa.py --all --months 12             # 전국 12개월
    python scripts/backfill_villa.py --all --months 1 --trade-only # 매매만
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
from collector.realprice import storage as rp_storage  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lawd", help="시군구 5자리 코드")
    g.add_argument("--sido", help="시도 2자리 코드")
    g.add_argument("--all", action="store_true", help="전국 시군구")
    p.add_argument("--month", help="단일 월 (YYYYMM)")
    p.add_argument("--months", type=int, default=1)
    p.add_argument("--trade-only", action="store_true", help="매매만")
    p.add_argument("--rent-only", action="store_true", help="전월세만")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--concurrency", type=int, default=4)
    return p.parse_args()


def resolve_sggs(conn, args):
    if args.lawd:
        row = conn.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_no LIKE ? "
            "AND cortar_type='dvsn' LIMIT 1", (args.lawd + "%",)).fetchone()
        return [(args.lawd, row[1] if row else args.lawd)]
    if args.sido:
        cur = conn.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_no LIKE ? "
            "AND cortar_type='dvsn' ORDER BY cortar_no", (args.sido + "%",))
        return [(r[0][:5], r[1]) for r in cur.fetchall()]
    cur = conn.execute(
        "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn' ORDER BY cortar_no")
    return [(r[0][:5], r[1]) for r in cur.fetchall()]


def resolve_months(args):
    if args.month:
        return [args.month]
    today = date.today()
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(args.months):
        months.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return months


def _process(lawd_cd: str, ymd: str, conn: sqlite3.Connection, args) -> dict:
    r = {"trade": 0, "rent": 0, "api_err": None}
    if not args.rent_only:
        try:
            items = list(rp_api.fetch_all(lawd_cd, ymd, endpoint=rp_api.ENDPOINT_RH_TRADE))
            if items and not args.dry_run:
                rp_storage.upsert_rh_transactions(conn, items)
            r["trade"] = len(items)
        except rp_api.APIError as e:
            r["api_err"] = f"trade:{e}"
    if not args.trade_only:
        try:
            items = list(rp_api.fetch_all(lawd_cd, ymd, endpoint=rp_api.ENDPOINT_RH_RENT))
            if items and not args.dry_run:
                rp_storage.upsert_rh_rentals(conn, items)
            r["rent"] = len(items)
        except rp_api.APIError as e:
            r["api_err"] = (r["api_err"] or "") + f" rent:{e}"
    return r


def main() -> int:
    args = parse_args()
    t_start = time.time()
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA journal_size_limit=1073741824")  # WAL 상한 1GB(체크포인트 후 자동 축소)
    rp_storage.init_schema(conn)

    sggs = resolve_sggs(conn, args)
    months = resolve_months(args)
    tasks = [(lawd, label, ymd) for (lawd, label) in sggs for ymd in months]
    total = len(tasks)
    print(f"[*] {len(sggs)} 시군구 × {len(months)} months = {total} tasks  "
          f"concurrency={args.concurrency}  "
          f"{'매매만' if args.trade_only else '전월세만' if args.rent_only else '매매+전월세'}"
          f"{'  (dry-run)' if args.dry_run else ''}")

    grand = {"trade": 0, "rent": 0, "api_errs": 0}
    plock = threading.Lock()
    done = 0

    def worker(lawd, label, ymd):
        return label, lawd, ymd, _process(lawd, ymd, conn, args)

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = [exe.submit(worker, *t) for t in tasks]
        for fut in as_completed(futs):
            label, lawd, ymd, r = fut.result()
            with plock:
                done += 1
                grand["trade"] += r["trade"]
                grand["rent"] += r["rent"]
                if r["api_err"]:
                    grand["api_errs"] += 1
                if done % 50 == 0 or r["api_err"] or done == total or (r["trade"] or r["rent"]):
                    rate = done / max(time.time() - t_start, 0.001)
                    line = (f"  [{done}/{total}] {label}({lawd}) {ymd}: "
                            f"매매={r['trade']} 전월세={r['rent']}")
                    if r["api_err"]:
                        line += f"  ERR: {r['api_err'][:50]}"
                    line += f"  ({rate:.1f}/s)"
                    print(line)

    print(f"\n[done] {time.time()-t_start:.0f}s  매매={grand['trade']:,}  "
          f"전월세={grand['rent']:,}  api_errs={grand['api_errs']}")
    if not args.dry_run:
        for tbl, lbl in (("rh_transactions", "매매"), ("rh_rentals", "전월세")):
            row = conn.execute(
                f"SELECT COUNT(*), MIN(deal_ymd), MAX(deal_ymd) FROM {tbl}").fetchone()
            print(f"  [stats] {tbl}({lbl}): total={row[0]:,}  range={row[1]}~{row[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
