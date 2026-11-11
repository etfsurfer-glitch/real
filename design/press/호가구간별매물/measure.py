# -*- coding: utf-8 -*-
"""서울 아파트 매매 매물 — 호가 5억 단위 구간별 건수(8/3·9/1·10/1·11/11). 박스에서 돌린다.

대상: 서울, 매매(A1), 아파트(APT)+재건축(JGC)+아파트 분양권(ABYG). 8·13 호가변동 자료와 같은 기준.
건수 두 가지: 광고(중개사무소가 올린 광고 전부) · 실매물(같은 집 중복 광고를 한 채로 = Σ1/same_addr_cnt).
구간: 10억 미만 / 10~15 / … / 45~50 / 50억 초과 (하한 포함·상한 미포함, 50억은 '45~50' 아님 → 50억 이상).
오기재: 같은 단지·같은 전용 중앙값의 0.4~2.5배 밖 광고는 따로 센다(자릿수 오타).
Run: /opt/koczip/.venv/bin/python3 measure.py → /tmp/hoga_band.json
"""
import json, os, sqlite3, statistics as st
from collections import defaultdict
import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq

P = {"2026-08-03": "/mnt/backup/policy_2026_tax_reform/daily/2026-08-03/listings_2026-08-03.parquet",
     "2026-09-01": "/mnt/backup/tmp_hoga813/listings_2026-09-01.parquet",
     "2026-10-01": "/mnt/backup/tmp_hoga813/listings_2026-10-01.parquet",
     "2026-11-11": "/opt/koczip/data/archive/listings/2026/11/listings_2026-11-11.parquet"}
TYPES = ["APT", "JGC", "ABYG"]
COLS = ["complex_no", "same_addr_cnt", "trade_type", "real_estate_type", "area2_m2", "deal_or_warrant_price"]
EOK = 1e8
BANDS = ["10억 미만"] + [f"{a}~{a+5}억" for a in range(10, 50, 5)] + ["50억 이상"]


def band(p):
    e = p / EOK
    if e < 10: return BANDS[0]
    if e >= 50: return BANDS[-1]
    a = int(e // 5) * 5
    return f"{a}~{a+5}억"


db = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
SEOUL = {str(c) for (c,) in db.execute("SELECT complex_no FROM complexes WHERE substr(cortar_no,1,2)='11'")}
db.close()

out = {"bands": BANDS, "dates": {}}
for d, path in P.items():
    t = pq.read_table(path, columns=COLS)
    t = t.filter(pc.and_(pc.equal(t["trade_type"], "A1"), pc.is_in(t["real_estate_type"], value_set=pa.array(TYPES))))
    x = t.to_pydict(); del t
    rows = []
    cell = defaultdict(list)
    for i, p in enumerate(x["deal_or_warrant_price"]):
        cx = str(x["complex_no"][i])
        if cx not in SEOUL or not p or p <= 0:
            continue
        a = round(x["area2_m2"][i] or 0)
        rows.append((cx, a, p, 1 / max(x["same_addr_cnt"][i] or 1, 1), x["real_estate_type"][i]))
        cell[(cx, a)].append(p)
    med = {k: st.median(v) for k, v in cell.items()}
    R = {b: {"ad": 0, "obj": 0.0} for b in BANDS}
    Rt = {ty: {b: {"ad": 0, "obj": 0.0} for b in BANDS} for ty in TYPES}
    typo = {"ad": 0, "obj": 0.0}
    for cx, a, p, w, ty in rows:
        m = med[(cx, a)]
        if not (0.4 * m <= p <= 2.5 * m):
            typo["ad"] += 1; typo["obj"] += w; continue
        b = band(p)
        R[b]["ad"] += 1; R[b]["obj"] += w
        Rt[ty][b]["ad"] += 1; Rt[ty][b]["obj"] += w
    rnd = lambda D: {b: {"ad": v["ad"], "obj": round(v["obj"])} for b, v in D.items()}
    out["dates"][d] = {"all": rnd(R), "by_type": {ty: rnd(Rt[ty]) for ty in TYPES},
                       "typo": {"ad": typo["ad"], "obj": round(typo["obj"])},
                       "total": {"ad": sum(v["ad"] for v in R.values()), "obj": round(sum(v["obj"] for v in R.values()))}}
    print(d, out["dates"][d]["total"], "오기재", out["dates"][d]["typo"], flush=True)
json.dump(out, open("/tmp/hoga_band.json", "w"), ensure_ascii=False, indent=1)
print("ok")
