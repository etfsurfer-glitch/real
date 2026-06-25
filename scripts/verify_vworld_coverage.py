"""시군구별 vworld 실제 총건수 ↔ DB 수집 건수 검증 + 부족분 재크롤.

각 시군구마다:
  1. vworld list 페이지 1건 fetch로 '총 X건' 값 받음 (probe)
  2. DB에 저장된 그 sgg 사무소 수와 비교
  3. 부족하면 list 재크롤 (parallel=1, fresh session)
  4. 진행 상황을 vworld_crawl_log에 기록

사용:
  python scripts/verify_vworld_coverage.py             # 모든 sgg 검증, 부족분 재크롤
  python scripts/verify_vworld_coverage.py --sido 11   # 서울만
  python scripts/verify_vworld_coverage.py --dry-run   # 불일치만 보고 (재크롤 안 함)
  python scripts/verify_vworld_coverage.py --threshold 5  # 5건 이상 차이날 때만 재크롤
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.vworld import fetch_list_page, iter_sigungu, new_session  # noqa: E402


def open_db() -> sqlite3.Connection:
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def list_sigungus(conn, sido_filter):
    q = "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn'"
    params = []
    if sido_filter:
        q += " AND substr(cortar_no,1,2)=?"
        params.append(sido_filter)
    q += " ORDER BY cortar_no"
    return [(c[:2], c[:5], n) for c, n in conn.execute(q, params).fetchall()]


def db_count(conn, sgg: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM vworld_brokers WHERE sgg_cd=?", (sgg,)).fetchone()[0]


def probe_total(client, sido, sgg) -> int | None:
    """vworld에서 '총 X건' 값만 받음. 0이면 재시도 (세션 reset)."""
    for attempt in range(3):
        try:
            total, _ = fetch_list_page(client, sido, sgg, page=1, page_size=10)
            if total > 0:
                return total
        except Exception as e:
            if attempt == 2:
                return None
        # 0 또는 에러 → 세션 갈아끼우기
        client.cookies.clear()
        try:
            client.get("https://www.vworld.kr/dtld/broker/dtld_list_s001.do")
        except Exception:
            pass
        time.sleep(0.5)
    return 0


def recrawl_sgg(client, conn, sido, sgg, page_size=50, sleep_s=0.4) -> int:
    """list 재크롤 (단일 sgg). 행마다 upsert + commit (락 짧게)."""
    now = datetime.now().isoformat(timespec="seconds")
    rows = 0
    for it in iter_sigungu(client, sido, sgg, page_size=page_size, sleep_s=sleep_s, max_pages=200):
        conn.execute(
            """
            INSERT INTO vworld_brokers
                (sys_regno, ra_regno, sgg_cd, business_name, address,
                 representative, registered_ymd, status, list_fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sys_regno) DO UPDATE SET
                ra_regno=excluded.ra_regno,
                sgg_cd=excluded.sgg_cd,
                business_name=excluded.business_name,
                address=excluded.address,
                representative=excluded.representative,
                registered_ymd=excluded.registered_ymd,
                status=excluded.status,
                list_fetched_at=excluded.list_fetched_at
            """,
            (it.sys_regno, it.ra_regno, it.sgg_cd, it.business_name, it.address,
             it.representative, it.registered_ymd, it.status, now),
        )
        conn.commit()
        rows += 1
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sido")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--threshold", type=int, default=10,
                   help="DB count + threshold < total인 경우 재크롤")
    p.add_argument("--page-size", type=int, default=50)
    p.add_argument("--sleep", type=float, default=0.4)
    args = p.parse_args()

    conn = open_db()
    sgs = list_sigungus(conn, args.sido)
    print(f"[*] checking {len(sgs)} sigungus...", flush=True)

    client = new_session()
    discrepancies = []
    for i, (sido, sgg, name) in enumerate(sgs, 1):
        have = db_count(conn, sgg)
        total = probe_total(client, sido, sgg)
        if total is None:
            print(f"  [{i}/{len(sgs)}] {sgg} {name:15s}  PROBE FAILED (have={have})", flush=True)
            continue
        diff = total - have
        flag = ""
        if diff > args.threshold:
            flag = f"  ⚠ MISSING {diff}"
            discrepancies.append((i, sido, sgg, name, have, total))
        print(f"  [{i}/{len(sgs)}] {sgg} {name:15s}  have={have:>5}  total={total:>5}{flag}", flush=True)

    print(f"\n[*] discrepancies (diff > {args.threshold}): {len(discrepancies)}", flush=True)
    if args.dry_run or not discrepancies:
        return 0

    print(f"\n[*] re-crawling {len(discrepancies)} short sigungus...", flush=True)
    for i, sido, sgg, name, have_was, total_was in discrepancies:
        t0 = time.time()
        rows = 0
        # fresh session per sigungu — 그리고 transient 네트워크 에러는 한 번 재시도
        for attempt in range(2):
            try:
                client = new_session()
                rows = recrawl_sgg(client, conn, sido, sgg, page_size=args.page_size, sleep_s=args.sleep)
                break
            except Exception as e:
                print(f"  ✗ {sgg} {name}: attempt {attempt+1}: {e}", flush=True)
                time.sleep(2.0)
        if rows == 0 and attempt == 1:
            continue
        new_count = db_count(conn, sgg)
        elapsed = time.time() - t0
        conn.execute(
            """
            INSERT INTO vworld_crawl_log(sgg_cd, last_listed_at, total_count, rows_seen, note)
            VALUES (?, ?, ?, ?, 'verify-recrawl')
            ON CONFLICT(sgg_cd) DO UPDATE SET
                last_listed_at=excluded.last_listed_at,
                total_count=excluded.total_count,
                rows_seen=excluded.rows_seen,
                note=excluded.note
            """,
            (sgg, datetime.now().isoformat(timespec="seconds"), total_was, new_count),
        )
        conn.commit()
        gap = total_was - new_count
        tag = "✓" if gap <= args.threshold else "✗"
        print(f"  {tag} {sgg} {name:15s}  {have_was}→{new_count}/{total_was}  (+{rows} rows, {elapsed:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
