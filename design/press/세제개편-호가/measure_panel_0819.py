# -*- coding: utf-8 -*-
"""세제개편안 전후 — '동일 물건' 호가 변동(패널). 8/19 기준. 평상시=발표 전 '한 달'.

같은 집을 두 시점에 이어 붙여 '호가가 얼마나(금액·%) 움직였나'를 본다. 값을 안 고친 집도 분모에.
0817 판과 달리: ①평상시 기준을 발표 전 '한 달'로 확장(더 견고한 정상 비교)
              ②'호가가 얼마나 내렸나'를 평균 변동률(%)·평균 변동액(만원)으로 정량화.

구간
  평상시  7/03 → 8/02   발표(8/03 18시) 전 '한 달'. 정상 시장의 추세.
  발표후  8/02 → 8/19   발표 직후 ~2.5주. 시작점 8/02가 발표 직전이라 이 창이 '발표 효과'.
  ※ 평상시(한 달)가 발표후(2.5주)보다 긴데도 발표후에 더 내렸다면 → 발표 효과가 더 뚜렷하다는 신호.

동일 물건 판정: 키 = 단지+동+층+전용면적+향+공급면적. 광고 여럿이면 호가 중앙값.

Run(박스, 메모리 보호): systemd-run --scope -p MemoryMax=2600M \
   /opt/koczip/.venv/bin/python3 measure_panel_0819.py   → /tmp/panel0819_csv/*.csv
"""
import csv, os, sqlite3
import statistics as st
from collections import defaultdict

import pyarrow.compute as pc
import pyarrow.parquet as pq

ARC = "/mnt/cold/archive/listings"
DB = "/opt/koczip/data/naverreal.sqlite"
OUT = "/tmp/panel0819_csv"
os.makedirs(OUT, exist_ok=True)

PANELS = [("평상시", "2026-07-03", "2026-08-02"),
          ("발표후", "2026-08-02", "2026-08-19")]
DATES = sorted({d for _, a, b in PANELS for d in (a, b)})

BANDS = [(0, 10e8, "10억 미만"), (10e8, 15e8, "10~15억"), (15e8, 20e8, "15~20억"),
         (20e8, 30e8, "20~30억"), (30e8, 9e18, "30억 이상")]
GANGNAM3 = ("강남구", "서초구", "송파구")
ZONE = {"강남구": "강남3구", "서초구": "강남3구", "송파구": "강남3구",
        "마포구": "마용성", "용산구": "마용성", "성동구": "마용성",
        "노원구": "노도강", "도봉구": "노도강", "강북구": "노도강",
        "양천구": "양천·강서", "강서구": "양천·강서"}
# 급지(똘똘함) 사다리 — 자치구 중앙호가 순 5계층(0817 판과 동일 기준).
TIER = {"강남구": "1급지", "서초구": "1급지", "송파구": "1급지",
        "용산구": "2급지", "성동구": "2급지", "마포구": "2급지", "광진구": "2급지", "동작구": "2급지",
        "강동구": "3급지", "영등포구": "3급지", "양천구": "3급지", "중구": "3급지", "서대문구": "3급지",
        "동대문구": "4급지", "성북구": "4급지", "강서구": "4급지", "종로구": "4급지", "은평구": "4급지",
        "관악구": "5급지", "구로구": "5급지", "중랑구": "5급지", "강북구": "5급지", "노원구": "5급지",
        "금천구": "5급지", "도봉구": "5급지"}
TIER_ORDER = ["1급지", "2급지", "3급지", "4급지", "5급지"]
COLS = ["complex_no", "trade_type", "real_estate_type", "area1_m2", "area2_m2",
        "floor_info", "building_name", "direction", "deal_or_warrant_price"]

db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
REG = {}
for cx, sido, gu in db.execute(
        "SELECT cx.complex_no, substr(cx.cortar_no,1,2), rg.cortar_name"
        " FROM complexes cx LEFT JOIN regions rg"
        "   ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000'"):
    REG[cx] = (sido, gu or "(미상)")
# 여의도동(영등포구 내 고가지역) 단지 — 자치구 표에서만 따로 분리한다(급지·전체는 영등포 그대로).
YEOUIDO_CX = {r[0] for r in db.execute(
    "SELECT complex_no FROM complexes WHERE substr(cortar_no,1,8)='11560110'")}
db.close()
print(f"단지 {len(REG):,}개 지역 매핑 · 여의도 단지 {len(YEOUIDO_CX):,}개", flush=True)

KEYCX = {}


def load(date):
    f = f"{ARC}/{date[:4]}/{date[5:7]}/listings_{date}.parquet"
    t = pq.read_table(f, columns=COLS)
    t = t.filter(pc.and_(pc.equal(t["trade_type"], "A1"),
                         pc.equal(t["real_estate_type"], "APT")))
    d = t.to_pydict()
    del t
    cxs, bns, fis, a1, a2, dr, pr = (d["complex_no"], d["building_name"], d["floor_info"],
                                     d["area1_m2"], d["area2_m2"], d["direction"],
                                     d["deal_or_warrant_price"])
    tmp = defaultdict(list)
    ads = 0
    for i in range(len(pr)):
        p = pr[i]
        if not p or p <= 0:
            continue
        ads += 1
        k = hash((cxs[i], bns[i], fis[i], a2[i], dr[i], a1[i]))
        tmp[k].append(p)
        KEYCX.setdefault(k, cxs[i])
    snap = {k: (v[0] if len(v) == 1 else st.median(v)) for k, v in tmp.items()}
    print(f"  {date}  광고 {ads:,} → 물건 {len(snap):,}", flush=True)
    return snap


SNAP = {}
print("\n스냅샷 적재", flush=True)
for dt in DATES:
    SNAP[dt] = load(dt)


def band(p):
    for lo, hi, lab in BANDS:
        if lo <= p < hi:
            return lab
    return BANDS[-1][2]


def blank():
    return {"n": 0, "dn": 0, "up": 0, "flat": 0, "chg": [], "base": [], "net": [],
            "dn_amt": [], "dn_pct": [], "up_amt": [], "up_pct": []}


def feed(a, p0, p1):
    a["n"] += 1
    a["base"].append(p0)
    a["net"].append(p1 - p0)                       # 부호 있는 변동액(원) — 무변동=0 포함
    if p1 < p0:
        a["dn"] += 1
        a["dn_amt"].append(p0 - p1); a["dn_pct"].append((p0 - p1) / p0 * 100)
    elif p1 > p0:
        a["up"] += 1
        a["up_amt"].append(p1 - p0); a["up_pct"].append((p1 - p0) / p0 * 100)
    else:
        a["flat"] += 1; return
    a["chg"].append((p1 - p0) / p0 * 100)


def run(label, d0, d1):
    s0, s1 = SNAP[d0], SNAP[d1]
    out = {"전체": defaultdict(blank), "밴드": defaultdict(blank), "권역": defaultdict(blank),
           "급지": defaultdict(blank), "자치구": defaultdict(blank), "교차": defaultdict(blank)}
    for k, p0 in s0.items():
        p1 = s1.get(k)
        if p1 is None:
            continue
        cx = KEYCX.get(k, "")
        sido, gu = REG.get(cx, ("", "(미상)"))
        bd = band(p0)
        feed(out["전체"]["전국"], p0, p1)
        if sido != "11":
            continue
        feed(out["전체"]["서울"], p0, p1)
        feed(out["전체"]["강남3구" if gu in GANGNAM3 else "서울(강남3구 외)"], p0, p1)
        feed(out["밴드"][bd], p0, p1)
        feed(out["권역"][ZONE.get(gu, "그 외 서울")], p0, p1)
        feed(out["급지"][TIER.get(gu, "5급지")], p0, p1)
        # 자치구 표만: 영등포구를 '여의도' / '영등포구(여의도 외)'로 분리
        gu_key = gu
        if gu == "영등포구":
            gu_key = "여의도" if cx in YEOUIDO_CX else "영등포구(여의도 외)"
        feed(out["자치구"][gu_key], p0, p1)
        feed(out["교차"][(gu, bd)], p0, p1)
    print(f"  {label:<8} {d0}→{d1}  잇힌 물건 전국 {out['전체']['전국']['n']:,}"
          f" / 서울 {out['전체']['서울']['n']:,}", flush=True)
    return out


print("\n패널 구성", flush=True)
RES = {lab: run(lab, a, b) for lab, a, b in PANELS}


def stat(a):
    if not a["n"]:
        return None
    ch = sorted(a["chg"])
    allch = sorted(ch + [0.0] * a["flat"])          # 무변동을 0으로 포함한 전체 변동률
    return {
        "물건수": a["n"], "인하물건": a["dn"], "인상물건": a["up"], "무변동": a["flat"],
        "인하비율": round(a["dn"] / a["n"] * 100, 1),
        "인상비율": round(a["up"] / a["n"] * 100, 1),
        "평균변동률": round(sum(allch) / len(allch), 2),          # 부호 있는 평균 %(내림=음수)
        "평균변동액_만원": round(sum(a["net"]) / len(a["net"]) / 1e4),   # 부호 있는 평균 원(만원)
        "기준_중앙호가_억": round(st.median(a["base"]) / 1e8, 2),
        "인하폭_중앙_만원": round(st.median(a["dn_amt"]) / 1e4) if a["dn_amt"] else None,
        "인하폭_중앙_률": round(st.median(a["dn_pct"]), 1) if a["dn_pct"] else None,
        "인상폭_중앙_만원": round(st.median(a["up_amt"]) / 1e4) if a["up_amt"] else None,
        "인상폭_중앙_률": round(st.median(a["up_pct"]), 1) if a["up_pct"] else None,
        "인하대인상_배": round(a["dn"] / a["up"], 2) if a["up"] else None,
    }


FIELDS = ("물건수", "인하물건", "인상물건", "무변동", "인하비율", "인상비율",
          "평균변동률", "평균변동액_만원", "인하폭_중앙_만원", "인하폭_중앙_률",
          "인상폭_중앙_만원", "인상폭_중앙_률", "인하대인상_배")
BEF, AFT = PANELS[0][0], PANELS[1][0]


def write(fn, keyname, group, order=None, minn=0):
    keys = order or sorted({k for r in RES.values() for k in r[group]})
    rows = []
    for k in keys:
        if RES[BEF][group].get(k) is None:
            continue
        if min((RES[lab][group][k]["n"] if k in RES[lab][group] else 0)
               for lab, _, _ in PANELS) < minn:
            continue
        row = {keyname: k if isinstance(k, str) else k[0]}
        if not isinstance(k, str):
            row["가격대"] = k[1]
        vals = {}
        for lab, _, _ in PANELS:
            s = stat(RES[lab][group][k]) if k in RES[lab][group] else None
            vals[lab] = s
            if s is None:
                continue
            for f in FIELDS:
                row[f"{lab}_{f}"] = s[f]
        b, c = vals[BEF], vals[AFT]
        if b and c:
            row["대비_인하비율변화p"] = round(c["인하비율"] - b["인하비율"], 1)
            row["대비_평균변동률차p"] = round(c["평균변동률"] - b["평균변동률"], 2)
            row["대비_평균변동액차_만원"] = round(c["평균변동액_만원"] - b["평균변동액_만원"])
            row["기준_중앙호가_억"] = c["기준_중앙호가_억"]
        rows.append(row)
    with open(f"{OUT}/{fn}", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"  {fn}  {len(rows)}행")
    return rows


def stock():
    rows = []
    for lo, hi, lab in BANDS:
        row = {"가격대": lab}
        for dt in ("2026-08-02", "2026-08-19"):
            row[dt] = sum(1 for k, p in SNAP[dt].items()
                          if lo <= p < hi and REG.get(KEYCX.get(k, ""), ("", ""))[0] == "11")
        a, b = row["2026-08-02"], row["2026-08-19"]
        row["발표후_증감"] = b - a
        row["발표후_증감률"] = round((b - a) / a * 100, 1) if a else None
        rows.append(row)
    with open(f"{OUT}/panel0819_stock.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"  panel0819_stock.csv  {len(rows)}행")
    return rows


print("\nCSV 생성", flush=True)
write("panel0819_overall.csv", "구분", "전체", order=["전국", "서울", "강남3구", "서울(강남3구 외)"])
t2 = write("panel0819_band.csv", "가격대", "밴드", order=[b[2] for b in BANDS])
write("panel0819_zone.csv", "권역", "권역", order=["강남3구", "마용성", "양천·강서", "노도강", "그 외 서울"])
tt = write("panel0819_tier.csv", "급지", "급지", order=TIER_ORDER)
write("panel0819_gu.csv", "자치구", "자치구", minn=150)
ts = stock()

print("\n■ 요약 — 서울 가격대별 (평상시 한 달 → 발표후)")
for r in t2:
    print(f"  {r['가격대']:<9} 평균변동 {r['평상시_평균변동률']:>5}%→{r['발표후_평균변동률']:>5}%"
          f"  변동액 {r['평상시_평균변동액_만원']:>6}→{r['발표후_평균변동액_만원']:>6}만"
          f"  인하 {r['평상시_인하비율']:>4}%→{r['발표후_인하비율']:>4}%")
print("\n■ 급지 사다리 (평상시→발표후)")
for r in tt:
    print(f"  {r['급지']:<5} 중앙 {r['기준_중앙호가_억']:>5}억  변동 {r['평상시_평균변동률']:>5}%→"
          f"{r['발표후_평균변동률']:>5}%  변동액 {r['발표후_평균변동액_만원']:>6}만  인하 "
          f"{r['평상시_인하비율']:>4}%→{r['발표후_인하비율']:>4}%")
print("\n■ 재고(8/02→8/19)")
for r in ts:
    print(f"  {r['가격대']:<9} {r['2026-08-02']:>6,}→{r['2026-08-19']:>6,} ({r['발표후_증감률']:+.1f}%)")
