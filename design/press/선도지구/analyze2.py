# -*- coding: utf-8 -*-
"""선도지구 기사용 통계 ② — 국민평형(전용 84㎡) 기준으로 다시.

평당가는 전용/공급 기준이 갈려 기사에서 오해를 부른다. 독자가 아는 숫자인
'전용 84㎡ 평균 실거래가(억원)'로 통일한다. 해제거래는 전부 제외.
"""
from __future__ import annotations
import json, sqlite3, sys

DB = "/opt/koczip/data/naverreal.sqlite"
A1 = "2024-11-27"    # 1기 신도시 1차 선도지구
A2 = "2026-07-15"    # 대전 둔산·송촌 선도지구

BUNDANG = {
    "샛별마을": [1618, 1633, 1654, 1663],
    "양지마을": [1954, 1980, 100754, 1994, 101537, 101536],
    "시범단지": [1840, 1923],
}
LEAD = [n for v in BUNDANG.values() for n in v]
DJ13 = [5986, 5962]          # 크로바·목련
DJ14 = [5792, 5780]          # 한가람·공작한양
DJ = DJ13 + DJ14


def c_():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    return c


def p84(c, ids, lo, hi):
    """전용 84㎡(±3) 평균 거래가(억) · 건수."""
    if not ids:
        return {"avg": None, "n": 0}
    ph = ",".join("?" * len(ids))
    r = c.execute(f"""
        SELECT AVG(deal_amount)/100000000.0 a, COUNT(*) n
        FROM transactions
        WHERE matched_complex_no IN ({ph}) AND is_cancelled=0
          AND excl_use_ar BETWEEN 81 AND 87
          AND deal_ymd>=? AND deal_ymd<?
    """, (*ids, lo, hi)).fetchone()
    return {"avg": round(r["a"], 2) if r["a"] else None, "n": r["n"]}


def series84(c, ids, lo, hi):
    ph = ",".join("?" * len(ids))
    return {r["m"]: {"avg": round(r["a"], 2), "n": r["n"]} for r in c.execute(f"""
        SELECT substr(deal_ymd,1,7) m, AVG(deal_amount)/100000000.0 a, COUNT(*) n
        FROM transactions WHERE matched_complex_no IN ({ph}) AND is_cancelled=0
          AND excl_use_ar BETWEEN 81 AND 87 AND deal_ymd>=? AND deal_ymd<=?
        GROUP BY m ORDER BY m""", (*ids, lo, hi))}


def listings(c, ids, lo, hi):
    """매물 수 추이(월별 평균). complex_daily_agg = 매물 스냅샷 집계."""
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    return {r["m"]: r["n"] for r in c.execute(f"""
        SELECT substr(snapshot_date,1,7) m, AVG(tot) n FROM (
          SELECT snapshot_date, SUM(listing_count) tot
          FROM complex_daily_agg
          WHERE complex_no IN ({ph}) AND trade_type='A1'
            AND snapshot_date>=? AND snapshot_date<=?
          GROUP BY snapshot_date)
        GROUP BY m ORDER BY m""", (*ids, lo, hi))}


def main():
    c = c_(); out = {}
    ph = ",".join("?" * len(LEAD))
    ctrl = [r[0] for r in c.execute(f"""
        SELECT complex_no FROM complexes WHERE cortar_no LIKE '41135%'
          AND total_household_count>=300
          AND substr(use_approve_ymd,1,4) BETWEEN '1988' AND '1996'
          AND complex_no NOT IN ({ph})""", LEAD)]

    W = {"pre": ("2024-05-27", A1), "post": (A1, "2025-05-27"),
         "now": ("2026-04-19", "2026-10-19")}
    out["bundang"] = {
        "lead": {k: p84(c, LEAD, *v) for k, v in W.items()},
        "ctrl": {k: p84(c, ctrl, *v) for k, v in W.items()},
        "zones": {z: {k: p84(c, ids, *v) for k, v in W.items()}
                  for z, ids in BUNDANG.items()},
        "ctrl_n": len(ctrl),
        "series_lead": series84(c, LEAD, "2024-01-01", "2026-10-31"),
        "series_ctrl": series84(c, ctrl, "2024-01-01", "2026-10-31"),
        "listings_lead": listings(c, LEAD, "2024-01-01", "2026-10-31"),
        "listings_ctrl": listings(c, ctrl, "2024-01-01", "2026-10-31"),
    }

    WD = {"pre": ("2026-01-15", A2), "post": (A2, "2026-10-19")}
    dctrl = [r[0] for r in c.execute(f"""
        SELECT complex_no FROM complexes WHERE cortar_no LIKE '30170%'
          AND total_household_count>=300
          AND substr(use_approve_ymd,1,4) BETWEEN '1988' AND '1999'
          AND complex_no NOT IN ({",".join("?"*len(DJ))})""", DJ)]
    out["daejeon"] = {
        "lead": {k: p84(c, DJ, *v) for k, v in WD.items()},
        "z13": {k: p84(c, DJ13, *v) for k, v in WD.items()},
        "z14": {k: p84(c, DJ14, *v) for k, v in WD.items()},
        "ctrl": {k: p84(c, dctrl, *v) for k, v in WD.items()},
        "ctrl_n": len(dctrl),
        "series_lead": series84(c, DJ, "2025-07-01", "2026-10-31"),
        "listings_lead": listings(c, DJ, "2025-07-01", "2026-10-31"),
    }

    # 선도지구 vs 비선도 스펙 — '어떤 단지가 뽑혔나'
    def agg(ids):
        ph = ",".join("?" * len(ids))
        r = c.execute(f"""SELECT AVG(total_household_count), AVG(batl_ratio), AVG(btl_ratio),
             AVG(CAST(substr(use_approve_ymd,1,4) AS INT)), COUNT(*)
             FROM complexes WHERE complex_no IN ({ph}) AND batl_ratio>0""", ids).fetchone()
        return {"hh": round(r[0]), "vol": round(r[1], 1), "cov": round(r[2], 1),
                "year": round(r[3], 1), "n": r[4]}
    out["spec"] = {"bundang_lead": agg(LEAD), "bundang_ctrl": agg(ctrl),
                   "daejeon_lead": agg(DJ)}

    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
