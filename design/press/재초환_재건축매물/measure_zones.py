# -*- coding: utf-8 -*-
"""기자 요청: 강남3구 사업 추진 중 1,000세대 이상 16개 구역(반포주공1 두 구역 제외) — 구역별 같은 집 호가 변동.
measure_cut.py 와 같은 정의(같은 집·직전 수요일 대비·±30% 제외). 구역 = 서울시 정비구역, 여러 단지면 합쳐서.
Run(박스): /opt/koczip/.venv/bin/python3 measure_zones.py → /tmp/jaecho_zones16.json
"""
import json, os, statistics as st
from collections import defaultdict
import pyarrow.parquet as pq

TMP = "/mnt/backup/tmp_jaecho3"
LOCAL = "/opt/koczip/data/archive/listings/{y}/{m}/listings_{d}.parquet"
WEEKS = ["2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28", "2026-11-04", "2026-11-11"]
SPANS = {"pre": ("2026-10-14", "2026-10-28"), "post": ("2026-10-28", "2026-11-11")}
ZONES = [  # (자치구, 구역, 단지번호들)
    ("서초구", "신반포2차", ["531"]), ("서초구", "신반포4차", ["532"]), ("서초구", "반포미도1차", ["444"]),
    ("강남구", "은마아파트", ["236"]),
    ("강남구", "압구정 5구역(한양1·2차)", ["494", "496"]),
    ("강남구", "압구정 3구역(구현대: 현대1~7·10·13·14차)", ["712", "705", "495", "708", "724", "514", "107189", "114923"]),
    ("강남구", "압구정 4구역(현대8차·한양3·4·6차)", ["8617", "497", "498", "500"]),
    ("강남구", "개포주공6·7단지", ["1303", "1307"]),
    ("강남구", "압구정 1구역(미성1·2차)", ["728", "742"]),
    ("강남구", "압구정 2구역(신현대: 현대9·11·12차)", ["3037"]),
    ("강남구", "경우현(개포경남·우성3차·현대1차)", ["28", "667", "1317"]),
    ("강남구", "대치미도", ["105"]),
    ("송파구", "오금현대", ["632"]), ("송파구", "잠실우성1·2·3차", ["12861"]),
    ("송파구", "잠실주공5단지", ["639"]), ("송파구", "장미1·2·3차", ["389", "3754", "622"]),
]
Z = {no: z[1] for z in ZONES for no in z[2]}
TOTAL = "16개 구역 합계"
COLS = ["complex_no", "trade_type", "area2_m2", "floor_info", "direction", "building_name", "area1_m2", "deal_or_warrant_price", "same_addr_cnt"]


def path(d):
    p = f"{TMP}/listings_{d}.parquet"
    return p if os.path.exists(p) else LOCAL.format(y=d[:4], m=d[5:7], d=d)


def load(d):
    h, cnt = defaultdict(list), defaultdict(float)
    for r in pq.read_table(path(d), columns=COLS).to_pylist():
        if r["trade_type"] != "A1" or r["complex_no"] not in Z:
            continue
        cnt[Z[r["complex_no"]]] += 1 / max(r["same_addr_cnt"] or 1, 1)
        if r["deal_or_warrant_price"]:
            h[(r["complex_no"], r["building_name"], r["floor_info"], r["area2_m2"], r["direction"], r["area1_m2"])].append(r["deal_or_warrant_price"])
    cnt[TOTAL] = sum(cnt.values())
    return {k: st.median(v) for k, v in h.items()}, cnt


def summ(ps):
    if not ps:
        return None
    n = len(ps)
    cut = [(b / a - 1, b - a) for a, b in ps if b < a]
    rise = [(b / a - 1, b - a) for a, b in ps if b > a]
    return {"n": n, "cut": len(cut) / n, "rise": len(rise) / n, "n_cut": len(cut), "n_rise": len(rise),
            "net_pct": st.mean(b / a - 1 for a, b in ps), "net_amt": st.mean(b - a for a, b in ps),
            "cut_pct_med": st.median(x for x, _ in cut) if cut else None, "cut_amt_med": st.median(y for _, y in cut) if cut else None,
            "cut_amt_sum": sum(y for _, y in cut)}


def compare(ha, hb):
    g = defaultdict(list)
    for k, a in ha.items():
        b = hb.get(k)
        if b and 0.7 <= b / a <= 1.3:
            g[Z[k[0]]].append((a, b)); g[TOTAL].append((a, b))
    return {z: summ(v) for z, v in g.items()}


H, CNT = {}, {}
for d in WEEKS:
    H[d], CNT[d] = load(d)
out = {"zones": [{"gu": z[0], "name": z[1], "complex_nos": z[2]} for z in ZONES], "total": TOTAL,
       "weekly": {b: compare(H[a], H[b]) for a, b in zip(WEEKS, WEEKS[1:])},
       "span": {k: compare(H[a], H[b]) for k, (a, b) in SPANS.items()},
       "counts": {d: dict(CNT[d]) for d in WEEKS}}
json.dump(out, open("/tmp/jaecho_zones16.json", "w"), ensure_ascii=False)
for z in [x[1] for x in ZONES] + [TOTAL]:
    p, q = out["span"]["pre"].get(z), out["span"]["post"].get(z)
    f = lambda s: f"n{s['n']} 내림{s['cut']:.0%}/올림{s['rise']:.0%} 평균{s['net_pct']:+.2%}({s['net_amt']/1e4:+,.0f}만)" if s else "-"
    print(z, "| 앞2주", f(p), "| 뒤2주", f(q), "| 매물", round(CNT['2026-10-28'].get(z, 0)), "→", round(CNT['2026-11-11'].get(z, 0)))
