"""Pre-compute and cache all stat endpoint responses to local cache.sqlite.

Runs every endpoint function directly (no HTTP overhead), stores the JSON
response keyed by `(path, sorted query_string)`. The FastAPI server's
prebuilt-cache middleware then serves these instantly.

Why this approach:
- Most stat endpoints are slow because they aggregate 8GB of SQLite live.
- The parameter space is finite (~17 sidos × ~250 sigungus, ~handful of trade
  types / area classes), so caching is practical.
- Free-text search (`/stats/realtors/search`, POST `/q`) is intentionally not
  cached — the live endpoints still handle those.

Coverage (this pass — easy to extend):
- Overview cards / charts (stats/recent-tx, top-complexes, listing-trend,
  top-listings, avg-price-trend per region)
- Changes page (changes/summary, changes/region-rank, changes/movers per region)
- Quick deals (per sido × trade_type × pyeong combos, defaults only)
- TxStats / TxStatsMore (each endpoint with default + trade variants)
- Region pulse (national + per-sido drill-downs)

Endpoints intentionally skipped:
- /complex/{complex_no}/* — 26k complexes; per-page is fast enough already
- /realtor/{realtor_id} — millions; first hit slow but in-memory cache helps
- /q, /health — POST or trivial
"""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# import the FastAPI app and its sidos/sigungus list helpers
from scripts.local_api import app, _CACHE_DB_PATH, persist_ranks  # noqa: E402

CACHE_DB = _CACHE_DB_PATH


def init_cache_db(wipe: bool = True) -> None:
    """Create the cache table. wipe=True 면 기존 행을 비운다(전량 재빌드).
    wipe=False 면 기존 캐시 위에 INSERT OR REPLACE 로 덧쌓는다 — 다운타임 없이
    default 캐시 위에 전체조합을 점진 추가할 때 사용.
    local_api.py 가 동시에 읽고 있어 파일 unlink 는 Windows sharing violation 이라
    truncate 방식.
    """
    with sqlite3.connect(CACHE_DB) as c:
        # WAL 모드: 빌드(쓰기)와 local_api 서버(읽기)가 서로 안 막힘. 기본 rollback
        # journal 은 쓰기 트랜잭션이 읽기를 블록해서, 빌드 중 페이지가 수 초씩 느려짐.
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_cache (
              cache_key   TEXT PRIMARY KEY,
              path        TEXT NOT NULL,
              query       TEXT NOT NULL,
              response    BLOB NOT NULL,
              size_bytes  INTEGER NOT NULL,
              elapsed_ms  REAL NOT NULL,
              computed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_api_cache_path ON api_cache(path);
            """
        )
        if wipe:
            c.execute("DELETE FROM api_cache")
    if wipe:
        # DELETE 만 하면 freed pages 가 freelist 에 쌓여 파일이 비대해짐. VACUUM 으로 반환.
        # local_api.py 가 동시에 잡고 있으면 SQLITE_BUSY 날 수 있어 best-effort.
        try:
            sqlite3.connect(CACHE_DB).execute("VACUUM")
        except sqlite3.OperationalError:
            pass


def make_key(path: str, params: dict | None) -> tuple[str, str]:
    """Return (cache_key, query_string)."""
    if not params:
        return path, ""
    items = sorted(params.items(), key=lambda kv: kv[0])
    qs = "&".join(f"{k}={v}" for k, v in items if v is not None and v != "")
    if not qs:
        return path, ""
    return f"{path}?{qs}", qs


def _list_sidos(client: TestClient) -> list[str]:
    r = client.get("/stats/changes/sido-list")
    if r.status_code != 200:
        return []
    return [it["code"] for it in r.json().get("items", [])]


def _list_sigungus(client: TestClient, sido: str) -> list[str]:
    r = client.get(f"/stats/sigungu-list?sido={sido}")
    if r.status_code != 200:
        return []
    return [it["code"] for it in r.json().get("items", [])]


def cache_one(
    client: TestClient,
    cur: sqlite3.Cursor,
    path: str,
    params: dict | None = None,
) -> tuple[bool, float, int]:
    """Hit the endpoint via TestClient, store JSON. Returns (ok, ms, bytes)."""
    key, qs = make_key(path, params)
    url = path + (("?" + qs) if qs else "")
    t0 = time.perf_counter()
    try:
        r = client.get(url)
    except Exception as e:
        print(f"  ERR  {url}  -- {e}", file=sys.stderr)
        return False, 0.0, 0
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if r.status_code != 200:
        print(f"  SKIP {url}  status={r.status_code}", file=sys.stderr)
        return False, elapsed_ms, 0
    body = r.content
    cur.execute(
        "INSERT OR REPLACE INTO api_cache "
        "(cache_key, path, query, response, size_bytes, elapsed_ms) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key, path, qs, body, len(body), elapsed_ms),
    )
    return True, elapsed_ms, len(body)


def quick_deals_sgg_targets(sidos: list[str], sigungus: list[str]) -> list[tuple[str, dict]]:
    """급매 와이드 캐시 타깃 — 지역(전국+시도+시군구) × 매매/전세 × 기간(90/180).

    콜드 디스크에서 지역당 30~76s 걸리는 유일한 페이지 구멍(2026-06 전수 콜드 감사).
    키는 '와이드' 한 종류뿐: min_samples=3·할인3%·전평형·limit=500.
    평형(area1_m2)·할인율(discount_min)·표본수(n_real)는 응답 필드에 있으므로
    페이지(QuickDeals.tsx)와 AI(find_quick_deals)가 클라이언트/후필터로 좁힌다.
    → 필터 조합 폭발 없이 키 1,092개로 전 화면 커버. days 만 집계가 달라 키 분리.
    """
    out: list[tuple[str, dict]] = []
    regions: list[dict] = [{}]                       # 전국
    regions += [{"sido": s} for s in sidos]          # 시도 (10자리 cortar)
    regions += [{"sigungu": sg} for sg in sigungus]  # 시군구
    for reg in regions:
        for tt in ("A1", "B1"):
            for d in (90, 180):
                out.append(("/stats/quick-deals", {
                    "days": d, "min_samples": 3, "trade_type": tt,
                    "min_discount": 0.03, "min_listings": 1, "limit": 500,
                    **reg}))
    return out


def recovery_targets(sidos: list[str]) -> list[tuple[str, dict]]:
    """전고점 대비 회복률(tx-recovery) 캐시 — 전국 + 시도 × 저평가/회복순.
    콜드 전국 21s. 시군구는 지역스코핑으로 빨라 라이브 폴백."""
    out: list[tuple[str, dict]] = []
    for order in ("asc", "desc"):
        out.append(("/stats/tx-recovery", {"order": order, "limit": 200}))
        for s in sidos:
            out.append(("/stats/tx-recovery", {"order": order, "limit": 200, "sido": s}))
    return out


def cancelled_summary_targets(sidos: list[str]) -> list[tuple[str, dict]]:
    """취소거래 종합표 캐시 — CancelledTx.tsx 가 보내는 전 조합.
    months=0(전체기간)이 이중신고 EXISTS 풀스캔으로 콜드 ~18s (로그 실측).
    asset(3) × months(1/3/6/0) × (전국+시도17) = 216키, 빌드 ~1분."""
    out: list[tuple[str, dict]] = []
    for asset in ("apt", "offi", "all"):
        for m in (1, 3, 6, 0):
            base = {"asset": asset, "months": m}
            out.append(("/stats/cancelled-summary", dict(base)))
            for s in sidos:
                out.append(("/stats/cancelled-summary", {**base, "sido": s}))
    return out


def ai_rank_targets() -> list[tuple[str, dict]]:
    """AI 도구(rank_complexes·find_record_high)가 보내는 캐논 파라미터 그대로 캐시.

    AI 는 파이썬 함수를 직접 호출해 HTTP 캐시를 우회하므로, ai_agent._rank_items
    가 같은 키로 cache_get 선조회한다. 풀은 항상 limit=500(건수 축소는 AI 쪽
    슬라이스). 콜드에서 매물적체 31s·저가거래 22s·신고가 21s 가 0초대로.
    """
    out: list[tuple[str, dict]] = []
    ACS = ["all", "10s", "20s", "30s", "40s"]   # rank_complexes 의 pyeong 매핑값
    for ac in ACS:
        for o in ("asc", "desc"):
            out.append(("/stats/tx-gap-rank", {"asset": "apt", "area_class": ac, "order": o, "limit": 500}))
            out.append(("/stats/tx-jeonse-rate", {"asset": "apt", "area_class": ac, "order": o, "limit": 500}))
            out.append(("/stats/tx-pyeong-price", {"asset": "apt", "area_class": ac, "order": o, "limit": 500}))
        out.append(("/stats/tx-top-price", {"trade": "A1", "asset": "apt", "area_class": ac, "limit": 500}))
        out.append(("/stats/tx-top-volume", {"trade": "A1", "asset": "apt", "area_class": ac, "limit": 500}))
        out.append(("/stats/tx-low-price", {"asset": "apt", "area_class": ac, "limit": 500}))
        out.append(("/stats/tx-turnover", {"trade": "A1", "asset": "apt", "area_class": ac, "limit": 500}))
        out.append(("/stats/tx-yield", {"asset": "apt", "area_class": ac, "limit": 500}))
        out.append(("/stats/tx-asking-vs-real", {"area_class": ac, "order": "desc", "limit": 500}))
        # tx-inventory-pressure(매물적체)는 페이지·AI에서 제거됨 — 캐시 빌드도 중단(가장 느린 31s 절약)
    # 신고가: months 1/3/6/12 → days 30/90/180/360 × 매매/전세
    for d in (30, 90, 180, 360):
        for tt in ("A1", "B1"):
            out.append(("/stats/tx-record-high",
                        {"days": d, "trade": tt, "asset": "apt", "order": "recent", "limit": 1000}))
    return out


def region_drill_targets(sidos: list[str], sigungus: list[str]) -> list[tuple[str, dict]]:
    """페이지 지역 드릴다운 캐시 보강.
    - avg-price-trend 시군구: Overview 드릴다운, 콜드 23.9s (default-only 는 시도까지만)
    - changes/summary 시군구: 콜드 5.1s
    - changes/region-rank 전국 필터그리드: 페이지에서 level/trade/평형 바꿀 때 콜드 3.6s
    - changes/movers trade 변형: 콜드 7.8s
    """
    out: list[tuple[str, dict]] = []
    for sg in sigungus:
        out.append(("/stats/avg-price-trend", {"days": 60, "sigungu": sg}))
        out.append(("/stats/changes/summary", {"sigungu": sg}))
    AREA = ["all", "10s", "20s", "30s", "40s", "over50"]
    for level in ("sido", "sigungu", "dong"):
        for tr in ("A1", "B1", "B2"):
            for ac in AREA:
                out.append(("/stats/changes/region-rank",
                            {"level": level, "trade": tr, "area_class": ac,
                             "min_listings": 30, "limit": 30}))
    for tr in ("A1", "B1", "B2"):
        base = {"trade": tr, "min_listings": 2, "limit": 5}
        out.append(("/stats/changes/movers", dict(base)))
        for s in sidos:
            out.append(("/stats/changes/movers", {**base, "sido": s}))
    return out


def build_all(limit: int = 0, scope: str = "stats", workers: int = 8,
              default_only: bool = False, wipe: bool = True,
              quick_deals_sgg: bool = False) -> None:
    """scope: stats | +complex | +realtor | all.  workers: 병렬 스레드 수.
    default_only: 각 페이지·탭의 '기본 화면' 호출만 캐시(~60개). 전체 필터조합은
    무거운 조합이 3,015개라 ~4~6h 걸리므로, 느린 페이지 로드만 빠르게 잡는 실용 모드.
    wipe=False: 기존 캐시를 안 지우고 덧쌓음 — default 캐시 위에 전체조합을 다운타임
    없이 점진 추가할 때."""
    init_cache_db(wipe=wipe)

    if not quick_deals_sgg:
        # 중개사 랭킹 영속 파일 갱신 (수집으로 listings 가 바뀌었으니 새로 빌드).
        # 서버는 realtor 페이지에서 이 파일을 즉시 로드 → 414만행 라이브 GROUP BY(~112s) 회피.
        print("persisting realtor ranks...", flush=True)
        try:
            persist_ranks()
        except Exception as e:
            print(f"  rank persist failed: {e}", file=sys.stderr, flush=True)
    client = TestClient(app)

    # ── Bootstrap: sidos / sigungus lists (used by other endpoints' loops) ──
    sidos = _list_sidos(client)
    print(f"sidos: {len(sidos)}")
    sigungus_by_sido = {s: _list_sigungus(client, s) for s in sidos}
    total_sigungus = sum(len(v) for v in sigungus_by_sido.values())
    print(f"sigungus: {total_sigungus}")

    AREA = ["all", "10s", "20s", "30s", "40s", "over50"]
    PERIOD_3 = [180, 365, 730]

    def prod(*spec):
        """spec: (key, [values]) → 모든 조합 dict 리스트. 값 None 이면 그 키 생략."""
        out = [{}]
        for key, vals in spec:
            nxt = []
            for d in out:
                for v in vals:
                    e = dict(d)
                    if v is not None:
                        e[key] = v
                    nxt.append(e)
            out = nxt
        return out

    targets: list[tuple[str, dict | None]] = []

    # ── 캐시 키 = 프런트가 실제 보내는 쿼리와 동일해야 HIT 한다 ─────────────
    #    (맨 경로로 캐시하면 프런트의 ?days=.. 와 키가 어긋나 미스 → 캐시 무용)

    # Overview 카드 + 드롭다운 목록 (고정 파라미터)
    targets += [
        ("/stats/recent-tx", {"days": 7}),
        ("/stats/top-complexes", {"days": 7}),
        ("/stats/top-listings", {"limit": 5}),
        ("/stats/listing-trend", {"days": 60}),
        ("/stats/changes/sido-list", None),
        ("/stats/sigungu-list", None),
        ("/stats/realtors/national", {"limit": 20}),
        ("/stats/realtors/by-sido", {"limit": 10}),
    ]
    for s in sidos:
        targets.append(("/stats/sigungu-list", {"sido": s}))

    # avg-price-trend(days=60) · changes/summary : 전국 + 시도 + 시군구, asset(apt/offi)별.
    # ★asset 필수 — 프런트(Changes.tsx)가 항상 asset=apt/offi 를 붙여 보내므로, asset
    #   없이 캐싱하면 키가 어긋나 100% 미스(콜드 8~11s)였다.
    for ep, base in (("/stats/avg-price-trend", {"days": 60}),
                     ("/stats/changes/summary", {})):
        for asset in ("apt", "offi"):
            b = {**base, "asset": asset}
            targets.append((ep, dict(b)))
            for s in sidos:
                targets.append((ep, {**b, "sido": s}))
                for sg in sigungus_by_sido[s]:
                    targets.append((ep, {**b, "sigungu": sg}))

    # changes/region-rank : level × trade × area × (전국+시도)
    for level in ["sido", "sigungu", "dong"]:
        for tr in ["A1", "B1", "B2"]:
            for ac in AREA:
                base = {"level": level, "trade": tr, "area_class": ac,
                        "min_listings": 30, "limit": 30}
                targets.append(("/stats/changes/region-rank", base))
                for s in sidos:
                    targets.append(("/stats/changes/region-rank", {**base, "sido": s}))

    # changes/movers : trade × (전국+시도)
    for tr in ["A1", "B1", "B2"]:
        base = {"trade": tr, "min_listings": 2, "limit": 5}
        targets.append(("/stats/changes/movers", base))
        for s in sidos:
            targets.append(("/stats/changes/movers", {**base, "sido": s}))

    # changes/events : trade
    for tr in ["A1", "B1", "B2"]:
        targets.append(("/stats/changes/events", {"trade": tr}))

    # quick-deals : '전국'만 캐시. 시도·시군구는 지역 스코핑 최적화로 라이브 <3초라
    # (강남 95s→1.5s 등) 캐시 불필요. 전국만 작업셋이 140만건이라 콜드 43초 → 캐시 필요.
    #   = trade(2) × pyeong(5) × days(2) × 할인율(2) = 40 (지역 차원 제거).
    for tt in ["A1", "B1"]:
        for py in ["", "10", "20", "30", "40"]:
            for d in (90, 180):
                for md in (0.05, 0.1):
                    base = {"days": d, "min_samples": 5, "trade_type": tt,
                            "min_discount": md, "limit": 200}
                    if py:
                        base["pyeong"] = py
                    targets.append(("/stats/quick-deals", base))   # 전국만

    # ── 빠른 tx 패밀리(<3s): 프런트 기본 호출 1개만 캐시 ──
    targets += [
        ("/stats/tx-top-price", {"days": 30, "trade": "A1", "asset": "all",
                                 "dealing": "all", "area_class": "all", "limit": 100}),
        ("/stats/tx-top-volume", {"days": 30, "trade": "A1", "asset": "all",
                                  "dealing": "all", "area_class": "all", "limit": 100}),
        ("/stats/tx-low-price", {"days": 180, "asset": "all", "discount": 0.2,
                                 "area_class": "all", "min_samples": 3, "limit": 300}),
    ]
    # NOTE: tx-gap-rank/jeonse-rate/price-change/yield/turnover/pyeong-price 6종은
    # tx_area_rollup 사전집계로 전환돼 콜드 0.3~0.8s → 캐시 불필요(라이브로 충분).
    # (build_tx_rollups.py 의 tx_area_rollup, local_api 의 _area_rollup_ready 참조)

    # ── 아직 라이브인 tx 패밀리: 프런트 기본 조합 위주로만 캐시 ──
    for p in prod(("asset", ["apt", "offi", "all"])):
        targets.append(("/stats/tx-region-pulse", p))
    # NOTE: tx-record-high 도 tx_record_rollup 사전집계로 전환돼 콜드 0.1~1.2s → 캐시 불필요.
    # tx-asking-vs-real(호가 vs 실거래)만 아직 라이브(~8s). 동시 콜드쿼리 디스크 쓰래싱
    # 방지 위해 프런트 기본 조합 몇 개만 캐시(나머지는 첫 로드 시 라이브).
    for p in prod(("days", [90, 180, 365]), ("order", ["desc", "asc"])):
        targets.append(("/stats/tx-asking-vs-real",
                        {**p, "area_class": "all", "min_samples": 3, "limit": 200}))

    # 단지별 페이지 (complex_no 단위)
    if scope in ("+complex", "all"):
        with sqlite3.connect(settings.local_db_path) as ndb:
            complex_nos = [r[0] for r in ndb.execute(
                "SELECT complex_no FROM complexes ORDER BY complex_no"
            ).fetchall()]
        print(f"complexes: {len(complex_nos)}")
        for cno in complex_nos:
            for ep in [
                f"/complex/{cno}/areas",
                f"/complex/{cno}/realtors",
                f"/complex/{cno}/transactions",
            ]:
                targets.append((ep, None))

    # 중개사별 페이지 (realtor_id 단위)
    if scope in ("+realtor", "all"):
        with sqlite3.connect(settings.local_db_path) as ndb:
            realtor_ids = [r[0] for r in ndb.execute(
                "SELECT DISTINCT realtor_id FROM listings_current "
                "WHERE realtor_id IS NOT NULL"
            ).fetchall()]
        print(f"realtors: {len(realtor_ids)}")
        for rid in realtor_ids:
            targets.append((f"/realtor/{rid}", None))

    if limit and limit < len(targets):
        targets = targets[:limit]
    # ── default-only: 각 페이지 기본 화면만 (느린 로드만 빠르게 잡는 실용 모드) ──
    if default_only:
        D = [
            ("/stats/recent-tx", {"days": 7}),
            ("/stats/freshness", None),
            ("/stats/region-compare", {"days": 30, "trade": "A1"}),
            ("/stats/region-compare", {"days": 30, "trade": "B1"}),
            # TODAY 탭 (오늘의실거래/오늘의매물)
            *[("/stats/today-deals", {"trade": tr, "min_discount": 0.05, "limit": 24, "sort": so})
              for tr in ("A1", "B1", "B2") for so in ("price", "discount")],
            ("/stats/today-listings-stats", None),
            # 오늘의 주요 신고가 — 매매/전세/월세 × 가격순/증가율순 (페이지 파라미터와 동일)
            *[("/stats/tx-record-high", {"days": 7, "trade": tr, "asset": "apt",
               "order": od, "min_prior": 1, "limit": 12})
              for tr in ("A1", "B1", "B2") for od in ("price", "premium")],
            ("/stats/top-complexes", {"days": 7}),
            ("/stats/top-listings", {"limit": 5}),
            ("/stats/listing-trend", {"days": 60}),
            ("/stats/avg-price-trend", {"days": 60, "asset": "apt"}),
            ("/stats/changes/summary", {"asset": "apt"}),
            ("/stats/changes/sido-list", None),
            ("/stats/sigungu-list", None),
            ("/stats/realtors/national", {"limit": 20}),
            ("/stats/realtors/by-sido", {"limit": 10}),
            ("/stats/changes/region-rank", {"level": "sido", "trade": "A1",
                "area_class": "all", "min_listings": 30, "limit": 30}),
            ("/stats/changes/movers", {"trade": "A1", "min_listings": 2, "limit": 5}),
            ("/stats/changes/events", {"trade": "A1"}),
            ("/stats/quick-deals", {"days": 90, "min_samples": 5, "trade_type": "A1",
                "min_discount": 0.05, "limit": 200}),
            ("/stats/tx-top-price", {"days": 30, "trade": "A1", "asset": "all",
                "dealing": "all", "area_class": "all", "limit": 100}),
            ("/stats/tx-top-volume", {"days": 30, "trade": "A1", "asset": "all",
                "dealing": "all", "area_class": "all", "limit": 100}),
            ("/stats/tx-low-price", {"days": 180, "asset": "all", "discount": 0.2,
                "area_class": "all", "min_samples": 3, "limit": 300}),
            ("/stats/tx-gap-rank", {"days": 365, "asset": "apt", "order": "asc",
                "area_class": "all", "min_samples": 3, "limit": 200}),
            ("/stats/tx-jeonse-rate", {"days": 365, "asset": "apt", "order": "desc",
                "area_class": "all", "min_samples": 3, "limit": 200}),
            ("/stats/tx-price-change", {"window_days": 90, "asset": "apt", "order": "desc",
                "area_class": "all", "min_samples": 3, "limit": 200}),
            ("/stats/tx-region-pulse", {"asset": "apt"}),
            ("/stats/tx-record-high", {"days": 90, "trade": "A1", "asset": "all",
                "area_class": "all", "max_gap_months": 0, "order": "premium",
                "min_prior": 1, "limit": 300}),
            ("/stats/tx-yield", {"days": 365, "asset": "apt", "area_class": "all",
                "min_samples": 3, "limit": 200}),
            ("/stats/tx-asking-vs-real", {"days": 90, "order": "desc",
                "area_class": "all", "min_samples": 3, "limit": 200}),
            ("/stats/tx-turnover", {"days": 365, "trade": "A1", "asset": "apt",
                "area_class": "all", "min_households": 50, "limit": 200}),
            ("/stats/tx-pyeong-price", {"days": 365, "asset": "apt", "order": "desc",
                "area_class": "all", "min_samples": 3, "limit": 200}),
        ]
        # 무거운 tx-stats 엔드포인트의 area_class×asset 조합도 캐시 — 미캐시 시 라이브가
        # 3~12s 라서 필터를 바꾸면 느려진다. 프론트와 동일 파라미터로 캐시히트되게.
        _ACS = ("all", "10s", "20s", "30s", "40s")
        for ac in _ACS:
            for a in ("apt", "offi", "all"):
                D.append(("/stats/tx-low-price", {"days": 180, "asset": a, "discount": 0.2,
                    "area_class": ac, "min_samples": 3, "limit": 300}))
                D.append(("/stats/tx-top-price", {"days": 30, "trade": "A1", "asset": a,
                    "dealing": "all", "area_class": ac, "limit": 100}))
                D.append(("/stats/tx-yield", {"days": 365, "asset": a, "area_class": ac,
                    "min_samples": 3, "limit": 200}))
                for o in ("asc", "desc"):
                    D.append(("/stats/tx-gap-rank", {"days": 365, "asset": a, "order": o,
                        "area_class": ac, "min_samples": 3, "limit": 200}))
            # tx-asking-vs-real 은 asset 인자 없음(area_class×order 만)
            for o in ("asc", "desc"):
                D.append(("/stats/tx-asking-vs-real", {"days": 90, "order": o,
                    "area_class": ac, "min_samples": 3, "limit": 200}))
        # tx-recovery(전고점 회복률): 저평가/회복순 기본화면
        for o in ("asc", "desc"):
            D.append(("/stats/tx-recovery", {"order": o, "limit": 200}))
        # 시도 선택 첫 화면 (national + 시도별 요약/추이)
        for s in sidos:
            D.append(("/stats/changes/summary", {"sido": s, "asset": "apt"}))
            D.append(("/stats/avg-price-trend", {"days": 60, "sido": s, "asset": "apt"}))
        targets = D

    # ── 지역/AI 보강 캐시 (단독 모드: 이것만 빌드) ──
    # 급매 와이드 + 취소 종합표 + AI 랭킹 캐논 + 지역 드릴다운
    all_sgg = [sg for s in sidos for sg in sigungus_by_sido[s]]
    extras = (quick_deals_sgg_targets(sidos, all_sgg)
              + cancelled_summary_targets(sidos)
              + ai_rank_targets()
              + recovery_targets(sidos)
              + region_drill_targets(sidos, all_sgg))
    if quick_deals_sgg:
        targets = extras
    elif not default_only:
        targets += extras

    # ── 병렬 실행 ─────────────────────────────────────────
    # sqlite 는 쿼리 실행 중 GIL 을 풀어 스레드로 진짜 병렬이 된다. 엔드포인트
    # 함수를 직접 호출(HTTP/미들웨어 우회)해 결과를 JSON 직렬화 후 캐시에 쓴다.
    # 무거운 집계의 디스크 읽기가 병렬에서 분할상환돼 순차 대비 크게 단축됨.
    # 캐시 쓰기(INSERT)만 락으로 직렬화한다.
    func_by_path = {r.path: r.endpoint for r in app.routes
                    if getattr(r, "endpoint", None) is not None}
    # 주의: realtors/* 가 의존하는 rank 테이블은 여기서 미리 빌드하지 않는다.
    # 1.4GB RAM 에서 rank 빌드가 디스크 바운드로 수 분 걸려 '전체 빌드 시작'을
    # 가로막던 문제 때문. realtors 타깃 2개가 워커에서 지연 빌드하고 나머지
    # 워커는 그동안 다른 타깃을 계속 처리한다.

    print(f"total targets: {len(targets)}  workers={workers}", flush=True)
    t_start = time.perf_counter()
    write_conn = sqlite3.connect(CACHE_DB, check_same_thread=False)
    lock = threading.Lock()
    cnt = {"ok": 0, "err": 0, "bytes": 0, "done": 0}
    last_log = [t_start]

    def work(item):
        path, params = item
        func = func_by_path.get(path)
        if func is None:
            return  # 엔티티(+complex/+realtor) 등 직접호출 불가 path 는 skip
        try:
            result = func(**dict(params or {}))
        except HTTPException:
            with lock:
                cnt["err"] += 1; cnt["done"] += 1
            return
        except Exception as e:
            print(f"  ERR {path} {params} -- {e}", file=sys.stderr, flush=True)
            with lock:
                cnt["err"] += 1; cnt["done"] += 1
            return
        key, qs = make_key(path, params)
        body = json.dumps(jsonable_encoder(result), ensure_ascii=False).encode("utf-8")
        with lock:
            write_conn.execute(
                "INSERT OR REPLACE INTO api_cache "
                "(cache_key, path, query, response, size_bytes, elapsed_ms) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (key, path, qs, body, len(body)),
            )
            cnt["ok"] += 1; cnt["bytes"] += len(body); cnt["done"] += 1
            # 주기적 커밋 — 중단돼도 여기까지 캐시가 살아남고(초반 Overview/changes
            # 부터 바로 HIT), 기존 캐시를 통째로 날리는 일이 없게 한다.
            if cnt["done"] % 200 == 0:
                write_conn.commit()
            now = time.perf_counter()
            if now - last_log[0] >= 5.0:
                d = cnt["done"]; rate = d / (now - t_start)
                eta = (len(targets) - d) / rate if rate > 0 else 0
                print(f"  {d}/{len(targets)}  ok={cnt['ok']} err={cnt['err']}  "
                      f"{cnt['bytes']/1048576:.1f}MB  ETA {eta:.0f}s", flush=True)
                last_log[0] = now

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, targets))
    write_conn.commit()
    write_conn.close()

    elapsed = time.perf_counter() - t_start
    print(
        f"\nDONE  {cnt['ok']} ok / {cnt['err']} err   "
        f"size {cnt['bytes']/1048576:.1f}MB   "
        f"wall clock: {elapsed:.0f}s  ({workers} workers)"
    )
    print(f"cache: {CACHE_DB}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap target count for smoke testing (0 = full)")
    ap.add_argument("--scope", default="stats",
                    choices=["stats", "+complex", "+realtor", "all"],
                    help="stats=기본 / +complex=단지 페이지 포함 / "
                         "+realtor=중개사 페이지 포함 / all=모두")
    ap.add_argument("--workers", type=int, default=8,
                    help="병렬 스레드 수 (기본 8)")
    ap.add_argument("--default-only", action="store_true",
                    help="각 페이지 기본 화면만 캐시(~60개, 빠름). 전체조합 생략.")
    ap.add_argument("--no-wipe", action="store_true",
                    help="기존 캐시를 안 지우고 덧쌓음(다운타임 없이 점진 추가).")
    ap.add_argument("--quick-deals-sgg", action="store_true",
                    help="시군구별 급매만 빌드(--no-wipe 와 함께 점진 추가 권장).")
    args = ap.parse_args()
    build_all(limit=args.limit, scope=args.scope, workers=args.workers,
              default_only=args.default_only, wipe=not args.no_wipe,
              quick_deals_sgg=args.quick_deals_sgg)
