"""SQLite local store. Mirrors the Supabase Postgres schema but with TEXT/JSON
for arrays and jsonb. The 4-worker collector serializes writes through a single
module-level lock — SQLite WAL handles read concurrency fine.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

from .prices import parse_price_text, parse_rent_pair

SCHEMA = """
CREATE TABLE IF NOT EXISTS regions (
    cortar_no TEXT PRIMARY KEY,
    cortar_name TEXT NOT NULL,
    cortar_type TEXT,
    parent_cortar_no TEXT,
    center_lat REAL,
    center_lon REAL
);

CREATE TABLE IF NOT EXISTS complexes (
    complex_no TEXT PRIMARY KEY,
    complex_name TEXT NOT NULL,
    cortar_no TEXT,
    real_estate_type TEXT,
    real_estate_type_name TEXT,
    detail_address TEXT,
    latitude REAL,
    longitude REAL,
    total_household_count INTEGER,
    total_building_count INTEGER,
    high_floor INTEGER,
    low_floor INTEGER,
    use_approve_ymd TEXT,
    raw TEXT,
    first_seen_date TEXT,
    last_seen_date TEXT
);
CREATE INDEX IF NOT EXISTS complexes_cortar_idx ON complexes(cortar_no);

CREATE TABLE IF NOT EXISTS listings_current (
    article_no TEXT PRIMARY KEY,
    complex_no TEXT,
    trade_type TEXT NOT NULL,
    real_estate_type TEXT,
    area_name TEXT,
    area1_m2 REAL,
    area2_m2 REAL,
    floor_info TEXT,
    direction TEXT,
    deal_or_warrant_price_text TEXT,
    deal_or_warrant_price INTEGER,
    rent_price_text TEXT,
    rent_price INTEGER,
    article_confirm_ymd TEXT,
    realtor_name TEXT,
    realtor_id TEXT,
    cp_name TEXT,
    verification_type TEXT,
    building_name TEXT,
    tag_list_json TEXT,
    same_addr_cnt INTEGER,
    same_addr_min_price INTEGER,
    same_addr_max_price INTEGER,
    price_change_state TEXT,
    is_price_modification INTEGER,
    article_status TEXT,
    article_feature_desc TEXT,
    cp_pc_article_url TEXT,
    latitude REAL,
    longitude REAL,
    snapshot_date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS listings_complex_trade_idx ON listings_current(complex_no, trade_type);
CREATE INDEX IF NOT EXISTS listings_snapshot_idx ON listings_current(snapshot_date);
CREATE INDEX IF NOT EXISTS listings_area_idx ON listings_current(complex_no, area_name);

CREATE TABLE IF NOT EXISTS complex_daily_agg (
    snapshot_date TEXT NOT NULL,
    complex_no TEXT NOT NULL,
    area_name TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    listing_count INTEGER NOT NULL,
    price_min INTEGER, price_max INTEGER, price_avg INTEGER,
    rent_min INTEGER, rent_max INTEGER, rent_avg INTEGER,
    PRIMARY KEY (snapshot_date, complex_no, area_name, trade_type)
);

CREATE TABLE IF NOT EXISTS region_daily_agg (
    snapshot_date TEXT NOT NULL,
    cortar_no TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    listing_count INTEGER NOT NULL,
    complex_count INTEGER NOT NULL,
    PRIMARY KEY (snapshot_date, cortar_no, trade_type)
);

CREATE TABLE IF NOT EXISTS collection_log (
    run_date TEXT NOT NULL,
    complex_no TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    article_count INTEGER,
    status TEXT,
    error TEXT,
    completed_at TEXT,
    PRIMARY KEY (run_date, complex_no, trade_type)
);
"""

_LOCK = threading.Lock()


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


_B_FIELDS = [
    ("same_addr_min_price", "INTEGER"),
    ("same_addr_max_price", "INTEGER"),
    ("price_change_state", "TEXT"),
    ("is_price_modification", "INTEGER"),
    ("article_status", "TEXT"),
    ("article_feature_desc", "TEXT"),
    ("cp_pc_article_url", "TEXT"),
]


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, type_ddl: str
) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {r[1] for r in cur.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_ddl}")


def init_schema(conn: sqlite3.Connection) -> None:
    with _LOCK:
        conn.executescript(SCHEMA)
        # Migrate older DBs to the B-field layout.
        for col, ddl in _B_FIELDS:
            _add_column_if_missing(conn, "listings_current", col, ddl)
        conn.commit()


def upsert_region(conn: sqlite3.Connection, region_obj: dict, parent: str | None) -> None:
    with _LOCK:
        conn.execute(
            """
            INSERT INTO regions(cortar_no, cortar_name, cortar_type,
                                parent_cortar_no, center_lat, center_lon)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(cortar_no) DO UPDATE SET
                cortar_name=excluded.cortar_name,
                cortar_type=excluded.cortar_type,
                parent_cortar_no=excluded.parent_cortar_no,
                center_lat=excluded.center_lat,
                center_lon=excluded.center_lon
            """,
            (
                region_obj["cortarNo"],
                region_obj.get("cortarName"),
                region_obj.get("cortarType"),
                parent,
                region_obj.get("centerLat"),
                region_obj.get("centerLon"),
            ),
        )
        conn.commit()


def upsert_complex(conn: sqlite3.Connection, c: dict) -> None:
    today = date.today().isoformat()
    with _LOCK:
        conn.execute(
            """
            INSERT INTO complexes(complex_no, complex_name, cortar_no, real_estate_type,
                real_estate_type_name, detail_address, latitude, longitude,
                total_household_count, total_building_count, high_floor, low_floor,
                use_approve_ymd, raw, first_seen_date, last_seen_date)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(complex_no) DO UPDATE SET
                complex_name=excluded.complex_name,
                cortar_no=excluded.cortar_no,
                real_estate_type=excluded.real_estate_type,
                real_estate_type_name=excluded.real_estate_type_name,
                detail_address=excluded.detail_address,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                total_household_count=excluded.total_household_count,
                total_building_count=excluded.total_building_count,
                high_floor=excluded.high_floor,
                low_floor=excluded.low_floor,
                use_approve_ymd=excluded.use_approve_ymd,
                raw=excluded.raw,
                last_seen_date=excluded.last_seen_date
            """,
            (
                str(c["complexNo"]),
                c.get("complexName"),
                c.get("cortarNo"),
                c.get("realEstateTypeCode"),
                c.get("realEstateTypeName"),
                c.get("detailAddress"),
                c.get("latitude"),
                c.get("longitude"),
                c.get("totalHouseholdCount"),
                c.get("totalBuildingCount"),
                c.get("highFloor"),
                c.get("lowFloor"),
                c.get("useApproveYmd"),
                json.dumps(c, ensure_ascii=False),
                today,
                today,
            ),
        )
        conn.commit()


def _article_row(complex_no: str, trade: str, snapshot_date: str, it: dict) -> tuple:
    deal_txt = it.get("dealOrWarrantPrc")
    rent_txt = it.get("rentPrc")
    deal_v = parse_price_text(deal_txt)
    rent_v_a, rent_v_b = parse_rent_pair(rent_txt)
    rent_v = rent_v_b if rent_v_b is not None else rent_v_a
    feat = (it.get("articleFeatureDesc") or "").strip()
    return (
        str(it["articleNo"]),
        complex_no,
        trade,
        it.get("realEstateTypeCode"),
        it.get("areaName"),
        it.get("area1"),
        it.get("area2"),
        it.get("floorInfo"),
        it.get("direction"),
        deal_txt,
        deal_v,
        rent_txt,
        rent_v,
        it.get("articleConfirmYmd"),
        it.get("realtorName"),
        it.get("realtorId"),
        it.get("cpName"),
        it.get("verificationTypeCode"),
        it.get("buildingName"),
        json.dumps(it.get("tagList") or [], ensure_ascii=False),
        it.get("sameAddrCnt"),
        parse_price_text(it.get("sameAddrMinPrc")),
        parse_price_text(it.get("sameAddrMaxPrc")),
        it.get("priceChangeState"),
        1 if it.get("isPriceModification") else 0,
        it.get("articleStatus"),
        feat[:500] if feat else None,
        it.get("cpPcArticleUrl"),
        float(it["latitude"]) if it.get("latitude") else None,
        float(it["longitude"]) if it.get("longitude") else None,
        snapshot_date,
    )


def save_articles(
    conn: sqlite3.Connection,
    complex_no: str,
    trade: str,
    items: list[dict],
    snapshot_date: str,
) -> None:
    rows = [_article_row(complex_no, trade, snapshot_date, it) for it in items]
    with _LOCK:
        conn.execute(
            "DELETE FROM listings_current WHERE complex_no=? AND trade_type=? AND snapshot_date=?",
            (complex_no, trade, snapshot_date),
        )
        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO listings_current(
                    article_no, complex_no, trade_type, real_estate_type,
                    area_name, area1_m2, area2_m2, floor_info, direction,
                    deal_or_warrant_price_text, deal_or_warrant_price,
                    rent_price_text, rent_price,
                    article_confirm_ymd, realtor_name, realtor_id, cp_name,
                    verification_type, building_name, tag_list_json,
                    same_addr_cnt, same_addr_min_price, same_addr_max_price,
                    price_change_state, is_price_modification,
                    article_status, article_feature_desc, cp_pc_article_url,
                    latitude, longitude, snapshot_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        conn.commit()


def log_completion(
    conn: sqlite3.Connection,
    run_date: str,
    complex_no: str,
    trade: str,
    count: int,
    status: str,
    error: str | None,
) -> None:
    with _LOCK:
        conn.execute(
            """
            INSERT INTO collection_log(run_date, complex_no, trade_type,
                article_count, status, error, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_date, complex_no, trade_type) DO UPDATE SET
                article_count=excluded.article_count,
                status=excluded.status,
                error=excluded.error,
                completed_at=excluded.completed_at
            """,
            (run_date, complex_no, trade, count, status, error, datetime.now().isoformat()),
        )
        conn.commit()


def get_completed_for_run(conn: sqlite3.Connection, run_date: str) -> set[tuple[str, str]]:
    with _LOCK:
        cur = conn.execute(
            "SELECT complex_no, trade_type FROM collection_log "
            "WHERE run_date=? AND status='success'",
            (run_date,),
        )
        return {(r[0], r[1]) for r in cur.fetchall()}


def compute_complex_daily_agg(conn: sqlite3.Connection, snapshot_date: str) -> int:
    with _LOCK:
        conn.execute("DELETE FROM complex_daily_agg WHERE snapshot_date=?", (snapshot_date,))
        conn.execute(
            """
            INSERT INTO complex_daily_agg(
                snapshot_date, complex_no, area_name, trade_type,
                listing_count, price_min, price_max, price_avg,
                rent_min, rent_max, rent_avg
            )
            SELECT
                snapshot_date, complex_no, COALESCE(area_name, ''), trade_type,
                COUNT(*),
                MIN(deal_or_warrant_price), MAX(deal_or_warrant_price),
                CAST(AVG(deal_or_warrant_price) AS INTEGER),
                MIN(rent_price), MAX(rent_price),
                CAST(AVG(rent_price) AS INTEGER)
            FROM listings_current
            WHERE snapshot_date=? AND complex_no IS NOT NULL
            GROUP BY snapshot_date, complex_no, COALESCE(area_name, ''), trade_type
            """,
            (snapshot_date,),
        )
        cur = conn.execute(
            "SELECT COUNT(*) FROM complex_daily_agg WHERE snapshot_date=?",
            (snapshot_date,),
        )
        conn.commit()
        return cur.fetchone()[0]


def compute_region_daily_agg(conn: sqlite3.Connection, snapshot_date: str) -> int:
    with _LOCK:
        conn.execute("DELETE FROM region_daily_agg WHERE snapshot_date=?", (snapshot_date,))
        conn.execute(
            """
            INSERT INTO region_daily_agg(
                snapshot_date, cortar_no, trade_type, listing_count, complex_count
            )
            SELECT
                ?, c.cortar_no, l.trade_type,
                COUNT(*),
                COUNT(DISTINCT l.complex_no)
            FROM listings_current l
            JOIN complexes c ON c.complex_no = l.complex_no
            WHERE l.snapshot_date = ? AND c.cortar_no IS NOT NULL
            GROUP BY c.cortar_no, l.trade_type
            """,
            (snapshot_date, snapshot_date),
        )
        cur = conn.execute(
            "SELECT COUNT(*) FROM region_daily_agg WHERE snapshot_date=?",
            (snapshot_date,),
        )
        conn.commit()
        return cur.fetchone()[0]


def region_summary(conn: sqlite3.Connection, snapshot_date: str, cortar_no: str) -> list[tuple]:
    with _LOCK:
        cur = conn.execute(
            """
            SELECT trade_type, listing_count, complex_count
            FROM region_daily_agg
            WHERE snapshot_date=? AND cortar_no=?
            ORDER BY trade_type
            """,
            (snapshot_date, cortar_no),
        )
        return cur.fetchall()
