"""오피스텔 매매·전월세 백필. (RTMSDataSvcOffiTrade + RTMSDataSvcOffiRent)

backfill_realprice.py 패턴 미러. 한 번에 매매+전월세 두 endpoint를 시군구×월
단위로 받아서 offi_transactions / offi_rentals에 저장.

Examples:
    python scripts/backfill_offi.py --lawd 11680 --month 202604       # 강남구 4월
    python scripts/backfill_offi.py --all --months 6                  # 전국 6개월
    python scripts/backfill_offi.py --all --months 6 --only rent      # 전월세만
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
    p.add_argument("--months", type=int, default=1)
    p.add_argument("--only", choices=("trade", "rent", "both"), default="both",
                   help="trade=매매만, rent=전월세만, both=둘 다")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--concurrency", type=int, default=4)
    return p.parse_args()


def resolve_sggs(conn, args):
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
            m = 12
            y -= 1
    return months


def _process_trade(lawd_cd: str, ymd: str, index: rp_match.ComplexIndex,
                   conn: sqlite3.Connection, dry_run: bool) -> dict:
    result = {"items": 0, "matched": 0, "unmatched": 0, "api_err": None}
    try:
        items = list(rp_api.fetch_all(lawd_cd, ymd, endpoint=rp_api.ENDPOINT_OFFI_TRADE))
    except rp_api.APIError as e:
        result["api_err"] = str(e)
        return result
    if not items:
        return result
    match_results = {}
    for tx in items:
        did = rp_storage.make_offi_deal_id(tx)
        trace = rp_match.match_one_with_trace(tx, index, keep_top=3)
        match_results[did] = trace
        if trace["chosen"]:
            result["matched"] += 1
        else:
            result["unmatched"] += 1
    result["items"] = len(items)
    if not dry_run:
        rp_storage.upsert_offi_transactions(conn, items, match_results)
    return result


def _process_rent(lawd_cd: str, ymd: str, index: rp_match.ComplexIndex,
                  conn: sqlite3.Connection, dry_run: bool) -> dict:
    result = {"items": 0, "matched": 0, "unmatched": 0, "api_err": None}
    try:
        items = list(rp_api.fetch_all(lawd_cd, ymd, endpoint=rp_api.ENDPOINT_OFFI_RENT))
    except rp_api.APIError as e:
        result["api_err"] = str(e)
        return result
    if not items:
        return result
    match_results = {}
    for tx in items:
        rid = rp_storage.make_offi_rental_id(tx)
        trace = rp_match.match_one_with_trace(tx, index, keep_top=3)
        match_results[rid] = trace
        if trace["chosen"]:
            result["matched"] += 1
        else:
            result["unmatched"] += 1
    result["items"] = len(items)
    if not dry_run:
        rp_storage.upsert_offi_rentals(conn, items, match_results)
    return result


def main() -> int:
    args = parse_args()
    t_start = time.time()
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA journal_size_limit=1073741824")  # WAL 상한 1GB(체크포인트 후 자동 축소)
    conn.execute("PRAGMA synchronous=NORMAL")
    rp_storage.init_schema(conn)

    sggs = resolve_sggs(conn, args)
    months = resolve_months(args)
    do_trade = args.only in ("trade", "both")
    do_rent = args.only in ("rent", "both")
    per_unit = (1 if do_trade else 0) + (1 if do_rent else 0)
    total_tasks = len(sggs) * len(months) * per_unit
    print(f"[*] {len(sggs)} 시군구 × {len(months)} months × {per_unit} feed = {total_tasks} tasks  "
          f"concurrency={args.concurrency}  only={args.only}")
    if args.dry_run:
        print("[*] dry-run mode")

    print(f"[1] building indexes for {len(sggs)} 시군구 ...")
    indexes: dict[str, rp_match.ComplexIndex] = {}
    for lawd_cd, _ in sggs:
        if lawd_cd not in indexes:
            complexes = rp_match.load_complexes(conn, cortar_prefix=lawd_cd)
            indexes[lawd_cd] = rp_match.ComplexIndex(complexes)
    print(f"    {len(indexes)} indexes built ({time.time()-t_start:.1f}s)")

    print(f"\n[2] running tasks ...")
    grand = {"trade_items": 0, "trade_matched": 0, "trade_unmatched": 0,
             "rent_items": 0, "rent_matched": 0, "rent_unmatched": 0,
             "api_calls": 0, "api_errs": 0}
    plock = threading.Lock()
    done = 0
    tasks = []
    for (lawd_cd, label) in sggs:
        for ymd in months:
            if do_trade:
                tasks.append(("trade", lawd_cd, label, ymd))
            if do_rent:
                tasks.append(("rent", lawd_cd, label, ymd))

    def worker(kind, lawd_cd, label, ymd):
        if kind == "trade":
            r = _process_trade(lawd_cd, ymd, indexes[lawd_cd], conn, args.dry_run)
        else:
            r = _process_rent(lawd_cd, ymd, indexes[lawd_cd], conn, args.dry_run)
        return kind, label, lawd_cd, ymd, r

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = [exe.submit(worker, *t) for t in tasks]
        for fut in as_completed(futs):
            kind, label, lawd_cd, ymd, r = fut.result()
            with plock:
                done += 1
                grand["api_calls"] += 1
                if r["api_err"]:
                    grand["api_errs"] += 1
                grand[f"{kind}_items"] += r["items"]
                grand[f"{kind}_matched"] += r["matched"]
                grand[f"{kind}_unmatched"] += r["unmatched"]
                if done % 50 == 0 or r["api_err"] or done == total_tasks:
                    elapsed = time.time() - t_start
                    rate = done / max(elapsed, 0.001)
                    line = (f"  [{done}/{total_tasks}] {kind} {label}({lawd_cd}) {ymd}: "
                            f"items={r['items']} m={r['matched']} u={r['unmatched']}")
                    if r["api_err"]:
                        line += f"  API_ERR: {r['api_err'][:60]}"
                    line += f"  ({rate:.1f} tasks/s)"
                    print(line)

    elapsed = time.time() - t_start
    print(f"\n[done] {elapsed:.0f}s")
    print(f"  api_calls: {grand['api_calls']:,}  api_errs: {grand['api_errs']}")
    if do_trade:
        ti = grand["trade_items"]
        pct = f"{grand['trade_matched']*100/ti:.1f}%" if ti else "0%"
        print(f"  trade: items={ti:,}  matched={grand['trade_matched']:,} ({pct})  "
              f"unmatched={grand['trade_unmatched']:,}")
    if do_rent:
        ri = grand["rent_items"]
        pct = f"{grand['rent_matched']*100/ri:.1f}%" if ri else "0%"
        print(f"  rent:  items={ri:,}  matched={grand['rent_matched']:,} ({pct})  "
              f"unmatched={grand['rent_unmatched']:,}")

    if not args.dry_run:
        print("\n[stats] offi tables:")
        for name in ("offi_transactions", "offi_rentals"):
            row = conn.execute(
                f"SELECT COUNT(*), COUNT(matched_complex_no), MIN(deal_ymd), MAX(deal_ymd) FROM {name}"
            ).fetchone()
            if row[0]:
                pct = f"{row[1]*100/row[0]:.1f}%"
                print(f"  {name}: total={row[0]:,}  matched={row[1]:,} ({pct})  range={row[2]}~{row[3]}")
            else:
                print(f"  {name}: empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
