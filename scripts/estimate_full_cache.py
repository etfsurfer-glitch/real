"""전체 파라미터 조합을 캐시할 경우의 용량/시간 추정.

프런트엔드 필터 UI 가 만들 수 있는 모든 URL 조합(= '전체 경우의 수')을
엔드포인트 패밀리별로 열거하고, 각 패밀리에서 무작위 샘플만 라이브로 실행해
평균 응답시간/크기를 잰 뒤 전체 조합 수로 외삽한다.

캐시 미들웨어는 _CACHE_DB_PATH 를 없는 경로로 바꿔 우회 → 항상 라이브 계산.
"""
from __future__ import annotations

import random
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import scripts.local_api as la  # noqa: E402

# 캐시 미들웨어 무력화 — 모든 요청을 라이브로 계산시키기 위함
la._CACHE_DB_PATH = Path("__no_such_cache__.sqlite")

client = TestClient(la.app)
random.seed(42)

# ── 지역 목록 ──────────────────────────────────────────────
sidos = [it["code"] for it in client.get("/stats/changes/sido-list").json()["items"]]
sigungus: list[str] = []
for s in sidos:
    sigungus += [it["code"] for it in client.get(f"/stats/sigungu-list?sido={s}").json()["items"]]
print(f"sidos={len(sidos)}  sigungus={len(sigungus)}", flush=True)

with sqlite3.connect(settings.local_db_path) as db:
    n_complex = db.execute("SELECT COUNT(*) FROM complexes").fetchone()[0]
    complex_ids = [r[0] for r in db.execute(
        "SELECT complex_no FROM complexes ORDER BY RANDOM() LIMIT 40")]
    n_realtor = db.execute(
        "SELECT COUNT(DISTINCT realtor_id) FROM listings_current "
        "WHERE realtor_id IS NOT NULL").fetchone()[0]
    realtor_ids = [r[0] for r in db.execute(
        "SELECT DISTINCT realtor_id FROM listings_current "
        "WHERE realtor_id IS NOT NULL ORDER BY RANDOM() LIMIT 40")]
print(f"complexes={n_complex}  realtors={n_realtor}", flush=True)

# OS 페이지캐시 워밍업 — 첫 쿼리가 콜드 디스크 I/O 로 수십 초씩 튀는 것 방지
client.get("/stats/tx-top-price?days=30&trade=A1&asset=all&limit=100")

# ── 프런트 필터 옵션 (frontend/src/pages/*.tsx 와 1:1) ─────
DAYS6 = [7, 30, 90, 180, 365, 0]
TRADE3 = ["A1", "B1", "B2"]
ASSET3 = ["all", "apt", "offi"]
ASSET2 = ["apt", "offi"]
DEALING3 = ["all", "broker", "direct"]
AREA6 = ["all", "10s", "20s", "30s", "40s", "over50"]
P3 = [180, 365, 730]
ORD2 = ["desc", "asc"]
REGIONS = [None] + sidos + sigungus  # 전국 + 시도 + 시군구


def combos(*lists):
    out = [{}]
    for key, vals in lists:
        out = [{**d, key: v} for d in out for v in vals]
    return out


FAMILIES: dict[str, tuple[str, list[dict], dict]] = {}  # name -> (path, combos, fixed)

FAMILIES["tx-top-price"] = ("/stats/tx-top-price", combos(
    ("days", DAYS6), ("trade", TRADE3), ("asset", ASSET3),
    ("dealing", DEALING3), ("area_class", AREA6)), {"limit": 100})
FAMILIES["tx-top-volume"] = ("/stats/tx-top-volume", combos(
    ("days", DAYS6), ("trade", TRADE3), ("asset", ASSET3),
    ("dealing", DEALING3), ("area_class", AREA6)), {"limit": 100})
FAMILIES["tx-low-price"] = ("/stats/tx-low-price", combos(
    ("days", [90, 180, 365, 730]), ("discount", [0.2, 0.3, 0.4, 0.5]),
    ("asset", ASSET3), ("area_class", AREA6)), {"min_samples": 3, "limit": 300})
FAMILIES["tx-inventory-pressure"] = ("/stats/tx-inventory-pressure", combos(
    ("trade", ["A1", "B1", "B2", "all"]), ("area_class", AREA6)),
    {"min_listings": 10, "min_households": 50, "limit": 200})
FAMILIES["tx-gap-rank"] = ("/stats/tx-gap-rank", combos(
    ("days", P3), ("asset", ASSET2), ("area_class", AREA6), ("order", ORD2)),
    {"min_samples": 3, "limit": 100})
FAMILIES["tx-jeonse-rate"] = ("/stats/tx-jeonse-rate", combos(
    ("days", P3), ("asset", ASSET2), ("area_class", AREA6), ("order", ORD2)),
    {"min_samples": 3, "limit": 100})
FAMILIES["tx-price-change"] = ("/stats/tx-price-change", combos(
    ("window_days", [30, 90, 180]), ("asset", ASSET2), ("area_class", AREA6),
    ("order", ORD2)), {"min_samples": 3, "limit": 100})
FAMILIES["tx-pyeong-price"] = ("/stats/tx-pyeong-price", combos(
    ("days", P3), ("asset", ASSET2), ("area_class", AREA6), ("order", ORD2)),
    {"min_samples": 3, "limit": 100})
FAMILIES["tx-turnover"] = ("/stats/tx-turnover", combos(
    ("days", P3), ("trade", ["A1", "B1"]), ("asset", ASSET2),
    ("area_class", AREA6)), {"min_households": 50, "limit": 100})
FAMILIES["tx-yield"] = ("/stats/tx-yield", combos(
    ("days", P3), ("sido", [None] + sidos), ("area_class", AREA6),
    ("asset", ASSET2)), {"min_samples": 3, "limit": 100})
FAMILIES["tx-record-high"] = ("/stats/tx-record-high", combos(
    ("days", [30, 90, 180, 365]), ("trade", TRADE3), ("asset", ASSET3),
    ("area_class", AREA6), ("max_gap_months", [0, 3, 6, 12, 24]),
    ("order", ["premium", "recent"])), {"min_prior": 1, "limit": 300})
FAMILIES["tx-asking-vs-real"] = ("/stats/tx-asking-vs-real", combos(
    ("days", [90, 180, 365]), ("area_class", AREA6), ("order", ORD2)),
    {"min_samples": 3, "limit": 100})
FAMILIES["quick-deals"] = ("/stats/quick-deals", combos(
    ("trade_type", ["A1", "B1"]), ("pyeong", [None, "10", "20", "30", "40", "50"]),
    ("days", [90, 180, 365]), ("min_discount", [0, 0.05, 0.1, 0.2, 0.3]),
    ("region", REGIONS)), {"min_samples": 5, "limit": 200})
FAMILIES["tx-region-pulse"] = ("/stats/tx-region-pulse", combos(
    ("asset", ["apt", "offi", "all"])), {})

SAMPLE_K = 8


def sample_run(path: str, all_combos: list[dict], fixed: dict) -> tuple[float, float, int]:
    """Return (avg_ms, avg_bytes, n_sampled)."""
    picks = random.sample(all_combos, min(SAMPLE_K, len(all_combos)))
    times, sizes = [], []
    for p in picks:
        params = {**fixed}
        for k, v in p.items():
            if v is None:
                continue
            if k == "region":  # quick-deals: region → sido/sigungu 판별
                params["sigungu" if len(str(v)) > 2 else "sido"] = v
            else:
                params[k] = v
        qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        t0 = time.perf_counter()
        try:
            r = client.get(f"{path}?{qs}")
        except Exception as e:
            print(f"  !! {path}?{qs} -> EXC {type(e).__name__}: {e}", flush=True)
            continue
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            times.append(ms)
            sizes.append(len(r.content))
        else:
            print(f"  !! {path}?{qs} -> {r.status_code}", flush=True)
    return (sum(times) / len(times) if times else 0,
            sum(sizes) / len(sizes) if sizes else 0, len(times))


print(f"\n{'family':24s} {'combos':>7s} {'avg_ms':>8s} {'avg_KB':>7s} "
      f"{'est_hours':>9s} {'est_MB':>8s}", flush=True)
total_n = total_sec = total_mb = 0.0
results = []
for name, (path, cs, fixed) in FAMILIES.items():
    t0 = time.perf_counter()
    avg_ms, avg_b, k = sample_run(path, cs, fixed)
    n = len(cs)
    est_sec = n * avg_ms / 1000
    est_mb = n * avg_b / 1024 / 1024
    total_n += n; total_sec += est_sec; total_mb += est_mb
    results.append((name, n, avg_ms, avg_b, est_sec, est_mb))
    print(f"{name:24s} {n:7d} {avg_ms:8.0f} {avg_b/1024:7.1f} "
          f"{est_sec/3600:9.2f} {est_mb:8.1f}   (sampled {k}, "
          f"{time.perf_counter()-t0:.0f}s)", flush=True)

print(f"\n[stats 전체조합] targets={total_n:,.0f}  "
      f"time={total_sec/3600:.1f}h  size={total_mb:.0f}MB", flush=True)

# ── +complex: 단지별 3개 엔드포인트 ────────────────────────
cx_times, cx_sizes = [], []
for cno in complex_ids:
    for ep in (f"/complex/{cno}/areas", f"/complex/{cno}/realtors",
               f"/complex/{cno}/transactions"):
        t0 = time.perf_counter()
        r = client.get(ep)
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            cx_times.append(ms); cx_sizes.append(len(r.content))
cx_n = n_complex * 3
cx_sec = cx_n * (sum(cx_times) / len(cx_times)) / 1000
cx_mb = cx_n * (sum(cx_sizes) / len(cx_sizes)) / 1024 / 1024
print(f"[+complex] targets={cx_n:,}  avg={sum(cx_times)/len(cx_times):.0f}ms  "
      f"time={cx_sec/3600:.1f}h  size={cx_mb:.0f}MB", flush=True)

# ── +realtor ───────────────────────────────────────────────
rl_times, rl_sizes = [], []
for rid in realtor_ids:
    t0 = time.perf_counter()
    r = client.get(f"/realtor/{rid}")
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code == 200:
        rl_times.append(ms); rl_sizes.append(len(r.content))
rl_sec = n_realtor * (sum(rl_times) / len(rl_times)) / 1000
rl_mb = n_realtor * (sum(rl_sizes) / len(rl_sizes)) / 1024 / 1024
print(f"[+realtor] targets={n_realtor:,}  avg={sum(rl_times)/len(rl_times):.0f}ms  "
      f"time={rl_sec/3600:.1f}h  size={rl_mb:.0f}MB", flush=True)

print(f"\n[총합] targets={total_n + cx_n + n_realtor:,.0f}  "
      f"time={(total_sec + cx_sec + rl_sec)/3600:.1f}h  "
      f"size={total_mb + cx_mb + rl_mb:.0f}MB", flush=True)
print("(현재 daily 캐시: 1,826개 / 6.4MB / ~80분)", flush=True)
