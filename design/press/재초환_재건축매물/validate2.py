# -*- coding: utf-8 -*-
"""논리 점검 2: '같은 집' 비교를 광고 구성으로 나눈다.
 A 같은 광고 그대로(두 날 광고 묶음이 같음) — 순수한 호가 수정
 B 일부 겹침 — 광고가 더해지거나 빠짐
 C 전혀 안 겹침 — 다른 광고(재등록 또는 같은 묶음의 다른 집)
층이 숫자인 묶음만(저·중·고 제외) 따로도 본다."""
import json, statistics as st
from collections import defaultdict
import pyarrow.parquet as pq
exec(open("validate.py").read().split("def load(d):")[0])   # grp·Z16·path·WEEKS 재사용
COLS = ["article_no", "complex_no", "trade_type", "deal_or_warrant_price", "building_name", "floor_info", "area2_m2", "area1_m2", "direction"]


def homes(d):
    h = defaultdict(list)
    for r in pq.read_table(path(d), columns=COLS).to_pylist():
        if r["trade_type"] == "A1" and r["complex_no"] in grp and r["deal_or_warrant_price"]:
            h[(r["complex_no"], r["building_name"], r["floor_info"], r["area2_m2"], r["direction"], r["area1_m2"])].append((r["article_no"], r["deal_or_warrant_price"]))
    return h


def labs(no):
    g = grp[no]
    return [g] + (["재건축 전체"] if g != "일반 아파트" else []) + (["16개 구역"] if no in Z16 else []) + ({"236": ["은마"], "639": ["잠실5"]}.get(no, []))


H = {d: homes(d) for d in WEEKS}
res = {}
for a, b in zip(WEEKS, WEEKS[1:]):
    g = defaultdict(list)
    for k, va in H[a].items():
        vb = H[b].get(k)
        if not vb:
            continue
        pa, pb = st.median(p for _, p in va), st.median(p for _, p in vb)
        if not 0.7 <= pb / pa <= 1.3:
            continue
        sa, sb = {x for x, _ in va}, {x for x, _ in vb}
        cat = "A" if sa == sb else "B" if sa & sb else "C"
        numf = k[2].split("/")[0].isdigit()
        for l in labs(k[0]):
            g[(l, cat)].append(pb / pa - 1)
            g[(l, "전체")].append(pb / pa - 1)
            if numf:
                g[(l, "숫자층")].append(pb / pa - 1)
    res[b] = {f"{l}|{c}": {"n": len(v), "cut": sum(x < 0 for x in v) / len(v), "rise": sum(x > 0 for x in v) / len(v), "mean": st.mean(v)} for (l, c), v in g.items()}
json.dump(res, open("/tmp/jaecho_validate2.json", "w"), ensure_ascii=False)
OCT = WEEKS[1:4]
for l in ["재건축 전체", "사업시행인가", "건축심의 통과", "건축심의 전", "관리처분인가", "일반 아파트", "16개 구역", "은마", "잠실5"]:
    for c in ["전체", "A", "B", "C", "숫자층"]:
        k = f"{l}|{c}"
        try:
            o = {m: st.mean(res[d][k][m] for d in OCT) for m in ("cut", "rise", "mean")}
            w = res["2026-11-11"][k]; n4 = res["2026-11-04"][k]
            sh = st.mean(res[d][k]["n"] / res[d][f"{l}|전체"]["n"] for d in OCT)
            print(f"{l:8} {c:4} 비중{sh:4.0%} n11={w['n']:5} | 10월 내림{o['cut']:5.1%} 올림{o['rise']:5.1%} 평균{o['mean']:+.2%} | 11/4 {n4['cut']:5.1%}/{n4['rise']:5.1%} {n4['mean']:+.2%} | 11/11 {w['cut']:5.1%}/{w['rise']:5.1%} {w['mean']:+.2%}")
        except KeyError:
            pass
