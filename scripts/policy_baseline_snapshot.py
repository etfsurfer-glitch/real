# -*- coding: utf-8 -*-
"""2026 세제개편안 발표(2026-08-03 18:00 KST) 직전 기준선 스냅샷.

매물 원본은 parquet(단지형 raw 포함 + 비단지 10종)이 정본이라 여기 중복 저장하지 않는다.
본DB 장시간 읽기가 WAL 체크포인트를 막아 디스크를 채웠던 적이 있어(08-03) 테이블마다
커넥션을 새로 연다.
"""
import hashlib, shutil, sqlite3, sys, time
from pathlib import Path

D = Path("/mnt/backup/policy_2026_tax_reform/2026-08-03_pre")
SRC = "/opt/koczip/data/naverreal.sqlite"
B = D / "baseline.sqlite"
DATE = "2026-08-03"
CATS = ["villa","oneroom","house","sangga","office","knowledge","redev","building","factory","land"]

SKIP_COLS = {"match_details", "raw"}   # 매칭 진단 JSON — 정책 분석에 안 쓰이고 I/O만 먹는다

def cols_of(con, table):
    names = [r[1] for r in con.execute(f"PRAGMA main.table_info({table})")]
    return ", ".join(f'"{c}"' for c in names if c not in SKIP_COLS)

JOBS = [
  ("special_deals",      "SELECT * FROM main.special_deals"),
  ("complexes",          "SELECT * FROM main.complexes"),
  ("complex_areas",      "SELECT * FROM main.complex_areas"),
  ("transactions",       "SELECT * FROM main.transactions       WHERE deal_ymd>='2025-01-01'"),
  ("rentals",            "SELECT * FROM main.rentals            WHERE deal_ymd>='2025-01-01'"),
  ("silv_transactions",  "SELECT * FROM main.silv_transactions  WHERE deal_ymd>='2025-01-01'"),
  ("rh_transactions",    "SELECT * FROM main.rh_transactions    WHERE deal_ymd>='2025-01-01'"),
  ("rh_rentals",         "SELECT * FROM main.rh_rentals         WHERE deal_ymd>='2025-01-01'"),
  ("offi_transactions",  "SELECT * FROM main.offi_transactions  WHERE deal_ymd>='2025-01-01'"),
  ("offi_rentals",       "SELECT * FROM main.offi_rentals       WHERE deal_ymd>='2025-01-01'"),
  ("sh_transactions",    "SELECT * FROM main.sh_transactions    WHERE deal_ymd>='2025-01-01'"),
  ("sh_rentals",         "SELECT * FROM main.sh_rentals         WHERE deal_ymd>='2025-01-01'"),
  ("nrg_transactions",   "SELECT * FROM main.nrg_transactions   WHERE deal_ymd>='2025-01-01'"),
  ("article_events",     "SELECT * FROM main.article_events WHERE event_date>='2026-08-01'"),
  ("article_events_daily",
   "SELECT event_date, event_type, trade_type, COUNT(*) n FROM main.article_events GROUP BY 1,2,3"),
  # 매물 요약 — parquet 없이도 바로 비교할 수 있게 집계만 얹는다.
  ("listings_summary",
   """SELECT substr(c.cortar_no,1,5) sgg, l.real_estate_type, l.trade_type,
             COUNT(*) n, COUNT(DISTINCT l.complex_no) complexes,
             SUM(CASE WHEN l.deal_or_warrant_price>0 THEN 1 ELSE 0 END) priced,
             AVG(l.deal_or_warrant_price) avg_price
        FROM main.listings_current l LEFT JOIN main.complexes c ON c.complex_no=l.complex_no
       GROUP BY 1,2,3"""),
]

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def main():
    D.mkdir(parents=True, exist_ok=True); (D / "parquet").mkdir(exist_ok=True)
    log("parquet 사본")
    srcs = [Path(f"/opt/koczip/data/archive/listings/2026/08/listings_{DATE}.parquet")]
    srcs += [Path(f"/opt/koczip/data/archive/{c}/2026/08/{c}_{DATE}.parquet") for c in CATS]
    for s in srcs:
        if not s.exists(): log(f"  !! MISSING {s}"); return 2
        shutil.copy2(s, D / "parquet" / s.name)
    log(f"  {len(srcs)}개")

    for p in (B, Path(str(B) + "-journal")):
        if p.exists(): p.unlink()

    for name, sql in JOBS:
        t0 = time.time()
        con = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True, timeout=60)
        con.execute(f"ATTACH '{B}' AS b")
        con.execute("PRAGMA b.journal_mode=OFF"); con.execute("PRAGMA b.synchronous=OFF")
        if "SELECT * FROM main." in sql:                 # * → 컬럼 명시(무거운 JSON 제외)
            src = sql.split("FROM main.")[1].split()[0]
            sql = sql.replace("SELECT *", f"SELECT {cols_of(con, src)}", 1)
        con.execute(f"CREATE TABLE b.{name} AS {sql}")
        con.commit()
        n = con.execute(f"SELECT COUNT(*) FROM b.{name}").fetchone()[0]
        con.execute("DETACH b"); con.close()          # 커넥션마다 닫아 WAL 체크포인트 허용
        log(f"  {name:<22}{n:>10,}  ({time.time()-t0:.0f}s, {B.stat().st_size/1e6:.0f}MB)")

    bc = sqlite3.connect(f"file:{B}?mode=ro", uri=True)
    rows = [(t, bc.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
            for (t,) in bc.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    bc.close()
    out = ["# 2026년 세제개편안 발표(2026-08-03 18:00 KST) 직전 기준선",
           f"# 생성: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
           "# 매물 원본은 parquet가 정본(baseline.sqlite에는 집계만).", "", "## baseline.sqlite"]
    out += [f"{t:<24}{n:>12,}" for t, n in rows]
    out += ["", "## parquet (sha256)"]
    for f in sorted((D / "parquet").iterdir()):
        out.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}  ({f.stat().st_size/1e6:.1f}MB)")
    (D / "MANIFEST.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    log("완료\n" + "\n".join(out))
    return 0

sys.exit(main())
