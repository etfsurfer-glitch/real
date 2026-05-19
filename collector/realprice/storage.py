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

    for tx in items:
        deal_id = make_deal_id(tx)
        ymd, y, m, d = _ymd(tx)
        amount = _coerce_amount_won(tx.get("dealAmount"))
        if amount is None or not ymd:
            continue
        trace = match_results.get(deal_id)
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
            matched_no, method, score,
            json.dumps(trace, ensure_ascii=False) if trace else None,
            now if trace else None,
            json.dumps(tx, ensure_ascii=False),
        ))

    if not rows:
        return counts

    with _LOCK:
        # Use ON CONFLICT to update matching fields on re-run (raw stays first).
        conn.executemany(
            """
            INSERT INTO transactions(
                deal_id, deal_ymd, deal_year, deal_month, deal_day, deal_amount,
                sgg_cd, umd_nm, apt_nm, apt_seq, jibun, road_nm,
                floor, excl_use_ar, build_year,
                dealing_gbn, buyer_gbn, sler_gbn,
                matched_complex_no, matched_method, matched_score,
                match_details, matched_at, raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deal_id) DO UPDATE SET
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
