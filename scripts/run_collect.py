"""Daily Naver real-estate snapshot collector — generalized.

Examples:
    # 특정 동만
    python scripts/run_collect.py --cortar 1165010800

    # 시군구 전체 (서초구)
    python scripts/run_collect.py --ancestor 1165000000

    # 시도 전체 (서울)
    python scripts/run_collect.py --ancestor 1100000000

    # 전국
    python scripts/run_collect.py --all

Resumable: re-running on the same day skips (complex, trade) pairs already
logged as successful. Use --reset-today to force re-collection.
"""
from __future__ import annotations

import argparse
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
    return p.parse_args()


def resolve_dongs(conn, args) -> list[str]:
    if args.cortar:
        return list(args.cortar)
    if args.ancestor:
        return regions.dong_cortar_nos_under(conn, args.ancestor)
    return regions.dong_cortar_nos(conn)


def main() -> int:
    args = parse_args()
    run_date = date.today().isoformat()
    t_start = time.time()

    conn = storage.open_db(settings.local_db_path)
    storage.init_schema(conn)
    creds = ensure_creds()

    dongs = resolve_dongs(conn, args)
    if args.shuffle:
        random.shuffle(dongs)
    if args.limit:
        dongs = dongs[: args.limit]

    print(f"[*] run_date={run_date}  dongs={len(dongs)}  "
          f"concurrency={settings.naver_concurrency}  jitter≤{settings.naver_delay_ms}ms")
    if not dongs:
        print("[!] no dongs to process — did you run build_region_tree.py?")
        return 1

    # Phase 1 — list complexes per dong (sequential, fast)
    print("\n[1/3] complex listing per dong")
    all_tasks: list[tuple[str, str]] = []
    list_errors = 0
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
            print(f"  [{i}/{len(dongs)}] tasks={len(all_tasks)}  list_err={list_errors}  ({elapsed:.0f}s)")

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

        def worker(cno: str, trade: str) -> tuple[str, str, int, str | None]:
            try:
                items = list(articles_for_complex(cno, trade, creds))
                storage.save_articles(conn, cno, trade, items, run_date)
                storage.log_completion(conn, run_date, cno, trade, len(items), "success", None)
                return cno, trade, len(items), None
            except Exception as e:  # noqa: BLE001
                storage.log_completion(conn, run_date, cno, trade, 0, "error", str(e)[:300])
                return cno, trade, 0, f"{type(e).__name__}: {str(e)[:80]}"

        with ThreadPoolExecutor(max_workers=settings.naver_concurrency) as exe:
            futs = [exe.submit(worker, c, t) for c, t in remaining]
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

    # Phase 3 — aggregates
    print("\n[3/3] aggregates")
    n_complex = storage.compute_complex_daily_agg(conn, run_date)
    n_region = storage.compute_region_daily_agg(conn, run_date)
    print(f"  complex_daily_agg rows: {n_complex}")
    print(f"  region_daily_agg rows: {n_region}")

    elapsed = time.time() - t_start
    print(f"\n[done] {elapsed:.0f}s  list_err={list_errors}  "
          f"items={prog.get('items', 0) if remaining else 0}  "
          f"errs={prog.get('errs', 0) if remaining else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
