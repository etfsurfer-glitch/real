"""비단지 실거래 백필 — 빌라/단독/상가. (RH/SH/Nrg) 단지 매칭 없음.

--kind villa|house|comm 디스패치. 매매+전월세 동시(comm은 매매만). daily 증분에도 재사용.

Examples:
    python scripts/backfill_nonresi.py --kind house --all --months 24
    python scripts/backfill_nonresi.py --kind comm  --all --months 24
    python scripts/backfill_nonresi.py --kind house --lawd 11680 --months 1   # 검증
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

# kind → (라벨, 매매 endpoint, 매매 upsert, 전월세 endpoint|None, 전월세 upsert|None)
KINDS = {
    "villa": ("빌라", rp_api.ENDPOINT_RH_TRADE, rp_storage.upsert_rh_transactions,
              rp_api.ENDPOINT_RH_RENT, rp_storage.upsert_rh_rentals),
    "house": ("단독", rp_api.ENDPOINT_SH_TRADE, rp_storage.upsert_sh_transactions,
              rp_api.ENDPOINT_SH_RENT, rp_storage.upsert_sh_rentals),
    "comm":  ("상가", rp_api.ENDPOINT_NRG_TRADE, rp_storage.upsert_nrg_transactions,
              None, None),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", required=True, choices=list(KINDS))
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lawd", help="시군구 5자리")
    g.add_argument("--sido", help="시도 2자리")
    g.add_argument("--all", action="store_true")
    p.add_argument("--month", help="단일 월 (YYYYMM)")
    p.add_argument("--months", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--concurrency", type=int, default=8)
    return p.parse_args()


def resolve_sggs(conn, args):
    if args.lawd:
        row = conn.execute(
            "SELECT cortar_name FROM regions WHERE cortar_no LIKE ? AND cortar_type='dvsn' LIMIT 1",
            (args.lawd + "%",)).fetchone()
        return [(args.lawd, row[0] if row else args.lawd)]
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
    months, y, m = [], today.year, today.month
    for _ in range(args.months):
        months.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return months


def main() -> int:
    args = parse_args()
    label, ep_sale, up_sale, ep_rent, up_rent = KINDS[args.kind]
    t_start = time.time()
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    rp_storage.init_schema(conn)

    sggs = resolve_sggs(conn, args)
    months = resolve_months(args)
    tasks = [(lawd, lbl, ymd) for (lawd, lbl) in sggs for ymd in months]
    total = len(tasks)
    print(f"[*] [{label}] {len(sggs)} 시군구 × {len(months)} months = {total} tasks  "
          f"concurrency={args.concurrency}  {'매매+전월세' if ep_rent else '매매만'}"
          f"{'  (dry-run)' if args.dry_run else ''}")

    grand = {"sale": 0, "rent": 0, "api_errs": 0}
    plock = threading.Lock()
    done = 0

    def _process(lawd, ymd):
        r = {"sale": 0, "rent": 0, "err": None}
        try:
            items = list(rp_api.fetch_all(lawd, ymd, endpoint=ep_sale))
            if items and not args.dry_run:
                up_sale(conn, items)
            r["sale"] = len(items)
        except rp_api.APIError as e:
            r["err"] = f"sale:{e}"
        if ep_rent:
            try:
                items = list(rp_api.fetch_all(lawd, ymd, endpoint=ep_rent))
                if items and not args.dry_run:
                    up_rent(conn, items)
                r["rent"] = len(items)
            except rp_api.APIError as e:
                r["err"] = (r["err"] or "") + f" rent:{e}"
        return r

    def worker(lawd, lbl, ymd):
        return lbl, lawd, ymd, _process(lawd, ymd)

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = [exe.submit(worker, *t) for t in tasks]
        for fut in as_completed(futs):
            lbl, lawd, ymd, r = fut.result()
            with plock:
                done += 1
                grand["sale"] += r["sale"]; grand["rent"] += r["rent"]
                if r["err"]:
                    grand["api_errs"] += 1
                if done % 50 == 0 or r["err"] or done == total or (r["sale"] or r["rent"]):
                    rate = done / max(time.time() - t_start, 0.001)
                    line = f"  [{done}/{total}] {lbl}({lawd}) {ymd}: 매매={r['sale']}"
                    if ep_rent:
                        line += f" 전월세={r['rent']}"
                    if r["err"]:
                        line += f"  ERR: {r['err'][:50]}"
                    print(line + f"  ({rate:.1f}/s)")

    print(f"\n[done] {time.time()-t_start:.0f}s  매매={grand['sale']:,}  "
          f"전월세={grand['rent']:,}  api_errs={grand['api_errs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
