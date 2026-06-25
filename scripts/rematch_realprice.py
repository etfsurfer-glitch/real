"""기존 transactions(아파트 매매) 테이블의 매칭을 새 단지 인덱스로 재계산.

API 호출 없음. raw 컬럼에 저장된 응답을 다시 매칭해서 matched_* 갱신.
단지 마스터에 새 카테고리(예: OPST)를 추가했을 때 매칭률 끌어올리는 용도.

Run:
    python scripts/rematch_realprice.py --only-unmatched
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realprice import matching as rp_match  # noqa: E402
from collector.realprice import storage as rp_storage  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only-unmatched", action="store_true",
                   help="현재 unmatched 행만 다시 시도")
    p.add_argument("--concurrency", type=int, default=4)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    t0 = time.time()
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    where = " WHERE matched_complex_no IS NULL" if args.only_unmatched else ""
    cur = conn.execute(
        f"SELECT deal_id, sgg_cd, raw, manual_override FROM transactions{where}"
    )
    by_sgg: dict[str, list[tuple]] = defaultdict(list)
    skipped_manual = 0
    for did, sgg_cd, raw, manual in cur.fetchall():
        if manual:
            skipped_manual += 1
            continue
        by_sgg[sgg_cd].append((did, raw))

    total = sum(len(v) for v in by_sgg.values())
    print(f"[*] rematch target: {total:,} rows over {len(by_sgg)} 시군구  "
          f"(manual_override 제외: {skipped_manual:,})  "
          f"only_unmatched={args.only_unmatched}  concurrency={args.concurrency}")

    plock = threading.Lock()
    stats = {"updated": 0, "newly_matched": 0, "still_unmatched": 0, "errors": 0}

    def worker(sgg_cd: str, rows: list[tuple]) -> dict:
        local = {"updated": 0, "newly_matched": 0, "still_unmatched": 0, "errors": 0}
        try:
            complexes = rp_match.load_complexes(conn, cortar_prefix=sgg_cd)
            idx = rp_match.ComplexIndex(complexes)
        except Exception:
            local["errors"] += len(rows)
            return local

        updates = []
        now = datetime.now().isoformat(timespec="seconds")
        for did, raw in rows:
            try:
                tx = json.loads(raw) if raw else {}
            except Exception:
                local["errors"] += 1
                continue
            trace = rp_match.match_one_with_trace(tx, idx, keep_top=3)
            if trace.get("chosen"):
                chosen = trace["chosen"]
                updates.append((
                    chosen["complex_no"], chosen["method"], chosen["score"],
                    json.dumps(trace, ensure_ascii=False), now, did,
                ))
                local["newly_matched"] += 1
            else:
                updates.append((
                    None, "unmatched", None,
                    json.dumps(trace, ensure_ascii=False), now, did,
                ))
                local["still_unmatched"] += 1

        if updates:
            with rp_storage._LOCK:
                conn.executemany(
                    """
                    UPDATE transactions
                    SET matched_complex_no = ?,
                        matched_method     = ?,
                        matched_score      = ?,
                        match_details      = ?,
                        matched_at         = ?
                    WHERE deal_id = ? AND manual_override = 0
                    """,
                    updates,
                )
                conn.commit()
                local["updated"] = len(updates)
        return local

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = {exe.submit(worker, k, v): k for k, v in by_sgg.items()}
        done_sgg = 0
        for fut in as_completed(futs):
            sgg = futs[fut]
            local = fut.result()
            with plock:
                for k in stats:
                    stats[k] += local[k]
                done_sgg += 1
                if done_sgg % 25 == 0 or done_sgg == len(by_sgg):
                    rate = done_sgg / max(time.time() - t0, 0.001)
                    print(f"  [{done_sgg}/{len(by_sgg)}] sgg={sgg}  "
                          f"updated={stats['updated']:,} new_matched={stats['newly_matched']:,}  "
                          f"({rate:.1f} sgg/s)")

    print(f"\n[done] {time.time()-t0:.0f}s")
    print(f"  updated:         {stats['updated']:,}")
    print(f"  newly matched:   {stats['newly_matched']:,}")
    print(f"  still unmatched: {stats['still_unmatched']:,}")
    print(f"  errors:          {stats['errors']:,}")

    n_total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    n_matched = conn.execute("SELECT COUNT(*) FROM transactions WHERE matched_complex_no IS NOT NULL").fetchone()[0]
    n_unmatched = n_total - n_matched
    print(f"\n[stats] transactions table after rematch:")
    print(f"  total:        {n_total:,}")
    print(f"  matched:      {n_matched:,}  ({n_matched*100/n_total:.1f}%)")
    print(f"  unmatched:    {n_unmatched:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
