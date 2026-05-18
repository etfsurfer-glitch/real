"""Push the local SQLite snapshot to Supabase Postgres via PostgREST.

Only columns that exist on both sides are sent; median columns on the
Postgres side stay NULL for now (we have min/max/avg). Median can be added
later as a Postgres computation over listings_current using percentile_cont.
"""
from __future__ import annotations

import json
import sqlite3
from itertools import islice
from typing import Any, Iterable

from supabase import Client, create_client

from .config import settings

BATCH = 500


def get_client() -> Client:
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY missing in .env")
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def _chunked(iterable: Iterable, size: int):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch


def _maybe_json(s: str | None) -> Any:
    if s is None:
        return None
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


def upsert_regions(conn: sqlite3.Connection, supa: Client) -> int:
    cur = conn.execute(
        "SELECT cortar_no, cortar_name, cortar_type, parent_cortar_no, "
        "       center_lat, center_lon FROM regions"
    )
    rows = [
        {
            "cortar_no": r[0], "cortar_name": r[1], "cortar_type": r[2],
            "parent_cortar_no": r[3], "center_lat": r[4], "center_lon": r[5],
        }
        for r in cur.fetchall()
    ]
    n = 0
    for chunk in _chunked(rows, BATCH):
        supa.table("regions").upsert(chunk, on_conflict="cortar_no").execute()
        n += len(chunk)
    return n


def upsert_complexes(conn: sqlite3.Connection, supa: Client) -> int:
    cur = conn.execute(
        """SELECT complex_no, complex_name, cortar_no, real_estate_type,
                  real_estate_type_name, detail_address, latitude, longitude,
                  total_household_count, total_building_count, high_floor, low_floor,
                  use_approve_ymd, raw, first_seen_date, last_seen_date
           FROM complexes"""
    )
    rows = [
        {
            "complex_no": r[0], "complex_name": r[1], "cortar_no": r[2],
            "real_estate_type": r[3], "real_estate_type_name": r[4],
            "detail_address": r[5], "latitude": r[6], "longitude": r[7],
            "total_household_count": r[8], "total_building_count": r[9],
            "high_floor": r[10], "low_floor": r[11], "use_approve_ymd": r[12],
            "raw": _maybe_json(r[13]),
            "first_seen_date": r[14], "last_seen_date": r[15],
        }
        for r in cur.fetchall()
    ]
    n = 0
    for chunk in _chunked(rows, BATCH):
        supa.table("complexes").upsert(chunk, on_conflict="complex_no").execute()
        n += len(chunk)
    return n


def replace_listings_current(
    conn: sqlite3.Connection, supa: Client, snapshot_date: str, skip_raw: bool = False
) -> int:
    """Replace today's listings_current on Supabase.

    skip_raw=True drops the JSONB raw column from the payload — useful for
    fitting nationwide volume in Supabase's free-tier 500 MB DB.
    """
    supa.table("listings_current").delete().eq("snapshot_date", snapshot_date).execute()

    cur = conn.execute(
        """SELECT article_no, complex_no, trade_type, real_estate_type,
                  area_name, area1_m2, area2_m2, floor_info, direction,
                  deal_or_warrant_price_text, deal_or_warrant_price,
                  rent_price, article_confirm_ymd, realtor_name, realtor_id,
                  cp_name, verification_type, building_name, tag_list_json,
                  same_addr_cnt, latitude, longitude, raw, snapshot_date
           FROM listings_current WHERE snapshot_date=?""",
        (snapshot_date,),
    )
    rows = []
    for r in cur.fetchall():
        rows.append({
            "article_no": r[0], "complex_no": r[1], "trade_type": r[2],
            "real_estate_type": r[3], "area_name": r[4],
            "area1_m2": r[5], "area2_m2": r[6], "floor_info": r[7],
            "direction": r[8], "deal_or_warrant_price_text": r[9],
            "deal_or_warrant_price": r[10], "rent_price": r[11],
            "article_confirm_ymd": r[12], "realtor_name": r[13],
            "realtor_id": r[14], "cp_name": r[15],
            "verification_type": r[16], "building_name": r[17],
            "tag_list": _maybe_json(r[18]),
            "same_addr_cnt": r[19],
            "latitude": r[20], "longitude": r[21],
            "raw": None if skip_raw else _maybe_json(r[22]),
            "snapshot_date": r[23],
        })
    n = 0
    for chunk in _chunked(rows, BATCH):
        supa.table("listings_current").upsert(chunk, on_conflict="article_no").execute()
        n += len(chunk)
    return n


def replace_complex_daily_agg(
    conn: sqlite3.Connection, supa: Client, snapshot_date: str
) -> int:
    supa.table("complex_daily_agg").delete().eq("snapshot_date", snapshot_date).execute()
    cur = conn.execute(
        """SELECT snapshot_date, complex_no, area_name, trade_type,
                  listing_count, price_min, price_max, price_avg,
                  rent_min, rent_max
           FROM complex_daily_agg WHERE snapshot_date=?""",
        (snapshot_date,),
    )
    rows = [
        {
            "snapshot_date": r[0], "complex_no": r[1], "area_name": r[2],
            "trade_type": r[3], "listing_count": r[4],
            "price_min": r[5], "price_max": r[6], "price_avg": r[7],
            "rent_min": r[8], "rent_max": r[9],
        }
        for r in cur.fetchall()
    ]
    n = 0
    for chunk in _chunked(rows, BATCH):
        supa.table("complex_daily_agg").insert(chunk).execute()
        n += len(chunk)
    return n


def replace_region_daily_agg(
    conn: sqlite3.Connection, supa: Client, snapshot_date: str
) -> int:
    supa.table("region_daily_agg").delete().eq("snapshot_date", snapshot_date).execute()
    cur = conn.execute(
        """SELECT snapshot_date, cortar_no, trade_type, listing_count, complex_count
           FROM region_daily_agg WHERE snapshot_date=?""",
        (snapshot_date,),
    )
    rows = [
        {
            "snapshot_date": r[0], "cortar_no": r[1], "trade_type": r[2],
            "listing_count": r[3], "complex_count": r[4],
        }
        for r in cur.fetchall()
    ]
    if rows:
        supa.table("region_daily_agg").insert(rows).execute()
    return len(rows)
