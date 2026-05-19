"""특정 단지의 오늘 스냅샷에 무엇이 기록됐는지 전체 dump."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COMPLEX_NO = sys.argv[1] if len(sys.argv) > 1 else "124311"  # 래미안리더스원
TODAY = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()

OUT = Path("D:/auto/naverreal/data/snapshots") / f"snapshot_{COMPLEX_NO}_{TODAY}.txt"

c = sqlite3.connect("D:/auto/naverreal/data/naverreal.sqlite")
c.row_factory = sqlite3.Row

out: list[str] = []
def w(s=""):
    out.append(s)

# ===== 단지 마스터 =====
w("=" * 80)
w(f"단지 마스터 (complexes)  — 단지 메타데이터, 일별 누적 X (latest만)")
w("=" * 80)
row = c.execute("SELECT * FROM complexes WHERE complex_no=?", (COMPLEX_NO,)).fetchone()
if row:
    for k in row.keys():
        v = row[k]
        if k == "raw" and v:
            v = "<JSON, " + str(len(v)) + " bytes — 네이버 원본 응답 보존>"
        w(f"  {k:<26} = {v}")

# ===== 오늘 listings_current =====
w("")
w("=" * 80)
w(f"오늘 매물 (listings_current, snapshot_date={TODAY})  — 매일 REPLACE")
w("=" * 80)
rows = c.execute(
    "SELECT trade_type, area_name, COUNT(*) as n FROM listings_current "
    "WHERE complex_no=? AND snapshot_date=? GROUP BY trade_type, area_name "
    "ORDER BY trade_type, area_name",
    (COMPLEX_NO, TODAY),
).fetchall()
w(f"  거래유형 × 평형 × 매물수:")
for r in rows:
    label = {"A1": "매매", "B1": "전세", "B2": "월세"}.get(r["trade_type"], r["trade_type"])
    w(f"    {label}({r['trade_type']:<2}) {r['area_name']:<8} {r['n']:>3}건")

n_total = c.execute(
    "SELECT COUNT(*) FROM listings_current WHERE complex_no=? AND snapshot_date=?",
    (COMPLEX_NO, TODAY),
).fetchone()[0]
w(f"\n  → 오늘 총 매물 {n_total}건. 매물 1건 = ~270 bytes (raw 제외)")

# Sample one full row
sample = c.execute(
    "SELECT * FROM listings_current WHERE complex_no=? AND snapshot_date=? LIMIT 1",
    (COMPLEX_NO, TODAY),
).fetchone()
if sample:
    w("\n  [샘플 1건 — 모든 컬럼]")
    for k in sample.keys():
        v = sample[k]
        if k == "raw" and v:
            v = f"<JSON, {len(v)} bytes — listings_current에서는 NULL — 우리 코드가 raw 안 씀>"
        w(f"    {k:<28} = {v}")

# ===== complex_daily_agg =====
w("")
w("=" * 80)
w(f"단지 일별 집계 (complex_daily_agg, snapshot_date={TODAY})  — 매일 INSERT 누적")
w("=" * 80)
rows = c.execute(
    """SELECT trade_type, area_name, listing_count,
              price_min, price_max, price_avg, rent_avg
       FROM complex_daily_agg
       WHERE complex_no=? AND snapshot_date=?
       ORDER BY trade_type, area_name""",
    (COMPLEX_NO, TODAY),
).fetchall()
for r in rows:
    label = {"A1": "매매", "B1": "전세", "B2": "월세"}.get(r["trade_type"], r["trade_type"])
    pmin = f"{r['price_min']:,}" if r["price_min"] else "-"
    pavg = f"{r['price_avg']:,}" if r["price_avg"] else "-"
    pmax = f"{r['price_max']:,}" if r["price_max"] else "-"
    rent = f" / 월세평균 {r['rent_avg']:,}" if r["rent_avg"] else ""
    w(f"  {label}({r['trade_type']:<2}) {r['area_name']:<8} n={r['listing_count']:>3}  "
      f"min={pmin:<14} avg={pavg:<14} max={pmax}{rent}")
w(f"\n  → 이 단지의 오늘 집계 행 수: {len(rows)} (평형 × 거래유형 조합)")
w(f"  → 매일 이만큼이 INSERT됨 (snapshot_date='2026-05-20', '2026-05-21' ...)")
w(f"  → 1행 = ~60 bytes")

# ===== article_events =====
w("")
w("=" * 80)
w(f"이벤트 로그 (article_events, event_date={TODAY})  — 변화만 기록")
w("=" * 80)
rows = c.execute(
    """SELECT event_type, COUNT(*) as n FROM article_events
       WHERE complex_no=? AND event_date=?
       GROUP BY event_type ORDER BY n DESC""",
    (COMPLEX_NO, TODAY),
).fetchall()
for r in rows:
    w(f"  {r['event_type']:<14} {r['n']:>3}건")

samples = c.execute(
    """SELECT event_type, article_no, trade_type, old_price, new_price
       FROM article_events WHERE complex_no=? AND event_date=? LIMIT 5""",
    (COMPLEX_NO, TODAY),
).fetchall()
if samples:
    w(f"\n  [최근 이벤트 샘플]")
    for r in samples:
        ev = r["event_type"]
        oldp = f"{r['old_price']:,}" if r["old_price"] else "-"
        newp = f"{r['new_price']:,}" if r["new_price"] else "-"
        w(f"    {ev:<14} article={r['article_no']} trade={r['trade_type']:<2}  "
          f"{oldp} → {newp}")

# ===== transactions (실거래) =====
w("")
w("=" * 80)
w(f"실거래 (transactions)  — 국토부 신고된 거래, 월 batch")
w("=" * 80)
rows = c.execute(
    """SELECT deal_ymd, deal_amount, excl_use_ar, floor, dealing_gbn
       FROM transactions WHERE matched_complex_no=?
       ORDER BY deal_ymd DESC LIMIT 8""",
    (COMPLEX_NO,),
).fetchall()
for r in rows:
    eok = r["deal_amount"] / 1e8 if r["deal_amount"] else 0
    w(f"  {r['deal_ymd']}  전용 {r['excl_use_ar']}m²  {r['floor']}층  "
      f"{eok:.1f}억  ({r['dealing_gbn']})")
n_total = c.execute(
    "SELECT COUNT(*) FROM transactions WHERE matched_complex_no=?", (COMPLEX_NO,)
).fetchone()[0]
w(f"\n  → 이 단지의 누적 거래: {n_total}건 (3년치 backfill)")

# ===== 사이즈 요약 =====
w("")
w("=" * 80)
w(f"오늘({TODAY}) 이 단지로 추가된 데이터 (rough size estimate):")
w("=" * 80)
n_lis = c.execute(
    "SELECT COUNT(*) FROM listings_current WHERE complex_no=? AND snapshot_date=?",
    (COMPLEX_NO, TODAY),
).fetchone()[0]
n_agg = c.execute(
    "SELECT COUNT(*) FROM complex_daily_agg WHERE complex_no=? AND snapshot_date=?",
    (COMPLEX_NO, TODAY),
).fetchone()[0]
n_ev = c.execute(
    "SELECT COUNT(*) FROM article_events WHERE complex_no=? AND event_date=?",
    (COMPLEX_NO, TODAY),
).fetchone()[0]
w(f"  listings_current  {n_lis}행 × ~270B = {n_lis*270/1024:.1f} KB  ← 매일 replace, 안 쌓임")
w(f"  complex_daily_agg {n_agg}행 × ~60B  = {n_agg*60/1024:.1f} KB  ← 매일 INSERT, 누적")
w(f"  article_events    {n_ev}행 × ~100B = {n_ev*100/1024:.1f} KB  ← 변화만 INSERT, 누적")
w("")
w("전국 단위로 보면:")
w("  listings_current  ~1.64M행 × 270B = ~443 MB/일  ← REPLACE, 사이즈 stable")
w("  complex_daily_agg ~136k행 × 60B   = ~8 MB/일   ← INSERT, 누적")
w("  article_events    ~145k행 × 100B  = ~14 MB/일  ← INSERT, 누적 (현재 Supabase 미push)")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {OUT}  ({sum(len(s) for s in out)} chars)")
print()
print("\n".join(out))
