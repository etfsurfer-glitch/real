# -*- coding: utf-8 -*-
"""1기 신도시 선도지구 기사용 통계.

선도지구 지정이 실거래가에 남긴 자국을 대조군과 견줘 뽑는다.
  · 분당 1차(2024-11-27 발표) 3개 구역 vs 같은 분당의 비선정 노후단지
  · 대전 둔산 13·14구역(2026-07-15 발표) vs 대전 서구 평균
  · 선도지구 단지들의 용적률·세대수·준공연도 공통점 → 다음 후보 조건

해제거래(is_cancelled=1)는 전부 뺀다. 넣으면 가짜 신고가가 섞인다.
"""
from __future__ import annotations
import json, sqlite3, sys
from pathlib import Path

DB = "/opt/koczip/data/naverreal.sqlite"
PYEONG = 3.3058
ANNOUNCE_1ST = "2024-11-27"      # 1기 신도시 1차 선도지구 발표
ANNOUNCE_DJ = "2026-07-15"       # 대전 둔산·송촌 선도지구 발표

# 분당 1차 선도지구 3개 구역(단지 단위로 풀어 쓴 것)
BUNDANG = {
    "샛별마을(동성·라이프·삼부·우방)": [1618, 1633, 1654, 1663],
    "양지마을(금호·청구·한양)": [1954, 1980, 100754, 1994, 101537, 101536],
    "시범단지(우성·현대)": [1840, 1923],
}
LEAD_IDS = [n for v in BUNDANG.values() for n in v]


def conn():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def ppy_series(c, ids, lo, hi):
    """월별 평당가(만원)·거래건수. 전용면적 기준."""
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    rows = c.execute(f"""
        SELECT substr(deal_ymd,1,7) m,
               AVG(deal_amount / (excl_use_ar/{PYEONG}) / 10000.0) ppy,
               COUNT(*) n
        FROM transactions
        WHERE matched_complex_no IN ({ph})
          AND is_cancelled=0 AND excl_use_ar>0
          AND deal_ymd>=? AND deal_ymd<=?
        GROUP BY m ORDER BY m
    """, (*ids, lo, hi)).fetchall()
    return {r["m"]: {"ppy": round(r["ppy"], 1), "n": r["n"]} for r in rows}


def window(c, ids, start, end):
    """구간 평균 평당가·거래건수."""
    if not ids:
        return None
    ph = ",".join("?" * len(ids))
    r = c.execute(f"""
        SELECT AVG(deal_amount / (excl_use_ar/{PYEONG}) / 10000.0) ppy, COUNT(*) n
        FROM transactions
        WHERE matched_complex_no IN ({ph})
          AND is_cancelled=0 AND excl_use_ar>0
          AND deal_ymd>=? AND deal_ymd<?
    """, (*ids, start, end)).fetchone()
    return {"ppy": round(r["ppy"], 1) if r["ppy"] else None, "n": r["n"]}


def main():
    c = conn()
    out: dict = {}

    # ── 대조군: 분당구 1988~1996 준공, 300세대 이상, 선도지구 제외 ──
    ph = ",".join("?" * len(LEAD_IDS))
    ctrl = [r[0] for r in c.execute(f"""
        SELECT complex_no FROM complexes
        WHERE cortar_no LIKE '41135%' AND total_household_count>=300
          AND substr(use_approve_ymd,1,4) BETWEEN '1988' AND '1996'
          AND complex_no NOT IN ({ph})
    """, LEAD_IDS)]
    out["control_count"] = len(ctrl)

    # ── 1) 분당: 발표 전후 ──
    pre = ("2024-05-27", ANNOUNCE_1ST)        # 발표 직전 6개월
    post = (ANNOUNCE_1ST, "2025-05-27")       # 발표 직후 6개월
    now = ("2026-04-19", "2026-10-19")        # 최근 6개월
    out["bundang"] = {
        "lead": {"pre": window(c, LEAD_IDS, *pre), "post": window(c, LEAD_IDS, *post),
                 "now": window(c, LEAD_IDS, *now)},
        "control": {"pre": window(c, ctrl, *pre), "post": window(c, ctrl, *post),
                    "now": window(c, ctrl, *now)},
    }
    out["bundang"]["by_zone"] = {
        k: {"pre": window(c, v, *pre), "post": window(c, v, *post), "now": window(c, v, *now)}
        for k, v in BUNDANG.items()
    }
    out["bundang"]["series_lead"] = ppy_series(c, LEAD_IDS, "2024-01-01", "2026-10-31")
    out["bundang"]["series_ctrl"] = ppy_series(c, ctrl, "2024-01-01", "2026-10-31")

    # ── 2) 대전 둔산 ──
    dj_ids = [r[0] for r in c.execute("""
        SELECT complex_no FROM complexes
        WHERE cortar_no LIKE '30170%' AND dong_name LIKE '둔산%'
          AND (complex_name LIKE '%크로바%' OR complex_name LIKE '%목련%'
               OR complex_name LIKE '%한가람%' OR complex_name LIKE '%공작%')
          AND total_household_count>=300
    """)]
    dj_ctrl = [r[0] for r in c.execute(f"""
        SELECT complex_no FROM complexes
        WHERE cortar_no LIKE '30170%' AND total_household_count>=300
          AND substr(use_approve_ymd,1,4) BETWEEN '1990' AND '1999'
          AND complex_no NOT IN ({",".join("?"*len(dj_ids)) or "''"})
    """, dj_ids)] if dj_ids else []
    dpre = ("2026-01-15", ANNOUNCE_DJ)
    dpost = (ANNOUNCE_DJ, "2026-10-19")
    out["daejeon"] = {
        "lead_ids": dj_ids, "ctrl_count": len(dj_ctrl),
        "lead": {"pre": window(c, dj_ids, *dpre), "post": window(c, dj_ids, *dpost)},
        "control": {"pre": window(c, dj_ctrl, *dpre), "post": window(c, dj_ctrl, *dpost)},
        "series_lead": ppy_series(c, dj_ids, "2025-07-01", "2026-10-31"),
    }

    # ── 3) 선도지구 단지 스펙(공통점 찾기용) ──
    def spec(ids):
        ph = ",".join("?" * len(ids))
        return [dict(r) for r in c.execute(f"""
            SELECT complex_name, total_household_count hh, substr(use_approve_ymd,1,4) y,
                   batl_ratio vol, btl_ratio cov, dong_name, complex_no
            FROM complexes WHERE complex_no IN ({ph}) ORDER BY total_household_count DESC
        """, ids)]
    out["spec_lead"] = spec(LEAD_IDS)
    out["spec_daejeon"] = spec(dj_ids) if dj_ids else []

    # 대조군 스펙 평균(선도지구와 뭐가 다른가)
    r = c.execute(f"""
        SELECT AVG(total_household_count), AVG(batl_ratio), AVG(btl_ratio),
               AVG(CAST(substr(use_approve_ymd,1,4) AS INT)), COUNT(*)
        FROM complexes WHERE complex_no IN ({",".join("?"*len(ctrl))})
    """, ctrl).fetchone()
    out["spec_control_avg"] = {"hh": round(r[0], 0), "vol": round(r[1], 1),
                               "cov": round(r[2], 1), "year": round(r[3], 1), "n": r[4]}

    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
