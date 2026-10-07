# -*- coding: utf-8 -*-
"""주별 전세 매물: 광고수 vs 실매물수(Σ1/same_addr_cnt) 동시 복원."""
import sqlite3, json
from datetime import date, timedelta
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite"); con.row_factory=sqlite3.Row
CX=[("184857","잠실르엘"),("180737","잠실래미안아이파크"),("22627","잠실엘스"),
    ("22746","리센츠"),("19127","트리지움"),("22675","파크리오"),
    ("15011","레이크팰리스"),("639","잠실주공5단지")]
def mondays(s,e):
    d=date.fromisoformat(s); d=d-timedelta(days=d.weekday()); out=[]; end=date.fromisoformat(e)
    while d<=end: out.append(d.isoformat()); d+=timedelta(days=7)
    return out
weeks=mondays("2026-05-18","2026-09-15")
ads={}; real={}
for cx,nm in CX:
    arts=con.execute("SELECT first_seen_date f, last_seen_date l, same_addr_cnt s FROM articles WHERE complex_no=? AND trade_type='B1'",(cx,)).fetchall()
    a_ser=[]; r_ser=[]
    for w in weeks:
        act=[x for x in arts if x["f"]<=w<=x["l"]]
        a_ser.append(len(act))
        r_ser.append(round(sum(1.0/x["s"] if (x["s"] and x["s"]>=1) else 1.0 for x in act),1))
    ads[nm]=a_ser; real[nm]=r_ser
out={"weeks":weeks,"ads":ads,"real":real}
open("/tmp/jamsil3.json","w").write(json.dumps(out,ensure_ascii=False))
print(f"{'단지':<14}{'광고 첫→끝':>16}{'실매물 첫→끝':>16}{'광고Δ%':>8}{'실매물Δ%':>9}")
for cx,nm in CX:
    a=ads[nm]; r=real[nm]
    ac=(a[-1]/a[0]-1)*100 if a[0] else 0; rc=(r[-1]/r[0]-1)*100 if r[0] else 0
    print(f"{nm:<14}{a[0]:>7}→{a[-1]:<7}{r[0]:>7.0f}→{r[-1]:<7.0f}{ac:>+7.0f}{rc:>+8.0f}")
