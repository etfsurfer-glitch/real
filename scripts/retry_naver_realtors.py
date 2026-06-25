"""naver_realtors fetch 실패한 realtor들을 다른 article로 retry.

기존 fetch_naver_realtors.py는 realtor당 article 1건만 시도 → 만료된 article이면 fail.
이 스크립트는 매물 활성된 article 순으로 최대 N개 시도해서 첫 성공 응답을 저장.

사용:
  python scripts/retry_naver_realtors.py --parallel 8 --max-attempts 5
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


def open_db() -> sqlite3.Connection:
    c = sqlite3.connect(settings.local_db_path, timeout=30.0, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout = 30000")
    return c


def pick_targets(conn, max_attempts: int) -> list[tuple[str, list[tuple[str, str, str]]]]:
    """Returns [(realtor_id, [(article_no, real_estate_type, trade_type), ...])]
    — realtor마다 최대 max_attempts개의 article 후보 (최신순)."""
    rows = conn.execute(
        f"""
        WITH ranked AS (
            SELECT l.realtor_id, l.article_no, l.real_estate_type, l.trade_type,
                   ROW_NUMBER() OVER (
                     PARTITION BY l.realtor_id
                     ORDER BY l.article_confirm_ymd DESC, l.article_no DESC
                   ) AS rk
            FROM listings_current l
            WHERE l.realtor_id IS NOT NULL
              AND l.realtor_id NOT IN (SELECT realtor_id FROM naver_realtors)
        )
        SELECT realtor_id, article_no, real_estate_type, trade_type
        FROM ranked WHERE rk <= {max_attempts}
        ORDER BY realtor_id, rk
        """
    ).fetchall()
    by_rid: dict[str, list] = {}
    for rid, art, ret, tt in rows:
        by_rid.setdefault(rid, []).append((art, ret, tt))
    return list(by_rid.items())


def fetch_one(creds, article_no, ret, tt):
    url = f"https://new.land.naver.com/api/articles/{article_no}"
    status, data = get_json(url, creds, params={
        "complexNo": "", "realestateType": ret, "tradeType": tt,
    })
    if status != 200 or not isinstance(data, dict) or "error" in data:
        return None
    return data.get("articleRealtor")


def upsert_realtor(conn, rid, art, ar, now):
    raw = json.dumps(ar, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO naver_realtors
            (realtor_id, realtor_name, representative_name, address,
             establish_registration_no, representative_tel_no, cell_phone_no,
             cortar_no, latitude, longitude, deal_count, lease_count, rent_count,
             home_page_url, profile_image_url, raw_json, sample_article_no, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(realtor_id) DO UPDATE SET
            realtor_name=excluded.realtor_name,
            representative_name=excluded.representative_name,
            address=excluded.address,
            establish_registration_no=excluded.establish_registration_no,
            representative_tel_no=excluded.representative_tel_no,
            cell_phone_no=excluded.cell_phone_no,
            cortar_no=excluded.cortar_no,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            deal_count=excluded.deal_count,
            lease_count=excluded.lease_count,
            rent_count=excluded.rent_count,
            home_page_url=excluded.home_page_url,
            profile_image_url=excluded.profile_image_url,
            raw_json=excluded.raw_json,
            sample_article_no=excluded.sample_article_no,
            fetched_at=excluded.fetched_at
        """,
        (rid, ar.get("realtorName"), ar.get("representativeName"), ar.get("address"),
         ar.get("establishRegistrationNo"), ar.get("representativeTelNo"),
         ar.get("cellPhoneNo"), ar.get("cortarNo"), ar.get("latitude"), ar.get("longitude"),
         ar.get("dealCount"), ar.get("leaseCount"), ar.get("rentCount"),
         ar.get("homePageUrl"), ar.get("profileImageUrl"), raw, art, now),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parallel", type=int, default=8)
    p.add_argument("--max-attempts", type=int, default=5,
                   help="realtor당 시도할 article 수 (만료 fallback)")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    conn = open_db()
    creds = ensure_creds()
    todo = pick_targets(conn, args.max_attempts)
    if args.limit:
        todo = todo[: args.limit]
    print(f"[*] retry realtors: {len(todo)}  parallel={args.parallel}  max_attempts={args.max_attempts}", flush=True)

    ok = miss = err = 0
    started = time.time()
    counter = {"i": 0}
    cl = threading.Lock()

    def _work(item):
        rid, articles = item
        for art, ret, tt in articles:
            try:
                ar = fetch_one(creds, art, ret, tt)
            except Exception:
                continue
            if ar:
                with DB_LOCK:
                    upsert_realtor(conn, rid, art, ar, datetime.now().isoformat(timespec="seconds"))
                    conn.commit()
                return rid, "ok"
        return rid, "miss"

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = [pool.submit(_work, item) for item in todo]
        for fut in as_completed(futs):
            try:
                rid, kind = fut.result()
            except Exception:
                err += 1
                continue
            if kind == "ok":
                ok += 1
            else:
                miss += 1
            with cl:
                counter["i"] += 1
                cur = counter["i"]
            if cur % 100 == 0:
                elapsed = time.time() - started
                rate = cur / max(elapsed, 0.001)
                eta = (len(todo) - cur) / max(rate, 0.001)
                print(f"  [{cur}/{len(todo)}]  ok={ok} miss={miss} err={err}  {rate:.1f}/s  ETA {eta/60:.1f}m", flush=True)

    print(f"\n[*] retry done. ok={ok} miss={miss} err={err}  total={time.time()-started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
