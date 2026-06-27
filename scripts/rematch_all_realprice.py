"""4개 실거래 테이블 (transactions / rentals / offi_transactions / offi_rentals)
의 매칭을 새 단지 인덱스로 재계산. API 호출 없음 — raw 컬럼만 다시 매칭.

기존 rematch_realprice.py / rematch_rentals.py 의 일반화 버전. 매칭 파이프라인
(brand prefix, 본번 fallback, substring 강화) 개선 후 4 테이블 모두 한 번에
정리할 때 사용.

manual_override=1 행은 절대 손대지 않음. 신뢰도 낮은 기존 매칭(substr 0.55/
0.75 등)도 새 로직으로 다시 채점되어 덮어쓰임 (단, manual 가 아닐 때만).

Run:
    python scripts/rematch_all_realprice.py                 # 4 tables 전부
    python scripts/rematch_all_realprice.py --tables apt    # transactions 만
    python scripts/rematch_all_realprice.py --only-unmatched
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realprice import matching as rp_match  # noqa: E402
from collector.realprice import storage as rp_storage  # noqa: E402


# 테이블별 PK 컬럼 + 사람에게 보여줄 키. 모든 테이블이 sgg_cd, raw,
# matched_*, manual_override 컬럼은 공통이라 SQL 은 PK 이름만 바꾸면 됨.
TABLE_SPECS = {
    "apt":       {"table": "transactions",      "pk": "deal_id",   "label": "아파트 매매"},
    "rent":      {"table": "rentals",           "pk": "rental_id", "label": "아파트 전월세"},
    "offi":      {"table": "offi_transactions", "pk": "deal_id",   "label": "오피스텔 매매"},
    "offi_rent": {"table": "offi_rentals",      "pk": "rental_id", "label": "오피스텔 전월세"},
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tables", nargs="+",
                   choices=list(TABLE_SPECS.keys()) + ["all"],
                   default=["all"], help="처리할 테이블 (기본: all)")
    p.add_argument("--only-unmatched", action="store_true",
                   help="현재 unmatched 인 행만 재시도")
    p.add_argument("--concurrency", type=int, default=4)
    return p.parse_args()


def rematch_table(conn: sqlite3.Connection, spec: dict, only_unmatched: bool,
                  concurrency: int) -> dict:
    table, pk, label = spec["table"], spec["pk"], spec["label"]
    t0 = time.time()
    # 기존 매칭 정보도 같이 읽어옴: local 매칭 실패 시 naver_search 결과(API 기반)
    # 같은 보존-가치 있는 매칭은 그대로 둔다.
    where = " WHERE matched_complex_no IS NULL" if only_unmatched else ""
    cur = conn.execute(
        f"SELECT {pk}, sgg_cd, raw, manual_override, matched_method "
        f"FROM {table}{where}"
    )
    by_sgg: dict[str, list[tuple]] = defaultdict(list)
    skipped_manual = 0
    for rid, sgg_cd, raw, manual, mm in cur.fetchall():
        if manual:
            skipped_manual += 1
            continue
        by_sgg[sgg_cd].append((rid, raw, mm))

    total = sum(len(v) for v in by_sgg.values())
    print(f"\n=== {label} ({table}) — target {total:,} rows over {len(by_sgg)} 시군구 ===")
    print(f"  (manual_override 제외: {skipped_manual:,}, only_unmatched={only_unmatched})")

    plock = threading.Lock()
    stats = {"updated": 0, "newly_matched": 0, "still_unmatched": 0, "errors": 0}

    def worker(sgg_cd: str, rows: list[tuple]) -> dict:
        local = {"updated": 0, "newly_matched": 0, "still_unmatched": 0, "errors": 0}
        try:
            complexes = rp_match.load_complexes(conn, cortar_prefix=sgg_cd)
            idx = rp_match.ComplexIndex(complexes)
        except Exception:
            local["errors"] += len(rows)
            return local

        updates = []
        now = datetime.now().isoformat(timespec="seconds")
        for rid, raw, prev_method in rows:
            try:
                tx = json.loads(raw) if raw else {}
            except Exception:
                local["errors"] += 1
                continue
            trace = rp_match.match_one_with_trace(tx, idx, keep_top=3)
            if trace.get("chosen"):
                chosen = trace["chosen"]
                updates.append((
                    chosen["complex_no"], chosen["method"], chosen["score"],
                    json.dumps(trace, ensure_ascii=False), now, rid,
                ))
                local["newly_matched"] += 1
            else:
                # Local 매칭 실패. 기존 매칭이 naver_search 류면 그건 reverse-lookup
                # 으로만 얻을 수 있는 결과라 보존. 아니면 unmatched 처리.
                if prev_method and prev_method.startswith("naver_search"):
                    # update 자체를 skip → 기존 행 그대로 유지
                    continue
                updates.append((
                    None, "unmatched", None,
                    json.dumps(trace, ensure_ascii=False), now, rid,
                ))
                local["still_unmatched"] += 1

        if updates:
            with rp_storage._LOCK:
                conn.executemany(
                    f"""
                    UPDATE {table}
                    SET matched_complex_no = ?,
                        matched_method     = ?,
                        matched_score      = ?,
                        match_details      = ?,
                        matched_at         = ?
                    WHERE {pk} = ? AND manual_override = 0
                    """,
                    updates,
                )
                conn.commit()
                local["updated"] = len(updates)
        return local

    with ThreadPoolExecutor(max_workers=concurrency) as exe:
        futs = {exe.submit(worker, k, v): k for k, v in by_sgg.items()}
        done_sgg = 0
        for fut in as_completed(futs):
            sgg = futs[fut]
            local = fut.result()
            with plock:
                for k in stats:
                    stats[k] += local[k]
                done_sgg += 1
                if done_sgg % 50 == 0 or done_sgg == len(by_sgg):
                    rate = done_sgg / max(time.time() - t0, 0.001)
                    print(f"  [{done_sgg}/{len(by_sgg)}] sgg={sgg}  "
                          f"updated={stats['updated']:,} new={stats['newly_matched']:,}  "
                          f"({rate:.1f} sgg/s)")

    elapsed = time.time() - t0
    n_total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    n_matched = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE matched_complex_no IS NOT NULL"
    ).fetchone()[0]
    print(f"  [done] {elapsed:.0f}s  updated={stats['updated']:,}  "
          f"matched_rate={n_matched*100/max(n_total,1):.1f}%  "
          f"unmatched={n_total - n_matched:,}")
    stats["elapsed"] = elapsed
    stats["n_total"] = n_total
    stats["n_matched"] = n_matched
    return stats


def main() -> int:
    args = parse_args()
    if "all" in args.tables:
        keys = list(TABLE_SPECS.keys())
    else:
        keys = args.tables

    conn = sqlite3.connect(str(settings.local_db_path),
                           check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA journal_size_limit=1073741824")  # WAL 상한 1GB(체크포인트 후 자동 축소)

    t0 = time.time()
    all_stats = {}
    for k in keys:
        spec = TABLE_SPECS[k]
        all_stats[k] = rematch_table(conn, spec, args.only_unmatched, args.concurrency)

    total_elapsed = time.time() - t0
    print(f"\n========== ALL DONE in {total_elapsed:.0f}s ==========")
    for k, s in all_stats.items():
        spec = TABLE_SPECS[k]
        print(f"  {spec['label']:<14s} updated={s['updated']:>8,d}  "
              f"matched_rate={s['n_matched']*100/max(s['n_total'],1):>5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
