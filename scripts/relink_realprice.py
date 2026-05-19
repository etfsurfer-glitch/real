"""Re-match transactions that local algorithm couldn't resolve.

전략: unmatched 거래의 (aptNm, sgg_cd) 조합을 dedup → 각 unique pair에 대해
Naver search/complex API 호출 → 시군구 필터 + digit hint로 candidate 선택
→ transactions.matched_complex_no 업데이트, method='naver_search'.

Naver 단지명 변형 (토큰 순서, 차수 위치, 괄호 등)을 그쪽 자체 검색으로 해결.

  python scripts/relink_realprice.py            # dry run, 통계만
  python scripts/relink_realprice.py --apply    # 실제 업데이트
  python scripts/relink_realprice.py --limit 50 # 50개 unique 쌍만 (테스트)
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
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.creds import ensure_creds  # noqa: E402
from collector.realprice import naver_lookup  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true",
                   help="실제로 transactions를 update. 기본은 dry-run")
    p.add_argument("--limit", type=int, default=0,
                   help="처리할 unique (aptNm,sgg) 쌍 수 제한 (debug)")
    p.add_argument("--concurrency", type=int, default=4)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    t_start = time.time()
    conn = sqlite3.connect(str(settings.local_db_path), check_same_thread=False,
                           timeout=30)
    conn.row_factory = sqlite3.Row

    # 1. unmatched 그룹화 (aptNm, sgg_cd, umd_nm) 단위
    print("[1] loading unmatched transactions ...")
    cur = conn.execute(
        """
        SELECT apt_nm, sgg_cd, umd_nm, COUNT(*) AS n
        FROM transactions
        WHERE matched_complex_no IS NULL
        GROUP BY apt_nm, sgg_cd
        ORDER BY n DESC
        """
    )
    groups = cur.fetchall()
    if args.limit:
        groups = groups[: args.limit]
    print(f"    unmatched 거래의 unique (aptNm, sgg) 쌍: {len(groups):,}")
    total_unmatched_tx = sum(g["n"] for g in groups)
    print(f"    이 쌍들이 커버하는 거래 수: {total_unmatched_tx:,}")

    # 2. Naver complex_no whitelist (우리 DB에 있는 단지만 선호)
    known_nos = {r[0] for r in conn.execute("SELECT complex_no FROM complexes")}
    print(f"    우리 complexes 마스터: {len(known_nos):,}")

    # 3. Bearer creds
    creds = ensure_creds()
    print(f"    bearer: {creds['bearer'][:24]}...\n")

    # 4. Process each group concurrently
    print(f"[2] looking up (concurrency={args.concurrency}) ...")
    stats = {"resolved": 0, "still_unmatched": 0, "errors": 0,
             "resolved_tx_count": 0}
    resolutions: dict[tuple, dict] = {}  # (apt_nm, sgg_cd) → resolution
    plock = threading.Lock()
    done_counter = [0]

    def worker(g):
        apt_nm = g["apt_nm"]
        sgg = g["sgg_cd"]
        n = g["n"]
        if not apt_nm or not sgg:
            return (apt_nm, sgg), None, 0
        try:
            complex_no, method, score, debug = naver_lookup.lookup_match(
                apt_nm, sgg, creds, known_complex_nos=known_nos
            )
        except Exception as e:  # noqa: BLE001
            return (apt_nm, sgg), {"error": str(e)}, n
        return (apt_nm, sgg), {
            "complex_no": complex_no,
            "method": method,
            "score": score,
            "debug": debug,
            "umd_nm": g["umd_nm"],
            "tx_count": n,
        }, n

    with ThreadPoolExecutor(max_workers=args.concurrency) as exe:
        futs = [exe.submit(worker, g) for g in groups]
        for fut in as_completed(futs):
            key, res, tx_count = fut.result()
            with plock:
                done_counter[0] += 1
                if res is None:
                    pass
                elif "error" in res:
                    stats["errors"] += 1
                elif res.get("complex_no"):
                    stats["resolved"] += 1
                    stats["resolved_tx_count"] += tx_count
                    resolutions[key] = res
                else:
                    stats["still_unmatched"] += 1
                if done_counter[0] % 100 == 0 or done_counter[0] == len(groups):
                    elapsed = time.time() - t_start
                    rate = done_counter[0] / max(elapsed, 0.001)
                    print(f"  [{done_counter[0]}/{len(groups)}]  "
                          f"resolved={stats['resolved']}  "
                          f"tx_resolved={stats['resolved_tx_count']:,}  "
                          f"({rate:.1f} q/s)")

    print(f"\n[summary]")
    print(f"  unique pairs scanned: {len(groups):,}")
    print(f"  resolved (group):     {stats['resolved']:,}")
    print(f"  resolved (tx):        {stats['resolved_tx_count']:,} / {total_unmatched_tx:,}")
    print(f"  still unmatched:      {stats['still_unmatched']:,}")
    print(f"  errors:               {stats['errors']:,}")

    if not args.apply:
        # Show a few example resolutions — display the ACTUAL chosen complex,
        # not just the first sgg-filtered hit.
        print("\n[sample resolutions] (--apply 안 함, dry-run)")
        for i, (key, res) in enumerate(list(resolutions.items())[:15]):
            chosen_cno = res.get("complex_no")
            chosen_name = None
            for h in res.get("debug", {}).get("hits", []):
                if str(h.get("complex_no")) == str(chosen_cno):
                    chosen_name = h.get("complex_name")
                    break
            print(f"  {key[0]!r} (sgg={key[1]}, n={res['tx_count']})")
            print(f"    → {chosen_name!r}  ({res['method']}, score {res['score']})")
        print("\n실제 적용하려면 --apply 추가")
        return 0

    # 5. Apply
    print("\n[3] updating transactions ...")
    n_updated = 0
    for (apt_nm, sgg), res in resolutions.items():
        if not res.get("complex_no"):
            continue
        # Build match_details for stored trace
        md = {
            "tx": {"aptNm": apt_nm, "sggCd": sgg, "umdNm": res.get("umd_nm")},
            "method": res["method"],
            "score": res["score"],
            "naver_lookup_debug": res["debug"],
            "chosen": {
                "complex_no": res["complex_no"],
                "method": res["method"],
                "score": res["score"],
            },
        }
        conn.execute(
            """
            UPDATE transactions
            SET matched_complex_no = ?,
                matched_method     = ?,
                matched_score      = ?,
                match_details      = ?,
                matched_at         = datetime('now')
            WHERE apt_nm = ? AND sgg_cd = ?
              AND manual_override = 0
              AND matched_complex_no IS NULL
            """,
            (res["complex_no"], res["method"], res["score"],
             json.dumps(md, ensure_ascii=False), apt_nm, sgg),
        )
        n_updated += conn.total_changes  # cumulative
    conn.commit()
    print(f"    applied to ~{stats['resolved_tx_count']:,} tx rows")

    print(f"\n[done] {time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
