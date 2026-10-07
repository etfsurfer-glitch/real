# -*- coding: utf-8 -*-
"""급매 보도자료 수치 실측 — 박스에서 실행, CSV 4종 출력. 숫자는 여기서만 만든다."""
import csv, os, re, sqlite3
from collections import defaultdict

DB = "/opt/koczip/data/naverreal.sqlite"
OUT = "/tmp/gm_csv"; os.makedirs(OUT, exist_ok=True)
db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
db.row_factory = sqlite3.Row
q = lambda s, *a: db.execute(s, a).fetchall()

SNAP = q("SELECT MAX(snapshot_date) d FROM listings_current")[0]["d"]
TXMAX = q("SELECT MAX(deal_ymd) d FROM transactions WHERE is_cancelled=0")[0]["d"]
print("snapshot", SNAP, "· tx max", TXMAX)

TARGETS = [("압구정 신현대", "3037", 183.41), ("압구정 신현대", "3037", 170.0),
           ("대치 은마", "236", 76.79), ("대치 은마", "236", 84.43),
           ("대치 한보미도", "105", 158.55), ("반포 신반포2차", "531", 107.16),
           ("잠실주공5", "639", 82.61), ("올림픽훼밀리타운", "610", 136.42),
           ("목동신시가지11", "22959", 51.87)]
TOL = 1.5
MONTHS = "-12 months"

def wr(fn, rows, cols):
    with open(f"{OUT}/{fn}", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in rows: w.writerow(r)
    print(f"  {fn}  {len(rows)}행")

# ── ① 단지·평형별 ────────────────────────────────────────────────────────
rows, allls = [], []
for nm, cno, ar in TARGETS:
    c = q("SELECT total_household_count hh, substr(use_approve_ymd,1,4) yr FROM complexes WHERE complex_no=?", cno)[0]
    ls = q("""SELECT deal_or_warrant_price p, floor_info, direction, article_feature_desc d
              FROM listings_current WHERE snapshot_date=? AND complex_no=? AND trade_type='A1'
                AND area2_m2 BETWEEN ? AND ? AND deal_or_warrant_price>0""",
           SNAP, cno, ar - TOL, ar + TOL)
    tx = q("""SELECT deal_amount a, floor, deal_ymd FROM transactions
              WHERE matched_complex_no=? AND is_cancelled=0 AND excl_use_ar BETWEEN ? AND ?
                AND deal_ymd >= date(?, ?) ORDER BY deal_ymd""", cno, ar - TOL, ar + TOL, TXMAX, MONTHS)
    tx6 = [r for r in tx if r["deal_ymd"] >= q("SELECT date(?, '-6 months') d", TXMAX)[0]["d"]]
    if not ls or not tx: print("  !! 빈 표본", nm, ar); continue
    ps = sorted(r["p"] for r in ls)
    lo = ps[0]; med = ps[len(ps) // 2]; p10 = ps[max(0, len(ps) // 10 - 1)]
    avg = sum(r["a"] for r in tx) / len(tx)
    avg6 = sum(r["a"] for r in tx6) / len(tx6) if tx6 else None
    ngm = sum(1 for r in ls if "급매" in (r["d"] or ""))
    rows.append(dict(단지=nm, 전용=round(ar), 세대=c["hh"], 준공=c["yr"], 매물수=len(ls),
                     급매표기=ngm, 최저호가=lo, 호가하위10=p10, 호가중앙=med,
                     실거래평균=round(avg), 실거래건수=len(tx),
                     실거래평균6=round(avg6) if avg6 else "", 실거래건수6=len(tx6),
                     최종거래일=tx[-1]["deal_ymd"], 차이율=round((lo - avg) / avg * 100, 1),
                     차이율6=round((lo - avg6) / avg6 * 100, 1) if avg6 else "",
                     중앙차이율=round((med - avg) / avg * 100, 1),
                     중앙차이율6=round((med - avg6) / avg6 * 100, 1) if avg6 else "",
                     하위10차이율6=round((p10 - avg6) / avg6 * 100, 1) if avg6 else ""))
    for r in ls: allls.append((nm, round(ar), r))
rows.sort(key=lambda r: r["차이율6"] if r["차이율6"] != "" else 99)
wr("press_gm_complex.csv", rows, list(rows[0]))

# ── ② 은마 76㎡ 층 ───────────────────────────────────────────────────────
def band(fi):
    m = re.match(r"^(\d+)/(\d+)", fi or "")
    if not m: return ("저층" if (fi or "").startswith(("저", "반")) else
                      "고층" if (fi or "").startswith("고") else
                      "중층" if (fi or "").startswith("중") else None)
    f, t = int(m.group(1)), int(m.group(2))
    return "저층" if f <= t / 3 else "고층" if f > t * 2 / 3 else "중층"

frows = []
for nm, cno, ar in [("대치 은마", "236", 76.79), ("대치 은마", "236", 84.43)]:
    tx = q("""SELECT deal_amount a, floor, deal_ymd FROM transactions
              WHERE matched_complex_no=? AND is_cancelled=0 AND excl_use_ar BETWEEN ? AND ?
                AND deal_ymd >= date(?, ?) AND floor IS NOT NULL""",
           cno, ar - TOL, ar + TOL, TXMAX, MONTHS)
    tb = defaultdict(list)
    for r in tx: tb[band(f"{r['floor']}/14")].append(r["a"])
    ls = q("""SELECT deal_or_warrant_price p, floor_info FROM listings_current
              WHERE snapshot_date=? AND complex_no=? AND trade_type='A1'
                AND area2_m2 BETWEEN ? AND ? AND deal_or_warrant_price>0""",
           SNAP, cno, ar - TOL, ar + TOL)
    lb = defaultdict(list)
    for r in ls:
        b = band(r["floor_info"])
        if b: lb[b].append(r["p"])
    for b in ("저층", "중층", "고층"):
        med = lambda v: sorted(v)[len(v) // 2] if v else None
        frows.append(dict(단지=nm, 전용=round(ar), 층대=b,
                          실거래평균=round(sum(tb[b]) / len(tb[b])) if tb[b] else "",
                          실거래건수=len(tb[b]),
                          호가중앙=med(lb[b]) or "", 호가건수=len(lb[b])))
wr("press_gm_floor.csv", frows, list(frows[0]))

# ── ③ 싼 순 5건 (은마 76) ────────────────────────────────────────────────
cheap = q("""SELECT deal_or_warrant_price p, floor_info fi, direction, article_feature_desc d
             FROM listings_current WHERE snapshot_date=? AND complex_no='236' AND trade_type='A1'
               AND area2_m2 BETWEEN ? AND ? AND deal_or_warrant_price>0
             ORDER BY deal_or_warrant_price LIMIT 5""", SNAP, 76.79 - TOL, 76.79 + TOL)
tb76 = defaultdict(list)
for r in q("""SELECT deal_amount a, floor FROM transactions WHERE matched_complex_no='236'
              AND is_cancelled=0 AND excl_use_ar BETWEEN ? AND ? AND deal_ymd>=date(?,?)
              AND floor IS NOT NULL""", 76.79 - TOL, 76.79 + TOL, TXMAX, MONTHS):
    tb76[band(f"{r['floor']}/14")].append(r["a"])
crows = []
for r in cheap:
    b = band(r["fi"]) or ""
    base = sum(tb76[b]) / len(tb76[b]) if tb76.get(b) else None
    crows.append(dict(호가=r["p"], 층=r["fi"] or "", 층대=b, 향=r["direction"] or "",
                      같은층대대비=round((r["p"] - base) / base * 100, 1) if base else "",
                      문구=(r["d"] or "").replace("\n", " ")[:60]))
wr("press_gm_cheap.csv", crows, list(crows[0]))

tot = len(allls)          # 메타(대상매물합계)에서 쓴다

# ── ④ 5분위 급매율 ───────────────────────────────────────────────────────
px = q("""SELECT l.complex_no cno, l.deal_or_warrant_price p, l.area1_m2 a1,
                 l.article_feature_desc d
          FROM listings_current l WHERE l.snapshot_date=? AND l.trade_type='A1'
            AND l.deal_or_warrant_price>0 AND l.area1_m2>0 AND l.real_estate_type='APT'""", SNAP)
per = defaultdict(list)
for r in px: per[r["cno"]].append(r["p"] / (r["a1"] / 3.3058))
cmed = {c: sorted(v)[len(v) // 2] for c, v in per.items() if len(v) >= 3}
srt = sorted(cmed, key=lambda c: cmed[c])
k = len(srt) // 5
qrows = []
for i in range(5):
    grp = set(srt[i * k:(i + 1) * k] if i < 4 else srt[4 * k:])
    sub = [r for r in px if r["cno"] in grp]
    ngm = sum(1 for r in sub if "급매" in (r["d"] or ""))
    med = sorted(cmed[c] for c in grp)[len(grp) // 2]
    qrows.append(dict(분위=f"{i+1}분위", 단지수=len(grp), 매물수=len(sub), 급매표기=ngm,
                      급매율=round(ngm / len(sub) * 100, 1), 평당중앙만원=round(med / 10000)))
qrows.reverse()
wr("press_gm_quintile.csv", qrows, list(qrows[0]))

# ── ⑤ 메타 ───────────────────────────────────────────────────────────────
meta = [dict(항목="기준일", 값=SNAP), dict(항목="실거래최종", 값=TXMAX),
        dict(항목="대상매물합계", 값=tot),
        dict(항목="대상급매표기", 값=sum(r["급매표기"] for r in rows)),
        dict(항목="대상급매율", 값=round(sum(r["급매표기"] for r in rows) / tot * 100, 1)),
        dict(항목="전체아파트매물", 값=len(px)),
        dict(항목="실거래집계개월", 값=12), dict(항목="전용허용오차", 값=TOL)]
wr("press_gm_meta.csv", meta, ["항목", "값"])
print("끝.")
