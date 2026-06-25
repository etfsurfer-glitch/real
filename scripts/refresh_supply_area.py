"""실거래 테이블에 supply_area 컬럼 채우기.

Naver listings_current의 (complex_no, area2_m2=전용) → area1_m2=공급
매핑을 만들어서 transactions/rentals/offi_* 의 excl_use_ar를 공급면적으로 변환.

전용율이 단지마다 다름 (특히 오피스텔 50-70%). 단순 ×1.33 변환보다 훨씬 정확.

사용:
  python scripts/refresh_supply_area.py
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402

TARGET_TABLES = ["transactions", "rentals", "offi_transactions", "offi_rentals"]


def open_db():
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.execute("PRAGMA busy_timeout=30000")
    return c


def ensure_columns(conn):
    for tbl in TARGET_TABLES:
        try:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN supply_area REAL")
            print(f"  added column: {tbl}.supply_area")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    conn.commit()


def build_supply_lookup(conn):
    """(complex_no, area_key=round(전용)) → 공급 매핑.
    1순위: complex_areas (Naver 단지 detail의 모든 평형 type)
    2순위: listings_current (현재 매물의 공급/전용 pair)
    """
    conn.execute("DROP TABLE IF EXISTS _supply_lookup")
    conn.execute("""
        CREATE TEMP TABLE _supply_lookup AS
        SELECT complex_no,
               CAST(ROUND(exclusive_area) AS INTEGER) AS area_key,
               AVG(supply_area) AS supply_area,
               COUNT(*) AS n
        FROM complex_areas
        WHERE exclusive_area IS NOT NULL AND supply_area IS NOT NULL
          AND exclusive_area > 0
        GROUP BY complex_no, area_key
    """)
    n_from_master = conn.execute("SELECT COUNT(*) FROM _supply_lookup").fetchone()[0]
    print(f"  complex_areas → lookup: {n_from_master:,}")
    # listings_current로 보완 (master에 없는 평형 — 임대주택, 분양권 등)
    conn.execute("""
        INSERT INTO _supply_lookup (complex_no, area_key, supply_area, n)
        SELECT l.complex_no,
               CAST(ROUND(l.area2_m2) AS INTEGER) AS area_key,
               AVG(l.area1_m2) AS supply_area,
               COUNT(*) AS n
        FROM listings_current l
        WHERE l.area1_m2 IS NOT NULL AND l.area2_m2 IS NOT NULL AND l.area2_m2 > 0
          AND NOT EXISTS (
            SELECT 1 FROM _supply_lookup s
            WHERE s.complex_no = l.complex_no
              AND s.area_key = CAST(ROUND(l.area2_m2) AS INTEGER)
          )
        GROUP BY l.complex_no, area_key
    """)
    conn.execute("CREATE INDEX _supply_lookup_idx ON _supply_lookup(complex_no, area_key)")
    n_total = conn.execute("SELECT COUNT(*) FROM _supply_lookup").fetchone()[0]
    print(f"  total lookup entries: {n_total:,} (+{n_total - n_from_master:,} from listings)")
    return n_total


def update_supply_fast(conn):
    """Python-side dict lookup + executemany. SQLite correlated subquery 보다 훨씬 빠름."""
    print("  loading lookups into memory...", flush=True)
    # 1) complex_areas 1순위 lookup
    supply_lookup = {}
    for r in conn.execute("""
        SELECT complex_no, CAST(ROUND(exclusive_area) AS INTEGER) AS area_key, AVG(supply_area) AS sa
        FROM complex_areas WHERE exclusive_area IS NOT NULL AND supply_area IS NOT NULL AND exclusive_area > 0
        GROUP BY complex_no, area_key
    """):
        supply_lookup[(r[0], r[1])] = r[2]
    # listings 보완
    for r in conn.execute("""
        SELECT complex_no, CAST(ROUND(area2_m2) AS INTEGER) AS area_key, AVG(area1_m2) AS sa
        FROM listings_current WHERE area1_m2 IS NOT NULL AND area2_m2 IS NOT NULL AND area2_m2 > 0
        GROUP BY complex_no, area_key
    """):
        supply_lookup.setdefault((r[0], r[1]), r[2])
    print(f"    lookup entries: {len(supply_lookup):,}")
    # 2) 단지별 평균 전용율 (fallback)
    ratio_map = {}
    for r in conn.execute("""
        SELECT complex_no, AVG(area1_m2 / area2_m2)
        FROM listings_current WHERE area1_m2 IS NOT NULL AND area2_m2 > 0
          AND area1_m2 / area2_m2 BETWEEN 1.0 AND 2.5
        GROUP BY complex_no
    """):
        ratio_map[r[0]] = r[1]
    print(f"    complex ratios: {len(ratio_map):,}")

    def _resolve(cno, excl):
        if excl is None or cno is None:
            return None
        key = int(round(excl))
        # ±1 tolerance
        for dk in (0, -1, 1):
            v = supply_lookup.get((cno, key + dk))
            if v is not None:
                return v
        # ratio fallback
        ratio = ratio_map.get(cno)
        return excl * ratio if ratio else None

    for tbl in TARGET_TABLES:
        t0 = time.time()
        print(f"  updating {tbl}...", flush=True)
        # fetch all rows needing supply
        rows = conn.execute(
            f"SELECT rowid, matched_complex_no, excl_use_ar FROM {tbl} "
            f"WHERE matched_complex_no IS NOT NULL AND excl_use_ar IS NOT NULL"
        ).fetchall()
        updates = []
        for rid, cno, excl in rows:
            s = _resolve(cno, excl)
            if s is not None:
                updates.append((s, rid))
        # batch update
        conn.executemany(f"UPDATE {tbl} SET supply_area = ? WHERE rowid = ?", updates)
        conn.commit()
        elapsed = time.time() - t0
        print(f"    {tbl}: {len(updates):,}/{len(rows):,} updated ({elapsed:.1f}s)")


def update_supply(conn):
    """레거시 — 호환용. update_supply_fast 호출."""
    update_supply_fast(conn)


def _legacy_update_supply(conn):
    """전용±1㎡ tolerance로 lookup. 48.6 트랜잭션 ↔ 48.0 listings 같은 케이스 잡음."""
    # 단지별 평균 전용율 (area1=공급, area2=전용 → 공급/전용 평균)
    conn.execute("DROP TABLE IF EXISTS _complex_ratio")
    conn.execute("""
        CREATE TEMP TABLE _complex_ratio AS
        SELECT complex_no, AVG(area1_m2 / area2_m2) AS ratio
        FROM listings_current
        WHERE area1_m2 IS NOT NULL AND area2_m2 IS NOT NULL
          AND area2_m2 > 0 AND area1_m2 / area2_m2 BETWEEN 1.0 AND 2.5
        GROUP BY complex_no
    """)
    conn.execute("CREATE INDEX _complex_ratio_idx ON _complex_ratio(complex_no)")
    n_ratios = conn.execute("SELECT COUNT(*) FROM _complex_ratio").fetchone()[0]
    print(f"  complex ratios: {n_ratios:,}")

    # ±1 tolerance를 lookup table에 미리 explode → single-pass UPDATE
    conn.execute("DROP TABLE IF EXISTS _supply_expanded")
    conn.execute("""
        CREATE TEMP TABLE _supply_expanded AS
        SELECT complex_no, area_key, supply_area, 0 AS dist FROM _supply_lookup
        UNION ALL
        SELECT complex_no, area_key + 1 AS area_key, supply_area, 1 AS dist FROM _supply_lookup
        UNION ALL
        SELECT complex_no, area_key - 1 AS area_key, supply_area, 1 AS dist FROM _supply_lookup
    """)
    # 각 (complex, area_key)에 대해 가장 가까운 (dist 작은) 1행만 keep
    conn.execute("""
        CREATE TEMP TABLE _supply_final AS
        SELECT complex_no, area_key, supply_area
        FROM (
          SELECT complex_no, area_key, supply_area, dist,
                 ROW_NUMBER() OVER (PARTITION BY complex_no, area_key ORDER BY dist) AS rk
          FROM _supply_expanded
        )
        WHERE rk = 1
    """)
    conn.execute("CREATE INDEX _supply_final_idx ON _supply_final(complex_no, area_key)")
    n_f = conn.execute("SELECT COUNT(*) FROM _supply_final").fetchone()[0]
    print(f"  expanded lookup: {n_f:,} entries")

    for tbl in TARGET_TABLES:
        t0 = time.time()
        print(f"  updating {tbl}...", flush=True)
        conn.execute(f"""
            UPDATE {tbl} SET supply_area = COALESCE(
                (SELECT supply_area FROM _supply_final
                 WHERE complex_no = {tbl}.matched_complex_no
                   AND area_key = CAST(ROUND({tbl}.excl_use_ar) AS INTEGER)),
                {tbl}.excl_use_ar * (
                  SELECT ratio FROM _complex_ratio
                  WHERE complex_no = {tbl}.matched_complex_no
                )
            )
            WHERE matched_complex_no IS NOT NULL AND excl_use_ar IS NOT NULL
        """)
        conn.commit()
        elapsed = time.time() - t0
        n_filled = conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE supply_area IS NOT NULL").fetchone()[0]
        n_total = conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE matched_complex_no IS NOT NULL").fetchone()[0]
        print(f"    {tbl}: {n_filled:,}/{n_total:,} ({n_filled/max(n_total,1)*100:.1f}%)  {elapsed:.0f}s")


def main():
    conn = open_db()
    print("[1/2] adding supply_area columns...", flush=True)
    ensure_columns(conn)
    print("\n[2/2] populating supply_area (Python in-memory lookup)...", flush=True)
    update_supply_fast(conn)
    print("\ndone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
