"""Naver new.land article detail의 articleRealtor 필드를 수집.

각 realtor_id마다 article 1건을 fetch하면 사무소의 등록번호/대표자/소재지/전화번호/
좌표가 다 들어옴 → vworld와 100% 정확 매칭의 키 `establishRegistrationNo`.

사용:
  python scripts/fetch_naver_realtors.py --parallel 5
  python scripts/fetch_naver_realtors.py --only-unmatched      # match_type=none/multi만
  python scripts/fetch_naver_realtors.py --skip-done            # 이미 fetch된 realtor 건너뜀
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


def pick_articles(conn: sqlite3.Connection, *, only_unmatched: bool, skip_done: bool) -> list[tuple]:
    """Returns [(realtor_id, article_no, real_estate_type, trade_type)] — one article per realtor."""
    # 우선순위: 최신 article_confirm_ymd. articles_current에 realtor당 한 행만 뽑기.
    where = ["l.realtor_id IS NOT NULL"]
    if skip_done:
        where.append("l.realtor_id NOT IN (SELECT realtor_id FROM naver_realtors)")
    if only_unmatched:
        where.append("""
            l.realtor_id IN (
                SELECT realtor_id FROM realtor_match
                WHERE match_type='none' OR match_type LIKE 'multi%'
            )
        """)
    sql = f"""
        WITH ranked AS (
            SELECT l.realtor_id, l.article_no, l.real_estate_type, l.trade_type,
                   ROW_NUMBER() OVER (PARTITION BY l.realtor_id ORDER BY l.article_confirm_ymd DESC) AS rk
            FROM listings_current l
            WHERE {' AND '.join(where)}
        )
        SELECT realtor_id, article_no, real_estate_type, trade_type
        FROM ranked WHERE rk = 1
    """
    return conn.execute(sql).fetchall()


def fetch_one(creds: dict, article_no: str, ret: str, tt: str) -> dict | None:
    """Fetch articleRealtor for a single article. Returns dict or None on error/missing."""
    url = f"https://new.land.naver.com/api/articles/{article_no}"
    status, data = get_json(url, creds, params={
        "complexNo": "",
        "realestateType": ret,
        "tradeType": tt,
    })
    if status != 200 or not isinstance(data, dict):
        return None
    if "error" in data:
        return None
    return data.get("articleRealtor")


def upsert_realtor(conn: sqlite3.Connection, realtor_id: str, article_no: str, ar: dict, now: str) -> None:
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
        (
            realtor_id,
            ar.get("realtorName"),
            ar.get("representativeName"),
            ar.get("address"),
            ar.get("establishRegistrationNo"),
            ar.get("representativeTelNo"),
            ar.get("cellPhoneNo"),
            ar.get("cortarNo"),
            ar.get("latitude"),
            ar.get("longitude"),
            ar.get("dealCount"),
            ar.get("leaseCount"),
            ar.get("rentCount"),
            ar.get("homePageUrl"),
            ar.get("profileImageUrl"),
            raw,
            article_no,
            now,
        ),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parallel", type=int, default=5)
    p.add_argument("--only-unmatched", action="store_true",
                   help="match_type=none/multi인 realtor만 처리")
    p.add_argument("--skip-done", action="store_true",
                   help="naver_realtors에 이미 row 있는 realtor 건너뜀")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    conn = open_db()
    creds = ensure_creds()
    todo = pick_articles(conn, only_unmatched=args.only_unmatched, skip_done=args.skip_done)
    if args.limit:
        todo = todo[: args.limit]
    print(f"[*] realtors to fetch: {len(todo)}  parallel={args.parallel}", flush=True)

    ok = miss = err = 0
    started = time.time()
    counter = {"i": 0}
    cl = threading.Lock()

    def _work(item):
        rid, art, ret, tt = item
        try:
            ar = fetch_one(creds, art, ret, tt)
        except Exception as e:
            return rid, "err", str(e)[:120]
        if not ar:
            return rid, "miss", None
        with DB_LOCK:
            upsert_realtor(conn, rid, art, ar, datetime.now().isoformat(timespec="seconds"))
            conn.commit()
        return rid, "ok", ar.get("establishRegistrationNo")

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = [pool.submit(_work, item) for item in todo]
        for fut in as_completed(futs):
            try:
                rid, kind, val = fut.result()
            except Exception as e:
                err += 1
                continue
            if kind == "ok":
                ok += 1
            elif kind == "miss":
                miss += 1
            else:
                err += 1
            with cl:
                counter["i"] += 1
                cur = counter["i"]
            if cur % 200 == 0:
                elapsed = time.time() - started
                rate = cur / max(elapsed, 0.001)
                eta = (len(todo) - cur) / max(rate, 0.001)
                print(
                    f"  [{cur}/{len(todo)}]  ok={ok} miss={miss} err={err}  "
                    f"{rate:.1f}/s  ETA {eta/60:.1f}m",
                    flush=True,
                )

    print(f"\n[*] fetch done. ok={ok} miss={miss} err={err}  total={time.time()-started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
