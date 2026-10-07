# -*- coding: utf-8 -*-
"""전월세 '씨 마름' 보도자료 데이터 백본"""
import sqlite3, json
con = sqlite3.connect("/opt/koczip/data/naverreal.sqlite")
con.row_factory = sqlite3.Row
out = {}

def region_of(sgg):
    s = (sgg or "")[:2]
    if s == "11": return "서울"
    if s in ("41","28"): return "수도권(경인)"
    if not s.isdigit(): return "기타"
    return "지방"

# ── 1. 전월세 실거래 월별 추이 (2023-06 ~ 2026-09), 지역 x 전세/월세 x 신규/갱신 ──
q = con.execute("""SELECT deal_year y, deal_month m, sgg_cd, monthly_rent mr, contract_type ct
    FROM rentals WHERE deal_ymd>='2023-06-01' AND deal_ymd<='2026-09-30'""")
# agg[(y,m,region)] = {jeonse, wolse, new, renew, new_jeonse, tot}
from collections import defaultdict
agg = defaultdict(lambda: defaultdict(int))
for r in q:
    reg = region_of(r["sgg_cd"])
    ym = f"{r['y']:04d}-{r['m']:02d}"
    a = agg[(ym, reg)]
    a["tot"] += 1
    is_j = (r["mr"] or 0) == 0
    if is_j: a["jeonse"] += 1
    else: a["wolse"] += 1
    ct = r["ct"] or ""
    if "신규" in ct: a["new"] += 1
    elif "갱신" in ct: a["renew"] += 1
    if is_j and "신규" in ct: a["new_jeonse"] += 1

months = sorted({k[0] for k in agg})
regions = ["서울","수도권(경인)","지방"]
series = {reg: [] for reg in regions}
for ym in months:
    for reg in regions:
        a = agg[(ym,reg)]
        series[reg].append({"ym":ym,"tot":a["tot"],"jeonse":a["jeonse"],"wolse":a["wolse"],
                            "new":a["new"],"renew":a["renew"],"new_jeonse":a["new_jeonse"],
                            "wolse_pct": round(a["wolse"]/a["tot"]*100,1) if a["tot"] else 0,
                            "jeonse_pct": round(a["jeonse"]/a["tot"]*100,1) if a["tot"] else 0})
out["rent_monthly"] = {"months":months, "series":series}

# ── 2. 서울 자치구별: 2023 vs 2026 상반기 전세 신규계약 건수 비교 ──
def half_counts(y0,m0,y1,m1):
    q = con.execute("""SELECT sgg_cd, SUM(CASE WHEN monthly_rent=0 THEN 1 ELSE 0 END) jeonse,
        SUM(CASE WHEN monthly_rent>0 THEN 1 ELSE 0 END) wolse, COUNT(*) tot
        FROM rentals WHERE sgg_cd LIKE '11%' AND deal_ymd BETWEEN ? AND ? GROUP BY sgg_cd""",
        (f"{y0}-{m0:02d}-01", f"{y1}-{m1:02d}-31"))
    return {r["sgg_cd"]:{"jeonse":r["jeonse"],"wolse":r["wolse"],"tot":r["tot"]} for r in q}
h2023 = half_counts(2023,6,2023,12)   # 2023 하반기 (데이터 시작)
h2024 = half_counts(2024,1,2024,6)
h2025 = half_counts(2025,1,2025,6)
h2026 = half_counts(2026,1,2026,6)
out["seoul_gu"] = {"h2024":h2024,"h2025":h2025,"h2026":h2026,"h2023h2":h2023}

# ── 3. 매물 호가 공급 (region_daily_agg): 주별 전세(B1)/월세(B2) 매물수, 지역별 ──
# cortar_no 앞2자리 = 시도
q = con.execute("""SELECT snapshot_date d, SUBSTR(cortar_no,1,2) sido, trade_type tt, SUM(listing_count) c
    FROM region_daily_agg WHERE trade_type IN ('B1','B2') GROUP BY d, sido, tt""")
supply = defaultdict(lambda: defaultdict(int))  # (date, region, tt)
for r in q:
    reg = {"11":"서울"}.get(r["sido"], "수도권(경인)" if r["sido"] in ("41","28") else "지방")
    supply[(r["d"], reg, r["tt"])] = r["c"]
sdates = sorted({k[0] for k in supply})
sup_series = {}
for reg in ["서울","수도권(경인)","지방","전국"]:
    sup_series[reg] = []
for d in sdates:
    natB1=natB2=0
    for reg in ["서울","수도권(경인)","지방"]:
        b1=supply[(d,reg,"B1")]; b2=supply[(d,reg,"B2")]
        natB1+=b1; natB2+=b2
        sup_series[reg].append({"d":d,"B1":b1,"B2":b2})
    sup_series["전국"].append({"d":d,"B1":natB1,"B2":natB2})
out["supply_daily"] = {"dates":sdates, "series":sup_series}

# ── 4. 전세 비중 장기 하락 확인: 연도별 전국 전세 vs 월세 신규계약 ──
q = con.execute("""SELECT deal_year y, SUM(CASE WHEN monthly_rent=0 THEN 1 ELSE 0 END) jeonse,
    SUM(CASE WHEN monthly_rent>0 THEN 1 ELSE 0 END) wolse, COUNT(*) tot
    FROM rentals WHERE contract_type LIKE '%신규%' GROUP BY deal_year ORDER BY y""")
out["yearly_new"] = [{"y":r["y"],"jeonse":r["jeonse"],"wolse":r["wolse"],"tot":r["tot"],
    "jeonse_pct":round(r["jeonse"]/r["tot"]*100,1) if r["tot"] else 0} for r in q]

print(json.dumps(out, ensure_ascii=False))
