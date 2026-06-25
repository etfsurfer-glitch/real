"""Naver realtor 정보를 article에 의존하지 않고 직접 fetch.

endpoint: /api/realtors/{realtorId}
- article과 무관하게 동작 (article 만료해도 OK)
- 단점: establishRegistrationNo 없음 → regno 매칭은 못 함
- 장점: rep_name, address, phone, lat/lng 등은 다 받음

사용:
  python scripts/fetch_naver_realtors_direct.py --parallel 8 --only-missing
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.creds import ensure_creds  # noqa: E402
from collector.http import get_json  # noqa: E402

DB_LOCK = threading.Lock()


def open_db():
    c = sqlite3.connect(settings.local_db_path, timeout=30.0, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def fetch_one(creds, realtor_id):
    url = f"https://new.land.naver.com/api/realtors/{realtor_id}"
    status, data = get_json(url, creds)
    if status != 200 or not isinstance(data, dict) or "error" in data:
        return None
    return data.get("realtor")


def upsert_realtor(conn, rid, r, now):
    raw = json.dumps(r, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO naver_realtors
            (realtor_id, realtor_name, representative_name, address,
             representative_tel_no, cell_phone_no,
             cortar_no, latitude, longitude, deal_count, lease_count, rent_count,
             home_page_url, profile_image_url, raw_json, sample_article_no, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(realtor_id) DO UPDATE SET
            realtor_name=COALESCE(excluded.realtor_name, realtor_name),
            representative_name=COALESCE(excluded.representative_name, representative_name),
            address=COALESCE(excluded.address, address),
            representative_tel_no=COALESCE(excluded.representative_tel_no, representative_tel_no),
            cell_phone_no=COALESCE(excluded.cell_phone_no, cell_phone_no),
            cortar_no=COALESCE(excluded.cortar_no, cortar_no),
            latitude=COALESCE(excluded.latitude, latitude),
            longitude=COALESCE(excluded.longitude, longitude),
            deal_count=COALESCE(excluded.deal_count, deal_count),
            lease_count=COALESCE(excluded.lease_count, lease_count),
            rent_count=COALESCE(excluded.rent_count, rent_count),
            home_page_url=COALESCE(excluded.home_page_url, home_page_url),
            raw_json=excluded.raw_json,
            fetched_at=excluded.fetched_at
        """,
        (rid, r.get("realtorName"), r.get("representativeName"), r.get("address"),
         r.get("representativeTelNo"), r.get("cellPhoneNo"),
         r.get("cortarNo"), r.get("latitude"), r.get("longitude"),
         r.get("dealCount"), r.get("leaseCount"), r.get("rentCount"),
         r.get("homePageUrl"), None, raw, None, now),
    )


def pick_targets(conn, only_missing: bool):
    if only_missing:
        # naver_realtors에 row 없거나 representative_name이 NULL인 케이스
        sql = """
            SELECT DISTINCT l.realtor_id FROM listings_current l
            LEFT JOIN naver_realtors nr ON nr.realtor_id = l.realtor_id
            WHERE l.realtor_id IS NOT NULL
              AND (nr.realtor_id IS NULL OR nr.representative_name IS NULL)
        """
    else:
        sql = "SELECT DISTINCT realtor_id FROM listings_current WHERE realtor_id IS NOT NULL"
    return [r[0] for r in conn.execute(sql).fetchall()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parallel", type=int, default=8)
    p.add_argument("--only-missing", action="store_true",
                   help="naver_realtors에 없거나 rep_name이 NULL인 케이스만")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    conn = open_db()
    creds = ensure_creds()
    todo = pick_targets(conn, args.only_missing)
    if args.limit:
        todo = todo[: args.limit]
    print(f"[*] realtors to fetch: {len(todo):,}  parallel={args.parallel}", flush=True)

    ok = miss = 0
    started = time.time()
    counter = {"i": 0}
    cl = threading.Lock()

    def _work(rid):
        try:
            r = fetch_one(creds, rid)
        except Exception:
            return rid, "err"
        if not r:
            return rid, "miss"
        with DB_LOCK:
            upsert_realtor(conn, rid, r, datetime.now().isoformat(timespec="seconds"))
            conn.commit()
        return rid, "ok"

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = [pool.submit(_work, rid) for rid in todo]
        for fut in as_completed(futs):
            try:
                rid, kind = fut.result()
            except Exception:
                continue
            if kind == "ok":
                ok += 1
            else:
                miss += 1
            with cl:
                counter["i"] += 1
                cur = counter["i"]
            if cur % 200 == 0:
                elapsed = time.time() - started
                rate = cur / max(elapsed, 0.001)
                eta = (len(todo) - cur) / max(rate, 0.001)
                print(f"  [{cur}/{len(todo)}]  ok={ok} miss={miss}  {rate:.1f}/s  ETA {eta/60:.1f}m", flush=True)

    print(f"\n[*] done. ok={ok} miss={miss}  total={time.time()-started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
