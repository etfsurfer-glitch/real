# -*- coding: utf-8 -*-
"""대상 9개 평형의 호가 시계열 — 같은 지표를 날짜에 걸쳐 잰다.

'시세가 안 내렸다'를 말하려면 호가 중앙값을 시점 간에 견줘야 한다.
콜드 디스크 파일을 읽으므로 파일마다 페이지 캐시를 되돌려 준다(운영 DB 캐시 보호).
"""
import csv, os, statistics as st
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/mnt/cold/archive/listings")
OUT = "/tmp/gm_csv/press_gm_series.csv"
TARGETS = [("압구정 신현대", "3037", 183.41), ("압구정 신현대", "3037", 170.0),
           ("대치 은마", "236", 76.79), ("대치 은마", "236", 84.43),
           ("대치 한보미도", "105", 158.55), ("반포 신반포2차", "531", 107.16),
           ("잠실주공5", "639", 82.61), ("올림픽훼밀리타운", "610", 136.42),
           ("목동신시가지11", "22959", 51.87)]
CNOS = {c for _, c, _ in TARGETS}
TOL = 1.5
COLS = ["complex_no", "trade_type", "area2_m2", "deal_or_warrant_price",
        "article_feature_desc", "snapshot_date"]

rows = []
files = sorted(ROOT.glob("*/*/*.parquet"))
print(f"{len(files)}일치")
for f in files:
    fd = os.open(f, os.O_RDONLY)
    try:
        t = pq.read_table(f, columns=COLS,
                          filters=[("complex_no", "in", list(CNOS)), ("trade_type", "=", "A1")])
        d = t.to_pylist()
    finally:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)   # 콜드 파일이 캐시를 밀어내지 않게
        os.close(fd)
    date = f.stem.replace("listings_", "")
    for nm, cno, ar in TARGETS:
        sub = [r for r in d if r["complex_no"] == cno and r["area2_m2"] is not None
               and abs(r["area2_m2"] - ar) <= TOL
               and (r["deal_or_warrant_price"] or 0) > 0]
        if not sub:
            continue
        ps = sorted(r["deal_or_warrant_price"] for r in sub)
        rows.append(dict(날짜=date, 단지=nm, 전용=round(ar), 매물수=len(ps),
                         최저=ps[0], 하위10=ps[max(0, len(ps) // 10 - 1)],
                         중앙=int(st.median(ps)), 평균=int(sum(ps) / len(ps)),
                         급매표기=sum(1 for r in sub
                                      if "급매" in (r["article_feature_desc"] or ""))))
    print(".", end="", flush=True)
print()
with open(OUT, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"{OUT}  {len(rows)}행")

# 첫날 대비 마지막날 변화
first, last = rows[0]["날짜"], rows[-1]["날짜"]
print(f"\n{first} → {last}")
print(f"{'단지·전용':<24}{'중앙값 변화':>14}{'최저가 변화':>14}{'매물수':>12}{'급매표기':>10}")
for nm, cno, ar in TARGETS:
    a = [r for r in rows if r["단지"] == nm and r["전용"] == round(ar) and r["날짜"] == first]
    b = [r for r in rows if r["단지"] == nm and r["전용"] == round(ar) and r["날짜"] == last]
    if not (a and b):
        continue
    a, b = a[0], b[0]
    dm = (b["중앙"] - a["중앙"]) / a["중앙"] * 100
    dl = (b["최저"] - a["최저"]) / a["최저"] * 100
    print(f"{nm + ' ' + str(round(ar)) + 'm2':<24}{dm:>+13.1f}%{dl:>+13.1f}%"
          f"{a['매물수']:>7}→{b['매물수']:<4}{a['급매표기']:>5}→{b['급매표기']:<4}")
