"""max_pages 한도(이전 100=2000매물)에 막혀 잘렸을 가능성이 있는
대단지만 빠르게 다시 fetch한다. listings_current를 그 (단지, 거래유형)
한정으로 오늘자 다시 채워넣는다.

기준: 오늘 snapshot에서 해당 (단지, 거래유형)의 매물 수가 임계값(기본 1500)
이상인 케이스만. cap된 2000 + 근접한 1500-1999 모두 포함.

Run:
    python scripts/refresh_capped_complexes.py
    python scripts/refresh_capped_complexes.py --threshold 1900   # cap만
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import date
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
    p.add_argument("--threshold", type=int, default=1500,
                   help="이 (단지, 거래유형) 매물 수 이상이면 다시 fetch")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    t0 = time.time()

    creds_path = Path(settings.snapshot_dir).parent / "naver_creds.json"
    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    storage.init_schema(conn)

    snap_row = conn.execute(
        "SELECT MAX(snapshot_date) FROM listings_current"
    ).fetchone()
    snapshot_date = snap_row[0] if snap_row and snap_row[0] else date.today().isoformat()

    targets = conn.execute(
        """
        SELECT complex_no, trade_type, COUNT(*) AS n
        FROM listings_current
        WHERE snapshot_date = ?
        GROUP BY complex_no, trade_type
        HAVING n >= ?
        ORDER BY n DESC
        """,
        (snapshot_date, args.threshold),
    ).fetchall()

    print(f"[*] snapshot_date={snapshot_date}  threshold={args.threshold}  "
          f"targets={len(targets)} (complex, trade) units")
    for cno, t, n in targets[:20]:
        name_row = conn.execute(
            "SELECT complex_name FROM complexes WHERE complex_no=?", (cno,)
        ).fetchone()
        nm = name_row[0] if name_row else "?"
        print(f"  - {cno:<8} {t}  {nm:<35} (현재 {n})")

    print()
    grand = {"items": 0, "complex_trades": 0, "errors": 0}
    for i, (cno, trade, prev_n) in enumerate(targets, 1):
        try:
            items = list(naver.articles_for_complex(cno, trade, creds))
        except Exception as e:  # noqa: BLE001
            grand["errors"] += 1
            print(f"  [{i}/{len(targets)}] {cno}/{trade}  ERR: {e}")
            continue
        storage.save_articles(conn, cno, trade, items, snapshot_date)
        grand["items"] += len(items)
        grand["complex_trades"] += 1
        delta = len(items) - prev_n
        sign = "+" if delta >= 0 else ""
        print(f"  [{i}/{len(targets)}] {cno}/{trade}  prev={prev_n}  now={len(items)}  ({sign}{delta})")

    elapsed = time.time() - t0
    print(f"\n[done] {elapsed:.1f}s  refreshed {grand['complex_trades']} units, "
          f"{grand['items']:,} items total  errors={grand['errors']}")

    # complex_daily_agg 재계산 — 늘어난 매물 카운트 반영
    print("\n[*] recomputing complex_daily_agg for these complexes ...")
    cnos = sorted({cno for cno, _, _ in targets})
    if cnos:
        placeholders = ",".join(["?"] * len(cnos))
        with storage._LOCK:
            conn.execute(
                f"DELETE FROM complex_daily_agg WHERE snapshot_date=? AND complex_no IN ({placeholders})",
                (snapshot_date, *cnos),
            )
            conn.execute(
                f"""
                INSERT INTO complex_daily_agg
                  (snapshot_date, complex_no, area_name, trade_type,
                   listing_count, price_min, price_max, price_avg,
                   rent_min, rent_max, rent_avg)
                SELECT
                  snapshot_date, complex_no, COALESCE(area_name,''), trade_type,
                  COUNT(*),
                  MIN(deal_or_warrant_price), MAX(deal_or_warrant_price), AVG(deal_or_warrant_price),
                  MIN(rent_price), MAX(rent_price), AVG(rent_price)
                FROM listings_current
                WHERE snapshot_date=? AND complex_no IN ({placeholders})
                GROUP BY snapshot_date, complex_no, COALESCE(area_name,''), trade_type
                """,
                (snapshot_date, *cnos),
            )
            conn.commit()
        print(f"  reaggregated {len(cnos)} complexes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
