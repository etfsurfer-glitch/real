"""단지 마스터(complexes)만 빠르게 새로고침/보강.

매물(article)은 받지 않고 region → complex list만 호출해서 upsert.
realEstateType 카테고리를 늘렸을 때(예: OPST 추가) 마스터를 빨리
보강하는 용도.

Run:
    python scripts/refresh_complex_master.py            # 전국 leaf 동
    python scripts/refresh_complex_master.py --sido 11  # 서울만
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import naver, storage  # noqa: E402
from collector.config import settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sido", help="시도 2자리 prefix (예: 11). 미지정 시 전국")
    p.add_argument("--concurrency", type=int, default=8)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    creds_path = Path(settings.snapshot_dir).parent / "naver_creds.json"
    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    storage.init_schema(conn)

    if args.sido:
        cur = conn.execute(
            "SELECT cortar_no FROM regions WHERE cortar_type='sec' AND cortar_no LIKE ?",
            (args.sido + "%",),
        )
    else:
        cur = conn.execute("SELECT cortar_no FROM regions WHERE cortar_type='sec'")
    dongs = [r[0] for r in cur.fetchall()]
    print(f"[*] {len(dongs):,} leaf 동 처리 (concurrency={args.concurrency})")

    plock = threading.Lock()
    stats = {"done": 0, "new": 0, "err": 0, "by_type": {}}
    t_start = time.time()

    def worker(cortar_no: str):
        try:
            cps = naver.complexes_in_region(cortar_no, creds)
        except Exception as e:  # noqa: BLE001
            return cortar_no, [], str(e)
        return cortar_no, cps, None

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = [exe.submit(worker, c) for c in dongs]
        for fut in as_completed(futs):
            cortar_no, cps, err = fut.result()
            with plock:
                stats["done"] += 1
                if err:
                    stats["err"] += 1
                else:
                    for c in cps:
                        storage.upsert_complex(conn, c)
                        t = c.get("realEstateTypeCode") or "?"
                        stats["by_type"][t] = stats["by_type"].get(t, 0) + 1
                if stats["done"] % 200 == 0 or stats["done"] == len(dongs):
                    rate = stats["done"] / max(time.time() - t_start, 0.001)
                    print(f"  [{stats['done']:,}/{len(dongs):,}] err={stats['err']}  "
                          f"({rate:.1f} dongs/s)")
    elapsed = time.time() - t_start

    print(f"\n[done] {elapsed:.0f}s")
    print(f"  errors: {stats['err']}")
    print(f"  complexes touched (by type):")
    for t, n in sorted(stats["by_type"].items(), key=lambda kv: -kv[1]):
        print(f"    {t:>6}  {n:>8,}")

    print("\n[final counts in complexes table]")
    for row in conn.execute(
        "SELECT real_estate_type, COUNT(*) FROM complexes GROUP BY real_estate_type ORDER BY 2 DESC"
    ):
        print(f"  {row[0] or '?':>6}  {row[1]:>8,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
