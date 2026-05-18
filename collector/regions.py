"""Naver region tree (시/도 → 시군구 → 동) discovery and queries.

cortar_type values from Naver:
    city = 시/도 (level 1, e.g. 서울특별시)
    dvsn = 시/군/구 (level 2, e.g. 서초구)
    sec  = 동 (level 3, leaf — complexes live here)

Build the tree once via walk_tree(); thereafter the collector reads it from
SQLite via dong_cortar_nos / dong_cortar_nos_under.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable

from . import storage
from .naver import list_region_children

ROOT_CORTAR = "0000000000"


def walk_tree(
    creds: dict,
    conn: sqlite3.Connection,
    on_progress: Callable[[str, dict], None] | None = None,
) -> dict[str, int]:
    """Discover the full Korea region tree and persist to SQLite. Idempotent."""
    counts: dict[str, int] = {"city": 0, "dvsn": 0, "sec": 0, "errors": 0}

    sido = list_region_children(ROOT_CORTAR, creds)
    for s in sido:
        storage.upsert_region(conn, s, parent=None)
        counts["city"] += 1
        if on_progress:
            on_progress("city", s)
        try:
            gus = list_region_children(s["cortarNo"], creds)
        except Exception as e:  # noqa: BLE001
            print(f"    ERROR listing 시군구 of {s.get('cortarName')}: {e}")
            counts["errors"] += 1
            continue
        for g in gus:
            storage.upsert_region(conn, g, parent=s["cortarNo"])
            counts["dvsn"] += 1
            if on_progress:
                on_progress("dvsn", g)
            try:
                dongs = list_region_children(g["cortarNo"], creds)
            except Exception as e:  # noqa: BLE001
                print(f"    ERROR listing 동 of {g.get('cortarName')}: {e}")
                counts["errors"] += 1
                continue
            for d in dongs:
                storage.upsert_region(conn, d, parent=g["cortarNo"])
                counts["sec"] += 1
                if on_progress:
                    on_progress("sec", d)
    return counts


def dong_cortar_nos(conn: sqlite3.Connection) -> list[str]:
    """All leaf 동 cortarNos."""
    with storage._LOCK:
        cur = conn.execute(
            "SELECT cortar_no FROM regions WHERE cortar_type='sec' ORDER BY cortar_no"
        )
        return [r[0] for r in cur.fetchall()]


def dong_cortar_nos_under(conn: sqlite3.Connection, ancestor: str) -> list[str]:
    """All 동 cortarNos descended from `ancestor` (which may be 시도 or 시군구)."""
    with storage._LOCK:
        cur = conn.execute(
            """
            WITH RECURSIVE subtree(cortar_no, cortar_type) AS (
                SELECT cortar_no, cortar_type FROM regions WHERE cortar_no = ?
                UNION ALL
                SELECT r.cortar_no, r.cortar_type
                FROM regions r JOIN subtree s ON r.parent_cortar_no = s.cortar_no
            )
            SELECT cortar_no FROM subtree WHERE cortar_type='sec' ORDER BY cortar_no
            """,
            (ancestor,),
        )
        return [r[0] for r in cur.fetchall()]


def region_path(conn: sqlite3.Connection, cortar_no: str) -> list[dict]:
    """Ancestor chain from root down to this region (root first)."""
    path: list[dict] = []
    cur_no: str | None = cortar_no
    for _ in range(5):
        with storage._LOCK:
            cur = conn.execute(
                "SELECT cortar_no, cortar_name, cortar_type, parent_cortar_no "
                "FROM regions WHERE cortar_no=?",
                (cur_no,),
            )
            row = cur.fetchone()
        if not row:
            break
        path.append(
            {"cortar_no": row[0], "cortar_name": row[1], "cortar_type": row[2]}
        )
        if not row[3]:
            break
        cur_no = row[3]
    return list(reversed(path))


def region_label(conn: sqlite3.Connection, cortar_no: str) -> str:
    """Human-readable path like '서울특별시 > 서초구 > 서초동'."""
    return " > ".join(r["cortar_name"] for r in region_path(conn, cortar_no))
