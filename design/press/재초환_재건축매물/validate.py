# -*- coding: utf-8 -*-
"""논리 점검: '같은 집'(단지·동·층·공급·방향·전용 묶음, 중앙값) 대신 '같은 광고'(article_no)로 다시 잰다.
층이 저·중·고로만 나오는 광고는 같은 묶음에 다른 집이 섞일 수 있어, 싼 매물이 새로 들어오면 '내린 집'으로 잡힐 위험이 있다.
같은 광고의 호가 변화는 그 위험이 없다(같은 중개사가 같은 집 값을 고친 것).
Run(박스): python3 validate.py → /tmp/jaecho_validate.json
"""
import json, os, statistics as st
from collections import defaultdict
import pyarrow.parquet as pq
import sqlite3

TMP = "/mnt/backup/tmp_jaecho"
LOCAL = "/opt/koczip/data/archive/listings/{y}/{m}/listings_{d}.parquet"
WEEKS = ["2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28", "2026-11-04", "2026-11-11"]
SPANS = {"pre": ("2026-10-14", "2026-10-28"), "post": ("2026-10-28", "2026-11-11")}


def path(d):
    p = f"{TMP}/listings_{d}.parquet"
    return p if os.path.exists(p) else LOCAL.format(y=d[:4], m=d[5:7], d=d)


c = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
typ = {r[0]: r[1] for r in c.execute("SELECT complex_no, real_estate_type FROM complexes WHERE cortar_no LIKE '11%'")}
zones = json.load(open(f"{TMP}/zone_map.json"))
STAGE_FIX = {"은마아파트": "사업시행", "잠실주공5단지": "사업시행"}
GROUP = {"관리처분": "관리처분인가", "사업시행": "사업시행인가", "건축심의": "건축심의 통과",
         "조합설립": "건축심의 전", "추진위": "건축심의 전", "구역지정": "건축심의 전"}
grp = {}
for z in zones:
    s = STAGE_FIX.get(z["name"], z["stage"])
    if s in GROUP:
        for no in z["complex_nos"]:
            grp[no] = GROUP[s]
for no, t in typ.items():
    if no not in grp and t == "APT":
        grp[no] = "일반 아파트"
Z16 = {n: 1 for n in "531 532 444 236 494 496 712 705 495 708 724 514 107189 114923 8617 497 498 500 1303 1307 728 742 3037 28 667 1317 105 632 12861 639 389 3754 622".split()}
COLS = ["article_no", "complex_no", "trade_type", "deal_or_warrant_price", "building_name", "floor_info", "area2_m2"]


def load(d):
    return {r["article_no"]: r for r in pq.read_table(path(d), columns=COLS).to_pylist()
            if r["trade_type"] == "A1" and r["complex_no"] in grp and r["deal_or_warrant_price"]}


def labels(no):
    g = grp[no]
    out = [g] + (["재건축 전체"] if g != "일반 아파트" else [])
    if no in Z16:
        out.append("강남3구 16개 구역")
    if no in ("236", "639"):
        out.append({"236": "은마", "639": "잠실주공5단지"}[no])
    return out


def compare(A, B):
    g = defaultdict(list)
    for k, a in A.items():
        b = B.get(k)
        if b and 0.7 <= b["deal_or_warrant_price"] / a["deal_or_warrant_price"] <= 1.3:
            pa, pb = a["deal_or_warrant_price"], b["deal_or_warrant_price"]
            for l in labels(a["complex_no"]):
                g[l].append((pa, pb))
    res = {}
    for l, v in g.items():
        n = len(v)
        cut = [b / a - 1 for a, b in v if b < a]
        res[l] = {"n": n, "cut": len(cut) / n, "rise": sum(b > a for a, b in v) / n, "net_pct": st.mean(b / a - 1 for a, b in v),
                  "net_amt": st.mean(b - a for a, b in v), "cut_pct_med": st.median(cut) if cut else None,
                  "cut_amt_med": st.median(b - a for a, b in v if b < a) if cut else None}
    return res


D = {d: load(d) for d in WEEKS}
out = {"weekly": {b: compare(D[a], D[b]) for a, b in zip(WEEKS, WEEKS[1:])},
       "span": {k: compare(D[a], D[b]) for k, (a, b) in SPANS.items()}}
# 은마·잠실5 큰 인하 사례가 같은 광고로도 확인되는지: 10/28·11/11 둘 다 있는 광고 중 인하 큰 순
ex = {}
A, B = D["2026-10-28"], D["2026-11-11"]
for no in ("236", "639"):
    v = [(B[k]["deal_or_warrant_price"] - a["deal_or_warrant_price"], a["building_name"], a["floor_info"], a["area2_m2"],
          a["deal_or_warrant_price"], B[k]["deal_or_warrant_price"]) for k, a in A.items() if a["complex_no"] == no and k in B]
    ex[no] = sorted(v)[:8]
out["examples_article"] = ex
json.dump(out, open("/tmp/jaecho_validate.json", "w"), ensure_ascii=False)
OCT = WEEKS[1:4]
for l in ["재건축 전체", "관리처분인가", "사업시행인가", "건축심의 통과", "건축심의 전", "일반 아파트", "강남3구 16개 구역", "은마", "잠실주공5단지"]:
    o = {k: st.mean(out["weekly"][d][l][k] for d in OCT) for k in ("cut", "rise", "net_pct", "net_amt")}
    w = out["weekly"]["2026-11-11"][l]
    p, q = out["span"]["pre"][l], out["span"]["post"][l]
    print(f"{l}: 주간 10월 내림{o['cut']:.1%} 올림{o['rise']:.1%} 평균{o['net_pct']:+.2%}({o['net_amt']/1e4:+,.0f}만) → 11/11 n{w['n']} 내림{w['cut']:.1%} "
          f"올림{w['rise']:.1%} 평균{w['net_pct']:+.2%}({w['net_amt']/1e4:+,.0f}만) 인하중앙 {(w['cut_amt_med'] or 0)/1e4:,.0f}만 | 2주 앞 {p['net_pct']:+.2%}({p['net_amt']/1e4:+,.0f}만) "
          f"뒤 {q['net_pct']:+.2%}({q['net_amt']/1e4:+,.0f}만) 내림{p['cut']:.0%}→{q['cut']:.0%}")
for no, v in ex.items():
    print(no, [(f"{x[0]/1e8:+.2f}억", x[1], x[2], x[3]) for x in v])
