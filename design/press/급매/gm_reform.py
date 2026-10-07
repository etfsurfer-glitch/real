# -*- coding: utf-8 -*-
"""세제개편안(2026-08-03 18시) 전후 급매 분위기 비교.

발표 전 7일(7/27~8/2) vs 발표 후 7일(8/4~8/10). 8/3 은 하루 안에 전후가 섞여 경계일로 따로 둔다.
5분위 코호트는 마지막 날 기준으로 한 번 정하고 전 기간에 같은 코호트를 적용한다
(날마다 분위를 다시 나누면 단지가 갈아타 비교가 깨진다).
콜드 디스크를 읽으므로 파일마다 페이지 캐시를 되돌려 준다.
"""
import csv, os, sqlite3, statistics as st
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/mnt/cold/archive/listings")
OUT = "/tmp/gm_csv"
os.makedirs(OUT, exist_ok=True)
COLS = ["complex_no", "trade_type", "real_estate_type", "area1_m2",
        "deal_or_warrant_price", "article_feature_desc"]
BOUNDARY = "2026-08-03"
PRE = [f"2026-07-{d}" for d in range(27, 32)] + ["2026-08-01", "2026-08-02"]
POST = [f"2026-08-{d:02d}" for d in range(4, 11)]

# ── 단지 → 시도 ──────────────────────────────────────────────────────────
db = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
SIDO = {c: (t or "")[:2] for c, t in db.execute(
    "SELECT complex_no, cortar_no FROM complexes")}
db.close()

files = sorted(ROOT.glob("*/*/*.parquet"))
days = [f.stem.replace("listings_", "") for f in files]
print(f"{len(files)}일치 {days[0]}~{days[-1]}")

# ── 1차 통과: 마지막 날로 5분위 코호트 확정 ──────────────────────────────
last = files[-1]
t = pq.read_table(last, columns=COLS,
                  filters=[("trade_type", "=", "A1"), ("real_estate_type", "=", "APT")])
per = defaultdict(list)
for r in t.to_pylist():
    p, a = r["deal_or_warrant_price"], r["area1_m2"]
    if p and a:
        per[r["complex_no"]].append(p / (a / 3.3058))
cmed = {c: st.median(v) for c, v in per.items() if len(v) >= 3}
srt = sorted(cmed, key=lambda c: cmed[c])
k = len(srt) // 5
QUINT = {}
for i in range(5):
    for c in (srt[i * k:(i + 1) * k] if i < 4 else srt[4 * k:]):
        QUINT[c] = i + 1
del t, per
print(f"코호트 확정 — 단지 {len(QUINT):,}개")

# ── 2차 통과: 날마다 급매 표기 집계 ──────────────────────────────────────
rows = []
for f in files:
    day = f.stem.replace("listings_", "")
    fd = os.open(f, os.O_RDONLY)
    try:
        d = pq.read_table(f, columns=COLS,
                          filters=[("trade_type", "=", "A1"),
                                   ("real_estate_type", "=", "APT")]).to_pylist()
    finally:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        os.close(fd)
    agg = defaultdict(lambda: [0, 0])          # 구분 → [매물, 급매]
    for r in d:
        if not r["deal_or_warrant_price"]:
            continue
        gm = 1 if "급매" in (r["article_feature_desc"] or "") else 0
        c = r["complex_no"]
        for key in ("전국", f"시도{SIDO.get(c, '??')}",
                    f"{QUINT[c]}분위" if c in QUINT else "분위없음"):
            agg[key][0] += 1
            agg[key][1] += gm
    for key, (nl, ng) in agg.items():
        rows.append(dict(날짜=day, 구분=key, 매물수=nl, 급매표기=ng,
                         급매율=round(ng / nl * 100, 3) if nl else 0))
    print(".", end="", flush=True)
print()

with open(f"{OUT}/press_gm_reform_daily.csv", "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"일별 {len(rows)}행")

# ── 발표 전후 요약 ───────────────────────────────────────────────────────
def band(key, days_):
    sub = [r for r in rows if r["구분"] == key and r["날짜"] in days_]
    if not sub:
        return None
    nl = sum(r["매물수"] for r in sub); ng = sum(r["급매표기"] for r in sub)
    return nl / len(sub), ng / len(sub), ng / nl * 100

KEYS = ["전국", "시도11"] + [f"{i}분위" for i in range(1, 6)]
NAME = {"전국": "전국", "시도11": "서울"}
out = []
print(f"\n{'구분':<8}{'발표 전 급매율':>14}{'발표 후':>10}{'변화':>10}"
      f"{'매물수 전':>12}{'매물수 후':>12}")
for key in KEYS:
    a, b = band(key, PRE), band(key, POST)
    if not (a and b):
        continue
    dl = b[2] - a[2]
    out.append(dict(구분=NAME.get(key, key), 전_매물평균=round(a[0]), 전_급매평균=round(a[1]),
                    전_급매율=round(a[2], 2), 후_매물평균=round(b[0]), 후_급매평균=round(b[1]),
                    후_급매율=round(b[2], 2), 급매율차=round(dl, 2),
                    상대변화=round(dl / a[2] * 100, 1) if a[2] else ""))
    print(f"{NAME.get(key, key):<8}{a[2]:>13.2f}%{b[2]:>9.2f}%{dl:>+9.2f}p"
          f"{a[0]:>12,.0f}{b[0]:>12,.0f}")
with open(f"{OUT}/press_gm_reform.csv", "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, list(out[0])); w.writeheader(); w.writerows(out)
print("\n경계일 8/3 은 요약에서 제외(하루 안에 전후가 섞임)")
