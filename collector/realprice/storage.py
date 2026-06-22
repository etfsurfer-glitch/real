"""실거래 transactions 테이블 + insert/매칭 helpers (SQLite).

스키마는 sql/04_transactions.sql 의 Postgres 버전과 짝을 이룸.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    deal_id              TEXT PRIMARY KEY,
    -- transaction core
    deal_ymd             TEXT NOT NULL,           -- YYYY-MM-DD
    deal_year            INTEGER,
    deal_month           INTEGER,
    deal_day             INTEGER,
    deal_amount          INTEGER NOT NULL,        -- 원 단위
    -- location
    sgg_cd               TEXT,                    -- 시군구 5자리
    umd_nm               TEXT,                    -- 법정동
    apt_nm               TEXT,                    -- 거래원본 단지명
    apt_seq              TEXT,                    -- 단지 ID (실거래 API)
    jibun                TEXT,
    road_nm              TEXT,
    -- property
    floor                INTEGER,
    excl_use_ar          REAL,                    -- 전용면적 m²
    build_year           INTEGER,
    -- nature
    dealing_gbn          TEXT,                    -- 중개거래 / 직거래
    buyer_gbn            TEXT,
    sler_gbn             TEXT,
    -- cancellation (국토부 신고 후 해제)
    is_cancelled         INTEGER NOT NULL DEFAULT 0,  -- cdealType='O' → 1
    cancel_date          TEXT,                        -- cdealDay → YYYY-MM-DD
    -- matching
    matched_complex_no   TEXT,
    matched_method       TEXT,
    matched_score        REAL,
    match_details        TEXT,                    -- JSON
    manual_override      INTEGER NOT NULL DEFAULT 0,
    matched_at           TEXT,
    -- audit
    raw                  TEXT,
    inserted_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS transactions_sgg_ymd_idx   ON transactions(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS transactions_complex_idx   ON transactions(matched_complex_no, deal_ymd);
CREATE INDEX IF NOT EXISTS transactions_method_idx    ON transactions(matched_method);
CREATE INDEX IF NOT EXISTS transactions_unmatched_idx ON transactions(matched_complex_no)
    WHERE matched_complex_no IS NULL;
CREATE INDEX IF NOT EXISTS transactions_ymd_idx ON transactions(deal_ymd DESC);
CREATE INDEX IF NOT EXISTS transactions_amount_idx ON transactions(deal_amount DESC);
-- 실거래 취소조회: 해제여부(cdealType) 표현식 인덱스 + 해제일 정렬용.
CREATE INDEX IF NOT EXISTS tx_cdeal_idx
    ON transactions(json_extract(raw,'$.cdealType'), json_extract(raw,'$.cdealDay'));
-- 이중신고 판별(같은 거래 쌍둥이 존재여부) 룩업용.
CREATE INDEX IF NOT EXISTS tx_twin_idx
    ON transactions(apt_seq, deal_ymd, deal_amount, excl_use_ar, floor);
-- 지역펄스(월별 신고 펄스)용: deal_year IN(...) AND deal_month IN(...) 필터가 인덱스
-- 없으면 풀스캔(10s). (deal_year, deal_month) 로 seek → 0.6s.
CREATE INDEX IF NOT EXISTS tx_year_month_idx ON transactions(deal_year, deal_month);
-- 단지×타입 집계(신고가·평당가 등) covering index: 거대한 raw 컬럼을 건드리지 않고
-- 인덱스만 스캔하도록 (단지, 전용면적, 거래일, 거래가, 층) 포함. floor는 신고가 거래의
-- 층수 룩업까지 index-only로 처리하려고 후행 컬럼으로 추가.
CREATE INDEX IF NOT EXISTS tx_recordhigh_idx
    ON transactions(matched_complex_no, excl_use_ar, deal_ymd, deal_amount, floor);

-- 전월세 실거래 (RTMSDataSvcAptRent). trade_type:
--   'B1' 전세 = monthly_rent = 0
--   'B2' 월세 = monthly_rent > 0
CREATE TABLE IF NOT EXISTS rentals (
    rental_id            TEXT PRIMARY KEY,
    deal_ymd             TEXT NOT NULL,
    deal_year            INTEGER,
    deal_month           INTEGER,
    deal_day             INTEGER,
    deposit              INTEGER NOT NULL,        -- 보증금 (원)
    monthly_rent         INTEGER NOT NULL DEFAULT 0,
    sgg_cd               TEXT,
    umd_nm               TEXT,
    apt_nm               TEXT,
    jibun                TEXT,
    floor                INTEGER,
    excl_use_ar          REAL,
    build_year           INTEGER,
    contract_type        TEXT,                    -- 신규 / 갱신
    contract_term        TEXT,
    use_rr_right         TEXT,                    -- 갱신청구권 사용 여부
    pre_deposit          INTEGER,
    pre_monthly_rent     INTEGER,
    matched_complex_no   TEXT,
    matched_method       TEXT,
    matched_score        REAL,
    match_details        TEXT,
    manual_override      INTEGER NOT NULL DEFAULT 0,
    matched_at           TEXT,
    raw                  TEXT,
    inserted_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS rentals_sgg_ymd_idx ON rentals(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS rentals_complex_idx ON rentals(matched_complex_no, deal_ymd);
CREATE INDEX IF NOT EXISTS rentals_ymd_idx     ON rentals(deal_ymd DESC);
CREATE INDEX IF NOT EXISTS rentals_inserted_idx ON rentals(inserted_at DESC);
CREATE INDEX IF NOT EXISTS rentals_monthly_idx ON rentals(monthly_rent);
CREATE INDEX IF NOT EXISTS rentals_recordhigh_idx
    ON rentals(matched_complex_no, excl_use_ar, deal_ymd, monthly_rent, deposit, floor);

-- 오피스텔 매매 (RTMSDataSvcOffiTrade)
CREATE TABLE IF NOT EXISTS offi_transactions (
    deal_id              TEXT PRIMARY KEY,
    deal_ymd             TEXT NOT NULL,
    deal_year            INTEGER,
    deal_month           INTEGER,
    deal_day             INTEGER,
    deal_amount          INTEGER NOT NULL,
    sgg_cd               TEXT,
    umd_nm               TEXT,
    offi_nm              TEXT,
    jibun                TEXT,
    floor                INTEGER,
    excl_use_ar          REAL,
    build_year           INTEGER,
    dealing_gbn          TEXT,
    buyer_gbn            TEXT,
    sler_gbn             TEXT,
    is_cancelled         INTEGER NOT NULL DEFAULT 0,  -- cdealType='O' → 1
    cancel_date          TEXT,                        -- cdealDay → YYYY-MM-DD
    matched_complex_no   TEXT,
    matched_method       TEXT,
    matched_score        REAL,
    match_details        TEXT,
    manual_override      INTEGER NOT NULL DEFAULT 0,
    matched_at           TEXT,
    raw                  TEXT,
    inserted_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS offi_tx_sgg_ymd_idx  ON offi_transactions(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS offi_tx_complex_idx  ON offi_transactions(matched_complex_no, deal_ymd);
CREATE INDEX IF NOT EXISTS offi_tx_ymd_idx      ON offi_transactions(deal_ymd DESC);
CREATE INDEX IF NOT EXISTS offi_tx_inserted_idx ON offi_transactions(inserted_at DESC);
CREATE INDEX IF NOT EXISTS offi_tx_year_month_idx ON offi_transactions(deal_year, deal_month);
CREATE INDEX IF NOT EXISTS offi_tx_cdeal_idx
    ON offi_transactions(json_extract(raw,'$.cdealType'), json_extract(raw,'$.cdealDay'));
CREATE INDEX IF NOT EXISTS offi_tx_twin_idx
    ON offi_transactions(offi_nm, deal_ymd, deal_amount, excl_use_ar, floor);
CREATE INDEX IF NOT EXISTS offitx_recordhigh_idx
    ON offi_transactions(matched_complex_no, excl_use_ar, deal_ymd, deal_amount, floor);

-- 오피스텔 전월세 (RTMSDataSvcOffiRent)
CREATE TABLE IF NOT EXISTS offi_rentals (
    rental_id            TEXT PRIMARY KEY,
    deal_ymd             TEXT NOT NULL,
    deal_year            INTEGER,
    deal_month           INTEGER,
    deal_day             INTEGER,
    deposit              INTEGER NOT NULL,
    monthly_rent         INTEGER NOT NULL DEFAULT 0,
    sgg_cd               TEXT,
    umd_nm               TEXT,
    offi_nm              TEXT,
    jibun                TEXT,
    floor                INTEGER,
    excl_use_ar          REAL,
    build_year           INTEGER,
    contract_type        TEXT,
    contract_term        TEXT,
    use_rr_right         TEXT,
    pre_deposit          INTEGER,
    pre_monthly_rent     INTEGER,
    matched_complex_no   TEXT,
    matched_method       TEXT,
    matched_score        REAL,
    match_details        TEXT,
    manual_override      INTEGER NOT NULL DEFAULT 0,
    matched_at           TEXT,
    raw                  TEXT,
    inserted_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS offi_rent_sgg_ymd_idx  ON offi_rentals(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS offi_rent_complex_idx  ON offi_rentals(matched_complex_no, deal_ymd);
CREATE INDEX IF NOT EXISTS offi_rent_ymd_idx      ON offi_rentals(deal_ymd DESC);
CREATE INDEX IF NOT EXISTS offi_rent_inserted_idx ON offi_rentals(inserted_at DESC);
-- freshness('오늘 적재') 가 date(inserted_at) 로 필터/집계 — 표현식 인덱스 없으면 풀스캔.
CREATE INDEX IF NOT EXISTS offi_rent_inserted_date_idx ON offi_rentals(date(inserted_at));
CREATE INDEX IF NOT EXISTS offi_rent_monthly_idx  ON offi_rentals(monthly_rent);
CREATE INDEX IF NOT EXISTS offirent_recordhigh_idx
    ON offi_rentals(matched_complex_no, excl_use_ar, deal_ymd, monthly_rent, deposit, floor);

-- 아파트 분양권/입주권 전매 실거래 (RTMSDataSvcSilvTrade). 신축·재건축 신규공급
-- 세그먼트(기존 매매 transactions는 준공 아파트만 커버). ownership_gbn 으로 분양권/입주권 구분.
CREATE TABLE IF NOT EXISTS silv_transactions (
    deal_id              TEXT PRIMARY KEY,
    deal_ymd             TEXT NOT NULL,
    deal_year            INTEGER,
    deal_month           INTEGER,
    deal_day             INTEGER,
    deal_amount          INTEGER NOT NULL,        -- 전매 실거래가 (원). 분양가+P 포함
    sgg_cd               TEXT,
    umd_nm               TEXT,
    apt_nm               TEXT,                    -- 분양/입주 단지명
    jibun                TEXT,
    floor                INTEGER,
    excl_use_ar          REAL,
    ownership_gbn        TEXT,                    -- ownershipGbn: '분'=분양권 / '입'=입주권
    dealing_gbn          TEXT,                    -- 중개거래 / 직거래
    buyer_gbn            TEXT,
    sler_gbn             TEXT,
    is_cancelled         INTEGER NOT NULL DEFAULT 0,  -- cdealType='O' → 1
    cancel_date          TEXT,                        -- cdealDay → YYYY-MM-DD
    matched_complex_no   TEXT,
    matched_method       TEXT,
    matched_score        REAL,
    match_details        TEXT,
    manual_override      INTEGER NOT NULL DEFAULT 0,
    matched_at           TEXT,
    raw                  TEXT,
    inserted_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS silv_tx_sgg_ymd_idx  ON silv_transactions(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS silv_tx_complex_idx  ON silv_transactions(matched_complex_no, deal_ymd);
CREATE INDEX IF NOT EXISTS silv_tx_ymd_idx      ON silv_transactions(deal_ymd DESC);
CREATE INDEX IF NOT EXISTS silv_tx_inserted_idx ON silv_transactions(inserted_at DESC);
CREATE INDEX IF NOT EXISTS silv_tx_year_month_idx ON silv_transactions(deal_year, deal_month);
CREATE INDEX IF NOT EXISTS silv_tx_cdeal_idx
    ON silv_transactions(json_extract(raw,'$.cdealType'), json_extract(raw,'$.cdealDay'));
CREATE INDEX IF NOT EXISTS silv_tx_twin_idx
    ON silv_transactions(apt_nm, deal_ymd, deal_amount, excl_use_ar, floor);
CREATE INDEX IF NOT EXISTS silvtx_recordhigh_idx
    ON silv_transactions(matched_complex_no, excl_use_ar, deal_ymd, deal_amount, floor);

-- match_suggestions: naver_lookup이 찾았지만 자동 적용에는 confidence가
-- 부족한 후보들 (score < 0.85). 관리자가 admin UI에서 검토 후 accept/reject.
CREATE TABLE IF NOT EXISTS match_suggestions (
    suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    apt_nm                  TEXT NOT NULL,
    sgg_cd                  TEXT NOT NULL,
    umd_nm                  TEXT,
    tx_count                INTEGER,
    suggested_complex_no    TEXT NOT NULL,
    suggested_method        TEXT,
    suggested_score         REAL,
    details                 TEXT,         -- JSON: lookup debug + candidates
    status                  TEXT NOT NULL DEFAULT 'pending',  -- pending|accepted|rejected
    reviewed_at             TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(apt_nm, sgg_cd, suggested_complex_no)
);
CREATE INDEX IF NOT EXISTS suggestions_status_idx
    ON match_suggestions(status, suggested_score DESC);
CREATE INDEX IF NOT EXISTS suggestions_tx_count_idx
    ON match_suggestions(status, tx_count DESC);

-- 비단지: 연립다세대(빌라) 매매. 단지(complex) 매칭 안 함 — 지번+건물명(mhouse_nm)으로 지역 집계.
CREATE TABLE IF NOT EXISTS rh_transactions (
    deal_id      TEXT PRIMARY KEY,
    deal_ymd     TEXT NOT NULL, deal_year INTEGER, deal_month INTEGER, deal_day INTEGER,
    deal_amount  INTEGER NOT NULL,          -- 매매가(원)
    sgg_cd       TEXT, umd_nm TEXT, jibun TEXT,
    mhouse_nm    TEXT,                       -- 건물명(연립/빌라명)
    house_type   TEXT,                       -- 다세대/연립
    floor        INTEGER, excl_use_ar REAL, land_ar REAL, build_year INTEGER,
    dealing_gbn  TEXT, buyer_gbn TEXT, sler_gbn TEXT,
    is_cancelled INTEGER NOT NULL DEFAULT 0, cancel_date TEXT,
    raw          TEXT, inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS rh_tx_sgg_ymd_idx ON rh_transactions(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS rh_tx_ymd_idx     ON rh_transactions(deal_ymd DESC);

-- 비단지: 연립다세대(빌라) 전월세.
CREATE TABLE IF NOT EXISTS rh_rentals (
    deal_id      TEXT PRIMARY KEY,
    deal_ymd     TEXT NOT NULL, deal_year INTEGER, deal_month INTEGER, deal_day INTEGER,
    deposit      INTEGER, monthly_rent INTEGER,    -- 보증금/월세(원)
    sgg_cd       TEXT, umd_nm TEXT, jibun TEXT, mhouse_nm TEXT, house_type TEXT,
    floor        INTEGER, excl_use_ar REAL, build_year INTEGER,
    contract_type TEXT, contract_term TEXT, use_rr_right TEXT,
    pre_deposit  INTEGER, pre_monthly_rent INTEGER,
    raw          TEXT, inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS rh_rent_sgg_ymd_idx ON rh_rentals(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS rh_rent_ymd_idx     ON rh_rentals(deal_ymd DESC);

-- 비단지: 단독/다가구 매매(동 단위·지번 마스킹). 연면적/대지면적 → 토지가치 관점.
CREATE TABLE IF NOT EXISTS sh_transactions (
    deal_id      TEXT PRIMARY KEY,
    deal_ymd     TEXT NOT NULL, deal_year INTEGER, deal_month INTEGER, deal_day INTEGER,
    deal_amount  INTEGER NOT NULL,          -- 매매가(원)
    sgg_cd       TEXT, umd_nm TEXT,
    house_type   TEXT,                       -- 단독/다가구
    total_floor_ar REAL, plottage_ar REAL,   -- 연면적/대지면적(㎡)
    build_year   INTEGER, dealing_gbn TEXT, buyer_gbn TEXT, sler_gbn TEXT,
    is_cancelled INTEGER NOT NULL DEFAULT 0, cancel_date TEXT,
    raw          TEXT, inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS sh_tx_sgg_ymd_idx ON sh_transactions(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS sh_tx_ymd_idx     ON sh_transactions(deal_ymd DESC);

-- 비단지: 단독/다가구 전월세.
CREATE TABLE IF NOT EXISTS sh_rentals (
    deal_id      TEXT PRIMARY KEY,
    deal_ymd     TEXT NOT NULL, deal_year INTEGER, deal_month INTEGER, deal_day INTEGER,
    deposit      INTEGER, monthly_rent INTEGER,
    sgg_cd       TEXT, umd_nm TEXT, house_type TEXT,
    total_floor_ar REAL, build_year INTEGER,
    contract_type TEXT, contract_term TEXT, use_rr_right TEXT,
    pre_deposit  INTEGER, pre_monthly_rent INTEGER,
    raw          TEXT, inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS sh_rent_sgg_ymd_idx ON sh_rentals(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS sh_rent_ymd_idx     ON sh_rentals(deal_ymd DESC);

-- 비단지: 상업업무용(상가·사무실) 매매. 지번+건물용도(building_use)+용도지역(land_use)+층. 매매만.
CREATE TABLE IF NOT EXISTS nrg_transactions (
    deal_id      TEXT PRIMARY KEY,
    deal_ymd     TEXT NOT NULL, deal_year INTEGER, deal_month INTEGER, deal_day INTEGER,
    deal_amount  INTEGER NOT NULL,          -- 매매가(원)
    sgg_cd       TEXT, umd_nm TEXT, jibun TEXT,
    building_use TEXT,                       -- 판매/업무/제1·2종근린생활시설 등
    building_type TEXT,                      -- 집합/일반
    land_use     TEXT,                       -- 용도지역(제2종일반주거 등)
    building_ar  REAL, plottage_ar REAL, floor INTEGER, build_year INTEGER,
    dealing_gbn  TEXT, buyer_gbn TEXT, sler_gbn TEXT,
    is_cancelled INTEGER NOT NULL DEFAULT 0, cancel_date TEXT,
    raw          TEXT, inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS nrg_tx_sgg_ymd_idx ON nrg_transactions(sgg_cd, deal_ymd);
CREATE INDEX IF NOT EXISTS nrg_tx_use_idx     ON nrg_transactions(sgg_cd, building_use, deal_ymd);
CREATE INDEX IF NOT EXISTS nrg_tx_ymd_idx     ON nrg_transactions(deal_ymd DESC);
"""

_LOCK = threading.Lock()


def init_schema(conn: sqlite3.Connection) -> None:
    with _LOCK:
        conn.executescript(SCHEMA)
        conn.commit()


def make_deal_id(tx: dict) -> str:
    """Deterministic ID derived from all natural keys + amount. Reruns are idempotent."""
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay",
                "aptSeq", "aptNm", "umdNm", "jibun",
                "floor", "excluUseAr", "dealAmount"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def _cancel_state(tx: dict) -> tuple[int, str | None]:
    """국토부 해제정보 → (is_cancelled 0/1, cancel_date 'YYYY-MM-DD'|None).
    cdealType='O' 면 해제건. cdealDay 'YY.MM.DD' → 'YYYY-MM-DD'."""
    is_c = 1 if (tx.get("cdealType") or "").strip() == "O" else 0
    cd = None
    if is_c:
        parts = (tx.get("cdealDay") or "").strip().split(".")
        if len(parts) == 3 and all(parts):
            cd = f"20{parts[0].zfill(2)}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return is_c, cd


def _coerce_int(s: str | None) -> int | None:
    if not s:
        return None
    try:
        return int(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _coerce_float(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


def _coerce_amount_won(s: str | None) -> int | None:
    """'187,055' (만원) → 1,870,550,000원."""
    n = _coerce_int(s)
    return n * 10_000 if n is not None else None


def _ymd(tx: dict) -> tuple[str, int | None, int | None, int | None]:
    y = _coerce_int(tx.get("dealYear"))
    m = _coerce_int(tx.get("dealMonth"))
    d = _coerce_int(tx.get("dealDay"))
    if y and m and d:
        return f"{y:04d}-{m:02d}-{d:02d}", y, m, d
    return "", y, m, d


def upsert_transactions(
    conn: sqlite3.Connection,
    items: Iterable[dict],
    match_results: dict[str, dict] | None = None,
) -> dict[str, int]:
    """Insert/upsert. match_results: {deal_id: trace_dict} produced by
    matching.match_one_with_trace. Reruns on the same items are idempotent.
    """
    match_results = match_results or {}
    counts = {"inserted": 0, "updated": 0, "matched": 0, "unmatched": 0}
    rows = []
    now = datetime.now().isoformat(timespec="seconds")
    seen: dict[str, int] = {}  # 같은 응답 내 동일거래(이중신고) occurrence 추적

    for tx in items:
        base = make_deal_id(tx)
        # 이중신고(양측 중개사가 동일 거래·동일 금액 신고)는 base 가 동일.
        # occ 0 → 기존과 같은 id(하위호환), occ≥1 → 접미사로 별도 행 보존.
        occ = seen.get(base, 0)
        seen[base] = occ + 1
        deal_id = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        is_cancelled, cancel_date = _cancel_state(tx)
        trace = match_results.get(base)  # 쌍둥이는 동일 매칭 → base 로 룩업
        if trace and trace.get("chosen"):
            chosen = trace["chosen"]
            matched_no = chosen["complex_no"]
            method = chosen["method"]
            score = chosen["score"]
            counts["matched"] += 1
        else:
            matched_no = None
            method = "unmatched" if trace else None
            score = None
            if trace:
                counts["unmatched"] += 1

        rows.append((
            deal_id, ymd, y, m, d, amount,
            (tx.get("sggCd") or "").strip() or None,
            (tx.get("umdNm") or "").strip() or None,
            (tx.get("aptNm") or "").strip() or None,
            (tx.get("aptSeq") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None,
            (tx.get("roadNm") or "").strip() or None,
            _coerce_int(tx.get("floor")),
            _coerce_float(tx.get("excluUseAr")),
            _coerce_int(tx.get("buildYear")),
            (tx.get("dealingGbn") or "").strip() or None,
            (tx.get("buyerGbn") or "").strip() or None,
            (tx.get("slerGbn") or "").strip() or None,
            is_cancelled, cancel_date,
            matched_no, method, score,
            json.dumps(trace, ensure_ascii=False) if trace else None,
            now if trace else None,
            json.dumps(tx, ensure_ascii=False),
        ))

    if not rows:
        return counts

    with _LOCK:
        # ON CONFLICT 으로 재수집 시 매칭 + 해제상태 갱신(raw 도 최신으로). 해제는
        # 거래가 나중에 해제되면 cdealType='' → 'O' 로 바뀌므로 반드시 갱신해야
        # 시세집계에서 제외된다.
        conn.executemany(
            """
            INSERT INTO transactions(
                deal_id, deal_ymd, deal_year, deal_month, deal_day, deal_amount,
                sgg_cd, umd_nm, apt_nm, apt_seq, jibun, road_nm,
                floor, excl_use_ar, build_year,
                dealing_gbn, buyer_gbn, sler_gbn,
                is_cancelled, cancel_date,
                matched_complex_no, matched_method, matched_score,
                match_details, matched_at, raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deal_id) DO UPDATE SET
                matched_complex_no = excluded.matched_complex_no,
                matched_method     = excluded.matched_method,
                matched_score      = excluded.matched_score,
                match_details      = excluded.match_details,
                matched_at         = excluded.matched_at,
                is_cancelled       = excluded.is_cancelled,
                cancel_date        = excluded.cancel_date,
                raw                = excluded.raw
            WHERE manual_override = 0
            """,
            rows,
        )
        counts["inserted"] = len(rows)
        conn.commit()
    return counts


def make_rental_id(tx: dict) -> str:
    """Idempotent ID for one rent filing. Includes deposit + monthly_rent so
    a re-signed contract on the same day/floor/area gets its own row."""
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay",
                "aptNm", "umdNm", "jibun",
                "floor", "excluUseAr",
                "deposit", "monthlyRent",
                "contractType", "contractTerm"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_rentals(
    conn: sqlite3.Connection,
    items: Iterable[dict],
    match_results: dict[str, dict] | None = None,
) -> dict[str, int]:
    """Insert/upsert rent rows. match_results keyed by rental_id."""
    match_results = match_results or {}
    counts = {"inserted": 0, "matched": 0, "unmatched": 0}
    rows = []
    now = datetime.now().isoformat(timespec="seconds")

    for tx in items:
        rid = make_rental_id(tx)
        ymd, y, m, d = _ymd(tx)
        deposit = _coerce_amount_won(tx.get("deposit"))
        monthly = _coerce_amount_won(tx.get("monthlyRent")) or 0
        if deposit is None or not ymd:
            continue
        trace = match_results.get(rid)
        if trace and trace.get("chosen"):
            chosen = trace["chosen"]
            matched_no = chosen["complex_no"]
            method = chosen["method"]
            score = chosen["score"]
            counts["matched"] += 1
        else:
            matched_no = None
            method = "unmatched" if trace else None
            score = None
            if trace:
                counts["unmatched"] += 1

        rows.append((
            rid, ymd, y, m, d, deposit, monthly,
            (tx.get("sggCd") or "").strip() or None,
            (tx.get("umdNm") or "").strip() or None,
            (tx.get("aptNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None,
            _coerce_int(tx.get("floor")),
            _coerce_float(tx.get("excluUseAr")),
            _coerce_int(tx.get("buildYear")),
            (tx.get("contractType") or "").strip() or None,
            (tx.get("contractTerm") or "").strip() or None,
            (tx.get("useRRRight") or "").strip() or None,
            _coerce_amount_won(tx.get("preDeposit")),
            _coerce_amount_won(tx.get("preMonthlyRent")),
            matched_no, method, score,
            json.dumps(trace, ensure_ascii=False) if trace else None,
            now if trace else None,
            json.dumps(tx, ensure_ascii=False),
        ))

    if not rows:
        return counts

    with _LOCK:
        conn.executemany(
            """
            INSERT INTO rentals(
                rental_id, deal_ymd, deal_year, deal_month, deal_day,
                deposit, monthly_rent,
                sgg_cd, umd_nm, apt_nm, jibun,
                floor, excl_use_ar, build_year,
                contract_type, contract_term, use_rr_right,
                pre_deposit, pre_monthly_rent,
                matched_complex_no, matched_method, matched_score,
                match_details, matched_at, raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rental_id) DO UPDATE SET
                matched_complex_no = excluded.matched_complex_no,
                matched_method     = excluded.matched_method,
                matched_score      = excluded.matched_score,
                match_details      = excluded.match_details,
                matched_at         = excluded.matched_at
            WHERE manual_override = 0
            """,
            rows,
        )
        counts["inserted"] = len(rows)
        conn.commit()
    return counts


def make_offi_deal_id(tx: dict) -> str:
    """Idempotent ID for one office-trade filing."""
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay",
                "offiNm", "umdNm", "jibun",
                "floor", "excluUseAr", "dealAmount"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def make_offi_rental_id(tx: dict) -> str:
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay",
                "offiNm", "umdNm", "jibun",
                "floor", "excluUseAr",
                "deposit", "monthlyRent",
                "contractType", "contractTerm"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_offi_transactions(
    conn: sqlite3.Connection,
    items: Iterable[dict],
    match_results: dict[str, dict] | None = None,
) -> dict[str, int]:
    match_results = match_results or {}
    counts = {"inserted": 0, "matched": 0, "unmatched": 0}
    rows = []
    now = datetime.now().isoformat(timespec="seconds")
    seen: dict[str, int] = {}

    for tx in items:
        base = make_offi_deal_id(tx)
        occ = seen.get(base, 0)
        seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        is_cancelled, cancel_date = _cancel_state(tx)
        trace = match_results.get(base)
        if trace and trace.get("chosen"):
            chosen = trace["chosen"]
            matched_no = chosen["complex_no"]
            method = chosen["method"]
            score = chosen["score"]
            counts["matched"] += 1
        else:
            matched_no = None
            method = "unmatched" if trace else None
            score = None
            if trace:
                counts["unmatched"] += 1

        rows.append((
            did, ymd, y, m, d, amount,
            (tx.get("sggCd") or "").strip() or None,
            (tx.get("umdNm") or "").strip() or None,
            (tx.get("offiNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None,
            _coerce_int(tx.get("floor")),
            _coerce_float(tx.get("excluUseAr")),
            _coerce_int(tx.get("buildYear")),
            (tx.get("dealingGbn") or "").strip() or None,
            (tx.get("buyerGbn") or "").strip() or None,
            (tx.get("slerGbn") or "").strip() or None,
            is_cancelled, cancel_date,
            matched_no, method, score,
            json.dumps(trace, ensure_ascii=False) if trace else None,
            now if trace else None,
            json.dumps(tx, ensure_ascii=False),
        ))

    if not rows:
        return counts

    with _LOCK:
        conn.executemany(
            """
            INSERT INTO offi_transactions(
                deal_id, deal_ymd, deal_year, deal_month, deal_day, deal_amount,
                sgg_cd, umd_nm, offi_nm, jibun,
                floor, excl_use_ar, build_year,
                dealing_gbn, buyer_gbn, sler_gbn,
                is_cancelled, cancel_date,
                matched_complex_no, matched_method, matched_score,
                match_details, matched_at, raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deal_id) DO UPDATE SET
                matched_complex_no = excluded.matched_complex_no,
                matched_method     = excluded.matched_method,
                matched_score      = excluded.matched_score,
                match_details      = excluded.match_details,
                matched_at         = excluded.matched_at,
                is_cancelled       = excluded.is_cancelled,
                cancel_date        = excluded.cancel_date,
                raw                = excluded.raw
            WHERE manual_override = 0
            """,
            rows,
        )
        counts["inserted"] = len(rows)
        conn.commit()
    return counts


def upsert_offi_rentals(
    conn: sqlite3.Connection,
    items: Iterable[dict],
    match_results: dict[str, dict] | None = None,
) -> dict[str, int]:
    match_results = match_results or {}
    counts = {"inserted": 0, "matched": 0, "unmatched": 0}
    rows = []
    now = datetime.now().isoformat(timespec="seconds")

    for tx in items:
        rid = make_offi_rental_id(tx)
        ymd, y, m, d = _ymd(tx)
        deposit = _coerce_amount_won(tx.get("deposit"))
        monthly = _coerce_amount_won(tx.get("monthlyRent")) or 0
        if deposit is None or not ymd:
            continue
        trace = match_results.get(rid)
        if trace and trace.get("chosen"):
            chosen = trace["chosen"]
            matched_no = chosen["complex_no"]
            method = chosen["method"]
            score = chosen["score"]
            counts["matched"] += 1
        else:
            matched_no = None
            method = "unmatched" if trace else None
            score = None
            if trace:
                counts["unmatched"] += 1

        rows.append((
            rid, ymd, y, m, d, deposit, monthly,
            (tx.get("sggCd") or "").strip() or None,
            (tx.get("umdNm") or "").strip() or None,
            (tx.get("offiNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None,
            _coerce_int(tx.get("floor")),
            _coerce_float(tx.get("excluUseAr")),
            _coerce_int(tx.get("buildYear")),
            (tx.get("contractType") or "").strip() or None,
            (tx.get("contractTerm") or "").strip() or None,
            (tx.get("useRRRight") or "").strip() or None,
            _coerce_amount_won(tx.get("preDeposit")),
            _coerce_amount_won(tx.get("preMonthlyRent")),
            matched_no, method, score,
            json.dumps(trace, ensure_ascii=False) if trace else None,
            now if trace else None,
            json.dumps(tx, ensure_ascii=False),
        ))

    if not rows:
        return counts

    with _LOCK:
        conn.executemany(
            """
            INSERT INTO offi_rentals(
                rental_id, deal_ymd, deal_year, deal_month, deal_day,
                deposit, monthly_rent,
                sgg_cd, umd_nm, offi_nm, jibun,
                floor, excl_use_ar, build_year,
                contract_type, contract_term, use_rr_right,
                pre_deposit, pre_monthly_rent,
                matched_complex_no, matched_method, matched_score,
                match_details, matched_at, raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rental_id) DO UPDATE SET
                matched_complex_no = excluded.matched_complex_no,
                matched_method     = excluded.matched_method,
                matched_score      = excluded.matched_score,
                match_details      = excluded.match_details,
                matched_at         = excluded.matched_at
            WHERE manual_override = 0
            """,
            rows,
        )
        counts["inserted"] = len(rows)
        conn.commit()
    return counts


def make_silv_deal_id(tx: dict) -> str:
    """분양권 전매 1건의 idempotent ID. 분양권/입주권(ownershipGbn) 포함 —
    같은 호실이 분양권→입주권으로 신고되면 별도 거래로 본다."""
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay",
                "aptNm", "umdNm", "jibun",
                "floor", "excluUseAr", "dealAmount", "ownershipGbn"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_silv_transactions(
    conn: sqlite3.Connection,
    items: Iterable[dict],
    match_results: dict[str, dict] | None = None,
) -> dict[str, int]:
    """분양권/입주권 전매 insert/upsert. offi_transactions 와 동일 패턴 +
    ownership_gbn. 이중신고(occ)·해제상태 갱신·매칭 트레이스 모두 동일."""
    match_results = match_results or {}
    counts = {"inserted": 0, "matched": 0, "unmatched": 0}
    rows = []
    now = datetime.now().isoformat(timespec="seconds")
    seen: dict[str, int] = {}

    for tx in items:
        base = make_silv_deal_id(tx)
        occ = seen.get(base, 0)
        seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        is_cancelled, cancel_date = _cancel_state(tx)
        trace = match_results.get(base)
        if trace and trace.get("chosen"):
            chosen = trace["chosen"]
            matched_no = chosen["complex_no"]
            method = chosen["method"]
            score = chosen["score"]
            counts["matched"] += 1
        else:
            matched_no = None
            method = "unmatched" if trace else None
            score = None
            if trace:
                counts["unmatched"] += 1

        rows.append((
            did, ymd, y, m, d, amount,
            (tx.get("sggCd") or "").strip() or None,
            (tx.get("umdNm") or "").strip() or None,
            (tx.get("aptNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None,
            _coerce_int(tx.get("floor")),
            _coerce_float(tx.get("excluUseAr")),
            (tx.get("ownershipGbn") or "").strip() or None,
            (tx.get("dealingGbn") or "").strip() or None,
            (tx.get("buyerGbn") or "").strip() or None,
            (tx.get("slerGbn") or "").strip() or None,
            is_cancelled, cancel_date,
            matched_no, method, score,
            json.dumps(trace, ensure_ascii=False) if trace else None,
            now if trace else None,
            json.dumps(tx, ensure_ascii=False),
        ))

    if not rows:
        return counts

    with _LOCK:
        conn.executemany(
            """
            INSERT INTO silv_transactions(
                deal_id, deal_ymd, deal_year, deal_month, deal_day, deal_amount,
                sgg_cd, umd_nm, apt_nm, jibun,
                floor, excl_use_ar, ownership_gbn,
                dealing_gbn, buyer_gbn, sler_gbn,
                is_cancelled, cancel_date,
                matched_complex_no, matched_method, matched_score,
                match_details, matched_at, raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deal_id) DO UPDATE SET
                matched_complex_no = excluded.matched_complex_no,
                matched_method     = excluded.matched_method,
                matched_score      = excluded.matched_score,
                match_details      = excluded.match_details,
                matched_at         = excluded.matched_at,
                is_cancelled       = excluded.is_cancelled,
                cancel_date        = excluded.cancel_date,
                raw                = excluded.raw
            WHERE manual_override = 0
            """,
            rows,
        )
        counts["inserted"] = len(rows)
        conn.commit()
    return counts


def make_rh_deal_id(tx: dict) -> str:
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay", "umdNm", "jibun",
                "mhouseNm", "floor", "excluUseAr", "dealAmount"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_rh_transactions(conn: sqlite3.Connection, items: Iterable[dict]) -> dict:
    """연립다세대(빌라) 매매 — 단지 매칭 없이 지번+건물명으로 저장. 해제(cdealType)·이중신고 처리."""
    counts = {"inserted": 0}
    rows, seen = [], {}
    for tx in items:
        base = make_rh_deal_id(tx)
        occ = seen.get(base, 0); seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        is_cancelled, cancel_date = _cancel_state(tx)
        rows.append((
            did, ymd, y, m, d, amount,
            (tx.get("sggCd") or "").strip() or None, (tx.get("umdNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None, (tx.get("mhouseNm") or "").strip() or None,
            (tx.get("houseType") or "").strip() or None,
            _coerce_int(tx.get("floor")), _coerce_float(tx.get("excluUseAr")),
            _coerce_float(tx.get("landAr")), _coerce_int(tx.get("buildYear")),
            (tx.get("dealingGbn") or "").strip() or None, (tx.get("buyerGbn") or "").strip() or None,
            (tx.get("slerGbn") or "").strip() or None, is_cancelled, cancel_date,
            json.dumps(tx, ensure_ascii=False),
        ))
    if not rows:
        return counts
    with _LOCK:
        conn.executemany(
            "INSERT INTO rh_transactions(deal_id,deal_ymd,deal_year,deal_month,deal_day,deal_amount,"
            "sgg_cd,umd_nm,jibun,mhouse_nm,house_type,floor,excl_use_ar,land_ar,build_year,"
            "dealing_gbn,buyer_gbn,sler_gbn,is_cancelled,cancel_date,raw) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(deal_id) DO UPDATE SET is_cancelled=excluded.is_cancelled,"
            "cancel_date=excluded.cancel_date,raw=excluded.raw", rows)
        conn.commit()
    counts["inserted"] = len(rows)
    return counts


def make_rh_rental_id(tx: dict) -> str:
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay", "umdNm", "jibun",
                "mhouseNm", "floor", "excluUseAr", "deposit", "monthlyRent"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_rh_rentals(conn: sqlite3.Connection, items: Iterable[dict]) -> dict:
    """연립다세대(빌라) 전월세."""
    counts = {"inserted": 0}
    rows, seen = [], {}
    for tx in items:
        base = make_rh_rental_id(tx)
        occ = seen.get(base, 0); seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        deposit = _coerce_amount_won(tx.get("deposit"))
        if deposit is None or not ymd:
            continue
        rows.append((
            did, ymd, y, m, d, deposit, _coerce_amount_won(tx.get("monthlyRent")) or 0,
            (tx.get("sggCd") or "").strip() or None, (tx.get("umdNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None, (tx.get("mhouseNm") or "").strip() or None,
            (tx.get("houseType") or "").strip() or None,
            _coerce_int(tx.get("floor")), _coerce_float(tx.get("excluUseAr")),
            _coerce_int(tx.get("buildYear")),
            (tx.get("contractType") or "").strip() or None, (tx.get("contractTerm") or "").strip() or None,
            (tx.get("useRRRight") or "").strip() or None,
            _coerce_amount_won(tx.get("preDeposit")), _coerce_amount_won(tx.get("preMonthlyRent")),
            json.dumps(tx, ensure_ascii=False),
        ))
    if not rows:
        return counts
    with _LOCK:
        conn.executemany(
            "INSERT INTO rh_rentals(deal_id,deal_ymd,deal_year,deal_month,deal_day,deposit,monthly_rent,"
            "sgg_cd,umd_nm,jibun,mhouse_nm,house_type,floor,excl_use_ar,build_year,"
            "contract_type,contract_term,use_rr_right,pre_deposit,pre_monthly_rent,raw) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(deal_id) DO UPDATE SET raw=excluded.raw", rows)
        conn.commit()
    counts["inserted"] = len(rows)
    return counts


def make_sh_deal_id(tx: dict) -> str:
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay", "umdNm", "houseType",
                "totalFloorAr", "plottageAr", "buildYear", "dealAmount"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_sh_transactions(conn: sqlite3.Connection, items: Iterable[dict]) -> dict:
    """단독/다가구 매매 — 동 단위. 연면적/대지면적 보존. 해제·이중신고 처리."""
    counts = {"inserted": 0}
    rows, seen = [], {}
    for tx in items:
        base = make_sh_deal_id(tx)
        occ = seen.get(base, 0); seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        is_cancelled, cancel_date = _cancel_state(tx)
        rows.append((
            did, ymd, y, m, d, amount,
            (tx.get("sggCd") or "").strip() or None, (tx.get("umdNm") or "").strip() or None,
            (tx.get("houseType") or "").strip() or None,
            _coerce_float(tx.get("totalFloorAr")), _coerce_float(tx.get("plottageAr")),
            _coerce_int(tx.get("buildYear")),
            (tx.get("dealingGbn") or "").strip() or None, (tx.get("buyerGbn") or "").strip() or None,
            (tx.get("slerGbn") or "").strip() or None, is_cancelled, cancel_date,
            json.dumps(tx, ensure_ascii=False),
        ))
    if not rows:
        return counts
    with _LOCK:
        conn.executemany(
            "INSERT INTO sh_transactions(deal_id,deal_ymd,deal_year,deal_month,deal_day,deal_amount,"
            "sgg_cd,umd_nm,house_type,total_floor_ar,plottage_ar,build_year,"
            "dealing_gbn,buyer_gbn,sler_gbn,is_cancelled,cancel_date,raw) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(deal_id) DO UPDATE SET is_cancelled=excluded.is_cancelled,"
            "cancel_date=excluded.cancel_date,raw=excluded.raw", rows)
        conn.commit()
    counts["inserted"] = len(rows)
    return counts


def make_sh_rental_id(tx: dict) -> str:
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay", "umdNm", "houseType",
                "totalFloorAr", "buildYear", "deposit", "monthlyRent"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_sh_rentals(conn: sqlite3.Connection, items: Iterable[dict]) -> dict:
    """단독/다가구 전월세."""
    counts = {"inserted": 0}
    rows, seen = [], {}
    for tx in items:
        base = make_sh_rental_id(tx)
        occ = seen.get(base, 0); seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        deposit = _coerce_amount_won(tx.get("deposit"))
        if deposit is None or not ymd:
            continue
        rows.append((
            did, ymd, y, m, d, deposit, _coerce_amount_won(tx.get("monthlyRent")) or 0,
            (tx.get("sggCd") or "").strip() or None, (tx.get("umdNm") or "").strip() or None,
            (tx.get("houseType") or "").strip() or None,
            _coerce_float(tx.get("totalFloorAr")), _coerce_int(tx.get("buildYear")),
            (tx.get("contractType") or "").strip() or None, (tx.get("contractTerm") or "").strip() or None,
            (tx.get("useRRRight") or "").strip() or None,
            _coerce_amount_won(tx.get("preDeposit")), _coerce_amount_won(tx.get("preMonthlyRent")),
            json.dumps(tx, ensure_ascii=False),
        ))
    if not rows:
        return counts
    with _LOCK:
        conn.executemany(
            "INSERT INTO sh_rentals(deal_id,deal_ymd,deal_year,deal_month,deal_day,deposit,monthly_rent,"
            "sgg_cd,umd_nm,house_type,total_floor_ar,build_year,"
            "contract_type,contract_term,use_rr_right,pre_deposit,pre_monthly_rent,raw) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(deal_id) DO UPDATE SET raw=excluded.raw", rows)
        conn.commit()
    counts["inserted"] = len(rows)
    return counts


def make_nrg_deal_id(tx: dict) -> str:
    h = hashlib.sha1()
    for key in ("sggCd", "dealYear", "dealMonth", "dealDay", "umdNm", "jibun",
                "buildingUse", "floor", "buildingAr", "dealAmount"):
        h.update((tx.get(key) or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:24]


def upsert_nrg_transactions(conn: sqlite3.Connection, items: Iterable[dict]) -> dict:
    """상업업무용(상가·사무실) 매매 — 지번+용도+층. 해제·이중신고 처리."""
    counts = {"inserted": 0}
    rows, seen = [], {}
    for tx in items:
        base = make_nrg_deal_id(tx)
        occ = seen.get(base, 0); seen[base] = occ + 1
        did = base if occ == 0 else f"{base}_{occ}"
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        is_cancelled, cancel_date = _cancel_state(tx)
        rows.append((
            did, ymd, y, m, d, amount,
            (tx.get("sggCd") or "").strip() or None, (tx.get("umdNm") or "").strip() or None,
            (tx.get("jibun") or "").strip() or None, (tx.get("buildingUse") or "").strip() or None,
            (tx.get("buildingType") or "").strip() or None, (tx.get("landUse") or "").strip() or None,
            _coerce_float(tx.get("buildingAr")), _coerce_float(tx.get("plottageAr")),
            _coerce_int(tx.get("floor")), _coerce_int(tx.get("buildYear")),
            (tx.get("dealingGbn") or "").strip() or None, (tx.get("buyerGbn") or "").strip() or None,
            (tx.get("slerGbn") or "").strip() or None, is_cancelled, cancel_date,
            json.dumps(tx, ensure_ascii=False),
        ))
    if not rows:
        return counts
    with _LOCK:
        conn.executemany(
            "INSERT INTO nrg_transactions(deal_id,deal_ymd,deal_year,deal_month,deal_day,deal_amount,"
            "sgg_cd,umd_nm,jibun,building_use,building_type,land_use,building_ar,plottage_ar,floor,build_year,"
            "dealing_gbn,buyer_gbn,sler_gbn,is_cancelled,cancel_date,raw) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(deal_id) DO UPDATE SET is_cancelled=excluded.is_cancelled,"
            "cancel_date=excluded.cancel_date,raw=excluded.raw", rows)
        conn.commit()
    counts["inserted"] = len(rows)
    return counts


def save_suggestion(
    conn: sqlite3.Connection,
    apt_nm: str,
    sgg_cd: str,
    umd_nm: str | None,
    tx_count: int,
    suggested_complex_no: str,
    suggested_method: str,
    suggested_score: float,
    details: dict,
) -> None:
    """Upsert a suggestion. Re-running relink refreshes details + score
    but preserves admin's accept/reject decision."""
    with _LOCK:
        conn.execute(
            """
            INSERT INTO match_suggestions(
                apt_nm, sgg_cd, umd_nm, tx_count,
                suggested_complex_no, suggested_method, suggested_score, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(apt_nm, sgg_cd, suggested_complex_no) DO UPDATE SET
                umd_nm           = excluded.umd_nm,
                tx_count         = excluded.tx_count,
                suggested_method = excluded.suggested_method,
                suggested_score  = excluded.suggested_score,
                details          = excluded.details
            WHERE match_suggestions.status = 'pending'
            """,
            (apt_nm, sgg_cd, umd_nm, tx_count,
             suggested_complex_no, suggested_method, suggested_score,
             json.dumps(details, ensure_ascii=False)),
        )
        conn.commit()


def accept_suggestion(conn: sqlite3.Connection, suggestion_id: int) -> int:
    """Accept a suggestion: apply the match to all unmatched transactions
    sharing the (apt_nm, sgg_cd), then mark the suggestion 'accepted'.
    Returns number of transactions updated.
    """
    from datetime import datetime
    with _LOCK:
        row = conn.execute(
            "SELECT apt_nm, sgg_cd, suggested_complex_no, suggested_method, "
            "       suggested_score, details "
            "FROM match_suggestions WHERE suggestion_id = ? AND status = 'pending'",
            (suggestion_id,),
        ).fetchone()
        if not row:
            return 0
        apt_nm, sgg_cd, complex_no, method, score, details_json = row
        try:
            details = json.loads(details_json) if details_json else {}
        except Exception:  # noqa: BLE001
            details = {}
        # Build match_details for transactions
        md = {
            "tx": {"aptNm": apt_nm, "sggCd": sgg_cd},
            "method": method,
            "score": score,
            "naver_lookup_debug": details,
            "manual_accepted": True,
            "chosen": {
                "complex_no": complex_no,
                "method": method,
                "score": score,
            },
        }
        cur = conn.execute(
            """
            UPDATE transactions
            SET matched_complex_no = ?,
                matched_method     = ?,
                matched_score      = ?,
                match_details      = ?,
                matched_at         = ?,
                manual_override    = 1
            WHERE apt_nm = ? AND sgg_cd = ?
              AND matched_complex_no IS NULL
            """,
            (complex_no, method, score,
             json.dumps(md, ensure_ascii=False),
             datetime.now().isoformat(timespec="seconds"),
             apt_nm, sgg_cd),
        )
        n = cur.rowcount
        conn.execute(
            "UPDATE match_suggestions SET status='accepted', reviewed_at=? "
            "WHERE suggestion_id = ?",
            (datetime.now().isoformat(timespec="seconds"), suggestion_id),
        )
        conn.commit()
        return n


def reject_suggestion(conn: sqlite3.Connection, suggestion_id: int) -> bool:
    from datetime import datetime
    with _LOCK:
        cur = conn.execute(
            "UPDATE match_suggestions SET status='rejected', reviewed_at=? "
            "WHERE suggestion_id = ? AND status = 'pending'",
            (datetime.now().isoformat(timespec="seconds"), suggestion_id),
        )
        conn.commit()
        return cur.rowcount > 0


def reset_suggestion(conn: sqlite3.Connection, suggestion_id: int) -> bool:
    """Revert accept/reject back to pending. Does NOT undo the transaction
    updates from a prior accept — those stay with manual_override=1."""
    from datetime import datetime
    with _LOCK:
        cur = conn.execute(
            "UPDATE match_suggestions SET status='pending', reviewed_at=? "
            "WHERE suggestion_id = ?",
            (datetime.now().isoformat(timespec="seconds"), suggestion_id),
        )
        conn.commit()
        return cur.rowcount > 0


def stats(conn: sqlite3.Connection) -> dict:
    with _LOCK:
        out: dict = {}
        cur = conn.execute("SELECT COUNT(*) FROM transactions")
        out["total"] = cur.fetchone()[0]
        cur = conn.execute(
            "SELECT matched_method, COUNT(*) FROM transactions "
            "GROUP BY matched_method ORDER BY COUNT(*) DESC"
        )
        out["by_method"] = cur.fetchall()
        cur = conn.execute(
            "SELECT MIN(deal_ymd), MAX(deal_ymd) FROM transactions"
        )
        out["date_range"] = cur.fetchone()
    return out
