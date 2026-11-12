# -*- coding: utf-8 -*-
"""재초환 보도 전후 서울 재건축 단지 매물(호가·매물 수) — 사업 단계별. 박스에서 실행.

단계: 서울시 정비사업 추진현황(26년 6월말, 열린데이터광장 OA-22856) + 은마·잠실주공5단지 7월 사업시행인가 반영.
      map_zones.py 결과(zone_map.json)로 우리 단지에 연결. 착공 단계는 뺀다(공사 중).
비교군: 서울 일반 아파트(APT 유형, 정비구역에 연결되지 않은 단지).
대상 매물: 매매(A1). 실매물 = Σ1/same_addr_cnt. 같은 집 = (단지, 동, 층, 공급, 방향, 전용), 같은 날 중앙값,
          ±30% 넘는 변화는 오기재로 보고 뺀다.
Run: /opt/koczip/.venv/bin/python3 measure.py → /tmp/jaecho.json
"""
import json, os, sqlite3, statistics as st
from collections import defaultdict
import pyarrow.parquet as pq

TMP = "/mnt/backup/tmp_jaecho"
LOCAL = "/opt/koczip/data/archive/listings/{y}/{m}/listings_{d}.parquet"
WEEKLY = ["2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16",
          "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28", "2026-11-04", "2026-11-11"]
DAILY = [f"2026-10-{d:02d}" for d in range(13, 32)] + [f"2026-11-{d:02d}" for d in range(1, 12)]


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
grp, zone_of = {}, {}
for z in zones:
    stage = STAGE_FIX.get(z["name"], (z["stage"], None))[0]
    if stage not in GROUP:
        continue
    for no in z["complex_nos"]:
        grp[no] = GROUP[stage]
        zone_of[no] = z["name"]
for no, v in info.items():
    if no not in grp and v["type"] == "APT":
        grp[no] = "일반 아파트"
ORDER = ["관리처분인가", "사업시행인가", "건축심의 통과", "건축심의 전", "일반 아파트"]
FOCUS = {"236": "은마", "639": "잠실주공5단지"}

COLS = ["complex_no", "trade_type", "area2_m2", "floor_info", "direction", "building_name", "area1_m2",
        "deal_or_warrant_price", "same_addr_cnt"]


def load(d):
    rows = pq.read_table(path(d), columns=COLS).to_pylist()
    return [r for r in rows if r["trade_type"] == "A1" and r["complex_no"] in grp]


def counts(rows):
    g, cx = defaultdict(float), defaultdict(float)
    for r in rows:
        w = 1 / max(r["same_addr_cnt"] or 1, 1)
        g[grp[r["complex_no"]]] += w
        cx[r["complex_no"]] += w
    return g, cx


def homes(rows):
    h = defaultdict(list)
    for r in rows:
        if r["deal_or_warrant_price"]:
            h[(r["complex_no"], r["building_name"], r["floor_info"], r["area2_m2"], r["direction"], r["area1_m2"])].append(r["deal_or_warrant_price"])
    return {k: st.median(v) for k, v in h.items()}


def compare(ha, hb):
    res, per = defaultdict(list), defaultdict(list)
    for k, a in ha.items():
        b = hb.get(k)
        if b and 0.7 <= b / a <= 1.3:
            res[grp[k[0]]].append(b / a - 1)
            per[k[0]].append(b / a - 1)
    def summ(v):
        return {"n": len(v), "cut": sum(x < 0 for x in v) / len(v), "rise": sum(x > 0 for x in v) / len(v),
                "mean": st.mean(v)} if v else None
    return {g: summ(v) for g, v in res.items()}, {k: summ(v) for k, v in per.items() if len(v) >= 10}


out = {"weekly": {}, "weekly_change": {}, "daily_change": {}, "groups": {}, "focus": {}, "span": {}}
H, CX = {}, {}
for d in WEEKLY:
    rows = load(d)
    g, cx = counts(rows)
    out["weekly"][d] = {k: round(v, 1) for k, v in g.items()}
    CX[d] = cx
    H[d] = homes(rows)
for a, b in zip(WEEKLY, WEEKLY[1:]):
    out["weekly_change"][b] = compare(H[a], H[b])[0]
# 일간(전날 대비)
prev = None
for d in DAILY:
    try:
        h = homes(load(d))
    except FileNotFoundError:
        continue
    if prev:
        out["daily_change"][d] = compare(prev[1], h)[0]
    prev = (d, h)
# 구간 누적: 보도 전 2주(10/21→11/4) · 보도 뒤 1주(11/4→11/11) · 8/5→11/11
for k, (a, b) in {"pre": ("2026-10-21", "2026-11-04"), "post": ("2026-11-04", "2026-11-11"),
                  "since_aug": ("2026-08-05", "2026-11-11"), "oct28_nov11": ("2026-10-28", "2026-11-11")}.items():
    gsum, per = compare(H[a], H[b])
    out["span"][k] = {"groups": gsum, "complex": {no: v for no, v in per.items() if grp.get(no) != "일반 아파트"}}
# 단지별 매물 수(재건축)
for no in set(grp):
    if grp[no] == "일반 아파트":
        continue
    out["focus"][no] = {"name": info.get(no, {}).get("name"), "gu": info.get(no, {}).get("gu"), "group": grp[no],
                        "zone": zone_of.get(no), "counts": {d: round(CX[d].get(no, 0), 1) for d in WEEKLY}}
out["groups"] = {g: sum(1 for v in grp.values() if v == g) for g in ORDER}
out["order"] = ORDER
json.dump(out, open("/tmp/jaecho.json", "w"), ensure_ascii=False)
print("단지 수", out["groups"])
for d in ("2026-08-05", "2026-10-28", "2026-11-04", "2026-11-11"):
    print(d, out["weekly"][d])
for k in ("pre", "post", "since_aug"):
    print(k, {g: (v["n"], f"{v['cut']:.1%}", f"{v['mean']:+.2%}") for g, v in out["span"][k]["groups"].items()})
for d, v in list(out["daily_change"].items())[-12:]:
    print(d, {g: f"{x['cut']:.1%}" for g, x in v.items() if x})
