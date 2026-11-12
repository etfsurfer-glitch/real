# -*- coding: utf-8 -*-
"""재초환 보도자료 추가 — 호가를 '얼마나' 내렸나(인하 폭). measure.py 와 같은 단계·같은 집 정의. 박스에서 실행.

같은 집 = (단지, 동, 층, 공급, 방향, 전용), 같은 날 광고 호가 중앙값, ±30% 넘는 변화는 오기재로 제외.
 · 주간: 매주 수요일을 직전 수요일과 비교(10/14~11/11 주). 내린 집의 인하율·인하액 중앙값, 올린 집도 같은 방식.
 · 2주 구간: 보도 전 10/14→10/28, 보도 뒤 10/28→11/11 — 두 날 모두 나와 있던 집.
 · 주요 단지: 2주 구간 인하율·인하액 + 인하액이 큰 사례(전용·층).
Run: /opt/koczip/.venv/bin/python3 measure_cut.py → /tmp/jaecho_cut.json
"""
import json, os, sqlite3, statistics as st
from collections import defaultdict
import pyarrow.parquet as pq

TMP = "/mnt/backup/tmp_jaecho"
LOCAL = "/opt/koczip/data/archive/listings/{y}/{m}/listings_{d}.parquet"
WEEKS = ["2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28", "2026-11-04", "2026-11-11"]
SPANS = {"pre": ("2026-10-14", "2026-10-28"), "post": ("2026-10-28", "2026-11-11")}


def path(d):
    p = f"{TMP}/listings_{d}.parquet"
    return p if os.path.exists(p) else LOCAL.format(y=d[:4], m=d[5:7], d=d)


c = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
info = {r[0]: {"name": r[1], "type": r[2], "gu": r[3]} for r in c.execute(
    "SELECT c.complex_no, c.complex_name, c.real_estate_type, g.cortar_name FROM complexes c "
    "JOIN regions g ON g.cortar_no = substr(c.cortar_no,1,5)||'00000' WHERE c.cortar_no LIKE '11%'")}
zones = json.load(open(f"{TMP}/zone_map.json"))
STAGE_FIX = {"은마아파트": ("사업시행", "2026-07-02"), "잠실주공5단지": ("사업시행", "2026-07-01")}
GROUP = {"관리처분": "관리처분인가", "사업시행": "사업시행인가", "건축심의": "건축심의 통과",
         "조합설립": "건축심의 전", "추진위": "건축심의 전", "구역지정": "건축심의 전"}
grp = {}
for z in zones:
    stage = STAGE_FIX.get(z["name"], (z["stage"], None))[0]
    if stage in GROUP:
        for no in z["complex_nos"]:
            grp[no] = GROUP[stage]
for no, v in info.items():
    if no not in grp and v["type"] == "APT":
        grp[no] = "일반 아파트"
FOCUS = {"236", "639"}
EX = "사업시행인가(은마·잠실5 제외)"
COLS = ["complex_no", "trade_type", "area2_m2", "floor_info", "direction", "building_name", "area1_m2",
        "deal_or_warrant_price"]


def homes(d):
    h = defaultdict(list)
    for r in pq.read_table(path(d), columns=COLS).to_pylist():
        if r["trade_type"] == "A1" and r["complex_no"] in grp and r["deal_or_warrant_price"]:
            h[(r["complex_no"], r["building_name"], r["floor_info"], r["area2_m2"], r["direction"], r["area1_m2"])].append(r["deal_or_warrant_price"])
    return {k: st.median(v) for k, v in h.items()}


def pairs(ha, hb):
    """(묶음, 단지, 키, 이전가, 이후가) — 같은 집, ±30% 이내."""
    out = []
    for k, a in ha.items():
        b = hb.get(k)
        if b and 0.7 <= b / a <= 1.3:
            g = grp[k[0]]
            gs = [g] + (["재건축 전체"] if g != "일반 아파트" else []) + ([EX] if g == "사업시행인가" and k[0] not in FOCUS else [])
            out.append((gs, k, a, b))
    return out


def summ(ps):
    n = len(ps)
    if not n:
        return None
    cut = [(b / a - 1, b - a) for _, _, a, b in ps if b < a]
    rise = [(b / a - 1, b - a) for _, _, a, b in ps if b > a]
    def side(v):
        if not v:
            return None
        return {"n": len(v), "pct_med": st.median(x for x, _ in v), "pct_mean": st.mean(x for x, _ in v),
                "amt_med": st.median(y for _, y in v), "amt_mean": st.mean(y for _, y in v)}
    return {"n": n, "cut": side(cut), "rise": side(rise),
            "cut_ge3": sum(1 for x, _ in cut if x <= -0.03) / n, "cut_ge5": sum(1 for x, _ in cut if x <= -0.05) / n,
            "rise_ge3": sum(1 for x, _ in rise if x >= 0.03) / n,
            "net_amt_mean": st.mean(b - a for _, _, a, b in ps), "net_pct_mean": st.mean(b / a - 1 for _, _, a, b in ps), "price_med": st.median(a for _, _, a, _ in ps)}


def by_group(ps):
    g = defaultdict(list)
    for p in ps:
        for x in p[0]:
            g[x].append(p)
    return {k: summ(v) for k, v in g.items()}


def by_complex(ps, min_n=5):
    g = defaultdict(list)
    for p in ps:
        if grp[p[1][0]] != "일반 아파트":
            g[p[1][0]].append(p)
    return {k: summ(v) for k, v in g.items() if len(v) >= min_n}


H = {d: homes(d) for d in WEEKS}
out = {"weekly": {}, "weekly_complex": {}, "span": {}, "examples": {}}
for a, b in zip(WEEKS, WEEKS[1:]):
    ps = pairs(H[a], H[b])
    out["weekly"][b] = by_group(ps)
    out["weekly_complex"][b] = by_complex(ps)
for name, (a, b) in SPANS.items():
    ps = pairs(H[a], H[b])
    out["span"][name] = {"groups": by_group(ps), "complex": by_complex(ps)}
    if name == "post":   # 은마·잠실5 인하액 큰 사례
        for no in FOCUS:
            ex = sorted((p for p in ps if p[1][0] == no and p[3] < p[2]), key=lambda p: p[3] - p[2])[:8]
            out["examples"][no] = [{"dong": k[1], "floor": k[2], "area2": k[3], "area1": k[5], "dir": k[4], "before": a_, "after": b_}
                                   for _, k, a_, b_ in ex]
out["names"] = {no: info[no]["name"] for no in grp if grp[no] != "일반 아파트" and no in info}
json.dump(out, open("/tmp/jaecho_cut.json", "w"), ensure_ascii=False)


def fmt(s):
    if not s:
        return "-"
    c_, r_ = s["cut"] or {}, s["rise"] or {}
    return (f"n={s['n']} 내림{c_.get('n',0)} 중앙 {c_.get('pct_med',0):+.2%}/{c_.get('amt_med',0):+.0f}만 · "
            f"올림{r_.get('n',0)} 중앙 {r_.get('pct_med',0):+.2%}/{r_.get('amt_med',0):+.0f}만 · 3%↑인하 {s['cut_ge3']:.1%} · 평균순변동 {s['net_amt_mean']:+.0f}만")


for d, v in out["weekly"].items():
    print(d)
    for g in ["재건축 전체", "관리처분인가", "사업시행인가", EX, "건축심의 통과", "건축심의 전", "일반 아파트"]:
        print("  ", g, fmt(v.get(g)))
for name in SPANS:
    print("SPAN", name)
    for g in ["재건축 전체", "관리처분인가", "사업시행인가", EX, "건축심의 통과", "건축심의 전", "일반 아파트"]:
        print("  ", g, fmt(out["span"][name]["groups"].get(g)))
    for no in ("236", "639"):
        print("  ", info[no]["name"], fmt(out["span"][name]["complex"].get(no)))
for no, ex in out["examples"].items():
    print(info[no]["name"], [(e["dong"], e["floor"], e["area1"], e["before"], e["after"]) for e in ex])
