# -*- coding: utf-8 -*-
"""세제개편안(2026-08-03 18시) 전후 서울 아파트 '호가 변경' 집계 — 기자 배포용 원자료.

무엇을 세나
  article_events(PRICE_CHANGE) — 같은 매물번호의 호가가 직전 수집 때와 달라진 사건.
  새 매물 등록·매물 회수는 포함하지 않는다. '이미 나와 있던 집이 값을 고쳐 부른 것'만이다.

구간(각 10일, 대칭)
  대조군   7/14~7/23   ← 발표와 무관한 평상시. 이게 없으면 '원래 그런 것'을 발표 효과로 오해한다.
  발표전   7/24~8/02
  발표후   8/04~8/13
  ⚠ 8/03 은 18시 발표라 하루 안에 전후가 섞인다 — 통째로 뺀다.

가격대 분류
  매물마다 '전 기간 첫 관측 호가' 하나로 고정한다. 이벤트마다 old_price 로 나누면
  값을 내린 매물이 아래 구간으로 옮겨가 저가 구간에 인하가 쌓인다(순환).

Run: python3 measure.py   → /tmp/tax_csv/*.csv
"""
import csv, os, sqlite3
from collections import defaultdict

DB = "/opt/koczip/data/naverreal.sqlite"
OUT = "/tmp/tax_csv"; os.makedirs(OUT, exist_ok=True)
W = [("대조군", "2026-07-14", "2026-07-23"),
     ("발표전", "2026-07-24", "2026-08-02"),
     ("발표후", "2026-08-04", "2026-08-13")]
BANDS = [(0, 10e8, "10억 미만"), (10e8, 15e8, "10~15억"), (15e8, 20e8, "15~20억"),
         (20e8, 30e8, "20~30억"), (30e8, 9e18, "30억 이상")]
GANGNAM3 = ("강남구", "서초구", "송파구")

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
      AND ae.event_date BETWEEN '2026-07-14' AND '2026-08-13'
      AND ae.event_date <> '2026-08-03'
      AND ae.old_price > 0 AND ae.new_price > 0
    ORDER BY ae.article_no, ae.event_date
""").fetchall()
print(f"  전국 {len(rows):,}건")

# 매물별 기준가 — 전 기간 첫 관측 호가로 고정
base = {}
for r in rows:
    base.setdefault(r["article_no"], r["old_price"])

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

agg_all, agg_band, agg_gu = defaultdict(blank), defaultdict(blank), defaultdict(blank)
agg_x = defaultdict(blank)                       # 자치구 × 가격대
for r in rows:
    w = win(r["event_date"])
    if not w:
        continue
    k = "up" if r["new_price"] > r["old_price"] else "dn" if r["new_price"] < r["old_price"] else None
    if not k:
        continue
    seoul = r["sido"] == "11"
    gu = r["gu"] or "(미상)"
    bd = band(base.get(r["article_no"], r["old_price"]))
    agg_all["전국"][w][k] += 1
    if seoul:
        agg_all["서울"][w][k] += 1
        agg_all["강남3구" if gu in GANGNAM3 else "서울(강남3구 외)"][w][k] += 1
        agg_band[bd][w][k] += 1
        agg_gu[gu][w][k] += 1
        agg_x[(gu, bd)][w][k] += 1

def rate(d):
    n = d["up"] + d["dn"]
    return round(d["up"] / n * 100, 1) if n else None

def write(fn, keyname, agg, order=None, minn=0):
    keys = order or sorted(agg)
    out = []
    for k in keys:
        if k not in agg:
            continue
        a = agg[k]
        tot = sum(a[w]["up"] + a[w]["dn"] for w, _, _ in W)
        if tot < minn:
            continue
        row = {keyname: k if isinstance(k, str) else k[0]}
        if not isinstance(k, str):
            row["가격대"] = k[1]
        for wl, _, _ in W:
            row[f"{wl}_건수"] = a[wl]["up"] + a[wl]["dn"]
            row[f"{wl}_인상"] = a[wl]["up"]
            row[f"{wl}_인하"] = a[wl]["dn"]
            row[f"{wl}_인상률"] = rate(a[wl])
        b, c = rate(a["발표전"]), rate(a["발표후"])
        row["발표전후_변화p"] = round(c - b, 1) if (b is not None and c is not None) else None
        d = rate(a["대조군"])
        row["대조군대비_변화p"] = round(c - d, 1) if (c is not None and d is not None) else None
        out.append(row)
    with open(f"{OUT}/{fn}", "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, list(out[0])); wr.writeheader(); wr.writerows(out)
    print(f"  {fn}  {len(out)}행")
    return out

print("\nCSV 생성")
t1 = write("press_tax_overall.csv", "구분", agg_all,
           order=["전국", "서울", "강남3구", "서울(강남3구 외)"])
t2 = write("press_tax_band.csv", "가격대", agg_band, order=[b[2] for b in BANDS])
t3 = write("press_tax_gu.csv", "자치구", agg_gu, minn=150)
t4 = write("press_tax_cross.csv", "자치구", agg_x, minn=80)

print("\n■ 요약 — 발표 후 인상률(발표전 대비)")
for r in t2:
    print(f"  {r['가격대']:<9} {r['발표전_인상률']:>5}% → {r['발표후_인상률']:>5}%"
          f"  ({r['발표전후_변화p']:+.1f}p)  [대조군 {r['대조군_인상률']}%]")
