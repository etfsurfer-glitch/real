"""단지별 급매 사전집계(quick_deals_cx) — 지도 축소 시 동·구 묶음("급매 N · 단지 N")용.

/stats/quick-deals 를 시군구마다 그대로 불러(같은 산식: 최근 90일 실거래 평균 대비 3% 이상 싼 호가,
(단지,평형) 실거래 3건 이상) 단지 단위로 접는다. 축소 지도는 전국 bbox 를 묶어야 해서 라이브 집계가
무거우니 하루 한 번 굽는다(daily step 11d). 매매(A1)·전세(B1) 둘 다.

열: trade, complex_no, cortar_no, name, lat, lng, n_deals(문턱 아래 매물 건수), n_groups(급매 평형 수),
    min_discount(가장 큰 할인), area_name·asking_min·avg_real(그 평형), built_at
"""
from __future__ import annotations
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.local_api import quick_deals, DB_PATH  # noqa: E402

MIN_DISCOUNT = 0.03
TRADES = ("A1", "B1")


def one(trade: str, sgg: str) -> list[tuple]:
    try:
        items = quick_deals(days=90, min_samples=3, asset="apt", trade_type=trade, sigungu=sgg,
                            min_discount=MIN_DISCOUNT, min_listings=1, limit=1000)["items"]
    except Exception as e:  # noqa: BLE001
        print(f"  {trade} {sgg}: ERR {e}", flush=True)
        return []
    if not items:
        return []
    by: dict[str, dict] = {}
    with sqlite3.connect(DB_PATH, timeout=30) as c:
        for it in items:
            no = it["complex_no"]
            thr = float(it["avg_real"]) * (1 - MIN_DISCOUNT)
            n = c.execute(
                "SELECT COUNT(*) FROM listings_current WHERE complex_no=? AND trade_type=? AND area_name=? "
                "AND deal_or_warrant_price>0 AND deal_or_warrant_price<=?",
                (no, trade, it["area_name"], thr)).fetchone()[0]
            d = by.setdefault(no, {"n_deals": 0, "n_groups": 0, "min": 0.0, "area": None, "ask": None, "avg": None,
                                   "name": it.get("complex_name"), "cortar": it.get("cortar_no")})
            d["n_deals"] += int(n or 0)
            d["n_groups"] += 1
            disc = float(it["discount_min"])
            if disc < d["min"]:
                d.update(min=disc, area=it["area_name"], ask=it["asking_min"], avg=it["avg_real"])
        out = []
        for no, d in by.items():
            if d["n_deals"] <= 0:
                continue
            r = c.execute("SELECT latitude, longitude, cortar_no, complex_name FROM complexes WHERE complex_no=?", (no,)).fetchone()
            if not r or not r[0]:
                continue
            out.append((trade, no, r[2] or d["cortar"], r[3] or d["name"], r[0], r[1], d["n_deals"], d["n_groups"],
                        d["min"], d["area"], d["ask"], d["avg"]))
    return out


def main() -> int:
    t0 = time.time()
    with sqlite3.connect(DB_PATH, timeout=30) as c:
        c.execute("PRAGMA journal_size_limit=1073741824")
        c.execute("""CREATE TABLE IF NOT EXISTS quick_deals_cx (
            trade TEXT NOT NULL, complex_no TEXT NOT NULL, cortar_no TEXT, name TEXT, lat REAL, lng REAL,
            n_deals INTEGER, n_groups INTEGER, min_discount REAL, area_name TEXT, asking_min INTEGER, avg_real REAL,
            built_at TEXT DEFAULT (datetime('now','+9 hours')), PRIMARY KEY (trade, complex_no))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_qdcx_pos ON quick_deals_cx(trade, lat, lng)")
        sggs = [r[0] for r in c.execute("SELECT cortar_no FROM regions WHERE cortar_type='dvsn' ORDER BY cortar_no")]
    print(f"시군구 {len(sggs)}곳 × {len(TRADES)}", flush=True)
    jobs = [(t, s) for t in TRADES for s in sggs]
    rows: list[tuple] = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, res in enumerate(ex.map(lambda j: one(*j), jobs), 1):
            rows.extend(res)
            if i % 40 == 0:
                print(f"  {i}/{len(jobs)} · 누적 {len(rows)}단지 · {time.time() - t0:.0f}s", flush=True)
    with sqlite3.connect(DB_PATH, timeout=60) as c:
        c.execute("PRAGMA journal_size_limit=1073741824")
        c.execute("DELETE FROM quick_deals_cx")
        c.executemany("INSERT OR REPLACE INTO quick_deals_cx (trade, complex_no, cortar_no, name, lat, lng, n_deals, n_groups, "
                      "min_discount, area_name, asking_min, avg_real) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    print(f"완료: {len(rows)}행 · {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
