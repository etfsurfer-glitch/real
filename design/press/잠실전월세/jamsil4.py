# -*- coding: utf-8 -*-
"""잠실: 전세 vs 월세 — ①실거래 월별 ②실매물 주별. 전환 vs 동반감소 판별."""
import sqlite3, json
from datetime import date, timedelta
from collections import defaultdict
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite"); con.row_factory=sqlite3.Row
CX=[("184857","잠실르엘"),("180737","잠실래미안아이파크"),("22627","잠실엘스"),
    ("22746","리센츠"),("19127","트리지움"),("22675","파크리오"),
    ("15011","레이크팰리스"),("639","잠실주공5단지")]
MATURE={"잠실엘스","리센츠","트리지움","파크리오","레이크팰리스","잠실주공5단지"}

# ① 월별 실거래: 전세 vs 월세 (2025-09~2026-09)
deal_monthly={}
for cx,nm in CX:
    mm=defaultdict(lambda:[0,0])
    for r in con.execute("SELECT deal_ymd, monthly_rent FROM rentals WHERE matched_complex_no=? AND deal_ymd>='2025-09-01'",(cx,)):
        k=r["deal_ymd"][:7]
        if (r["monthly_rent"] or 0)==0: mm[k][0]+=1
        else: mm[k][1]+=1
    deal_monthly[nm]={k:mm[k] for k in sorted(mm)}

# ② 주별 실매물: 전세(B1) vs 월세(B2)
def mondays(s,e):
    d=date.fromisoformat(s); d=d-timedelta(days=d.weekday()); out=[]; end=date.fromisoformat(e)
    while d<=end: out.append(d.isoformat()); d+=timedelta(days=7)
    return out
weeks=mondays("2026-05-18","2026-09-15")
def wreal(cx,tt):
    arts=con.execute("SELECT first_seen_date f,last_seen_date l,same_addr_cnt s FROM articles WHERE complex_no=? AND trade_type=?",(cx,tt)).fetchall()
    return [round(sum(1.0/x["s"] if (x["s"] and x["s"]>=1) else 1.0 for x in arts if x["f"]<=w<=x["l"]),1) for w in weeks]
listing_weekly={}
for cx,nm in CX:
    listing_weekly[nm]={"j":wreal(cx,"B1"),"w":wreal(cx,"B2")}

# 현재 스냅샷 월세 배율 보강
snap={}
for cx,nm in CX:
    w=con.execute("SELECT COUNT(*) a, SUM(1.0/CASE WHEN same_addr_cnt>=1 THEN same_addr_cnt ELSE 1 END) r FROM articles WHERE complex_no=? AND trade_type='B2' AND is_active=1",(cx,)).fetchone()
    snap[nm]={"w_ads":w["a"] or 0,"w_real":round(w["r"] or 0,1),"w_mult":round((w["a"] or 0)/w["r"],2) if w["r"] else 0}

out={"weeks":weeks,"deal_monthly":deal_monthly,"listing_weekly":listing_weekly,"snap":snap}
open("/tmp/jamsil4.json","w").write(json.dumps(out,ensure_ascii=False))

# 요약: 마스터 집계 — 전세 vs 월세 실거래 3개월 전후 + 매물 실매물 첫끝
def agg_deals(period0,period1):
    tot=[0,0]
    for nm in MATURE:
        for k,(j,w) in deal_monthly[nm].items():
            if period0<=k<=period1: tot[0]+=j; tot[1]+=w
    return tot
print("=== 잠실 기축6 실거래: 전세 vs 월세 ===")
for lab,(a,b) in [("2025 4Q(10~12)",agg_deals("2025-10","2025-12")),("2026 1Q(1~3)",agg_deals("2026-01","2026-03")),
                  ("2026 2Q(4~6)",agg_deals("2026-04","2026-06")),("2026 최근3M(7~9)",agg_deals("2026-07","2026-09"))]:
    t=a+b; print(f"  {lab:<16} 전세 {a:>4}  월세 {b:>4}  월세비중 {b/t*100:.0f}%" if t else f"  {lab}: 0")
print("\n=== 현재 매물 실매물: 전세 vs 월세(첫→끝 주) ===")
for cx,nm in CX:
    j=listing_weekly[nm]["j"]; w=listing_weekly[nm]["w"]
    print(f"  {nm:<14} 전세 {j[0]:>5.0f}→{j[-1]:<5.0f}  월세 {w[0]:>5.0f}→{w[-1]:<5.0f}")
