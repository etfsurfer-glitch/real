# -*- coding: utf-8 -*-
"""세제개편안 전후 — '동일 물건' 호가 수준 비교(패널). measure.py 와 별개 산출물.

measure.py 와 무엇이 다른가
  measure.py  = 호가를 '고친 사건'을 센다(인상 ÷ 인상+인하). 값을 안 고친 집은 안 보인다.
  이 파일     = 같은 집을 두 시점에 이어 붙여 '호가가 얼마나 움직였나'를 본다.
                값을 안 고친 집도 분모에 들어간다 — 그래서 '시장 전체가 얼마나 내렸나'를 말할 수 있다.

동일 물건 판정
  한 집을 여러 중개사무소가 올리면 광고는 여러 건이다(전국 아파트 매매 광고 126만 → 물건 52만).
  키 = 단지 + 동 + 층 + 전용면적 + 향 + 공급면적.  호가는 키에 넣지 않는다
  (넣으면 값이 바뀐 순간 다른 물건이 돼 패널이 끊긴다).
  검증: 이 키로 센 물건 수가 네이버 자체 신호 Σ1/same_addr_cnt 의 97.8% — 거의 일치한다.
  같은 키에 광고가 여럿이면 호가의 중앙값을 그 물건의 호가로 쓴다.

구간(각 10일, 양끝 스냅샷을 잇는다)
  대조군  7/13 → 7/23    발표와 무관한 평상시
  발표전  7/23 → 8/02
  발표후  8/02 → 8/12    ⚠ 8/03 18시 발표 → 8/02 가 마지막 '발표 전' 상태다
  민감도  8/03 → 8/13    (8/03 스냅샷은 19시 수집이라 발표 뒤다. 기준점을 바꿔도 같은 결론인지 본다)

Run: /opt/koczip/.venv/bin/python3 measure_panel.py   → /tmp/panel_csv/*.csv
"""
import csv
import os
import sqlite3
import statistics as st
from collections import defaultdict

import pyarrow.compute as pc
import pyarrow.parquet as pq

ARC = "/mnt/cold/archive/listings"
DB = "/opt/koczip/data/naverreal.sqlite"
OUT = "/tmp/panel_csv"
os.makedirs(OUT, exist_ok=True)

PANELS = [("대조군", "2026-07-13", "2026-07-23"),
          ("발표전", "2026-07-23", "2026-08-02"),
          ("발표후", "2026-08-02", "2026-08-12")]
SENS = ("민감도(8/03→8/13)", "2026-08-03", "2026-08-13")
DATES = sorted({d for _, a, b in PANELS + [SENS] for d in (a, b)})

BANDS = [(0, 10e8, "10억 미만"), (10e8, 15e8, "10~15억"), (15e8, 20e8, "15~20억"),
         (20e8, 30e8, "20~30억"), (30e8, 9e18, "30억 이상")]
GANGNAM3 = ("강남구", "서초구", "송파구")
ZONE = {"강남구": "강남3구", "서초구": "강남3구", "송파구": "강남3구",
        "마포구": "마용성", "용산구": "마용성", "성동구": "마용성",
        "노원구": "노도강", "도봉구": "노도강", "강북구": "노도강",
        "양천구": "양천·강서", "강서구": "양천·강서"}
COLS = ["complex_no", "trade_type", "real_estate_type", "area1_m2", "area2_m2",
        "floor_info", "building_name", "direction", "deal_or_warrant_price"]

# ── 지역 사전 ───────────────────────────────────────────────────────────
db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
REG = {}
for cx, sido, gu in db.execute(
        "SELECT cx.complex_no, substr(cx.cortar_no,1,2), rg.cortar_name"
        " FROM complexes cx LEFT JOIN regions rg"
        "   ON rg.cortar_no = substr(cx.cortar_no,1,5)||'00000'"):
    REG[cx] = (sido, gu or "(미상)")
db.close()
print(f"단지 {len(REG):,}개 지역 매핑", flush=True)


def load(date):
    """하루치 스냅샷 → {물건키해시: 호가}. 광고를 물건으로 접는다."""
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


KEYCX = {}
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
    return {"n": 0, "dn": 0, "up": 0, "flat": 0, "chg": [], "base": [],
            "dn_amt": [], "dn_pct": [], "up_amt": [], "up_pct": []}


def feed(acc, p0, p1):
    a = acc
    a["n"] += 1
    a["base"].append(p0)
    if p1 < p0:
        a["dn"] += 1
        a["dn_amt"].append(p0 - p1)
        a["dn_pct"].append((p0 - p1) / p0 * 100)
    elif p1 > p0:
        a["up"] += 1
        a["up_amt"].append(p1 - p0)
        a["up_pct"].append((p1 - p0) / p0 * 100)
    else:
        a["flat"] += 1
        return
    a["chg"].append((p1 - p0) / p0 * 100)


def run(label, d0, d1):
    """두 시점에 모두 살아 있는 물건만 잇는다."""
    s0, s1 = SNAP[d0], SNAP[d1]
    out = {"전체": defaultdict(blank), "밴드": defaultdict(blank),
           "권역": defaultdict(blank), "자치구": defaultdict(blank),
           "교차": defaultdict(blank)}
    for k, p0 in s0.items():
        p1 = s1.get(k)
        if p1 is None:
            continue
        sido, gu = REG.get(KEYCX.get(k, ""), ("", "(미상)"))
        bd = band(p0)
        feed(out["전체"]["전국"], p0, p1)
        if sido != "11":
            continue
        feed(out["전체"]["서울"], p0, p1)
        feed(out["전체"]["강남3구" if gu in GANGNAM3 else "서울(강남3구 외)"], p0, p1)
        feed(out["밴드"][bd], p0, p1)
        feed(out["권역"][ZONE.get(gu, "그 외 서울")], p0, p1)
        feed(out["자치구"][gu], p0, p1)
        feed(out["교차"][(gu, bd)], p0, p1)
    print(f"  {label:<8} {d0}→{d1}  잇힌 물건 전국 {out['전체']['전국']['n']:,}"
          f" / 서울 {out['전체']['서울']['n']:,}", flush=True)
    return out


print("\n패널 구성", flush=True)
RES = {lab: run(lab, a, b) for lab, a, b in PANELS}
RES[SENS[0]] = run(SENS[0], SENS[1], SENS[2])


def stat(a):
    """물건 하나하나의 호가 변동을 요약. 중앙값을 대표로 쓴다(이상치에 안 흔들린다)."""
    if not a["n"]:
        return None
    ch = sorted(a["chg"])
    # 값을 고친 물건만의 변동폭(중앙값) — 안 고친 집을 넣으면 전부 0이 돼 뭉개진다
    md = round(st.median(ch), 2) if ch else 0.0
    # 전체 물건 기준: 안 고친 집은 0% 로 넣는다
    allch = sorted(ch + [0.0] * a["flat"])
    return {
        "물건수": a["n"],
        "인하물건": a["dn"], "인상물건": a["up"], "무변동": a["flat"],
        "인하비율": round(a["dn"] / a["n"] * 100, 1),
        "인상비율": round(a["up"] / a["n"] * 100, 1),
        "변동물건비율": round((a["dn"] + a["up"]) / a["n"] * 100, 1),
        "전체_평균변동률": round(sum(allch) / len(allch), 2),
        "고친것만_중앙변동률": md,
        "기준_중앙호가_억": round(st.median(a["base"]) / 1e8, 2),
        # 값을 내린 집만 놓고 '얼마를 깎았나' — 퍼센트보다 그림이 그려진다
        "인하폭_중앙_만원": round(st.median(a["dn_amt"]) / 1e4) if a["dn_amt"] else None,
        "인하폭_중앙_률": round(st.median(a["dn_pct"]), 1) if a["dn_pct"] else None,
        "인상폭_중앙_만원": round(st.median(a["up_amt"]) / 1e4) if a["up_amt"] else None,
        "인상폭_중앙_률": round(st.median(a["up_pct"]), 1) if a["up_pct"] else None,
        # 내린 집이 올린 집보다 몇 배 많나
        "인하대인상_배": round(a["dn"] / a["up"], 2) if a["up"] else None,
    }


def write(fn, keyname, group, order=None, minn=0):
    keys = order or sorted({k for r in RES.values() for k in r[group]})
    rows = []
    for k in keys:
        base = RES[PANELS[0][0]][group].get(k)
        if base is None:
            continue
        if min((RES[lab][group][k]["n"] if k in RES[lab][group] else 0)
               for lab, _, _ in PANELS) < minn:
            continue
        row = {keyname: k if isinstance(k, str) else k[0]}
        if not isinstance(k, str):
            row["가격대"] = k[1]
        vals = {}
        for lab, _, _ in PANELS + [SENS]:
            s = stat(RES[lab][group][k]) if k in RES[lab][group] else None
            vals[lab] = s
            if s is None:
                continue
            for f in ("물건수", "인하물건", "인상물건", "무변동",
                      "인하비율", "인상비율", "전체_평균변동률",
                      "인하폭_중앙_만원", "인하폭_중앙_률", "인상폭_중앙_만원",
                      "인상폭_중앙_률", "인하대인상_배"):
                row[f"{lab}_{f}"] = s[f]
        b, c, d = vals[PANELS[1][0]], vals[PANELS[2][0]], vals[PANELS[0][0]]
        if b and c:
            row["발표전후_인하비율변화p"] = round(c["인하비율"] - b["인하비율"], 1)
            row["발표전후_평균변동률차p"] = round(c["전체_평균변동률"] - b["전체_평균변동률"], 2)
        if d and c:
            row["대조군대비_인하비율변화p"] = round(c["인하비율"] - d["인하비율"], 1)
            row["대조군대비_평균변동률차p"] = round(c["전체_평균변동률"] - d["전체_평균변동률"], 2)
        if d:
            row["기준_중앙호가_억"] = d["기준_중앙호가_억"]
        rows.append(row)
    with open(f"{OUT}/{fn}", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  {fn}  {len(rows)}행")
    return rows


# ── 재고: 가격대별 물건 수가 기간마다 어떻게 달라졌나(진입·이탈 포함) ────────
def stock():
    rows = []
    for lo, hi, lab in BANDS:
        row = {"가격대": lab}
        for dt in ("2026-07-13", "2026-07-23", "2026-08-02", "2026-08-12"):
            c = 0
            for k, p in SNAP[dt].items():
                if lo <= p < hi and REG.get(KEYCX.get(k, ""), ("", ""))[0] == "11":
                    c += 1
            row[dt] = c
        a, b = row["2026-08-02"], row["2026-08-12"]
        row["발표후_증감"] = b - a
        row["발표후_증감률"] = round((b - a) / a * 100, 1) if a else None
        rows.append(row)
    with open(f"{OUT}/panel_stock.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  panel_stock.csv  {len(rows)}행")
    return rows


print("\nCSV 생성", flush=True)
t1 = write("panel_overall.csv", "구분", "전체",
           order=["전국", "서울", "강남3구", "서울(강남3구 외)"])
t2 = write("panel_band.csv", "가격대", "밴드", order=[b[2] for b in BANDS])
write("panel_zone.csv", "권역", "권역",
      order=["강남3구", "마용성", "양천·강서", "노도강", "그 외 서울"])
write("panel_gu.csv", "자치구", "자치구", minn=300)
write("panel_cross.csv", "자치구", "교차", minn=150)
ts = stock()

print("\n■ 요약 — 서울 가격대별 (동일 물건 패널)")
print(f"  {'가격대':<10}{'대조군':>22}{'발표전':>22}{'발표후':>22}")
for r in t2:
    line = f"  {r['가격대']:<10}"
    for lab, _, _ in PANELS:
        line += (f"  인하{r[f'{lab}_인하비율']:>5}% 평균{r[f'{lab}_전체_평균변동률']:>6}%")
    print(line + f"   [{r['대조군_물건수']:,}물건]")

print("\n■ 민감도 — 기준점을 8/02 대신 8/03 으로 바꾸면")
for r in t2:
    print(f"  {r['가격대']:<10} 발표후 인하 {r['발표후_인하비율']:>5}%"
          f"  vs 민감도 {r[f'{SENS[0]}_인하비율']:>5}%"
          f"   평균 {r['발표후_전체_평균변동률']:>6}% vs {r[f'{SENS[0]}_전체_평균변동률']:>6}%")

print("\n■ 재고 — 서울 가격대별 물건 수")
for r in ts:
    print(f"  {r['가격대']:<10} 8/02 {r['2026-08-02']:>7,} → 8/12 {r['2026-08-12']:>7,}"
          f"  ({r['발표후_증감']:+,}, {r['발표후_증감률']:+.1f}%)")
