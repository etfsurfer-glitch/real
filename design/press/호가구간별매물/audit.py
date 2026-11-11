# 점검용(2026-11-11): 인접일 출렁임·경계값(정확히 N억)·미매핑·고가 이상치·분양권 호가·공개 집계 대조. 박스에서 9/1·10/1 등은 nfind 에서 /mnt/backup/tmp_hoga_band 로 받아 돌리고 지운다.
import os, sqlite3, statistics as st, json
from collections import defaultdict, Counter
import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq
T="/mnt/backup/tmp_hoga_band"; ARC="/opt/koczip/data/archive/listings"; POL="/mnt/backup/policy_2026_tax_reform/daily"
def path(d):
    for p in (f"{POL}/{d}/listings_{d}.parquet", f"{T}/listings_{d}.parquet", f"{ARC}/{d[:4]}/{d[5:7]}/listings_{d}.parquet"):
        if os.path.exists(p): return p
DATES=["2026-08-02","2026-08-03","2026-08-04","2026-08-31","2026-09-01","2026-09-02","2026-09-30","2026-10-01","2026-10-02","2026-11-10","2026-11-11"]
db=sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro",uri=True)
CX={str(c):(cn,t) for c,cn,t in db.execute("SELECT complex_no,cortar_no,real_estate_type FROM complexes")}
SEOUL={c for c,(cn,t) in CX.items() if cn and str(cn).startswith("11")}
NAME={str(c):n for c,n in db.execute("SELECT complex_no,complex_name FROM complexes WHERE substr(cortar_no,1,2)='11'")}
TYPES=["APT","JGC","ABYG"]
COLS=["complex_no","same_addr_cnt","trade_type","real_estate_type","area2_m2","deal_or_warrant_price","cortar_no"]
R={}
for d in DATES:
    p=path(d)
    if not p: print(d,"없음"); continue
    sch=pq.read_schema(p).names
    cols=[c for c in COLS if c in sch]
    t=pq.read_table(p,columns=cols)
    t=t.filter(pc.equal(t["trade_type"],"A1")); x=t.to_pydict(); del t
    r={"obj":0.0,"ad":0,"edge":Counter(),"edge_obj":defaultdict(float),"unmapped_ad":0,"unmapped_seoulcortar":0,"type":Counter(),"top":[], "abyg":[], "zero":0, "cplx":set()}
    for i,pz in enumerate(x["deal_or_warrant_price"]):
        cx=str(x["complex_no"][i]); ty=x["real_estate_type"][i]
        if ty not in TYPES: continue
        if cx not in CX:
            r["unmapped_ad"]+=1
            if "cortar_no" in x and str(x["cortar_no"][i] or "").startswith("11"): r["unmapped_seoulcortar"]+=1
            continue
        if cx not in SEOUL: continue
        if not pz or pz<=0: r["zero"]+=1; continue
        w=1/max(x["same_addr_cnt"][i] or 1,1)
        r["obj"]+=w; r["ad"]+=1; r["type"][ty]+=w; r["cplx"].add(cx)
        e=pz/1e8
        if e>=10 and e<=50 and abs(e/5-round(e/5))<1e-9: r["edge"][int(round(e))]+=1; r["edge_obj"][int(round(e))]+=w
        if e>=150: r["top"].append((round(e,1),NAME.get(cx),x["area2_m2"][i]))
        if ty=="ABYG": r["abyg"].append(e)
    R[d]=r
    print(d, "실매물 %.0f 광고 %d 단지 %d 가격0 %d 미매핑광고(전국) %d 미매핑서울cortar %d" % (r["obj"],r["ad"],len(r["cplx"]),r["zero"],r["unmapped_ad"],r["unmapped_seoulcortar"]), {k:round(v) for k,v in r["type"].items()}, flush=True)
for d in ["2026-08-03","2026-09-01","2026-10-01","2026-11-11"]:
    r=R[d]; print(d,"경계(정확히 N억) 실매물:",{k:round(r["edge_obj"][k]) for k in sorted(r["edge_obj"])})
    print("  150억 이상 광고", len(r["top"]), sorted(r["top"],reverse=True)[:8])
    a=r["abyg"]; print("  분양권 호가 중앙 %.1f억 n=%d" % (st.median(a) if a else 0, len(a)))
# 공개 집계(complex_daily_agg) 대조
for d in ["2026-08-03","2026-09-01","2026-10-01","2026-11-11"]:
    rows=db.execute("SELECT complex_no, sum(listing_count), sum(unit_count) FROM complex_daily_agg WHERE snapshot_date=? AND trade_type='A1' GROUP BY complex_no",(d,)).fetchall()
    ad=sum(r[1] or 0 for r in rows if str(r[0]) in SEOUL and CX[str(r[0])][1] in TYPES)
    ob=sum(r[2] or 0 for r in rows if str(r[0]) in SEOUL and CX[str(r[0])][1] in TYPES)
    ad2=sum(r[1] or 0 for r in rows if str(r[0]) in SEOUL); ob2=sum(r[2] or 0 for r in rows if str(r[0]) in SEOUL)
    print(d,"agg(단지유형 APT/JGC/ABYG) 광고",ad,"실매물 %.0f" % ob, "| agg 서울 전 유형 광고",ad2,"실매물 %.0f"%ob2)
db.close()
