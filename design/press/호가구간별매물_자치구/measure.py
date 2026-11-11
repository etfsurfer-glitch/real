# -*- coding: utf-8 -*-
"""서울 아파트 매매 매물 — 20~25억·25~30억·30~35억 구간의 자치구별 건수(8/3·11/11). 박스에서 돌린다.

기준은 ../호가구간별매물/measure.py 와 같다(아파트+재건축+분양권, 실매물=Σ1/same_addr_cnt, 오기재 0.4~2.5배 제외,
구간 하한 포함·상한 미포함). 실매물은 소수라 구별로 반올림하면 25개 구 합이 서울 구간 합계와 몇 채 어긋난다 →
서울 구간 합계(구간별 반올림, 앞서 보낸 표와 같은 값)에 맞춰 최대 나머지 방식으로 정수 배분한다.
같은 집 호가 비교(두 날 모두 있던 집)도 구별로 낸다 — 8/3 호가 기준 구간.
Run: /opt/koczip/.venv/bin/python3 measure.py → /tmp/hoga_band_gu.json
"""
import json, sqlite3, statistics as st
from collections import defaultdict
import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq

P = {"2026-08-03": "/mnt/backup/policy_2026_tax_reform/daily/2026-08-03/listings_2026-08-03.parquet",
     "2026-11-11": "/opt/koczip/data/archive/listings/2026/11/listings_2026-11-11.parquet"}
TYPES = ["APT", "JGC", "ABYG"]
COLS = ["complex_no", "same_addr_cnt", "trade_type", "real_estate_type", "area1_m2", "area2_m2",
        "floor_info", "building_name", "direction", "deal_or_warrant_price"]
BANDS = ["20~25억", "25~30억", "30~35억"]


def band(p):
    e = p / 1e8
    if 20 <= e < 25: return BANDS[0]
    if 25 <= e < 30: return BANDS[1]
    if 30 <= e < 35: return BANDS[2]
    return None


db = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
GU, GUCODE = {}, {}
for cx, gu, code in db.execute(
        "SELECT cx.complex_no, rg.cortar_name, rg.cortar_no FROM complexes cx JOIN regions rg"
        " ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000' WHERE substr(cx.cortar_no,1,2)='11'"):
    GU[str(cx)] = gu; GUCODE[gu] = code
db.close()
ORDER = sorted(GUCODE, key=lambda g: GUCODE[g])          # 행정 코드 순(종로→강동)


def alloc(raw: dict, total: int) -> dict:
    fl = {k: int(v) for k, v in raw.items()}
    rest = total - sum(fl.values())
    for k in sorted(raw, key=lambda k: raw[k] - int(raw[k]), reverse=True)[:max(rest, 0)]:
        fl[k] += 1
    return fl


out = {"bands": BANDS, "gus": ORDER, "dates": {}}
OBJ = {}
for d, path in P.items():
    t = pq.read_table(path, columns=COLS)
    t = t.filter(pc.and_(pc.equal(t["trade_type"], "A1"), pc.is_in(t["real_estate_type"], value_set=pa.array(TYPES))))
    x = t.to_pydict(); del t
    cell = defaultdict(list); rows = []; objs = defaultdict(list)
    for i, p in enumerate(x["deal_or_warrant_price"]):
        cx = str(x["complex_no"][i])
        if cx not in GU or not p or p <= 0:
            continue
        a = round(x["area2_m2"][i] or 0)
        rows.append((cx, a, p, 1 / max(x["same_addr_cnt"][i] or 1, 1)))
        cell[(cx, a)].append(p)
        objs[(cx, x["building_name"][i], x["floor_info"][i], x["area2_m2"][i], x["direction"][i], x["area1_m2"][i])].append(p)
    med = {k: st.median(v) for k, v in cell.items()}
    raw = {b: defaultdict(float) for b in BANDS}; ad = {b: defaultdict(int) for b in BANDS}
    for cx, a, p, w in rows:
        m = med[(cx, a)]
        if not (0.4 * m <= p <= 2.5 * m):
            continue
        b = band(p)
        if b:
            raw[b][GU[cx]] += w; ad[b][GU[cx]] += 1
    res = {}
    for b in BANDS:
        tot = round(sum(raw[b].values()))                  # 서울 구간 합계(앞 자료와 같은 반올림)
        r = {g: raw[b].get(g, 0.0) for g in ORDER}
        res[b] = {"obj": alloc(r, tot), "obj_total": tot, "ad": {g: ad[b].get(g, 0) for g in ORDER}, "ad_total": sum(ad[b].values())}
    out["dates"][d] = res
    OBJ[d] = {}
    for k, v in objs.items():
        p = st.median(v); m = med[(k[0], round(k[3] or 0))]
        if 0.4 * m <= p <= 2.5 * m:
            OBJ[d][k] = p
    print(d, {b: res[b]["obj_total"] for b in BANDS}, flush=True)

A, B = list(P)
pan = {b: defaultdict(lambda: {"n": 0, "cut": 0, "rise": 0, "pct": []}) for b in BANDS}
for k, p0 in OBJ[A].items():
    b = band(p0); p1 = OBJ[B].get(k)
    if not b or p1 is None or abs(p1 / p0 - 1) > 0.3:
        continue
    for g in (GU[k[0]], "서울"):
        r = pan[b][g]; r["n"] += 1; r["pct"].append((p1 / p0 - 1) * 100)
        r["cut"] += p1 < p0; r["rise"] += p1 > p0
# 구간 이동: 두 날 모두 있던 집 중 11/11 에 이 구간인데 8/3 엔 위(above)·아래(below) 구간이던 집 = 유입, 반대 = 유출
def bfull(p):
    return int(p / 1e8 // 5)
idx = {"20~25억": 4, "25~30억": 5, "30~35억": 6}
mv = {b: defaultdict(lambda: {"in_above": 0, "in_below": 0, "out_down": 0, "out_up": 0, "new": 0}) for b in BANDS}
for k, p1 in OBJ[B].items():
    b1 = band(p1)
    if b1 and k not in OBJ[A]:
        for g in (GU[k[0]], "서울"):
            mv[b1][g]["new"] += 1
for k, p0 in OBJ[A].items():
    p1 = OBJ[B].get(k)
    if p1 is None or abs(p1 / p0 - 1) > 0.3:
        continue
    f0, f1 = bfull(p0), bfull(p1)
    if f0 == f1:
        continue
    for b, i in idx.items():
        for g in (GU[k[0]], "서울"):
            if f1 == i:
                mv[b][g]["in_above" if f0 > i else "in_below"] += 1
            if f0 == i:
                mv[b][g]["out_down" if f1 < i else "out_up"] += 1
out["move"] = {b: {g: dict(v) for g, v in mv[b].items()} for b in BANDS}
out["panel"] = {b: {g: {"n": r["n"], "cut": r["cut"], "rise": r["rise"], "mean": st.mean(r["pct"]) if r["pct"] else None}
                    for g, r in pan[b].items()} for b in BANDS}
json.dump(out, open("/tmp/hoga_band_gu.json", "w"), ensure_ascii=False, indent=1)
print("ok")
