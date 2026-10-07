# -*- coding: utf-8 -*-
"""세제개편안 보도자료 — 1~3일차 지표 재산출 (첫 보도자료와 동일 방법).

  · 분위     = 최근 1년 실거래(해제 제외) 시군구별 평당가 중위값, 거래 100건 이상 219개를 5등분
  · 실질소멸 = 그날 사라진 매물(article_events DELISTED) 중 광고 기간만료(확인일자+31일)를 뺀 건수
  · 비교     = 직전 3주 같은 요일 평균
  · 정상대비 = 당일 순증가율 ÷ 3주 평균 순증가율 (재고는 일별 스냅샷 건수)
출력: /tmp/press_3days.csv · /tmp/press_top_3days.csv
"""
import csv
import sqlite3
import statistics as st
from collections import defaultdict
from datetime import date, timedelta

import pyarrow.parquet as pq

DB = "file:/opt/koczip/data/naverreal.sqlite?mode=ro"
ARC = "/opt/koczip/data/archive/listings/2026/{0:%m}/listings_{0:%Y-%m-%d}.parquet"
PYEONG, EXPIRE = 3.3058, 31
TRADE = {"A1": "매매", "B1": "전세", "B2": "월세"}
DAYS = {"1일차": date(2026, 8, 4), "2일차": date(2026, 8, 5), "3일차": date(2026, 8, 6)}

con = sqlite3.connect(DB, uri=True)

# ── 분위 ────────────────────────────────────────────────────────────────
px = defaultdict(list)
for sgg, ar, amt in con.execute(
        "select sgg_cd, excl_use_ar, deal_amount from transactions where is_cancelled=0 "
        "and deal_ymd>='2025-08-04' and deal_ymd<'2026-08-04' and excl_use_ar>0 and deal_amount>0"):
    if sgg:
        px[sgg].append(amt / (ar / PYEONG) / 10000)
MED = {s: st.median(v) for s, v in px.items() if len(v) >= 100}
order = sorted(MED, key=lambda s: -MED[s])
N = len(order)
QNAME = {1: "5분위", 2: "4분위", 3: "3분위", 4: "2분위", 5: "1분위"}
TIER = {s: QNAME[i + 1] for i in range(5) for s in order[N * i // 5:N * (i + 1) // 5]}

SIDO = {c[:2]: n for c, n in con.execute(
    "select cortar_no, cortar_name from regions where cortar_type='city'")}
SGGNM = {c[:5]: f"{SIDO.get(c[:2], '')} {n}".strip() for c, n in con.execute(
    "select cortar_no, cortar_name from regions where cortar_type='dvsn'")}
CXS = {}                                        # complex_no -> sgg
for cno, cortar in con.execute("select complex_no, cortar_no from complexes"):
    if cortar:
        CXS[cno] = cortar[:5]
print(f"[tier] 시군구 {N}개")

# ── 실질소멸 (article_events) ────────────────────────────────────────────
DEL_DATES = sorted({d - timedelta(days=7 * k) for d in DAYS.values() for k in (0, 1, 2, 3)})


def gone(d):
    """d일 실질소멸: (거래, 분위)->건수, (거래, sgg)->건수"""
    lim = (d - timedelta(days=EXPIRE)).strftime("%Y%m%d")
    q, s = defaultdict(int), defaultdict(int)
    for cno, tt, cy in con.execute(
            "select e.complex_no, e.trade_type, a.article_confirm_ymd "
            "from article_events e join articles a on a.article_no=e.article_no "
            "where e.event_date=? and e.event_type='DELISTED'", (d.isoformat(),)):
        t = TRADE.get(tt)
        if not t or (cy and cy <= lim):
            continue
        sgg = CXS.get(cno)
        q[(t, "전국")] += 1
        if sgg and sgg in TIER:
            q[(t, TIER[sgg])] += 1
        if sgg:
            s[(t, sgg)] += 1
    return q, s


def fresh(d):
    """d일 신규 등록: (거래, 분위)->건수, (거래, sgg)->건수"""
    q, s = defaultdict(int), defaultdict(int)
    for cno, tt in con.execute(
            "select complex_no, trade_type from article_events "
            "where event_date=? and event_type='NEW'", (d.isoformat(),)):
        t = TRADE.get(tt)
        if not t:
            continue
        sgg = CXS.get(cno)
        q[(t, "전국")] += 1
        if sgg and sgg in TIER:
            q[(t, TIER[sgg])] += 1
        if sgg:
            s[(t, sgg)] += 1
    return q, s


GONE = {d: gone(d) for d in DEL_DATES}
NEW = {d: fresh(d) for d in DEL_DATES}
con.close()

# ── 재고 (일별 스냅샷) ───────────────────────────────────────────────────
STOCK_DATES = sorted({d - timedelta(days=x) for d in DEL_DATES for x in (0, 1)})


def stock(d):
    t = pq.read_table(ARC.format(d), columns=["complex_no", "trade_type"])
    tt, cn = t.column("trade_type").to_pylist(), t.column("complex_no").to_pylist()
    q, s = defaultdict(int), defaultdict(int)
    for i in range(len(tt)):
        tr = TRADE.get(tt[i])
        if not tr:
            continue
        sgg = CXS.get(cn[i])
        q[(tr, "전국")] += 1
        if sgg and sgg in TIER:
            q[(tr, TIER[sgg])] += 1
        if sgg:
            s[(tr, sgg)] += 1
    return q, s


STOCK = {d: stock(d) for d in STOCK_DATES}
print("[stock] 완료")

QS = ("5분위", "4분위", "3분위", "2분위", "1분위", "전국")
with open("/tmp/press_3days.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow("일차,거래,구분,d3,d4,chg,dchg,n3,n4,nchg,inc3,inc4,stock".split(","))
    for label, d in DAYS.items():
        base = [d - timedelta(days=7 * k) for k in (3, 2, 1)]
        for t in ("매매", "전세", "월세"):
            for q in QS:
                k = (t, q)
                d4 = GONE[d][0][k]
                d3 = st.mean([GONE[b][0][k] for b in base])
                sc, sp = STOCK[d][0][k], STOCK[d - timedelta(days=1)][0][k]
                inc4 = sc - sp
                incs = [STOCK[b][0][k] - STOCK[b - timedelta(days=1)][0][k] for b in base]
                n4 = NEW[d][0][k]
                n3 = st.mean([NEW[b][0][k] for b in base])
                w.writerow([label, t, q, round(d3), d4, f"{(d4-d3)/d3*100:.1f}", round(d4 - d3),
                            round(n3), n4, f"{(n4-n3)/n3*100:.1f}" if n3 else "0.0",
                            round(st.mean(incs)), inc4, sc])

TOP10 = order[:10]
with open("/tmp/press_top_3days.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(("일차,지역,평당가만원,실질소멸_3주평균,실질소멸_당일,소멸증감,"
                "신규_3주평균,신규_당일,신규증감,매물수").split(","))
    for label, d in DAYS.items():
        base = [d - timedelta(days=7 * k) for k in (3, 2, 1)]
        for sgg in TOP10:
            d4 = GONE[d][1][("매매", sgg)]
            d3 = st.mean([GONE[b][1][("매매", sgg)] for b in base])
            n4 = NEW[d][1][("매매", sgg)]
            n3 = st.mean([NEW[b][1][("매매", sgg)] for b in base])
            w.writerow([label, SGGNM.get(sgg, sgg), round(MED[sgg]), round(d3), d4,
                        f"{(d4-d3)/d3*100:.1f}" if d3 else "0.0",
                        round(n3), n4, f"{(n4-n3)/n3*100:.1f}" if n3 else "0.0",
                        STOCK[d][1][("매매", sgg)]])
print("[done]")
