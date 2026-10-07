# -*- coding: utf-8 -*-
"""잠실 단지: ①평형(전용㎡) 밴드별 전세 매물·실거래 ②주별 전세 매물(호가) 흐름 복원."""
import sqlite3, json
from datetime import date, timedelta
from collections import defaultdict
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite"); con.row_factory=sqlite3.Row

CX=[("184857","잠실르엘"),("180737","잠실래미안아이파크"),("22627","잠실엘스"),
    ("22746","리센츠"),("19127","트리지움"),("22675","파크리오"),
    ("15011","레이크팰리스"),("639","잠실주공5단지")]

def band(m2):
    if m2 is None: return None
    if m2<=66: return "59㎡대"
    if m2<=99: return "84㎡대"
    return "대형(100㎡+)"

# ── ① 평형 밴드별: 전세 매물(ads/real/mult) + 전세 실거래 3M(건수/중위) ──
bands=[]
for cx,nm in CX:
    agg=defaultdict(lambda: defaultdict(float))
    for r in con.execute("SELECT area2_m2 a, same_addr_cnt sac FROM articles WHERE complex_no=? AND trade_type='B1' AND is_active=1",(cx,)):
        b=band(r["a"])
        if b is None: continue
        agg[b]["ads"]+=1; agg[b]["real"]+= 1.0/r["sac"] if (r["sac"] and r["sac"]>=1) else 1.0
    deal=defaultdict(list)
    for r in con.execute("SELECT excl_use_ar a, deposit d FROM rentals WHERE matched_complex_no=? AND monthly_rent=0 AND deal_ymd>='2026-07-01'",(cx,)):
        b=band(r["a"])
        if b: deal[b].append(r["d"])
    for b in ["59㎡대","84㎡대","대형(100㎡+)"]:
        a=agg[b]; ds=sorted(deal[b])
        if a["ads"]==0 and not ds: continue
        bands.append({"cx":cx,"name":nm,"band":b,
            "j_ads":int(a["ads"]),"j_real":round(a["real"],1),
            "j_mult":round(a["ads"]/a["real"],2) if a["real"] else 0,
            "rt_n3":len(ds),"rt_med3":round(ds[len(ds)//2]/10000) if ds else None})

# ── ② 주별 활성 전세 매물(광고) 복원: first_seen<=주 && last_seen>=주 ──
def mondays(s,e):
    d=date.fromisoformat(s); d=d-timedelta(days=d.weekday()); out=[]
    end=date.fromisoformat(e)
    while d<=end: out.append(d.isoformat()); d+=timedelta(days=7)
    return out
weeks=mondays("2026-05-18","2026-09-15")
weekly={}
for cx,nm in CX:
    arts=con.execute("SELECT first_seen_date f, last_seen_date l FROM articles WHERE complex_no=? AND trade_type='B1'",(cx,)).fetchall()
    ser=[]
    for w in weeks:
        c=sum(1 for a in arts if a["f"]<=w<=a["l"])
        ser.append(c)
    weekly[nm]=ser

out={"bands":bands,"weeks":weeks,"weekly":weekly}
open("/tmp/jamsil2.json","w").write(json.dumps(out,ensure_ascii=False))

print("=== 평형 밴드별(요약) ===")
for cx,nm in CX:
    rows=[b for b in bands if b["cx"]==cx]
    print(f"[{nm}]")
    for b in rows:
        print(f"   {b['band']:<12} 광고{b['j_ads']:>4} 실매물{b['j_real']:>6.1f} 배율{b['j_mult']:>5} | 실거래3M {b['rt_n3']:>3} 중위 {b['rt_med3'] or '-'}")
print("\n=== 주별 활성 전세매물(첫·끝) ===")
for nm,ser in weekly.items():
    print(f"   {nm:<14} {weeks[0]}:{ser[0]:>4}  →  {weeks[-1]}:{ser[-1]:>4}  (min {min(ser)} max {max(ser)})")
