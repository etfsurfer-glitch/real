# -*- coding: utf-8 -*-
"""잠실 주요단지 전세: 매물(광고/실매물/배율) + 실거래(건수/가격/월별흐름)."""
import sqlite3, json
from collections import defaultdict
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite"); con.row_factory=sqlite3.Row

CX=[  # (complex_no, 표기명, 요청/확대, 세대수)
 ("184857","잠실르엘","요청",1865),
 ("180737","잠실래미안아이파크","요청",2678),
 ("22627","잠실엘스","요청",5678),
 ("22746","리센츠","요청",5563),
 ("19127","트리지움","요청",3696),
 ("22675","파크리오","요청",6864),
 ("15011","레이크팰리스","확대",2678),
 ("639","잠실주공5단지","확대",3930),
]

def listing(cx, tt):
    """is_active=1 매물수(광고)·실매물수(Σ1/same_addr_cnt)."""
    ads=real=0
    for sac, in con.execute("SELECT same_addr_cnt FROM articles WHERE complex_no=? AND trade_type=? AND is_active=1",(cx,tt)):
        ads+=1; real+= 1.0/sac if (sac and sac>=1) else 1.0
    return ads, real

def rent_recent(cx):
    """전세(월세0) 실거래: 최근3개월·6개월 건수, 보증금 중위(만원), 최근계약일, 월별 12개월."""
    rows=con.execute("SELECT deal_ymd, deposit, excl_use_ar FROM rentals "
        "WHERE matched_complex_no=? AND monthly_rent=0 AND deal_ymd>='2025-09-01' ORDER BY deal_ymd",(cx,)).fetchall()
    m3=[r for r in rows if r["deal_ymd"]>='2026-07-01']
    m6=[r for r in rows if r["deal_ymd"]>='2026-04-01']
    def med(rs):
        v=sorted(r["deposit"] for r in rs)
        return round(v[len(v)//2]/10000) if v else None   # 만원
    monthly=defaultdict(int)
    for r in rows: monthly[r["deal_ymd"][:7]]+=1
    last=con.execute("SELECT MAX(deal_ymd) FROM rentals WHERE matched_complex_no=? AND monthly_rent=0",(cx,)).fetchone()[0]
    return {"n3":len(m3),"n6":len(m6),"med3":med(m3),"med6":med(m6),"last":last,
            "monthly":dict(sorted(monthly.items()))}

out=[]
for cx,nm,tag,hh in CX:
    j_ads,j_real=listing(cx,"B1"); w_ads,w_real=listing(cx,"B2"); s_ads,s_real=listing(cx,"A1")
    rr=rent_recent(cx)
    out.append({"cx":cx,"name":nm,"tag":tag,"hh":hh,
        "j_ads":j_ads,"j_real":round(j_real,1),"j_mult":round(j_ads/j_real,2) if j_real else 0,
        "w_ads":w_ads,"w_real":round(w_real,1),
        "sale_real":round(s_real,1),
        **{("rt_"+k):v for k,v in rr.items()}})

open("/tmp/jamsil.json","w").write(json.dumps(out,ensure_ascii=False))
print(f"{'단지':<14}{'세대':>5}{'전세매물':>7}{'실매물':>7}{'배율':>6}{'월세실':>7}{'전세실거래3M':>10}{'보증금중위':>9}{'최근':>12}")
for r in out:
    print(f"{r['name']:<14}{r['hh']:>5}{r['j_ads']:>7}{r['j_real']:>7.0f}{r['j_mult']:>6}{r['w_real']:>7.0f}"
          f"{r['rt_n3']:>10}{(r['rt_med3'] or 0):>9,}{str(r['rt_last']):>13}")
