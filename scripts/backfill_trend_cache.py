"""avg-price-trend / changes/summary 프리빌드 캐시 백필 — asset 차원 포함.

기존 프리빌드는 asset 없이 캐싱해 프런트(Changes.tsx)가 항상 보내는 asset=apt/offi
키와 어긋나 100% 미스(콜드 8~11s)였다. 이 스크립트는 전국+시도 × (apt,offi) 조합을
api_cache.sqlite 에 INSERT OR REPLACE 로 즉시 채운다(기존 캐시 안전, wipe 없음).

시군구는 엔드포인트 인메모리 캐시(첫 호출 후 즉시) + 다음 야간 build_api_cache 가 커버.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from scripts.local_api import app, _CACHE_DB_PATH  # noqa: E402
from scripts.build_api_cache import make_key, _list_sidos  # noqa: E402


def main(workers: int = 6) -> None:
    client = TestClient(app)
    sidos = _list_sidos(client)
    regions = [{}] + [{"sido": s} for s in sidos]   # 전국 + 시도
    specs: list[tuple[str, dict]] = []
    for asset in ("apt", "offi"):
        for reg in regions:
            specs.append(("/stats/avg-price-trend", {"days": 60, "asset": asset, **reg}))
            specs.append(("/stats/changes/summary", {"asset": asset, **reg}))
    func_by_path = {r.path: r.endpoint for r in app.routes if getattr(r, "endpoint", None)}
    print(f"specs: {len(specs)}  workers={workers}", flush=True)

    conn = sqlite3.connect(str(_CACHE_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    import threading
    lock = threading.Lock()
    cnt = {"ok": 0, "err": 0}
    t0 = time.perf_counter()

    def work(item):
        path, params = item
        func = func_by_path.get(path)
        if func is None:
            return
        try:
            res = func(**params)
        except HTTPException:
            with lock:
                cnt["err"] += 1
            return
        except Exception as e:  # noqa: BLE001
            print(f"  ERR {path} {params} -- {e}", file=sys.stderr, flush=True)
            with lock:
                cnt["err"] += 1
            return
        key, qs = make_key(path, params)
        body = json.dumps(jsonable_encoder(res), ensure_ascii=False).encode("utf-8")
        with lock:
            conn.execute(
                "INSERT OR REPLACE INTO api_cache "
                "(cache_key, path, query, response, size_bytes, elapsed_ms, computed_at) "
                "VALUES (?, ?, ?, ?, ?, 0, datetime('now'))",
                (key, path, qs, body, len(body)),
            )
            cnt["ok"] += 1

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, specs))
    conn.commit()
    conn.close()
    print(f"DONE ok={cnt['ok']} err={cnt['err']}  {time.perf_counter()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
