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
