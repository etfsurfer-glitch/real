"""Archive today's listings_current snapshot to compressed parquet.

매물 raw를 매일 별도 보관 — 미래에 어떻게 가공할지 모르니까. parquet은 컬럼 압축
+ columnar 포맷이라 1일치 ~50-90 MB (zstd, vs JSON 443MB), 미래에 pandas/duckdb로
바로 query 가능.

  python scripts/archive_listings.py              # today
  python scripts/archive_listings.py 2026-05-19   # specific date

파일 경로: data/archive/listings/YYYY/MM/listings_YYYY-MM-DD.parquet
"""
from __future__ import annotations

import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from collector.config import settings  # noqa: E402

ARCHIVE_ROOT = settings.snapshot_dir.parent / "archive" / "listings"


def archive(snapshot_date: str) -> Path:
    out_dir = ARCHIVE_ROOT / snapshot_date[:4] / snapshot_date[5:7]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"listings_{snapshot_date}.parquet"

    conn = sqlite3.connect(str(settings.local_db_path))
    cur = conn.execute(
        "SELECT * FROM listings_current WHERE snapshot_date = ?",
        (snapshot_date,),
    )
    cols = [d[0] for d in cur.description]

    # Build columnar — list per column for pa.table().
    data: dict[str, list] = {c: [] for c in cols}
    n = 0
    t0 = time.time()
    for row in cur:
        for i, c in enumerate(cols):
            data[c].append(row[i])
        n += 1
    print(f"  loaded {n:,} rows from SQLite ({time.time()-t0:.1f}s)")

    if n == 0:
        print(f"  [warning] no rows for snapshot_date={snapshot_date}; skipping write")
        return out

    t0 = time.time()
    table = pa.table(data)
    # zstd: ~10x compression for Korean text-heavy data
    pq.write_table(table, str(out), compression="zstd", compression_level=3)
    write_secs = time.time() - t0
    size_mb = out.stat().st_size / 1024 / 1024
    raw_est_mb = sum(len(str(row[k]) if row[k] is not None else "") for k in range(len(cols)) for row in cur) / 1024 / 1024
    print(f"  wrote {out.relative_to(ARCHIVE_ROOT.parent.parent)}: "
          f"{size_mb:.1f} MB  ({write_secs:.1f}s)")
    return out


def main() -> int:
    snapshot_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(f"[*] archive listings snapshot_date={snapshot_date}")
    print(f"[*] root: {ARCHIVE_ROOT}")
    out = archive(snapshot_date)
    print(f"\n[done] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
