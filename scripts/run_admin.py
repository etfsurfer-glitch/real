"""Launch the local admin UI (FastAPI on localhost:8001).

  python scripts/run_admin.py
  -> http://localhost:8001/

Read-only v1: filter by method, search by 단지/동, see match_details.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "collector.admin.server:app",
        host="127.0.0.1",
        port=8001,
        reload=False,
        log_level="info",
    )
