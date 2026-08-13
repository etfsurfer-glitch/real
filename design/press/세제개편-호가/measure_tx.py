# -*- coding: utf-8 -*-
"""세제개편안 전후 — 실거래(참고) 집계. 호가 자료의 보조 근거로만 쓴다.

왜 조심해야 하나 — 실측 두 가지
  ① 신고 지연: 계약 후 7일이면 27.9%, 14일이면 50.2%만 신고된다(6월 계약분 실측).
     8월 계약분을 7월과 나란히 놓으면 '거래 급감'처럼 보이는데 그건 시장이 아니라 달력이다.
  ② 조기 신고 편향: 싼 거래가 먼저 신고된다. 6월 계약분에서 9일 이내 신고분의 중앙가는
     10일 이후 신고분보다 26.6% 낮다. 그래서 8월 관측가를 그대로 비교하면 안 된다.

해법: **같은 지연 구간끼리** 비교한다(세 구간 모두 '계약 후 9일 이내 신고분'만).
      그래도 발표후 표본은 258건, 고가(15억+)는 33건이라 결론을 내기엔 얇다.

Run: /opt/koczip/.venv/bin/python3 measure_tx.py   → /tmp/tx_csv/*.csv
"""
import csv
import os
import sqlite3
import statistics as st
from datetime import date

DB = "/opt/koczip/data/naverreal.sqlite"
OUT = "/tmp/tx_csv"
os.makedirs(OUT, exist_ok=True)
TODAY = date(2026, 8, 13)
MAXLAG = 9                      # 발표후 구간이 최대 9일 경과 — 세 구간을 여기 맞춘다
W = "sgg_cd LIKE '11%' AND is_cancelled=0 AND inserted_at IS NOT NULL"
PER = [("대조군", "2026-07-13", "2026-07-23"), ("발표전", "2026-07-24", "2026-08-02"),
       ("발표후", "2026-08-04", "2026-08-12")]
BANDS = [(0, 10e8, "10억 미만"), (10e8, 15e8, "10~15억"), (15e8, 20e8, "15~20억"),
         (20e8, 30e8, "20~30억"), (30e8, 9e18, "30억 이상")]
LAGSQL = "CAST(julianday(substr(inserted_at,1,10)) - julianday(deal_ymd) AS INT)"

db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def write(fn, rows):
    with open(f"{OUT}/{fn}", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  {fn}  {len(rows)}행")


# ── 1) 신고 지연 곡선 — 6월 1~20일 계약(8/13 기준 54~73일 경과 = 정착) ─────
raw = db.execute(f"""SELECT {LAGSQL} d, COUNT(*) FROM transactions WHERE {W}
    AND deal_ymd BETWEEN '2026-06-01' AND '2026-06-20' GROUP BY d ORDER BY d""").fetchall()
tot = sum(c for _, c in raw)
cum, curve = 0, {}
for d, c in raw:
    cum += c
    if d >= 0:
        curve[d] = cum / tot
lag_rows = [{"계약후_일수": d, "신고완료율": round(curve.get(d, 0) * 100, 1)}
            for d in (1, 2, 3, 5, 7, 10, 14, 20, 25, 30, 40)]
print(f"[지연 곡선] 6월 1~20일 계약 {tot:,}건 기준")
write("tx_lag.csv", lag_rows)

# ── 2) 조기 신고 가격 편향 ────────────────────────────────────────────────
rows = db.execute(f"""SELECT {LAGSQL} d, deal_amount FROM transactions WHERE {W}
    AND deal_ymd BETWEEN '2026-06-01' AND '2026-06-20'""").fetchall()
fast = sorted(a for d, a in rows if d <= MAXLAG)
slow = sorted(a for d, a in rows if d > MAXLAG)
bias = [{"구분": f"{MAXLAG}일 이내 신고", "건수": len(fast),
         "중앙가_억": round(st.median(fast) / 1e8, 2),
         "평균가_억": round(sum(fast) / len(fast) / 1e8, 2)},
        {"구분": f"{MAXLAG+1}일 이후 신고", "건수": len(slow),
         "중앙가_억": round(st.median(slow) / 1e8, 2),
         "평균가_억": round(sum(slow) / len(slow) / 1e8, 2)}]
bias.append({"구분": "차이(조기−후기)", "건수": "",
             "중앙가_억": f"{(st.median(fast)/st.median(slow)-1)*100:+.1f}%",
             "평균가_억": f"{(sum(fast)/len(fast))/(sum(slow)/len(slow))*100-100:+.1f}%"})
write("tx_bias.csv", bias)

# ── 3) 구간별 — 같은 지연 구간끼리만 ─────────────────────────────────────
per_rows, band_rows = [], []
base_med = None
for lab, a, b in PER:
    rs = db.execute(f"""SELECT deal_amount, excl_use_ar FROM transactions WHERE {W}
        AND deal_ymd BETWEEN ? AND ? AND {LAGSQL} <= ?""", (a, b, MAXLAG)).fetchall()
    amt = sorted(r[0] for r in rs)
    pp = sorted(r[0] / (r[1] / 3.3058) for r in rs if r[1] and r[1] > 10)
    med = st.median(amt) / 1e8
    if base_med is None:
        base_med = med
    per_rows.append({
        "구간": lab, "기간": f"{a[5:]}~{b[5:]}", "건수": len(rs),
        "중앙가_억": round(med, 2), "평균가_억": round(sum(amt) / len(amt) / 1e8, 2),
        "평당가_중앙_만": round(st.median(pp) / 1e4) if pp else None,
        "대조군대비_중앙가": round((med / base_med - 1) * 100, 1),
    })
    cnt = {t: 0 for _, _, t in BANDS}
    for v in amt:
        for lo, hi, t in BANDS:
            if lo <= v < hi:
                cnt[t] += 1
                break
    for _, _, t in BANDS:
        band_rows.append({"구간": lab, "가격대": t, "건수": cnt[t],
                          "비중": round(cnt[t] / len(rs) * 100, 1)})
write("tx_period.csv", per_rows)
write("tx_band.csv", band_rows)

print("\n■ 요약")
for r in per_rows:
    print(f"  {r['구간']} {r['기간']}  {r['건수']:>4,}건  중앙 {r['중앙가_억']:>5}억"
          f"  평당 {r['평당가_중앙_만']:>5,}만  (대조군대비 {r['대조군대비_중앙가']:+.1f}%)")
hi = {}
for r in band_rows:
    if r["가격대"] in ("15~20억", "20~30억", "30억 이상"):
        hi[r["구간"]] = hi.get(r["구간"], 0) + r["건수"]
print("\n  고가(15억 이상) 거래 비중")
for r in per_rows:
    print(f"    {r['구간']}  {hi[r['구간']]:>4,}건 / {r['건수']:,}건 = "
          f"{hi[r['구간']]/r['건수']*100:.1f}%")
