# -*- coding: utf-8 -*-
"""주인대출(매도인 자금 제공) 광고 — 2026-09-28 기준 재집계.

입력: sf3_candidates.csv(6/16~9/27 파케이) + sf_today.csv(9/28 운영DB) + sf3_summary.csv(분모)
      + cx_region.csv(단지→시도·시군구)
분류기: 후보정규식 − (자금어+없/무) − (승계 인접) − (주인세대: '주인세대여서'의 대여 오탐)
        → 기존 79일 시계열 78일 정확 재현, 9/3만 −1(원 보고서가 못 거른 오탐 1건)
출력: 일별상세_0928/*.csv + sf_daily.json
"""
import csv, json, re, collections, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/Users/hcode/auto/naverreal/design/press/매도인자금/일별상세_0928")
OUT.mkdir(exist_ok=True)

SUBJ = r"(?:매도인|매도자|집\s*주인|주인|소유자|소유주)"
FIN = r"(?:대출|융자|근저당|담보|대여)"
CAND = re.compile(SUBJ + r"[^가-힣]{0,2}[가-힣]{0,8}?" + FIN)
NEG = re.compile(FIN + r"\s*(?:없|무|x|X|엑스)")
INH = re.compile(FIN + r"[^가-힣]{0,2}[가-힣]{0,4}?승계|승계[^가-힣]{0,2}[가-힣]{0,4}?" + FIN)
SEDAE = re.compile(r"주인\s*세대")


def positive(d):
    return bool(CAND.search(d)) and not NEG.search(d) and not INH.search(d) and not SEDAE.search(d)


# ── 지역 매핑 ────────────────────────────────────────────────
SIDO_SHORT = {"서울시": "서울", "부산시": "부산", "대구시": "대구", "인천시": "인천",
              "광주시": "광주", "대전시": "대전", "울산시": "울산", "세종시": "세종",
              "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원",
              "충청북도": "충북", "충청남도": "충남", "전라북도": "전북",
              "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
              "경상남도": "경남", "제주도": "제주", "제주특별자치도": "제주"}
CXR = {}
for r in csv.reader(open(HERE / "cx_region.csv")):
    if len(r) < 3:
        continue
    CXR[r[0]] = (SIDO_SHORT.get(r[1], r[1]), r[2])

# ── 후보 적재 ────────────────────────────────────────────────
recs = []          # (day, article_no, complex_no, won, area, same_addr_cnt)
for r in csv.DictReader(open(HERE / "sf3_candidates.csv")):
    if positive(r["desc"]):
        recs.append((r["day"], r["article_no"], r["complex_no"], r["price_won"],
                     r["area"], r["same_addr_cnt"]))
# 오늘(9/28) — 주체어 사전필터만 된 원자료라 여기서 후보정규식부터 적용
with open(HERE / "sf_today.csv") as f:
    for r in csv.reader(f):
        if len(r) < 8:
            continue
        if positive(r[5]):
            recs.append((r[0], r[1], r[2], r[3], r[4], r[7]))

# 추석 연휴(2026-09-24~26)는 등록·삭제가 사실상 멈춰 추세를 왜곡하므로 제외한다.
CHUSEOK = {"2026-09-24", "2026-09-25", "2026-09-26"}
recs = [r for r in recs if r[0] not in CHUSEOK]

DAYS = sorted({r[0] for r in recs})
print("일자 %d개: %s ~ %s (추석 %s 제외)"
      % (len(DAYS), DAYS[0], DAYS[-1], "·".join(sorted(CHUSEOK))))

# ── 분모(전체 매매 광고·밴드) ────────────────────────────────
DEN = {}
for r in csv.DictReader(open(HERE / "sf3_summary.csv")):
    DEN[r["day"]] = dict(sale=int(r["sale"]), desc=int(r["desc"]),
                         bands=[int(r["b_u5"]), int(r["b_5_10"]), int(r["b_10_20"]),
                                int(r["b_20_30"]), int(r["b_30p"])], neg=int(r["neg"]))
DEN["2026-09-28"] = dict(sale=1570519, desc=1520148,
                         bands=[764034, 508908, 185214, 58565, 53798], neg=None)

BANDS = ["5억 미만", "5~10억", "10~20억", "20~30억", "30억 이상"]


def band(e):
    if e <= 0:
        return None
    return BANDS[0] if e < 5 else BANDS[1] if e < 10 else BANDS[2] if e < 20 else BANDS[3] if e < 30 else BANDS[4]


# ── 일별 집계 ────────────────────────────────────────────────
by_day = collections.defaultdict(list)
for d, an, cx, won, area, sac in recs:
    by_day[d].append((an, cx, won, area, sac))

import datetime

seen = set()
daily = {}
prev = None
for d in DAYS:
    rows = by_day[d]
    ids = {x[0] for x in rows}
    # 신규 포착은 '전날 대비'라야 뜻이 있다. 앞 관측일이 바로 전날이 아니면(결측·추석 직후)
    # 그 사이에 등록된 광고가 한꺼번에 잡히므로 수치를 내지 않는다.
    contiguous = prev is not None and (
        datetime.date.fromisoformat(d) - datetime.date.fromisoformat(prev)).days == 1
    new = len(ids - seen) if contiguous else None
    seen |= ids
    prev = d
    itemsA = len({(x[1], x[3], x[2]) for x in rows})
    itemsB = 0.0
    for x in rows:
        try:
            n = int(float(x[4]))
        except (TypeError, ValueError):
            n = 1
        itemsB += 1.0 / max(n, 1)
    prices = []
    for x in rows:
        try:
            e = float(x[2]) / 1e8
        except (TypeError, ValueError):
            continue
        if e > 0:
            prices.append(e)
    sido = collections.Counter()
    sgg = collections.Counter()
    bnd = collections.Counter()
    for x in rows:
        s, g = CXR.get(x[1], ("미상", "미상"))
        sido[s] += 1
        sgg["%s %s" % (s, g)] += 1
        try:
            b = band(float(x[2]) / 1e8)
        except (TypeError, ValueError):
            b = None
        if b:
            bnd[b] += 1
    daily[d] = dict(tot=len(rows), new=new, itemsA=itemsA, itemsB=round(itemsB, 1),
                    avg=round(statistics.mean(prices), 2) if prices else 0,
                    med=round(statistics.median(prices), 2) if prices else 0,
                    sido=dict(sido), sgg=dict(sgg), band=dict(bnd),
                    den=DEN.get(d, {}).get("sale"))

# 관측 기간에 한 번이라도 나타난 고유 광고 수 — 일별 '신규' 합계는 첫날·결측 직후를
# 산출하지 않으므로 이 값보다 작다. 보고서 본문은 이 값을 누적으로 쓴다.
uniq = len({x[1] for x in recs})

json.dump(dict(days=DAYS, daily=daily, den=DEN, uniq=uniq), open(OUT / "sf_daily.json", "w"),
          ensure_ascii=False, indent=1)

# ── CSV 산출 ─────────────────────────────────────────────────
with open(OUT / "일별요약.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["날짜", "게재 광고", "신규 포착", "물건수A(단지·면적·호가)", "물건수B(동일주소 환산)",
                "평균 호가(억)", "중앙 호가(억)", "전체 매매광고", "비중(만분율)"])
    for d in DAYS:
        x = daily[d]
        share = round(x["tot"] / x["den"] * 10000, 2) if x["den"] else ""
        w.writerow([d, x["tot"], x["new"] if x["new"] is not None else "",
                    x["itemsA"], x["itemsB"], x["avg"], x["med"], x["den"], share])

SIDO_ORDER = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종",
              "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "미상"]
used_sido = [s for s in SIDO_ORDER if any(daily[d]["sido"].get(s) for d in DAYS)]
with open(OUT / "일별_지역별.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["날짜"] + used_sido)
    for d in DAYS:
        w.writerow([d] + [daily[d]["sido"].get(s, 0) for s in used_sido])

with open(OUT / "일별_가격대별.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["날짜"] + BANDS)
    for d in DAYS:
        w.writerow([d] + [daily[d]["band"].get(b, 0) for b in BANDS])

tot_sgg = collections.Counter()
for d in DAYS:
    for k, v in daily[d]["sgg"].items():
        tot_sgg[k] += v
top = [k for k, _ in tot_sgg.most_common(15)]
with open(OUT / "일별_시군구별.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["날짜"] + top + ["그 외"])
    for d in DAYS:
        s = daily[d]["sgg"]
        picked = [s.get(k, 0) for k in top]
        w.writerow([d] + picked + [sum(s.values()) - sum(picked)])

print("== 검산 ==")
for d in (DAYS[0], "2026-07-01", "2026-09-03", DAYS[-1]):
    if d in daily:
        x = daily[d]
        assert sum(x["sido"].values()) == x["tot"], d
        print("  %s 게재 %d (지역합 %d) 평균 %.2f억 비중 %.4f%%"
              % (d, x["tot"], sum(x["sido"].values()), x["avg"], x["tot"] / x["den"] * 100))
print("상위 시군구:", tot_sgg.most_common(8))
