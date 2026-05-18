"""Push today's SQLite snapshot to Supabase Postgres."""
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import storage, supabase_uploader  # noqa: E402
from collector.config import settings  # noqa: E402


def main() -> int:
    run_date = date.today().isoformat()
    print(f"[*] target: {settings.supabase_url}")
    print(f"[*] snapshot_date={run_date}")
    print(f"[*] sqlite={settings.local_db_path}")

    conn = storage.open_db(settings.local_db_path)
    supa = supabase_uploader.get_client()

    t0 = time.time()
    print()

    n = supabase_uploader.upsert_regions(conn, supa)
    print(f"  regions:               {n:>6}  ({time.time()-t0:.1f}s)")

    n = supabase_uploader.upsert_complexes(conn, supa)
    print(f"  complexes:             {n:>6}  ({time.time()-t0:.1f}s)")

    n = supabase_uploader.replace_listings_current(conn, supa, run_date)
    print(f"  listings_current:      {n:>6}  ({time.time()-t0:.1f}s)")

    n = supabase_uploader.replace_complex_daily_agg(conn, supa, run_date)
    print(f"  complex_daily_agg:     {n:>6}  ({time.time()-t0:.1f}s)")

    n = supabase_uploader.replace_region_daily_agg(conn, supa, run_date)
    print(f"  region_daily_agg:      {n:>6}  ({time.time()-t0:.1f}s)")

    elapsed = time.time() - t0
    print(f"\n[done] total {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
