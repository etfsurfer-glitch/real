# -*- coding: utf-8 -*-
"""현재 등록 전월세 매물: 매물수(광고)·실매물수(중복제거)·광고배율. 지역×유형."""
import sqlite3, json
from collections import defaultdict
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite")

# 단지형 매물(articles, complex_no 有)은 complex_no로 지역. complexes.cortar_no 앞2자리=시도
# articles엔 지역이 직접 없음 → complex_no→complexes.cortar_no 조인
cx_reg={}
for cx,cort in con.execute("SELECT complex_no,cortar_no FROM complexes WHERE cortar_no IS NOT NULL"):
    s=(cort or "")[:2]
    cx_reg[cx] = "서울" if s=="11" else ("수도권" if s in("41","28") else ("지방" if s.isdigit() else None))

agg=defaultdict(lambda: defaultdict(float))  # (region,tt)->{ads,real}
q=con.execute("""SELECT complex_no, trade_type, same_addr_cnt FROM articles
    WHERE is_active=1 AND trade_type IN ('B1','B2')""")
for cx,tt,sac in q:
    reg=cx_reg.get(cx)
    if reg is None: continue
    for sc in (reg,"전국"):
        k=agg[(sc,tt)]
        k["ads"]+=1
        k["real"]+= 1.0/sac if (sac and sac>=1) else 1.0

def row(reg):
    b1=agg[(reg,"B1")]; b2=agg[(reg,"B2")]
    r1=b1["real"]; r2=b2["real"]
    return {
      "region":reg,
      "j_ads":int(b1["ads"]), "j_real":round(r1), "j_mult":round(b1["ads"]/r1,2) if r1 else 0,
      "w_ads":int(b2["ads"]), "w_real":round(r2), "w_mult":round(b2["ads"]/r2,2) if r2 else 0,
      "j_share_ads":round(b1["ads"]/(b1["ads"]+b2["ads"])*100,1) if (b1["ads"]+b2["ads"]) else 0,
      "j_share_real":round(r1/(r1+r2)*100,1) if (r1+r2) else 0,
    }
out={"snapshot":[row(r) for r in ["전국","서울","수도권","지방"]],
     "asof":con.execute("SELECT MAX(last_seen_date) FROM articles WHERE is_active=1").fetchone()[0]}
open("/tmp/listing.json","w").write(json.dumps(out,ensure_ascii=False))
for r in out["snapshot"]:
    print(f"[{r['region']}] 전세 매물{r['j_ads']:>7,} 실{r['j_real']:>6,} 배율{r['j_mult']} | "
          f"월세 매물{r['w_ads']:>7,} 실{r['w_real']:>6,} 배율{r['w_mult']} | "
          f"전세비중 광고{r['j_share_ads']}% 실매물{r['j_share_real']}%")
print("asof", out["asof"])
