# -*- coding: utf-8 -*-
"""차트용 정제 JSON + 검증(수도권/지방 전세%, 신고지연, 갱신율)"""
import sqlite3, json
from collections import defaultdict
con=sqlite3.connect("/opt/koczip/data/naverreal.sqlite"); con.row_factory=sqlite3.Row
def reg_of(s):
    s=(s or "")[:2]
    return "서울" if s=="11" else ("수도권" if s in("41","28") else ("기타" if not s.isdigit() else "지방"))

# 월별 지역별: 전세건수/월세건수/신규건수/갱신건수/갱신청구권사용
q=con.execute("""SELECT deal_year y,deal_month m,sgg_cd,monthly_rent mr,contract_type ct,use_rr_right rr
    FROM rentals WHERE deal_ymd>='2022-01-01'""")
a=defaultdict(lambda:defaultdict(int))
for r in q:
    reg=reg_of(r["sgg_cd"]);
    if reg=="기타":continue
    ym=f"{r['y']:04d}-{r['m']:02d}"
    for scope in (reg,"전국"):
        k=a[(ym,scope)]; k["tot"]+=1
        if (r["mr"] or 0)==0: k["j"]+=1
        else: k["w"]+=1
        ct=r["ct"] or ""
        if "신규" in ct: k["new"]+=1
        elif "갱신" in ct:
            k["renew"]+=1
            if (r["rr"] or "").strip() in("사용","1","Y","y","true"): k["rr"]+=1
months=sorted({k[0] for k in a})
scopes=["전국","서울","수도권","지방"]
mon={s:[] for s in scopes}
for ym in months:
    for s in scopes:
        k=a[(ym,s)]
        if not k["tot"]: mon[s].append(None); continue
        mon[s].append({"ym":ym,"tot":k["tot"],"jeonse_pct":round(k["j"]/k["tot"]*100,1),
            "wolse_pct":round(k["w"]/k["tot"]*100,1),"jeonse":k["j"],"wolse":k["w"],
            "renew_pct":round(k["renew"]/k["tot"]*100,1) if k["tot"] else 0})
# 신고지연 진단: 최근 6개월 전국 tot
diag=[(m, a[(m,"전국")]["tot"]) for m in months[-6:]]

# 서울 자치구 랭킹: 2024상 vs 2026상 전세계약 감소율 + 월세비중 변화
SGG={"11680":"강남","11650":"서초","11710":"송파","11440":"마포","11170":"용산","11215":"광진","11305":"강북","11530":"구로","11740":"강동","11200":"성동","11110":"종로","11140":"중구","11350":"노원","11620":"관악","11500":"강서","11590":"동작","11470":"양천","11560":"영등포","11380":"은평","11410":"서대문","11230":"동대문","11260":"중랑","11290":"성북","11320":"도봉","11545":"금천"}
def gu(y0,y1):
    q=con.execute("""SELECT sgg_cd,SUM(CASE WHEN monthly_rent=0 THEN 1 ELSE 0 END) j,COUNT(*) t
        FROM rentals WHERE sgg_cd LIKE '11%' AND deal_ymd BETWEEN ? AND ? GROUP BY sgg_cd""",(y0,y1))
    return {r["sgg_cd"]:(r["j"],r["t"]) for r in q}
g24=gu("2024-01-01","2024-06-30"); g26=gu("2026-01-01","2026-06-30")
gurank=[]
for sgg,nm in SGG.items():
    j24,t24=g24.get(sgg,(0,0)); j26,t26=g26.get(sgg,(0,0))
    if j24>50:
        gurank.append({"gu":nm,"j24":j24,"j26":j26,"chg":round((j26/j24-1)*100),
            "w24":round((t24-j24)/t24*100) if t24 else 0,"w26":round((t26-j26)/t26*100) if t26 else 0})
gurank.sort(key=lambda x:x["chg"])

out={"months":months,"monthly":mon,"gurank":gurank,"diag":diag,
     "yearly":[dict(r) for r in con.execute("""SELECT deal_year y,
        SUM(CASE WHEN monthly_rent=0 THEN 1 ELSE 0 END) j, COUNT(*) t
        FROM rentals WHERE contract_type LIKE '%신규%' AND deal_year>=2022 GROUP BY y ORDER BY y""")]}
open("/tmp/chart.json","w").write(json.dumps(out,ensure_ascii=False))
print("months",len(months),months[0],months[-1])
print("신고지연 진단(최근6개월 전국 계약수):",diag)
print("전국 전세% 흐름:", [ (mon["전국"][i]["ym"],mon["전국"][i]["jeonse_pct"]) for i in range(0,len(months),6)])
print("수도권 전세% 최근:", [(x["ym"],x["jeonse_pct"]) for x in mon["수도권"][-4:]])
print("지방 전세% 최근:", [(x["ym"],x["jeonse_pct"]) for x in mon["지방"][-4:]])
