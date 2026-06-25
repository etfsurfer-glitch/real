"""Naver 단지 detail fetch — 모든 평형(공급/전용) + 단지 상세 정보.

endpoint: /api/complexes/{complex_no}
- complexDetail: 용적률·건폐율·주차·건설사·관리사무소 전화·도로명주소 등
- complexPyeongDetailList: 단지의 모든 평형 type별 supplyArea/exclusiveArea/세대수

사용:
  python scripts/fetch_complex_detail.py --parallel 8 --only-missing
"""
from __future__ import annotations

import argparse
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


def fetch_one(creds, complex_no):
    url = f"https://new.land.naver.com/api/complexes/{complex_no}"
    status, data = get_json(url, creds)
    if status != 200 or not isinstance(data, dict) or "error" in data:
        return None
    return data


def upsert(conn, complex_no, data, now):
    detail = data.get("complexDetail") or {}
    pyeong_list = data.get("complexPyeongDetailList") or []

    def _f(k):
        v = detail.get(k)
        if v in (None, "", "-"): return None
        try: return float(v)
        except: return None

    def _i(k):
        v = detail.get(k)
        if v in (None, "", "-"): return None
        try: return int(float(v))
        except: return None

    conn.execute(
        """
        UPDATE complexes SET
            batl_ratio = COALESCE(?, batl_ratio),
            btl_ratio = COALESCE(?, btl_ratio),
            parking_possible_count = COALESCE(?, parking_possible_count),
            parking_per_household = COALESCE(?, parking_per_household),
            construction_company = COALESCE(?, construction_company),
            management_office_tel = COALESCE(?, management_office_tel),
            road_address = COALESCE(?, road_address),
            max_supply_area = COALESCE(?, max_supply_area),
            min_supply_area = COALESCE(?, min_supply_area),
            heat_method_code = COALESCE(?, heat_method_code),
            detail_fetched_at = ?
        WHERE complex_no = ?
        """,
        (
            _f("batlRatio"), _f("btlRatio"),
            _i("parkingPossibleCount"), _f("parkingCountByHousehold"),
            detail.get("constructionCompanyName"),
            detail.get("managementOfficeTelNo"),
            detail.get("roadAddress"),
            _f("maxSupplyArea"), _f("minSupplyArea"),
            detail.get("heatMethodTypeCode"),
            now, complex_no,
        ),
    )
    conn.execute("DELETE FROM complex_areas WHERE complex_no = ?", (complex_no,))
    for p in pyeong_list:
        conn.execute(
            "INSERT OR REPLACE INTO complex_areas "
            "(complex_no, pyeong_name, supply_area, exclusive_area, household_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                complex_no,
                p.get("pyeongName"),
                float(p["supplyArea"]) if p.get("supplyArea") else None,
                float(p["exclusiveArea"]) if p.get("exclusiveArea") else None,
                int(p["householdCountByPyeong"]) if p.get("householdCountByPyeong") else None,
            ),
        )


def pick_targets(conn, only_missing):
    if only_missing:
        sql = "SELECT complex_no FROM complexes WHERE detail_fetched_at IS NULL"
    else:
        sql = "SELECT complex_no FROM complexes"
    return [r[0] for r in conn.execute(sql).fetchall()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parallel", type=int, default=8)
    p.add_argument("--only-missing", action="store_true")
    p.add_argument("--limit", type=int)
    args = p.parse_args()

    conn = open_db()
    creds = ensure_creds()
    todo = pick_targets(conn, args.only_missing)
    if args.limit:
        todo = todo[: args.limit]
    print(f"[*] complexes to fetch: {len(todo):,}  parallel={args.parallel}", flush=True)

    ok = miss = 0
    started = time.time()
    counter = {"i": 0}
    cl = threading.Lock()

    def _work(cno):
        try:
            data = fetch_one(creds, cno)
        except Exception:
            return cno, "err"
        if not data or not data.get("complexDetail"):
            return cno, "miss"
        with DB_LOCK:
            upsert(conn, cno, data, datetime.now().isoformat(timespec="seconds"))
            conn.commit()
        return cno, "ok"

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futs = [pool.submit(_work, cno) for cno in todo]
        for fut in as_completed(futs):
            try:
                cno, kind = fut.result()
            except Exception:
                continue
            if kind == "ok": ok += 1
            else: miss += 1
            with cl:
                counter["i"] += 1
                cur = counter["i"]
            if cur % 500 == 0:
                elapsed = time.time() - started
                rate = cur / max(elapsed, 0.001)
                eta = (len(todo) - cur) / max(rate, 0.001)
                print(f"  [{cur}/{len(todo)}]  ok={ok} miss={miss}  {rate:.1f}/s  ETA {eta/60:.1f}m", flush=True)

    print(f"\ndone. ok={ok} miss={miss} total={time.time()-started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
