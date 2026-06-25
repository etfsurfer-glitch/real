"""중개사무소별 일별 매물수(매매/전세/월세) 스냅샷 → realtor_daily_count.
관심중개사무소 대시보드의 '오늘 증감' 산출용. daily_run에서 매물 수집 후 1회 호출.
listings_current(오늘 스냅샷) 기준으로 그날치를 upsert한다."""
import sqlite3
import sys
from pathlib import Path

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "naverreal.sqlite"


def main():
    con = sqlite3.connect(str(DB))
    con.execute(
        """CREATE TABLE IF NOT EXISTS realtor_daily_count(
             snapshot_date TEXT NOT NULL, realtor_id TEXT NOT NULL,
             a1 INTEGER DEFAULT 0, b1 INTEGER DEFAULT 0, b2 INTEGER DEFAULT 0, total INTEGER DEFAULT 0,
             PRIMARY KEY(snapshot_date, realtor_id))"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS rdc_rid_idx ON realtor_daily_count(realtor_id, snapshot_date)")
    day = con.execute("SELECT MAX(snapshot_date) FROM listings_current").fetchone()[0]
    if not day:
        print("realtor_daily_count: no listings, skip")
        return
    rows = con.execute(
        "SELECT realtor_id, trade_type, COUNT(*) FROM listings_current "
        "WHERE realtor_id IS NOT NULL AND realtor_id<>'' GROUP BY realtor_id, trade_type"
    ).fetchall()
    agg: dict[str, list[int]] = {}
    for rid, tt, n in rows:
        a = agg.setdefault(rid, [0, 0, 0])
        if tt == "A1":
            a[0] += n
        elif tt == "B1":
            a[1] += n
        elif tt == "B2":
            a[2] += n
    con.execute("DELETE FROM realtor_daily_count WHERE snapshot_date=?", (day,))
    con.executemany(
        "INSERT INTO realtor_daily_count VALUES(?,?,?,?,?,?)",
        [(day, rid, a[0], a[1], a[2], a[0] + a[1] + a[2]) for rid, a in agg.items()],
    )
    # 90일 넘은 이력은 정리(증감은 직전일만 필요)
    con.execute("DELETE FROM realtor_daily_count WHERE snapshot_date < date(?, '-90 days')", (day,))
    con.commit()
    print(f"realtor_daily_count: {day} offices={len(agg)}")


if __name__ == "__main__":
    main()
