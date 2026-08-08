# -*- coding: utf-8 -*-
"""비단지 10종 매물 스냅샷 일별 parquet 아카이브 — 스냅샷이 매일 덮어써지므로 원본 보존.

archive_villa_listings.py(빌라 전용)를 전 카테고리로 일반화(2026-07-13).
raw JSON 제외 슬림 스키마(sameAddrCnt만 raw에서 컬럼화, 상가·빌딩은 premium_price 포함)
+ zstd. 전 10종 합계 대략 35~40MB/일(용량은 서버 측과 협의됨 — 사용자).
경로: /opt/koczip/data/archive/{cat}/YYYY/MM/{cat}_YYYY-MM-DD.parquet
사용: archive_nonresi_listings.py [--cat villa,sangga] [날짜(파일명용)]
"""
import argparse
import datetime
import sqlite3
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DATA = Path("/opt/koczip/data")
CATS = ["villa", "oneroom", "house", "sangga", "office",
        "knowledge", "redev", "building", "factory", "land"]

BASE_COLS = [
    ("article_no", pa.string()), ("cortar_no", pa.string()),
    ("real_estate_type_name", pa.string()), ("trade_type", pa.string()),
    ("deal_or_warrant_price", pa.int64()), ("rent_price", pa.int64()),
    ("area1_m2", pa.float32()), ("area2_m2", pa.float32()),
    ("floor_info", pa.string()), ("direction", pa.string()),
    ("building_name", pa.string()), ("realtor_id", pa.string()),
    ("latitude", pa.float64()), ("longitude", pa.float64()),
    ("article_confirm_ymd", pa.string()), ("first_seen_date", pa.string()),
]


def run_cat(cat, d):
    db_path = DATA / f"listings_{cat}.sqlite"
    out = DATA / "archive" / cat / d[:4] / d[5:7] / f"{cat}_{d}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    has_premium = any(r[1] == "premium_price"
                      for r in con.execute("PRAGMA table_info(listings)"))
    cols = BASE_COLS + ([("premium_price", pa.int64())] if has_premium else []) \
        + [("same_addr_cnt", pa.int32())]
    sel = ", ".join(n for n, _ in cols[:-1]) \
        + ", MAX(CAST(COALESCE(same_addr_cnt, json_extract(raw,'$.sameAddrCnt')) AS INT), 1)"
    snap = con.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
    rows = con.execute(f"SELECT {sel} FROM listings WHERE snapshot_date=?", (snap,)).fetchall()
    con.close()
    if not rows:
        print(f"archive {cat:<10} {d}: 0 rows — skip", flush=True)
        return

    arrs = list(zip(*rows))
    table = pa.table({name: pa.array(arrs[i], type=t) for i, (name, t) in enumerate(cols)})
    pq.write_table(table, out, compression="zstd", compression_level=7)
    print(f"archive {cat:<10} {d}: snapshot={snap} rows={len(rows):>7,} "
          f"{out.stat().st_size/1e6:5.1f}MB", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="", help="쉼표구분 카테고리(기본 전체)")
    ap.add_argument("date", nargs="?", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    cats = [c.strip() for c in a.cat.split(",") if c.strip()] or CATS
    bad = [c for c in cats if c not in CATS]
    if bad:
        raise SystemExit(f"unknown cat: {bad}")
    for cat in cats:
        run_cat(cat, a.date)


if __name__ == "__main__":
    main()
