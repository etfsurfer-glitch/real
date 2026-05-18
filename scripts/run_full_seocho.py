"""Full daily snapshot for 서초동 (cortarNo=1165010800) into local SQLite.

Walks regions → complexes(248) → articles per A1/B1/B2 with bounded
concurrency. Resumable: on restart, already-successful (complex, trade)
pairs are skipped via collection_log.
"""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

# UTF-8 for cp949 console
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import storage  # noqa: E402
from collector.config import settings  # noqa: E402
from collector.creds import ensure_creds  # noqa: E402
from collector.naver import (  # noqa: E402
    TRADE_TYPES,
    articles_for_complex,
    complexes_in_region,
    find_child,
    list_region_children,
)

TARGET_CORTAR = "1165010800"  # 서초동
TARGET_LABEL = "서초동"


def main() -> int:
    run_date = date.today().isoformat()
    t_start = time.time()
    print(f"[*] run_date={run_date}  target={TARGET_LABEL} ({TARGET_CORTAR})")
    print(f"[*] concurrency={settings.naver_concurrency}  jitter≤{settings.naver_delay_ms}ms")
    print(f"[*] sqlite={settings.local_db_path}")

    conn = storage.open_db(settings.local_db_path)
    storage.init_schema(conn)

    creds = ensure_creds()
    print(f"[*] creds: bearer={creds['bearer'][:20]}...  cookie_keys="
          f"{[c.split('=')[0] for c in creds['cookie'].split('; ')]}")

    # 1. Region path
    print("\n[1] region tree")
    sido = list_region_children("0000000000", creds)
    seoul = find_child(sido, "서울")
    storage.upsert_region(conn, seoul, parent=None)
    gus = list_region_children(seoul["cortarNo"], creds)
    seocho_gu = find_child(gus, "서초구")
    storage.upsert_region(conn, seocho_gu, parent=seoul["cortarNo"])
    dongs = list_region_children(seocho_gu["cortarNo"], creds)
    seocho_dong = next((d for d in dongs if d["cortarNo"] == TARGET_CORTAR), None)
    if not seocho_dong:
        print(f"    target cortarNo {TARGET_CORTAR} not found")
        return 1
    storage.upsert_region(conn, seocho_dong, parent=seocho_gu["cortarNo"])
    print(f"    서울({seoul['cortarNo']}) > {seocho_gu['cortarName']}({seocho_gu['cortarNo']})"
          f" > {seocho_dong['cortarName']}({seocho_dong['cortarNo']})")

    # 2. Complexes in region
    print("\n[2] complexes")
    cps = complexes_in_region(TARGET_CORTAR, creds)
    print(f"    {len(cps)} complexes")
    for c in cps:
        storage.upsert_complex(conn, c)

    # 3. Articles per complex per trade with concurrency + resume
    print(f"\n[3] articles  ({len(cps)} × {len(TRADE_TYPES)} trades)")
    tasks = [(str(c["complexNo"]), c.get("complexName", "?"), t)
             for c in cps for t in TRADE_TYPES]
    done = storage.get_completed_for_run(conn, run_date)
    remaining = [(cno, name, t) for (cno, name, t) in tasks if (cno, t) not in done]
    print(f"    already_done={len(done)}  remaining={len(remaining)}")

    prog = {"n": 0, "items": 0, "errs": 0}
    plock = threading.Lock()

    def worker(cno: str, name: str, trade: str) -> tuple[str, str, int, str | None]:
        try:
            items = list(articles_for_complex(cno, trade, creds))
            storage.save_articles(conn, cno, trade, items, run_date)
            storage.log_completion(conn, run_date, cno, trade, len(items), "success", None)
            return cno, trade, len(items), None
        except Exception as e:  # noqa: BLE001
            storage.log_completion(conn, run_date, cno, trade, 0, "error", str(e)[:300])
            return cno, trade, 0, f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=settings.naver_concurrency) as exe:
        futs = {exe.submit(worker, cno, name, t): (cno, name, t) for cno, name, t in remaining}
        for fut in as_completed(futs):
            cno, name, t = futs[fut]
            _cno, _t, n, err = fut.result()
            with plock:
                prog["n"] += 1
                if err:
                    prog["errs"] += 1
                else:
                    prog["items"] += n
                if prog["n"] % 50 == 0 or err:
                    elapsed = time.time() - t_start
                    rate = prog["n"] / max(elapsed, 0.001)
                    msg = f"  [{prog['n']}/{len(remaining)}] {cno}/{t} +{n}"
                    if err:
                        msg += f"  ERROR: {err[:80]}"
                    msg += f"  ({rate:.1f} req/s, items={prog['items']})"
                    print(msg)

    # 4. Aggregates
    print("\n[4] aggregates")
    ncpx = storage.compute_complex_daily_agg(conn, run_date)
    nreg = storage.compute_region_daily_agg(conn, run_date)
    print(f"    complex_daily_agg rows: {ncpx}")
    print(f"    region_daily_agg rows: {nreg}")

    # 5. Summary
    print("\n=== SUMMARY ===")
    elapsed = time.time() - t_start
    print(f"elapsed: {elapsed:.1f}s   items: {prog['items']}   errors: {prog['errs']}")
    rows = storage.region_summary(conn, run_date, TARGET_CORTAR)
    print(f"\n{TARGET_LABEL} ({TARGET_CORTAR}):")
    label = {"A1": "매매", "B1": "전세", "B2": "월세"}
    for trade, n, cpx in rows:
        print(f"  {label.get(trade, trade)} ({trade}): listings={n}  복합 단지수={cpx}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
