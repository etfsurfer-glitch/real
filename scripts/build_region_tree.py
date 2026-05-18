"""Walk the full Naver region tree and persist to local SQLite.

Run this once before the first nationwide collection. Idempotent —
re-running refreshes names/coords. Takes ~3-5 minutes for full Korea
(17 시도 × ~250 시군구 × ~5000 동 = ~5300 fetches at jittered rate).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector import regions, storage  # noqa: E402
from collector.config import settings  # noqa: E402
from collector.creds import ensure_creds  # noqa: E402


def main() -> int:
    conn = storage.open_db(settings.local_db_path)
    storage.init_schema(conn)
    creds = ensure_creds()
    print(f"[*] walking national region tree → {settings.local_db_path}")
    t0 = time.time()
    last_sido = {"name": ""}

    def on_progress(level: str, node: dict) -> None:
        if level == "city":
            last_sido["name"] = node.get("cortarName", "?")
            print(f"  [시/도] {last_sido['name']}")
        elif level == "dvsn":
            print(f"    [시군구] {node.get('cortarName')}", end="\r")

    counts = regions.walk_tree(creds, conn, on_progress=on_progress)
    elapsed = time.time() - t0
    print(f"\n[done] {elapsed:.0f}s  counts={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
