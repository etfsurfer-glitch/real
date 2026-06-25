"""특정 시군구의 동(dong) 단위로 vworld 크롤. 페이지네이션이 sgg 단위에서
중간에 끊기는 경우(예: 강남구 11680)를 우회.

사용:
  python scripts/crawl_vworld_by_dong.py --sgg 11680
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.vworld import LIST_URL, parse_list, new_session  # noqa: E402


def open_db() -> sqlite3.Connection:
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def fetch_dong_page(client, sido_cd, sigungu_cd, dong_cd, page, page_size=50):
    data = {
        "sidoCd": sido_cd,
        "sigunguCd": sigungu_cd,
        "dongCd": dong_cd,
        "pageIndex": str(page),
        "recordCountPerPage": str(page_size),
    }
    r = client.post(LIST_URL, data=data)
    r.raise_for_status()
    return parse_list(r.text, sigungu_cd)


def iter_dong(client, sido, sgg, dong, page_size=50, sleep_s=0.3, max_pages=100):
    page = 1
    seen = 0
    known_total = None
    while page <= max_pages:
        total, items = fetch_dong_page(client, sido, sgg, dong, page, page_size)
        if known_total is None:
            known_total = total
        if not items:
            break
        for it in items:
            yield it
        seen += len(items)
        if known_total and seen >= known_total:
            break
        page += 1
        time.sleep(sleep_s)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sgg", required=True, help="시군구 5자리 코드 (예: 11680)")
    p.add_argument("--page-size", type=int, default=50)
    p.add_argument("--sleep", type=float, default=0.3)
    args = p.parse_args()

    conn = open_db()
    sido = args.sgg[:2]
    sgg = args.sgg

    # dong 목록
    dongs = conn.execute(
        "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='sec' AND substr(cortar_no,1,5)=? ORDER BY cortar_no",
        (sgg,),
    ).fetchall()
    print(f"[*] sgg={sgg}  dongs={len(dongs)}", flush=True)

    before = conn.execute("SELECT COUNT(*) FROM vworld_brokers WHERE sgg_cd=?", (sgg,)).fetchone()[0]
    print(f"  before: {before}", flush=True)

    grand = 0
    for cortar_no, dname in dongs:
        # fresh session per dong
        client = new_session()
        rows = 0
        t0 = time.time()
        try:
            now = datetime.now().isoformat(timespec="seconds")
            for it in iter_dong(client, sido, sgg, cortar_no, args.page_size, args.sleep):
                conn.execute(
                    """
                    INSERT INTO vworld_brokers
                        (sys_regno, ra_regno, sgg_cd, business_name, address,
                         representative, registered_ymd, status, list_fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sys_regno) DO UPDATE SET
                        ra_regno=excluded.ra_regno, sgg_cd=excluded.sgg_cd,
                        business_name=excluded.business_name, address=excluded.address,
                        representative=excluded.representative,
                        registered_ymd=excluded.registered_ymd, status=excluded.status,
                        list_fetched_at=excluded.list_fetched_at
                    """,
                    (it.sys_regno, it.ra_regno, it.sgg_cd, it.business_name, it.address,
                     it.representative, it.registered_ymd, it.status, now),
                )
                conn.commit()
                rows += 1
        except Exception as e:
            print(f"  ✗ {cortar_no} {dname}: {e}", flush=True)
            continue
        grand += rows
        print(f"  ✓ {cortar_no} {dname:8s}  rows={rows}  ({time.time()-t0:.1f}s)", flush=True)

    after = conn.execute("SELECT COUNT(*) FROM vworld_brokers WHERE sgg_cd=?", (sgg,)).fetchone()[0]
    print(f"\n[*] before={before}  after={after}  added={after-before}  iter_total={grand}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
