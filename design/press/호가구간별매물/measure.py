# -*- coding: utf-8 -*-
"""서울 아파트 매매 매물 — 호가 5억 단위 구간별 건수(8/3·9/1·10/1·11/11). 박스에서 돌린다.

대상: 서울, 매매(A1), 아파트(APT)+재건축(JGC)+아파트 분양권(ABYG). 8·13 호가변동 자료와 같은 기준.
건수 두 가지: 광고(중개사무소가 올린 광고 전부) · 실매물(같은 집 중복 광고를 한 채로 = Σ1/same_addr_cnt).
구간: 10억 미만 / 10~15 / … / 45~50 / 50억 초과 (하한 포함·상한 미포함, 50억은 '45~50' 아님 → 50억 이상).
오기재: 같은 단지·같은 전용 중앙값의 0.4~2.5배 밖 광고는 따로 센다(자릿수 오타).
9/1·10/1 은 nfind 에서 /mnt/backup/tmp_hoga_band/ 로 받아 두고 끝나면 지운다.
Run: /opt/koczip/.venv/bin/python3 measure.py → /tmp/hoga_band.json
"""
import json, os, sqlite3, statistics as st
from collections import defaultdict
import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq

P = {"2026-08-03": "/mnt/backup/policy_2026_tax_reform/daily/2026-08-03/listings_2026-08-03.parquet",
     "2026-09-01": "/mnt/backup/tmp_hoga_band/listings_2026-09-01.parquet",
     "2026-10-01": "/mnt/backup/tmp_hoga_band/listings_2026-10-01.parquet",
     "2026-11-11": "/opt/koczip/data/archive/listings/2026/11/listings_2026-11-11.parquet"}
TYPES = ["APT", "JGC", "ABYG"]
COLS = ["complex_no", "same_addr_cnt", "trade_type", "real_estate_type", "area1_m2", "area2_m2",
        "floor_info", "building_name", "direction", "deal_or_warrant_price"]
EOK = 1e8
BANDS = ["10억 미만"] + [f"{a}~{a+5}억" for a in range(10, 50, 5)] + ["50억 이상"]


def band(p):
    e = p / EOK
    if e < 10: return BANDS[0]
    if e >= 50: return BANDS[-1]
    a = int(e // 5) * 5
    return f"{a}~{a+5}억"


db = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
GU = {str(cx): gu for cx, gu in db.execute(
    "SELECT cx.complex_no, rg.cortar_name FROM complexes cx JOIN regions rg"
    " ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000' WHERE substr(cx.cortar_no,1,2)='11'")}
SEOUL = set(GU)
ZONE = {"강남구": "강남3구", "서초구": "강남3구", "송파구": "강남3구",
        "마포구": "마용성", "용산구": "마용성", "성동구": "마용성",
        "노원구": "노도강", "도봉구": "노도강", "강북구": "노도강",
        "금천구": "금관구", "관악구": "금관구", "구로구": "금관구"}
db.close()

out = {"bands": BANDS, "dates": {}}
OBJ = {}   # 날짜 → {물건키: 호가 중앙값}  (8.13 자료와 같은 물건 키: 단지+동+층+전용+향+공급)
for d, path in P.items():
    t = pq.read_table(path, columns=COLS)
    t = t.filter(pc.and_(pc.equal(t["trade_type"], "A1"), pc.is_in(t["real_estate_type"], value_set=pa.array(TYPES))))
    x = t.to_pydict(); del t
    rows = []
    cell = defaultdict(list)
    objs = defaultdict(list)
    for i, p in enumerate(x["deal_or_warrant_price"]):
        cx = str(x["complex_no"][i])
        if cx not in SEOUL or not p or p <= 0:
            continue
        a = round(x["area2_m2"][i] or 0)
        rows.append((cx, a, p, 1 / max(x["same_addr_cnt"][i] or 1, 1), x["real_estate_type"][i]))
        cell[(cx, a)].append(p)
        objs[(cx, x["building_name"][i], x["floor_info"][i], x["area2_m2"][i], x["direction"][i], x["area1_m2"][i])].append(p)
    med = {k: st.median(v) for k, v in cell.items()}
    OBJ[d] = {}
    for k, v in objs.items():
        p = st.median(v); m = med[(k[0], round(k[3] or 0))]
        if 0.4 * m <= p <= 2.5 * m:
            OBJ[d][k] = p
    R = {b: {"ad": 0, "obj": 0.0} for b in BANDS}
    Rt = {ty: {b: {"ad": 0, "obj": 0.0} for b in BANDS} for ty in TYPES}
    typo = {"ad": 0, "obj": 0.0}
    Z = defaultdict(lambda: {b: {"ad": 0, "obj": 0.0} for b in BANDS})
    for cx, a, p, w, ty in rows:
        m = med[(cx, a)]
        if not (0.4 * m <= p <= 2.5 * m):
            typo["ad"] += 1; typo["obj"] += w; continue
        b = band(p)
        R[b]["ad"] += 1; R[b]["obj"] += w
        Rt[ty][b]["ad"] += 1; Rt[ty][b]["obj"] += w
        for g in (ZONE.get(GU[cx], "그 외 13개구"), GU[cx]):
            Z[g][b]["ad"] += 1; Z[g][b]["obj"] += w
    rnd = lambda D: {b: {"ad": v["ad"], "obj": round(v["obj"])} for b, v in D.items()}
    out["dates"][d] = {"all": rnd(R), "by_type": {ty: rnd(Rt[ty]) for ty in TYPES},
                       "by_zone": {g: rnd(v) for g, v in Z.items()},
                       "typo": {"ad": typo["ad"], "obj": round(typo["obj"])},
                       "total": {"ad": sum(v["ad"] for v in R.values()), "obj": sum(round(v["obj"]) for v in R.values())}}  # 합계=반올림한 구간의 합(표에서 더하면 맞게)
    print(d, out["dates"][d]["total"], "오기재", out["dates"][d]["typo"], flush=True)
# 8/3 → 11/11: 두 날 모두 있던 집의 구간 이동, 11/11 매물 중 새로 나온 집
A, B = "2026-08-03", "2026-11-11"
idx = {b: i for i, b in enumerate(BANDS)}
mv = {b: {"n": 0, "down": 0, "up": 0, "stay": 0, "gone": 0, "pct": []} for b in BANDS}
trans = {b: {c: 0 for c in BANDS} for b in BANDS}   # 두 날 모두 있던 집: 8/3 구간 → 11/11 구간
for k, p0 in OBJ[A].items():
    b0 = band(p0); p1 = OBJ[B].get(k)
    if p1 is None:
        mv[b0]["gone"] += 1; continue
    if abs(p1 / p0 - 1) > 0.3:
        continue
    d_ = idx[band(p1)] - idx[b0]
    trans[b0][band(p1)] += 1; mv[b0]["pct"].append((p1 / p0 - 1) * 100)
    mv[b0]["n"] += 1; mv[b0]["down" if d_ < 0 else "up" if d_ > 0 else "stay"] += 1
new = {b: {"all": 0, "new": 0} for b in BANDS}
for k, p in OBJ[B].items():
    b = band(p); new[b]["all"] += 1
    if k not in OBJ[A]:
        new[b]["new"] += 1
for b in BANDS:
    v = mv[b].pop("pct")
    mv[b]["mean_pct"] = st.mean(v) if v else None
    mv[b]["cut_r"] = sum(1 for c in v if c < 0) / len(v) * 100 if v else None
    mv[b]["rise_r"] = sum(1 for c in v if c > 0) / len(v) * 100 if v else None
out["trans"] = trans
out["move"] = mv; out["new"] = new
out["obj_n"] = {d: len(v) for d, v in OBJ.items()}
json.dump(out, open("/tmp/hoga_band.json", "w"), ensure_ascii=False, indent=1)
print("ok")
