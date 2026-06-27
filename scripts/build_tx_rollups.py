"""실거래 평형별 일단위 사전집계(tx_avg_rollup) 빌더.

quick_deals 등 "단지×평형 실거래 평균" 계열 쿼리의 바닥 계산 —
  transactions/rentals × complex_areas 의 ROW_NUMBER 평형 매칭 + 집계 —
을 밤에 1번만 수행해 일단위 rollup 으로 저장한다. 이후 쿼리는 이 작은
테이블에서 SUM(sum_amt)/SUM(n) 으로 어떤 일수 윈도우든 **정확히 동일한**
평균을 0.1초에 얻는다 (금액이 정수라 합산이 2^53 미만 → 부동소수점까지 동일).

정확성 보존 원칙:
- 평형 매칭 SQL 은 local_api.quick_deals 의 union_real 과 **글자까지 동일**
  (ORDER BY ABS(...) 동점 처리 포함). 다른 점은 날짜필터가 없고(전 기간)
  GROUP BY 에 deal_ymd 가 추가된 것뿐.
- 필터(직거래 제외 / monthly_rent=0 / matched_score>=0.85 / area_tol=5.0)는
  kind 별로 베이크. 지역필터는 베이크하지 않음 — 매칭이 tx별 독립
  (PARTITION BY tx.rowid)이라 조회 시 complex_no IN (...) 후행 적용과 동치.

daily_run: 재매칭(step 11) 후·캐시 빌드(step 12) 전에 실행해야 한다.
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402

DB = settings.local_db_path

AREA_TOL = 5.0  # local_api.quick_deals 의 area_tol 과 반드시 동일

# kind 별 (원본테이블, 금액컬럼, 추가필터) — quick_deals 의 sale_tables/amount_col/
# extra_filter 매핑과 1:1. 변경 시 양쪽을 같이 바꿀 것.
# 매매(sale/offi_sale)는 해제거래(is_cancelled=1) 제외 — quick_deals extra_filter 와
# 글자까지 동일해야 함. 전월세는 국토부가 해제필드를 안 줘 is_cancelled 컬럼 없음.
KINDS = {
    "sale":        ("transactions",      "tx.deal_amount", "AND COALESCE(tx.dealing_gbn,'') <> '직거래' AND tx.is_cancelled = 0"),
    "jeonse":      ("rentals",           "tx.deposit",     "AND COALESCE(tx.monthly_rent,0) = 0"),
    "wolse":       ("rentals",           "tx.monthly_rent", "AND tx.monthly_rent > 0"),
    "offi_sale":   ("offi_transactions", "tx.deal_amount", "AND COALESCE(tx.dealing_gbn,'') <> '직거래' AND tx.is_cancelled = 0"),
    "offi_jeonse": ("offi_rentals",      "tx.deposit",     "AND COALESCE(tx.monthly_rent,0) = 0"),
    # 분양권/입주권 전매 — 거래금액=실거래총액이라 매매와 같은 scale. 해제건 제외.
    "silv":        ("silv_transactions", "tx.deal_amount", "AND tx.is_cancelled = 0"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tx_avg_rollup (
  kind       TEXT NOT NULL,
  complex_no TEXT NOT NULL,
  pyeong     TEXT NOT NULL,      -- complex_areas.pyeong_name (= listings area_name)
  deal_ymd   TEXT NOT NULL,      -- 일 단위 보존 → 임의 일수 윈도우 정확 재구성
  n          INTEGER NOT NULL,
  sum_amt    INTEGER NOT NULL,
  min_amt    INTEGER NOT NULL,
  max_amt    INTEGER NOT NULL,
  sum_excl   REAL    NOT NULL,   -- avg_excl 재구성용 (REAL 합산순서로 1e-9 ulp 차 가능)
  PRIMARY KEY (kind, complex_no, pyeong, deal_ymd)
);
CREATE INDEX IF NOT EXISTS txr_kind_ymd_idx ON tx_avg_rollup(kind, deal_ymd);
"""


def build(kind: str, c: sqlite3.Connection) -> tuple[int, float]:
    tbl, amount_col, extra_filter = KINDS[kind]
    t0 = time.perf_counter()
    c.execute("DELETE FROM tx_avg_rollup WHERE kind=?", (kind,))
    # 매칭 서브쿼리: quick_deals union_real 과 동일 (날짜필터 제외, deal_ymd 추출 추가)
    c.execute(
        f"""
        INSERT INTO tx_avg_rollup
          (kind, complex_no, pyeong, deal_ymd, n, sum_amt, min_amt, max_amt, sum_excl)
        SELECT ?, cno, pyeong, deal_ymd,
               COUNT(*), SUM(amount), MIN(amount), MAX(amount), SUM(tx_excl)
        FROM (
            SELECT tx.matched_complex_no AS cno,
                   ca.pyeong_name AS pyeong,
                   tx.deal_ymd    AS deal_ymd,
                   tx.excl_use_ar AS tx_excl,
                   {amount_col} AS amount,
                   ROW_NUMBER() OVER (
                     PARTITION BY tx.rowid
                     ORDER BY ABS(ca.exclusive_area - tx.excl_use_ar)
                   ) AS rn
            FROM {tbl} tx
            JOIN complex_areas ca
              ON ca.complex_no = tx.matched_complex_no
             AND ca.exclusive_area IS NOT NULL
             AND ABS(ca.exclusive_area - tx.excl_use_ar) <= {AREA_TOL}
            WHERE tx.matched_complex_no IS NOT NULL
              AND tx.excl_use_ar IS NOT NULL
              {extra_filter}
              AND tx.matched_score >= 0.85
        )
        WHERE rn = 1 AND pyeong IS NOT NULL
        GROUP BY cno, pyeong, deal_ymd
        """,
        (kind,),
    )
    n = c.execute("SELECT COUNT(*) FROM tx_avg_rollup WHERE kind=?", (kind,)).fetchone()[0]
    c.commit()
    return n, time.perf_counter() - t0


# ───────────────────────────────────────────────────────────────────
# tx_area_rollup — area_key(=ROUND(전용면적)) 기준 사전집계.
# tx-gap/jeonse-rate/price-change/pyeong-price/turnover/yield 랭킹 엔드포인트용.
# tx_avg_rollup 과 다른 점:
#   - 그룹키가 pyeong_name(complex_areas 조인) 이 아니라 ROUND(excl_use_ar) → 조인 없음(빠름).
#   - 매매에 '직거래 제외'·matched_score 필터 없음 (랭킹 엔드포인트가 안 거름).
#   - wolse 는 sum_amt=월세, sum_amt2=보증금 둘 다 보존(수익률 계산용).
# area_key 별 일단위 보존 → 임의 일수 윈도우(가격변동 recent/prev 포함) 정확 재구성.
SCHEMA_AREA = """
CREATE TABLE IF NOT EXISTS tx_area_rollup (
  kind       TEXT NOT NULL,
  complex_no TEXT NOT NULL,
  area_key   INTEGER NOT NULL,    -- CAST(ROUND(excl_use_ar) AS INTEGER)
  deal_ymd   TEXT NOT NULL,
  n          INTEGER NOT NULL,
  sum_amt    INTEGER NOT NULL,    -- sale:deal_amount, jeonse:deposit, wolse:monthly_rent
  sum_amt2   INTEGER,             -- wolse:deposit (그 외 NULL)
  max_amt    INTEGER NOT NULL,    -- 해당 일자 최고 금액(신고가 tx-record-high 재구성용)
  sum_excl   REAL    NOT NULL,    -- 평당가 avg 면적 재구성용
  PRIMARY KEY (kind, complex_no, area_key, deal_ymd)
);
CREATE INDEX IF NOT EXISTS txa_kind_ymd_idx ON tx_area_rollup(kind, deal_ymd);
"""

# kind → (원본테이블, 금액컬럼, 보조금액컬럼 or None, 필터)
KINDS_AREA = {
    "sale":        ("transactions",      "deal_amount", None,      "AND is_cancelled = 0"),
    "jeonse":      ("rentals",           "deposit",     None,      "AND monthly_rent = 0"),
    "wolse":       ("rentals",           "monthly_rent", "deposit", "AND monthly_rent > 0"),
    "offi_sale":   ("offi_transactions", "deal_amount", None,      "AND is_cancelled = 0"),
    "offi_jeonse": ("offi_rentals",      "deposit",     None,      "AND monthly_rent = 0"),
    "offi_wolse":  ("offi_rentals",      "monthly_rent", "deposit", "AND monthly_rent > 0"),
    "silv":        ("silv_transactions", "deal_amount", None,      "AND is_cancelled = 0"),
}


def build_area(kind: str, c: sqlite3.Connection) -> tuple[int, float]:
    tbl, amt, amt2, filt = KINDS_AREA[kind]
    amt2_sql = f"SUM({amt2})" if amt2 else "NULL"
    t0 = time.perf_counter()
    c.execute("DELETE FROM tx_area_rollup WHERE kind=?", (kind,))
    c.execute(
        f"""
        INSERT INTO tx_area_rollup (kind, complex_no, area_key, deal_ymd, n, sum_amt, sum_amt2, max_amt, sum_excl)
        SELECT ?, matched_complex_no, CAST(ROUND(excl_use_ar) AS INTEGER), deal_ymd,
               COUNT(*), SUM({amt}), {amt2_sql}, MAX({amt}), SUM(excl_use_ar)
        FROM {tbl}
        WHERE matched_complex_no IS NOT NULL AND excl_use_ar IS NOT NULL {filt}
        GROUP BY matched_complex_no, CAST(ROUND(excl_use_ar) AS INTEGER), deal_ymd
        """,
        (kind,),
    )
    n = c.execute("SELECT COUNT(*) FROM tx_area_rollup WHERE kind=?", (kind,)).fetchone()[0]
    c.commit()
    return n, time.perf_counter() - t0


# ───────────────────────────────────────────────────────────────────
# tx_record_rollup — 단지×평형(area_key)당 '역대 최고가 + 직전 최고가' 1행 사전집계.
# tx-record-high(신고가 경신) 전용. tx_area_rollup(일별 max_amt) 에서 계산:
#   record_price = MAX(max_amt), record_date = 그 날, prev_high = record_date 이전 max,
#   prev_date = prev_high 최초 수립일, n_total/n_prior = 거래수. (라이브와 정확히 동일)
# 전기간 스캔이 필요한 record-high 를 단지당 1행 조회로 바꿔 콜드 25s → 0.x초.
SCHEMA_RECORD = """
CREATE TABLE IF NOT EXISTS tx_record_rollup (
  kind         TEXT NOT NULL,
  complex_no   TEXT NOT NULL,
  area_key     INTEGER NOT NULL,
  record_price INTEGER NOT NULL,
  record_date  TEXT NOT NULL,
  prev_high    INTEGER NOT NULL,
  prev_date    TEXT,
  n_total      INTEGER NOT NULL,
  n_prior      INTEGER NOT NULL,
  PRIMARY KEY (kind, complex_no, area_key)
);
CREATE INDEX IF NOT EXISTS txr_rec_date_idx ON tx_record_rollup(kind, record_date);
"""

RECORD_KINDS = list(KINDS_AREA.keys())  # sale/jeonse/wolse + offi_*


def build_record(kind: str, c: sqlite3.Connection) -> tuple[int, float]:
    t0 = time.perf_counter()
    c.execute("DELETE FROM tx_record_rollup WHERE kind=?", (kind,))
    # prev_high 가 있는(=record 이전 거래가 있는) 그룹만 = 신고가 경신 후보.
    c.execute(
        """
        INSERT INTO tx_record_rollup
          (kind, complex_no, area_key, record_price, record_date, prev_high, prev_date, n_total, n_prior)
        WITH a AS (
          SELECT complex_no AS cno, area_key, deal_ymd, max_amt, n
          FROM tx_area_rollup WHERE kind=?
        ),
        grp AS (SELECT cno, area_key, MAX(max_amt) AS record_price, SUM(n) AS n_total
                FROM a GROUP BY cno, area_key),
        rec AS (
          SELECT a.cno, a.area_key, g.record_price, g.n_total,
                 MAX(CASE WHEN a.max_amt=g.record_price THEN a.deal_ymd END) AS record_date
          FROM a JOIN grp g ON g.cno=a.cno AND g.area_key=a.area_key
          GROUP BY a.cno, a.area_key
        ),
        prev AS (
          SELECT a.cno, a.area_key, MAX(a.max_amt) AS prev_high, SUM(a.n) AS n_prior
          FROM a JOIN rec r ON r.cno=a.cno AND r.area_key=a.area_key
          WHERE a.deal_ymd < r.record_date
          GROUP BY a.cno, a.area_key
        ),
        prevd AS (
          SELECT a.cno, a.area_key, MIN(a.deal_ymd) AS prev_date
          FROM a JOIN rec r ON r.cno=a.cno AND r.area_key=a.area_key
          JOIN prev p ON p.cno=a.cno AND p.area_key=a.area_key AND a.max_amt=p.prev_high
          WHERE a.deal_ymd < r.record_date
          GROUP BY a.cno, a.area_key
        )
        SELECT ?, r.cno, r.area_key, r.record_price, r.record_date,
               p.prev_high, pd.prev_date, r.n_total, p.n_prior
        FROM rec r
        JOIN prev p ON p.cno=r.cno AND p.area_key=r.area_key
        JOIN prevd pd ON pd.cno=r.cno AND pd.area_key=r.area_key
        """,
        (kind, kind),
    )
    n = c.execute("SELECT COUNT(*) FROM tx_record_rollup WHERE kind=?", (kind,)).fetchone()[0]
    c.commit()
    return n, time.perf_counter() - t0


SCHEMA_RENTREF = """
CREATE TABLE IF NOT EXISTS rent_ref_sgg (
  sgg5     TEXT PRIMARY KEY,   -- 시군구 코드(5자리)
  rent_cap INTEGER NOT NULL,   -- 실거래 월세 p99 × 1.5 (원). 매물 월세 상한 기준.
  n        INTEGER NOT NULL    -- 표본수
);
"""


def build_rent_ref(c: sqlite3.Connection) -> tuple[int, float]:
    """시군구별 실거래 월세 상한 기준 — 깨끗한 실거래 월세(원)의 p99×1.5.
    매물 월세 이상치(보증금 오입력·제주 년세 등)를 지역 적응적으로 발라내는 데 사용.
    실거래는 오류 0%에 수렴하고 제주 년세도 월 단위로 정확 신고되므로 신뢰 기준이 됨."""
    t0 = time.perf_counter()
    c.execute("DELETE FROM rent_ref_sgg")
    c.execute(
        """
        INSERT INTO rent_ref_sgg(sgg5, rent_cap, n)
        WITH u AS (
          SELECT sgg_cd AS sgg, monthly_rent AS r FROM rentals
            WHERE monthly_rent>0 AND sgg_cd IS NOT NULL AND deal_ymd>=date('now','-3 years')
          UNION ALL
          SELECT sgg_cd AS sgg, monthly_rent AS r FROM offi_rentals
            WHERE monthly_rent>0 AND sgg_cd IS NOT NULL AND deal_ymd>=date('now','-3 years')
        ),
        d AS (SELECT sgg, r, CUME_DIST() OVER (PARTITION BY sgg ORDER BY r) cd FROM u)
        SELECT sgg,
               CAST(COALESCE(MAX(CASE WHEN cd<=0.99 THEN r END), MAX(r)) * 1.5 AS INTEGER) AS cap,
               COUNT(*) AS n
        FROM d GROUP BY sgg HAVING COUNT(*) >= 20
        """
    )
    n = c.execute("SELECT COUNT(*) FROM rent_ref_sgg").fetchone()[0]
    return n, time.perf_counter() - t0


def main() -> None:
    t_all = time.perf_counter()
    with sqlite3.connect(DB) as c:
        # WAL 파일 상한 1GB — 롤업 재빌드(수백만 행)가 WAL을 GB로 부풀린 뒤 안 줄던 문제 방지.
        c.execute("PRAGMA journal_size_limit=1073741824")
        c.executescript(SCHEMA)
        c.executescript(SCHEMA_AREA)
        c.executescript(SCHEMA_RECORD)
        c.executescript(SCHEMA_RENTREF)
        total = 0
        for kind in KINDS:
            n, dt = build(kind, c)
            total += n
            print(f"  {kind:12s} {n:>8,} rows  {dt:6.1f}s", flush=True)
        for kind in KINDS_AREA:
            n, dt = build_area(kind, c)
            total += n
            print(f"  area:{kind:11s} {n:>8,} rows  {dt:6.1f}s", flush=True)
        for kind in RECORD_KINDS:
            n, dt = build_record(kind, c)
            total += n
            print(f"  record:{kind:9s} {n:>8,} rows  {dt:6.1f}s", flush=True)
        # 통계 갱신 — 플래너가 새 테이블 인덱스를 잘 쓰도록
        c.execute("ANALYZE tx_avg_rollup")
        c.execute("ANALYZE tx_area_rollup")
        c.execute("ANALYZE tx_record_rollup")
        c.commit()
    print(f"DONE  {total:,} rows  wall {time.perf_counter()-t_all:.1f}s  ({DB})")


if __name__ == "__main__":
    main()
