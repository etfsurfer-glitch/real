"""아파트 분양권/입주권 전매 실거래 백필. (RTMSDataSvcSilvTrade)

backfill_offi.py 패턴 미러. 시군구×월 단위로 분양권 전매를 받아 silv_transactions에 저장.
매칭은 기존 complexes 인덱스(매매와 동일) — 신축이라도 네이버에 등록된 단지는 매칭됨.

Examples:
    python scripts/backfill_silv.py --lawd 11740 --month 202505   # 강동구 5월
    python scripts/backfill_silv.py --all --months 12             # 전국 12개월
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


def _process(lawd_cd: str, ymd: str, index: rp_match.ComplexIndex,
             conn: sqlite3.Connection, dry_run: bool) -> dict:
    result = {"items": 0, "matched": 0, "unmatched": 0, "api_err": None}
    try:
        items = list(rp_api.fetch_all(lawd_cd, ymd, endpoint=rp_api.ENDPOINT_SILV))
    except rp_api.APIError as e:
        result["api_err"] = str(e)
        return result
    if not items:
        return result
    match_results = {}
    for tx in items:
        did = rp_storage.make_silv_deal_id(tx)
        trace = rp_match.match_one_with_trace(tx, index, keep_top=3)
        match_results[did] = trace
        if trace["chosen"]:
            result["matched"] += 1
        else:
            result["unmatched"] += 1
    result["items"] = len(items)
    if not dry_run:
        rp_storage.upsert_silv_transactions(conn, items, match_results)
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
          f"concurrency={args.concurrency}")
    if args.dry_run:
        print("[*] dry-run mode")

    print(f"[1] building indexes for {len(sggs)} 시군구 ...")
    indexes: dict[str, rp_match.ComplexIndex] = {}
    for lawd_cd, _ in sggs:
        if lawd_cd not in indexes:
            complexes = rp_match.load_complexes(conn, cortar_prefix=lawd_cd)
            indexes[lawd_cd] = rp_match.ComplexIndex(complexes)
    print(f"    {len(indexes)} indexes built ({time.time()-t_start:.1f}s)")

    print("\n[2] running tasks ...")
    grand = {"items": 0, "matched": 0, "unmatched": 0, "api_calls": 0, "api_errs": 0}
    plock = threading.Lock()
    done = 0
    tasks = [(lawd_cd, label, ymd) for (lawd_cd, label) in sggs for ymd in months]

    def worker(lawd_cd, label, ymd):
        r = _process(lawd_cd, ymd, indexes[lawd_cd], conn, args.dry_run)
        return label, lawd_cd, ymd, r

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
                if done % 50 == 0 or r["api_err"] or done == total_tasks or r["items"]:
                    elapsed = time.time() - t_start
                    rate = done / max(elapsed, 0.001)
                    line = (f"  [{done}/{total_tasks}] {label}({lawd_cd}) {ymd}: "
                            f"items={r['items']} m={r['matched']} u={r['unmatched']}")
                    if r["api_err"]:
                        line += f"  API_ERR: {r['api_err'][:60]}"
                    line += f"  ({rate:.1f} tasks/s)"
                    print(line)

    elapsed = time.time() - t_start
    it = grand["items"]
    pct = f"{grand['matched']*100/it:.1f}%" if it else "0%"
    print(f"\n[done] {elapsed:.0f}s  api_calls={grand['api_calls']:,} errs={grand['api_errs']}")
    print(f"  분양권: items={it:,}  matched={grand['matched']:,} ({pct})  "
          f"unmatched={grand['unmatched']:,}")

    if not args.dry_run:
        row = conn.execute(
            "SELECT COUNT(*), COUNT(matched_complex_no), MIN(deal_ymd), MAX(deal_ymd) "
            "FROM silv_transactions").fetchone()
        if row[0]:
            mp = f"{row[1]*100/row[0]:.1f}%"
            print(f"  [stats] silv_transactions: total={row[0]:,}  "
                  f"matched={row[1]:,} ({mp})  range={row[2]}~{row[3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
