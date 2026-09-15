# -*- coding: utf-8 -*-
"""상업용 광고 흐름 일일 증분 — nfind 아카이브 parquet diff(완전본) 결과를 적재.

로컬 listings 스냅샷은 아카이브 회수 후 부분 잔존물(2026-09-04 실측: 전일 2.4만/66만)이라
diff 소스로 쓸 수 없다 → sync_archive_offbox(22:30) 후 nfind에서 diff를 돌려 가져온다.
크론: 23:20 (아카이브 rsync 완료 뒤). 멱등(같은 날 재실행 시 교체).
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
NFIND = "root@115.68.177.72"


def run(kind: str) -> None:
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=20", NFIND,
         f"/opt/koczip-archive/.venv/bin/python /opt/koczip-archive/comm_flow_incr_nfind.py {kind}"],
        capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        print(f"{kind}: nfind diff 실패 — {out.stderr.strip()[:200]}")
        return
    rows = [ln.split(",") for ln in out.stdout.strip().splitlines() if ln and not ln.startswith("#")]
    if not rows:
        print(f"{kind}: 결과 없음")
        return
    day = rows[0][0]
    with sqlite3.connect(DATA / f"listings_{kind}.sqlite") as c:
        c.execute("CREATE TABLE IF NOT EXISTS comm_flow_daily "
                  "(date TEXT, cortar_no TEXT, trade_type TEXT, new INTEGER, gone INTEGER, re INTEGER)")
        c.execute("DELETE FROM comm_flow_daily WHERE date=?", (day,))
        c.executemany("INSERT INTO comm_flow_daily VALUES (?,?,?,?,?,?)", rows)
        c.commit()
        n = c.execute("SELECT SUM(new), SUM(gone), SUM(re) FROM comm_flow_daily WHERE date=?",
                      (day,)).fetchone()
        print(f"{kind} {day}: new {n[0]} gone {n[1]} re {n[2]}")


if __name__ == "__main__":
    for k in (sys.argv[1:] or ["sangga", "office"]):
        run(k)
