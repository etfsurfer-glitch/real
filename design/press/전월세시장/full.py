# -*- coding: utf-8 -*-
"""전월세 시장 종합 통계 — 1회 스캔. 반전세(한국부동산원 4분류) 포함. 사실지표만."""
import sqlite3, json
from collections import defaultdict
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite"); con.row_factory=None

def reg_of(s):
    s=(s or "")[:2]
    return "서울" if s=="11" else ("수도권" if s in("41","28") else (None if not s.isdigit() else "지방"))

SGG={"11680":"강남","11650":"서초","11710":"송파","11440":"마포","11170":"용산","11215":"광진","11305":"강북","11530":"구로","11740":"강동","11200":"성동","11110":"종로","11140":"중구","11350":"노원","11620":"관악","11500":"강서","11590":"동작","11470":"양천","11560":"영등포","11380":"은평","11410":"서대문","11230":"동대문","11260":"중랑","11290":"성북","11320":"도봉","11545":"금천"}

def cls_of(mr, dep):
    if mr==0: return "전세"
    if dep > mr*240: return "준전세"
    if dep > mr*12:  return "준월세"
    return "월세"

# 월별×스코프: 4분류 카운트 + 신규/갱신 + 갱신청구권 + 보증금/월세 합
mon=defaultdict(lambda: defaultdict(float))
# 자치구 반기: (period, sgg) -> 4분류 카운트
gu=defaultdict(lambda: defaultdict(int))
# 연도별 4분류(신규만)
yr=defaultdict(lambda: defaultdict(int))
# 보증금·월세 수준: 월별 서울 전세보증금합/건수, 월세(순월세+준월세) 보증금·월세 합/건수
lvl=defaultdict(lambda: defaultdict(float))

cur=con.execute("""SELECT deal_year,deal_month,sgg_cd,monthly_rent,deposit,contract_type,use_rr_right,deal_ymd
    FROM rentals WHERE deal_ymd>='2023-06-01'""")
for y,m,sgg,mr,dep,ct,rr,dymd in cur:
    reg=reg_of(sgg)
    if reg is None: continue
    mr=mr or 0; dep=dep or 0
    cls=cls_of(mr,dep)
    ym="%04d-%02d"%(y,m)
    ct=ct or ""; rr=(rr or "").strip()
    for sc in (reg,"전국"):
        k=mon[(ym,sc)]
        k["tot"]+=1; k[cls]+=1
        if "신규" in ct: k["new"]+=1
        elif "갱신" in ct:
            k["renew"]+=1
            if rr=="사용": k["rr_used"]+=1
    # 수준(서울, 만원 환산은 후처리)
    ks=lvl[(ym,reg)]
    if cls=="전세":
        ks["j_dep_sum"]+=dep; ks["j_cnt"]+=1
    elif mr>0:
        ks["w_dep_sum"]+=dep; ks["w_rent_sum"]+=mr; ks["w_cnt"]+=1
    # 자치구 반기 (서울)
    if sgg in SGG:
        half = "%d-%s"%(y, "H1" if m<=6 else "H2")
        gu[(half,sgg)][cls]+=1
        gu[(half,sgg)]["tot"]+=1
    # 연도별 신규
    if "신규" in ct:
        yr[y][cls]+=1; yr[y]["tot"]+=1

months=sorted({k[0] for k in mon})
scopes=["전국","서울","수도권","지방"]
def pack(k):
    t=k["tot"]
    if not t: return None
    d={"ym":None,"tot":int(t)}
    for c in ("전세","준전세","준월세","월세"):
        d[c]=int(k[c]); d[c+"_p"]=round(k[c]/t*100,1)
    d["banjeonse_p"]=round((k["준전세"])/t*100,1)  # 준전세=반전세
    d["wolse_all_p"]=round((k["준전세"]+k["준월세"]+k["월세"])/t*100,1)
    d["new"]=int(k["new"]); d["renew"]=int(k["renew"])
    d["renew_p"]=round(k["renew"]/t*100,1)
    d["rr_used"]=int(k["rr_used"])
    d["rr_of_renew_p"]=round(k["rr_used"]/k["renew"]*100,1) if k["renew"] else 0
    return d
series={sc:[] for sc in scopes}
for ym in months:
    for sc in scopes:
        p=pack(mon[(ym,sc)])
        if p: p["ym"]=ym
        series[sc].append(p)

# 수준 시계열(만원)
levels={sc:[] for sc in scopes}
for ym in months:
    for sc in scopes:
        k=lvl[(ym,sc)]
        row={"ym":ym,
          "jeonse_dep": round(k["j_dep_sum"]/k["j_cnt"]/10000) if k["j_cnt"] else None,   # 만원
          "wolse_dep":  round(k["w_dep_sum"]/k["w_cnt"]/10000) if k["w_cnt"] else None,     # 만원
          "wolse_rent": round(k["w_rent_sum"]/k["w_cnt"]/10000,1) if k["w_cnt"] else None}  # 만원(원/10000)
        levels[sc].append(row)

# 자치구 반기 비교 2024H1 vs 2026H1
gurows=[]
for sgg,nm in SGG.items():
    a=gu[("2024-H1",sgg)]; b=gu[("2026-H1",sgg)]
    if a["tot"]>50:
        gurows.append({"gu":nm,
            "j24":a["전세"],"j26":b["전세"],"jchg":round((b["전세"]/a["전세"]-1)*100) if a["전세"] else 0,
            "jp24":round(a["전세"]/a["tot"]*100),"jp26":round(b["전세"]/b["tot"]*100),
            "bp24":round(a["준전세"]/a["tot"]*100),"bp26":round(b["준전세"]/b["tot"]*100),
            "tot24":a["tot"],"tot26":b["tot"],"totchg":round((b["tot"]/a["tot"]-1)*100)})
gurows.sort(key=lambda x:x["jchg"])

yearly=[]
for y in sorted(yr):
    k=yr[y]; t=k["tot"]
    yearly.append({"y":y,"tot":t,
      "전세":k["전세"],"준전세":k["준전세"],"준월세":k["준월세"],"월세":k["월세"],
      "전세_p":round(k["전세"]/t*100,1),"준전세_p":round(k["준전세"]/t*100,1),
      "준월세_p":round(k["준월세"]/t*100,1),"월세_p":round(k["월세"]/t*100,1)})

out={"months":months,"series":series,"levels":levels,"gurows":gurows,"yearly":yearly,
     "meta":{"rr_note":"갱신청구권 사용은 갱신계약 중 use_rr_right='사용'"}}
open("/tmp/full.json","w").write(json.dumps(out,ensure_ascii=False))
# 콘솔 요약
print("months",months[0],"~",months[-1],len(months))
print("월세 평균(만원) 서울 최근:", [ (levels['서울'][i]['ym'],levels['서울'][i]['wolse_rent']) for i in range(-3,0)])
print("전국 연도 4분류%:")
for r in yearly: print("  ",r["y"],"전세",r["전세_p"],"준전세",r["준전세_p"],"준월세",r["준월세_p"],"월세",r["월세_p"])
print("전국 최근월 구성:", pack(mon[(months[-2],"전국")]))
