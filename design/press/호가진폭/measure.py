"""8.3 세제개편 전후 '동일평형 호가 진폭' — 박스에서 돌려 JSON 을 뽑는다.

산식(전 구간 동일):
  셀 = (단지, 평형) · 매매 · APT · 매물 5건 이상
  진폭 = (최고호가 - 최저호가) / 평균호가 × 100
  대표값 = 셀들의 중앙값(평균은 재건축 단지 몇 개에 끌려간다)
  오타 가드: 같은 단지 같은 평형에서 최고가 최저의 4배를 넘으면 제외

출처는 **parquet 하나로 통일**한다. complex_daily_agg 는 같은 날 서울 8.71% 로
parquet(7.55%)과 1.16%p 어긋난다(셀 수도 57,858 vs 48,806) — 담는 범위가 달라
두 구간을 섞어 쓰면 출처 차이를 시장 변화로 오독한다.
"""
import pyarrow.parquet as pq, statistics as st, sqlite3, json, os, sys

BASE = "/mnt/backup/policy_2026_tax_reform"
COLS = ["complex_no", "trade_type", "real_estate_type", "area_name", "deal_or_warrant_price"]
MIN_N, TYPO = 5, 4
GN3 = {"11680": "강남구", "11650": "서초구", "11710": "송파구"}

nav = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
CX = {str(r[0]): (r[1] or "")[:5] for r in nav.execute("SELECT complex_no, cortar_no FROM complexes")}
NM = {r[0][:5]: r[1] for r in nav.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn'")}
SIDO = {r[0][:2]: r[1] for r in nav.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'")}


def cells(path):
    t = pq.read_table(path, columns=COLS)
    tt, rt = t.column("trade_type").to_pylist(), t.column("real_estate_type").to_pylist()
    cn, an = t.column("complex_no").to_pylist(), t.column("area_name").to_pylist()
    pr = t.column("deal_or_warrant_price").to_pylist()
    g = {}
    for i in range(len(tt)):
        if tt[i] == "A1" and rt[i] == "APT" and pr[i] and pr[i] > 0 and cn[i]:
            g.setdefault((cn[i], an[i]), []).append(float(pr[i]))
    out = {}
    for k, v in g.items():
        if len(v) < MIN_N:
            continue
        mn, mx = min(v), max(v)
        if mx > mn * TYPO:
            continue
        out[k] = {"mn": mn, "mx": mx, "av": sum(v) / len(v),
                  "sp": (mx - mn) / (sum(v) / len(v)) * 100, "n": len(v)}
    return out


def med(ks, src, f):
    v = [f(src[k]) for k in ks if k in src]
    return st.median(v) if v else None


# 5/18~6/15 는 맥의 data_archive_may, 6/16~8/2 는 nfind 박스 아카이브
# (/opt/koczip-archive/archive/listings/)에서 /tmp 로 받아 둔다. 전 구간 끊김 없다.
DAYS = [(d, f"/tmp/listings_{d}.parquet") for d in
        ("2026-05-25", "2026-06-01", "2026-06-08", "2026-06-15", "2026-06-22", "2026-06-29",
         "2026-07-06", "2026-07-13", "2026-07-20", "2026-07-27", "2026-08-01")]
DAYS += [("2026-08-03", f"{BASE}/2026-08-03_pre/parquet/listings_2026-08-03.parquet")]
DAYS += [(d, f"{BASE}/daily/{d}/listings_{d}.parquet")
         for d in ("2026-08-17", "2026-08-31", "2026-09-14", "2026-09-28", "2026-10-06")]

snap, series = {}, {}
for d, p in DAYS:
    if not os.path.exists(p):
        print("없음:", p, file=sys.stderr); continue
    c = cells(p); snap[d] = c
    seo = [k for k in c if CX.get(str(k[0]), "")[:2] == "11"]
    g3 = [k for k in c if CX.get(str(k[0]), "") in GN3]
    # 강남3구 = 강남구+서초구+송파구를 묶은 말이다. 묶음과 별개로 구별 수치도 각각 낸다.
    series[d] = {"cells": len(c),
                 "nat": med(c, c, lambda x: x["sp"]),
                 "seoul": med(seo, c, lambda x: x["sp"]),
                 "gn3": med(g3, c, lambda x: x["sp"])}
    for code, nm in GN3.items():
        ks = [k for k in c if CX.get(str(k[0]), "") == code]
        series[d][nm] = med(ks, c, lambda x: x["sp"])
    print(d, series[d])

A, B, C = snap["2026-06-15"], snap["2026-08-03"], snap["2026-10-06"]

def table(keys, namer, minc):
    buck = {}
    for k in keys:
        g = CX.get(str(k[0]), "")
        if g:
            buck.setdefault(namer(g), []).append(k)
    rows = []
    for nm, ks in buck.items():
        a, b, c = med(ks, A, lambda x: x["sp"]), med(ks, B, lambda x: x["sp"]), med(ks, C, lambda x: x["sp"])
        nC = sum(1 for k in ks if k in C)
        if None in (a, b, c) or nC < minc:
            continue
        rows.append({"name": nm, "cells": nC, "d0615": a, "d0803": b, "d1006": c,
                     "chg": (c / b - 1) * 100,
                     "gap_eok": med(ks, C, lambda x: x["mx"] - x["mn"]) / 1e8})
    return sorted(rows, key=lambda r: -r["chg"])


allk = set(A) | set(B) | set(C)
# 묶음(강남3구)도 자치구 표와 같은 형식의 한 줄로 낸다 — 기사에서 나란히 쓰기 위해.
def group_row(name, codes):
    ks = [k for k in allk if CX.get(str(k[0]), "") in codes]
    a, b, c = med(ks, A, lambda x: x["sp"]), med(ks, B, lambda x: x["sp"]), med(ks, C, lambda x: x["sp"])
    return {"name": name, "cells": sum(1 for k in ks if k in C), "d0615": a, "d0803": b,
            "d1006": c, "chg": (c / b - 1) * 100,
            "gap_eok": med(ks, C, lambda x: x["mx"] - x["mn"]) / 1e8}


out = {"series": series,
       "sido": table(allk, lambda g: SIDO.get(g[:2], g[:2]), 300),
       "gu": table([k for k in allk if CX.get(str(k[0]), "")[:2] == "11"], lambda g: NM.get(g, g), 60),
       "groups": [group_row("강남3구", set(GN3)),
                  group_row("서울시 전체", {g for g in NM if g.startswith("11")})]}

pan = [k for k in set(B) & set(C) if CX.get(str(k[0]), "") in GN3]
gb = sorted((B[k]["mx"] - B[k]["mn"]) / 1e8 for k in pan)
gc = sorted((C[k]["mx"] - C[k]["mn"]) / 1e8 for k in pan)
q = lambda a, p: a[min(len(a) - 1, int(round((len(a) - 1) * p)))]
out["gn3"] = {
    "panel": len(pan),
    "level": {k: {"b": med(pan, B, lambda x, k=k: x[k]) / 1e8, "c": med(pan, C, lambda x, k=k: x[k]) / 1e8}
              for k in ("mn", "mx", "av")},
    "gap": {str(p): {"b": q(gb, p), "c": q(gc, p)} for p in (.50, .75, .90, .95)},
    "over10": {"b": sum(1 for x in gb if x >= 10), "c": sum(1 for x in gc if x >= 10)},
}
json.dump(out, open("/tmp/press_spread.json", "w"), ensure_ascii=False, indent=1)
print("\n저장: /tmp/press_spread.json")
