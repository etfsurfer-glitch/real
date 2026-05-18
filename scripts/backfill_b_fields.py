"""Parse existing listings_current.raw into the new B-field columns, then
clear raw to reclaim space. One-shot — safe to re-run (idempotent).

Run order:
  1. python scripts/backfill_b_fields.py
  2. apply sql/02_b_fields.sql in Supabase Studio
  3. python scripts/upload_to_supabase.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import storage  # noqa: E402
from collector.config import settings  # noqa: E402
from collector.prices import parse_price_text  # noqa: E402


def main() -> int:
    print(f"[*] sqlite: {settings.local_db_path}")
    size_before = os.path.getsize(settings.local_db_path)
    print(f"[*] size before: {size_before/1024/1024:.1f} MB")

    conn = storage.open_db(settings.local_db_path)
    storage.init_schema(conn)  # ensure B-field columns exist

    cur = conn.execute(
        "SELECT article_no, raw FROM listings_current WHERE raw IS NOT NULL"
    )
    rows = cur.fetchall()
    print(f"[*] rows with raw to backfill: {len(rows)}")

    t0 = time.time()
    updates: list[tuple] = []
    parse_errors = 0
    for article_no, raw_text in rows:
        try:
            r = json.loads(raw_text)
        except Exception:  # noqa: BLE001
            parse_errors += 1
            continue
        feat = (r.get("articleFeatureDesc") or "").strip()
        updates.append((
            parse_price_text(r.get("sameAddrMinPrc")),
            parse_price_text(r.get("sameAddrMaxPrc")),
            r.get("priceChangeState"),
            1 if r.get("isPriceModification") else 0,
            r.get("articleStatus"),
            feat[:500] if feat else None,
            r.get("cpPcArticleUrl"),
            article_no,
        ))

    print(f"[*] parsed: {len(updates)}  parse_errors: {parse_errors}  ({time.time()-t0:.1f}s)")

    print("[*] UPDATE listings_current ...")
    with storage._LOCK:
        conn.executemany(
            """
            UPDATE listings_current SET
                same_addr_min_price = ?,
                same_addr_max_price = ?,
                price_change_state  = ?,
                is_price_modification = ?,
                article_status      = ?,
                article_feature_desc = ?,
                cp_pc_article_url   = ?
            WHERE article_no = ?
            """,
            updates,
        )
        conn.commit()

    print("[*] clearing raw column …")
    with storage._LOCK:
        conn.execute("UPDATE listings_current SET raw = NULL WHERE raw IS NOT NULL")
        # complexes.raw is small (~0.3MB total), leave alone.
        conn.commit()

    print("[*] VACUUM ...")
    with storage._LOCK:
        conn.execute("VACUUM")

    size_after = os.path.getsize(settings.local_db_path)
    print(f"\n[done] size after: {size_after/1024/1024:.1f} MB  "
          f"(saved {(size_before-size_after)/1024/1024:.1f} MB)")

    # Quick sanity counts
    n_total = conn.execute("SELECT COUNT(*) FROM listings_current").fetchone()[0]
    n_with_pcs = conn.execute(
        "SELECT COUNT(*) FROM listings_current WHERE price_change_state IS NOT NULL"
    ).fetchone()[0]
    n_increase = conn.execute(
        "SELECT COUNT(*) FROM listings_current WHERE price_change_state='INCREASE'"
    ).fetchone()[0]
    n_decrease = conn.execute(
        "SELECT COUNT(*) FROM listings_current WHERE price_change_state='DECREASE'"
    ).fetchone()[0]
    print(f"\n[verify] listings_current rows: {n_total}")
    print(f"  price_change_state populated: {n_with_pcs}")
    print(f"  INCREASE: {n_increase}  DECREASE: {n_decrease}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
