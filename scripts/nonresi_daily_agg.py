# -*- coding: utf-8 -*-
"""비단지 10종 일별 집계 축적 — 스냅샷은 매일 덮어써지므로 이 테이블들이 유일한 일별 이력.

villa_daily_agg.py(빌라 전용, 2026-07-13)를 전 카테고리로 일반화(2026-07-13 확대).
박스에서 daily 수집 후 크론(22:30) 실행. 사용:
  nonresi_daily_agg.py [--cat villa,sangga] [날짜]     # 기본 --all 전 카테고리, 날짜=백필

각 카테고리 DB 안에 동일 스키마 2테이블:
  dong_daily    동(cortar10)×거래유형 (ads·units·가격 합계/구간) — 자유 롤업용
  region_daily  전국('00')/시도(2·광주29/전남46 표준)/시군구(5)×거래유형
                (ads·units·px med/avg/p25/p75·㎡당 med·월세 med/avg) — 서빙용
빌라는 legacy villa_daily_agg(시도×유형)도 region_daily에서 유도해 유지(기존 보고서 호환).

가격 단위 만원. 오타 로버스트 컷: 카테고리별 sane band(아래 PX_HI) 밖은 가격 집계에서
제외(건수 ads엔 포함). ㎡당가는 매매만, 면적=COALESCE(전용 area2, area1).
units = Σ1/max(sameAddrCnt,1) (중복 광고 제거 실매물).
백필 주의: 과거 날짜의 가격은 현재 저장가(마지막 관측가) 근사 — 건수는 정확.
광주/전남 네이버 12* 코드는 villa DB의 villa_region_map으로 시도 표준 귀속.
"""
import argparse
import datetime
import sqlite3
from collections import defaultdict
from pathlib import Path

DATA = Path("/opt/koczip/data")
CATS = {  # cat: (DB파일, 매매/전세 가격상한 만원)
    "villa":     ("listings_villa.sqlite",     500_000),    # 50억
    "oneroom":   ("listings_oneroom.sqlite",   500_000),
    "house":     ("listings_house.sqlite",   1_000_000),    # 100억
    "sangga":    ("listings_sangga.sqlite",  2_000_000),    # 200억
    "office":    ("listings_office.sqlite",  2_000_000),
    "knowledge": ("listings_knowledge.sqlite", 2_000_000),
    "redev":     ("listings_redev.sqlite",   2_000_000),
    "building":  ("listings_building.sqlite", 5_000_000),   # 500억
    "factory":   ("listings_factory.sqlite", 5_000_000),
    "land":      ("listings_land.sqlite",    5_000_000),
}
PX_LO = 100          # 100만원
RENT_LO, RENT_HI = 3, 10_000   # 월세 3만~1억(상가 큰 임대 허용)
AREA_LO, AREA_HI = 3, 100_000  # ㎡당가용 면적 밴드(토지·공장 대면적 허용)

DDL = """
CREATE TABLE IF NOT EXISTS dong_daily (
  snapshot_date TEXT NOT NULL, cortar_no TEXT NOT NULL, trade_type TEXT NOT NULL,
  ads INTEGER NOT NULL, units REAL NOT NULL,
  px_cnt INTEGER, px_sum REAL, px_min INTEGER, px_max INTEGER,
  rent_cnt INTEGER, rent_sum REAL,
  PRIMARY KEY (snapshot_date, cortar_no, trade_type));
CREATE TABLE IF NOT EXISTS region_daily (
  snapshot_date TEXT NOT NULL, region TEXT NOT NULL, trade_type TEXT NOT NULL,
  ads INTEGER NOT NULL, units INTEGER NOT NULL,
  px_med REAL, px_avg REAL, px_p25 REAL, px_p75 REAL,
  ppm2_med REAL, rent_med REAL, rent_avg REAL,
  PRIMARY KEY (snapshot_date, region, trade_type));
"""


def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = (len(sorted_vals) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def load_sido_map():
    with sqlite3.connect(f"file:{DATA/'listings_villa.sqlite'}?mode=ro", uri=True) as c:
        return dict(c.execute("SELECT sgg5, sido_std FROM villa_region_map"))


def run_cat(cat, d, sido_map):
    db_file, px_hi = CATS[cat]
    db = sqlite3.connect(DATA / db_file)
    db.execute("PRAGMA journal_size_limit=1073741824")
    db.executescript(DDL)

    rows = db.execute(
        """SELECT cortar_no, trade_type, deal_or_warrant_price, rent_price,
                  COALESCE(area2_m2, area1_m2),
                  MAX(CAST(COALESCE(same_addr_cnt, json_extract(raw,'$.sameAddrCnt')) AS INT), 1)
           FROM listings
           WHERE first_seen_date<=? AND snapshot_date>=? AND trade_type IN ('A1','B1','B2')""",
        (d, d)).fetchall()

    dong = defaultdict(lambda: [0, 0.0, 0, 0.0, None, None, 0, 0.0])
    reg = defaultdict(lambda: {"ads": 0, "units": 0.0, "px": [], "ppm2": [], "rent": []})
    for cortar, tt, pr, rp, ar, sa in rows:
        u = 1.0 / sa
        g = dong[(cortar, tt)]
        g[0] += 1
        g[1] += u
        px_ok = pr is not None and PX_LO <= pr <= px_hi
        rent_ok = tt == "B2" and rp is not None and RENT_LO <= rp <= RENT_HI
        if px_ok:
            g[2] += 1
            g[3] += pr
            g[4] = pr if g[4] is None else min(g[4], pr)
            g[5] = pr if g[5] is None else max(g[5], pr)
        if rent_ok:
            g[6] += 1
            g[7] += rp
        sgg5 = cortar[:5]
        for r in ("00", sido_map.get(sgg5, cortar[:2]), sgg5):
            v = reg[(r, tt)]
            v["ads"] += 1
            v["units"] += u
            if px_ok:
                v["px"].append(pr)
                if tt == "A1" and ar and AREA_LO <= ar <= AREA_HI:
                    v["ppm2"].append(pr / ar)
            if rent_ok:
                v["rent"].append(rp)

    db.execute("DELETE FROM dong_daily WHERE snapshot_date=?", (d,))
    db.executemany(
        "INSERT INTO dong_daily VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(d, c, t, g[0], round(g[1], 3), g[2] or None, round(g[3], 1) or None,
          g[4], g[5], g[6] or None, round(g[7], 1) or None)
         for (c, t), g in dong.items()])

    db.execute("DELETE FROM region_daily WHERE snapshot_date=?", (d,))
    db.executemany(
        "INSERT INTO region_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(d, r, t, v["ads"], int(round(v["units"])),
          pct(px, .5), round(sum(px) / len(px), 1) if px else None,
          pct(px, .25), pct(px, .75),
          round(pct(ppm2, .5), 2) if ppm2 else None,
          pct(rent, .5), round(sum(rent) / len(rent), 1) if rent else None)
         for (r, t), v in reg.items()
         for px, ppm2, rent in [(sorted(v["px"]), sorted(v["ppm2"]), sorted(v["rent"]))]])

    if cat == "villa":  # legacy 호환(기존 보고서 스크립트가 참조)
        db.execute("""CREATE TABLE IF NOT EXISTS villa_daily_agg (
          snapshot_date TEXT NOT NULL, sido TEXT NOT NULL, trade_type TEXT NOT NULL,
          ads INTEGER NOT NULL, units INTEGER NOT NULL,
          PRIMARY KEY (snapshot_date, sido, trade_type))""")
        db.execute("DELETE FROM villa_daily_agg WHERE snapshot_date=?", (d,))
        db.execute("""INSERT INTO villa_daily_agg
          SELECT snapshot_date, region, trade_type, ads, units FROM region_daily
          WHERE snapshot_date=? AND length(region)=2 AND region!='00'""", (d,))
    db.commit()
    n1 = db.execute("SELECT COUNT(*) FROM dong_daily WHERE snapshot_date=?", (d,)).fetchone()[0]
    n2 = db.execute("SELECT COUNT(*) FROM region_daily WHERE snapshot_date=?", (d,)).fetchone()[0]
    db.close()
    print(f"agg {cat:<10} {d}: listings={len(rows):>7,} dong={n1:>6,} region={n2:>4}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="", help="쉼표구분 카테고리(기본 전체)")
    ap.add_argument("date", nargs="?", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    cats = [c.strip() for c in a.cat.split(",") if c.strip()] or list(CATS)
    bad = [c for c in cats if c not in CATS]
    if bad:
        raise SystemExit(f"unknown cat: {bad}")
    sido_map = load_sido_map()
    for cat in cats:
        run_cat(cat, a.date, sido_map)


if __name__ == "__main__":
    main()
