# -*- coding: utf-8 -*-
"""수집한 블로그 데이터를 자기모순·범위로 검산한다. 네트워크를 타지 않는다.

블로그는 사람이 손으로 적은 표다. 자리수가 빠지기도 한다(파크원타워 33F 임대면적
1,008.84평 → 100.84평). 전용면적이 임대면적보다 클 수는 없으므로 그런 행은 잡힌다.
건축물대장과의 대조는 별도다 — 여기는 글 안에서만 보는 검산이다.
"""
from __future__ import annotations

import os
import sqlite3
import sys

DB = os.path.expanduser("~/auto/naverreal_data/blog_building.sqlite")

CHECKS = [
    ("전용>임대 — 불가능",
     "SELECT seed_name, posted_on, floor, rent_py, excl_py FROM floor_area "
     "WHERE excl_py IS NOT NULL AND rent_py IS NOT NULL AND excl_py > rent_py"),
    ("전용률 90% 초과 — 오피스에선 비현실적",
     "SELECT seed_name, posted_on, floor, rent_py, excl_py FROM floor_area "
     "WHERE rent_py > 0 AND excl_py / rent_py > 0.9"),
    ("전용률 30% 미만 — 자리수 의심",
     "SELECT seed_name, posted_on, floor, rent_py, excl_py FROM floor_area "
     "WHERE rent_py > 0 AND excl_py / rent_py < 0.3"),
    ("평당 임대료 2만 미만·40만 초과",
     "SELECT seed_name, posted_on, field, lo, hi FROM unit_price "
     "WHERE field='u_rent' AND (lo < 20000 OR lo > 400000)"),
    ("평당 관리비가 임대료보다 큼",
     "SELECT c.seed_name, c.posted_on, c.lo, r.lo FROM unit_price c "
     "JOIN unit_price r ON r.url=c.url AND r.field='u_rent' "
     "WHERE c.field='u_cam' AND c.lo > r.lo"),
    ("보증금/임대료 배수가 5~20 밖 — 보통 10배다",
     "SELECT d.seed_name, d.posted_on, d.lo, r.lo, ROUND(d.lo/r.lo,1) FROM unit_price d "
     "JOIN unit_price r ON r.url=d.url AND r.field='u_rent' "
     "WHERE d.field='u_deposit' AND r.lo>0 AND (d.lo/r.lo < 5 OR d.lo/r.lo > 20)"),
    ("작성일 없음 — 시점 없는 가격은 못 쓴다",
     "SELECT url, seed_name, posted_raw FROM post WHERE posted_on IS NULL"),
    ("층별 가격이 있는데 면적이 없음",
     "SELECT p.seed_name, p.posted_on, p.floor FROM floor_price p "
     "LEFT JOIN floor_area a ON a.url=p.url AND a.idx=p.idx WHERE a.url IS NULL"),
]


def main():
    d = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    bad = 0
    for title, q in CHECKS:
        rows = d.execute(q).fetchall()
        bad += len(rows)
        mark = "·" if not rows else "!"
        print(f"{mark} {title}: {len(rows)}건")
        for r in rows[:5]:
            print("    ", " | ".join("" if x is None else str(x) for x in r))
    base = d.execute("SELECT (SELECT COUNT(*) FROM floor_area)+(SELECT COUNT(*) FROM "
                     "floor_price)+(SELECT COUNT(*) FROM unit_price)").fetchone()[0]
    print(f"\n수치행 {base}건 중 의심 {bad}건 ({bad/base*100:.1f}%)")
    d.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
