# -*- coding: utf-8 -*-
"""세제개편안(2026-08-03 18시) 전후 서울 아파트 '호가 변경' 집계 — 기준①(사건) 전용.
   8월 17일 기준 · 전후 2주(대조군 포함 각 14일).

무엇을 세나 (measure.py 와 동일 방법론)
  article_events(PRICE_CHANGE) — 같은 매물번호의 호가가 직전 수집 때와 달라진 사건.
  새 매물 등록·매물 회수는 포함하지 않는다. '이미 나와 있던 집이 값을 고쳐 부른 것'만.
  지표 = 인상률 = 인상 ÷ (인상+인하).

구간(각 2주, 대칭)
  대조군   7/06~7/19   ← 발표와 무관한 평상시 기준선(대조군 대비 변화를 재려면 필수).
  발표전   7/20~8/02
  발표후   8/04~8/17   ← 8월 17일 기준, 발표 후 2주.
  ⚠ 8/03 은 18시 발표라 하루 안에 전후가 섞인다 — 통째로 뺀다.

가격대 분류
  매물마다 '전 기간 첫 관측 호가' 하나로 고정한다(순환논리 차단).

Run(박스): /opt/koczip/.venv/bin/python3 measure_gijun1_0817.py  → /tmp/tax0817_csv/*.csv
"""
import csv, os, sqlite3
from collections import defaultdict
from statistics import median

DB = "/opt/koczip/data/naverreal.sqlite"
OUT = "/tmp/tax0817_csv"; os.makedirs(OUT, exist_ok=True)
W = [("대조군", "2026-07-06", "2026-07-19"),
     ("발표전", "2026-07-20", "2026-08-02"),
     ("발표후", "2026-08-04", "2026-08-17")]
Q_LO, Q_HI = "2026-07-06", "2026-08-17"
BANDS = [(0, 10e8, "10억 미만"), (10e8, 15e8, "10~15억"), (15e8, 20e8, "15~20억"),
         (20e8, 30e8, "20~30억"), (30e8, 9e18, "30억 이상")]
GANGNAM3 = ("강남구", "서초구", "송파구")
ZONE = {"강남구": "강남3구", "서초구": "강남3구", "송파구": "강남3구",
        "마포구": "마용성", "용산구": "마용성", "성동구": "마용성",
        "노원구": "노도강", "도봉구": "노도강", "강북구": "노도강",
        "양천구": "양천·강서", "강서구": "양천·강서"}

db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
db.row_factory = sqlite3.Row

print("이벤트 적재…", flush=True)
rows = db.execute("""
    SELECT ae.article_no, ae.event_date, ae.old_price, ae.new_price,
           substr(cx.cortar_no,1,2) sido, rg.cortar_name gu
    FROM article_events ae
    JOIN complexes cx ON cx.complex_no = ae.complex_no
    LEFT JOIN regions rg ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000'
    WHERE ae.event_type='PRICE_CHANGE' AND ae.trade_type='A1'
      AND ae.event_date BETWEEN ? AND ?
      AND ae.event_date <> '2026-08-03'
      AND ae.old_price > 0 AND ae.new_price > 0
    ORDER BY ae.article_no, ae.event_date
""", (Q_LO, Q_HI)).fetchall()
print(f"  전국 {len(rows):,}건")

# 매물별 기준가·소속 — 전 기간 첫 관측으로 고정
base, gu_of, sido_of = {}, {}, {}
for r in rows:
    if r["article_no"] not in base:
        base[r["article_no"]] = r["old_price"]
        gu_of[r["article_no"]] = r["gu"] or "(미상)"
        sido_of[r["article_no"]] = r["sido"]

def band(p):
    for lo, hi, lab in BANDS:
        if lo <= p < hi:
            return lab
    return BANDS[-1][2]

def win(d):
    for lab, a, b in W:
        if a <= d <= b:
            return lab
    return None

def blank():
    return {w[0]: {"up": 0, "dn": 0} for w in W}

agg_all, agg_band, agg_gu, agg_zone = (defaultdict(blank), defaultdict(blank),
                                       defaultdict(blank), defaultdict(blank))
# 중앙호가(억) — 그 묶음에서 값을 고친 매물들의 기준호가 중앙값
px_all, px_band, px_gu, px_zone = (defaultdict(list), defaultdict(list),
                                   defaultdict(list), defaultdict(list))
seen = set()
for r in rows:
    w = win(r["event_date"])
    if not w:
        continue
    k = "up" if r["new_price"] > r["old_price"] else "dn" if r["new_price"] < r["old_price"] else None
    if not k:
        continue
    an = r["article_no"]
    seoul = sido_of[an] == "11"
    gu = gu_of[an]
    bp = base.get(an, r["old_price"])
    bd = band(bp)
    zn = ZONE.get(gu, "그 외 서울")
    agg_all["전국"][w][k] += 1
    if seoul:
        agg_all["서울"][w][k] += 1
        agg_all["강남3구" if gu in GANGNAM3 else "서울(강남3구 외)"][w][k] += 1
        agg_band[bd][w][k] += 1
        agg_gu[gu][w][k] += 1
        agg_zone[zn][w][k] += 1
    # 중앙호가는 매물당 1회만 반영
    if an not in seen:
        seen.add(an)
        px_all["전국"].append(bp)
        if seoul:
            px_all["서울"].append(bp)
            px_all["강남3구" if gu in GANGNAM3 else "서울(강남3구 외)"].append(bp)
            px_band[bd].append(bp); px_gu[gu].append(bp); px_zone[zn].append(bp)

def rate(d):
    n = d["up"] + d["dn"]
    return round(d["up"] / n * 100, 1) if n else None

def med_eok(lst):
    return round(median(lst) / 1e8, 1) if lst else None

def write(fn, keyname, agg, pxmap, order=None, minn=0):
    keys = order or sorted(agg)
    out = []
    for k in keys:
        if k not in agg:
            continue
        a = agg[k]
        tot = sum(a[w]["up"] + a[w]["dn"] for w, _, _ in W)
        if tot < minn:
            continue
        row = {keyname: k, "중앙호가_억": med_eok(pxmap.get(k, []))}
        for wl, _, _ in W:
            row[f"{wl}_건수"] = a[wl]["up"] + a[wl]["dn"]
            row[f"{wl}_인상"] = a[wl]["up"]
            row[f"{wl}_인하"] = a[wl]["dn"]
            row[f"{wl}_인상률"] = rate(a[wl])
        b, c, ct = rate(a["발표전"]), rate(a["발표후"]), rate(a["대조군"])
        row["발표전후_변화p"] = round(c - b, 1) if (b is not None and c is not None) else None
        row["대조군대비_변화p"] = round(c - ct, 1) if (c is not None and ct is not None) else None
        out.append(row)
    with open(f"{OUT}/{fn}", "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, list(out[0])); wr.writeheader(); wr.writerows(out)
    print(f"  {fn}  {len(out)}행")
    return out

print("\nCSV 생성")
write("press_tax0817_overall.csv", "구분", agg_all, px_all,
      order=["전국", "서울", "강남3구", "서울(강남3구 외)"])
t2 = write("press_tax0817_band.csv", "가격대", agg_band, px_band, order=[b[2] for b in BANDS])
write("press_tax0817_gu.csv", "자치구", agg_gu, px_gu, minn=150)
write("press_tax0817_zone.csv", "권역", agg_zone, px_zone,
      order=["강남3구", "마용성", "양천·강서", "노도강", "그 외 서울"])

print("\n■ 요약 — 발표 후 인상률(발표전 대비 / 대조군 대비)")
for r in t2:
    print(f"  {r['가격대']:<9} 대조군 {r['대조군_인상률']:>5}% · "
          f"발표전 {r['발표전_인상률']:>5}% → 발표후 {r['발표후_인상률']:>5}%"
          f"  (전후 {r['발표전후_변화p']:+.1f}p · 대조군대비 {r['대조군대비_변화p']:+.1f}p)")
