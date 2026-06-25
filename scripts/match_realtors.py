"""Naver realtor_id ↔ vworld broker 매칭 실행."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import run_matching  # noqa: E402


def main() -> int:
    conn = sqlite3.connect(settings.local_db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 30000")

    stats = run_matching(conn)

    total = sum(stats.values())
    print()
    print("=== 매칭 결과 ===")
    for k in sorted(stats, key=lambda x: -stats[x]):
        n = stats[k]
        print(f"  {k:30s} {n:>6}  ({n/max(total,1)*100:.1f}%)")
    print(f"  {'total':30s} {total:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
