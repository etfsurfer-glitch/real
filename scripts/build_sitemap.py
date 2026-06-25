"""웹서비스 엔드포인트 경우의 수 사이트맵 HTML 생성.

프런트 필터 UI 가 만들 수 있는 모든 파라미터 조합(= '경우의 수')을 엔드포인트별로
정리해 사람이 한눈에 보도록 단일 HTML 로 출력한다. 조합수/응답시간/용량은
scripts/estimate_full_cache.py 실측값(2026-06-08) 기준.

  python scripts/build_sitemap.py   →  sitemap.html
"""
from __future__ import annotations

import html
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sitemap.html"

# 라이브 측정 대상 서버 + 엔티티 엔드포인트용 샘플 id
# localhost 대신 127.0.0.1 — Windows 에서 urllib 이 localhost 를 IPv6(::1) 로 먼저
# 시도하다 ~2초씩 지연됨(서버는 IPv4 listen). 127.0.0.1 직접 지정으로 회피.
API_BASE = "http://127.0.0.1:8000"
SAMPLE_COMPLEX = "136343"
SAMPLE_REALTOR = "toptop71200"


# 프런트 각 페이지가 '초기 로드 시' 실제로 보내는 쿼리 (default state 기준).
# build_api_cache 는 tx-* 를 파라미터 없는 맨 경로로 캐시했지만 프런트는 명시적
# 기본 파라미터를 붙여 보내 캐시 키가 어긋난다 → 실제 페이지는 캐시 미스. 이 쿼리로
# 측정해야 '실제 페이지 호출 소요시간'이 나온다.
PROBE_QUERY = {
    "/stats/recent-tx": "?days=7",
    "/stats/top-complexes": "?days=7",
    "/stats/top-listings": "?limit=5",
    "/stats/listing-trend": "?days=60",
    "/stats/avg-price-trend": "?days=60",
    "/stats/quick-deals": "?days=90&min_samples=5&min_discount=0.05&trade_type=A1&limit=200",
    "/stats/changes/summary": "",
    "/stats/changes/region-rank": "?level=sido&trade=A1&area_class=all&min_listings=30&limit=30",
    "/stats/changes/movers": "?trade=A1&min_listings=2&limit=5",
    "/stats/changes/events": "?trade=A1",
    "/stats/changes/sido-list": "",
    "/stats/sigungu-list": "",
    "/stats/tx-region-pulse": "?asset=apt",
    "/stats/tx-top-price": "?days=30&trade=A1&asset=all&dealing=all&area_class=all&limit=100",
    "/stats/tx-record-high": "?days=90&trade=A1&asset=all&area_class=all&max_gap_months=0&order=premium&min_prior=1&limit=300",
    "/stats/tx-top-volume": "?days=30&trade=A1&asset=all&dealing=all&area_class=all&limit=100",
    "/stats/tx-low-price": "?days=180&asset=all&discount=0.2&area_class=all&min_samples=3&limit=300",
    "/stats/tx-gap-rank": "?days=365&asset=apt&order=asc&area_class=all&min_samples=3&limit=200",
    "/stats/tx-jeonse-rate": "?days=365&asset=apt&order=desc&area_class=all&min_samples=3&limit=200",
    "/stats/tx-price-change": "?window_days=90&asset=apt&order=desc&area_class=all&min_samples=3&limit=200",
    "/stats/tx-asking-vs-real": "?days=90&order=desc&area_class=all&min_samples=3&limit=200",
    "/stats/tx-pyeong-price": "?days=365&asset=apt&order=desc&area_class=all&min_samples=3&limit=200",
    "/stats/tx-turnover": "?days=365&trade=A1&asset=apt&area_class=all&min_households=50&limit=200",
    "/stats/tx-yield": "?days=365&asset=apt&area_class=all&min_samples=3&limit=200",
    "/stats/realtors/national": "?limit=20",
    "/stats/realtors/by-sido": "?limit=10",
    "/stats/realtors/search": "?q=" + urllib.parse.quote("부동산") + "&limit=30",
    "/realtor/{realtor_id}/reviews": "",
    "/realtor/{realtor_id}": "",
    "/complex/{complex_no}/areas": "",
    "/complex/{complex_no}/realtors": "?limit=10",
    "/complex/{complex_no}/transactions": "?months=24",
    "/admin/suspicious-realtors": "?limit=500",
    "/admin/reviews/pending": "",
    "/health": "",
}


def _probe_one(method: str, path: str) -> tuple[float, str] | None:
    """라이브 서버에 실제 호출해 (응답ms, 캐시상태) 측정. GET 만. 3회 중 최소.
    프런트 초기 로드 쿼리(PROBE_QUERY) 사용 → 실제 페이지 호출 시간.
    캐시상태: 'hit'(사전캐시) | 'live'(실시간 계산) | 'err'."""
    if method != "GET":
        return None
    base = path.replace("{complex_no}", SAMPLE_COMPLEX).replace(
        "{realtor_id}", SAMPLE_REALTOR)
    if "{" in base:  # review_id 등 샘플 없는 path param 은 측정 생략
        return None
    url_path = base + PROBE_QUERY.get(path, "")
    best = None
    cache = "err"
    for _ in range(2):
        req = urllib.request.Request(API_BASE + url_path)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                r.read()
                ms = (time.perf_counter() - t0) * 1000
                cache = "hit" if (r.headers.get("X-Cache") == "HIT") else "live"
        except (urllib.error.URLError, TimeoutError):
            return None
        best = ms if best is None else min(best, ms)
    return (best, cache)


# 수동 보정값(probe 가 콜드 타임아웃으로 놓치는 엔드포인트용). 지금은 default-only
# 캐시가 이들의 기본 호출을 모두 커버해 probe 가 빠르게 HIT 하므로 비워둠 → 전부 실측.
MANUAL_MS: dict[str, tuple[float, str]] = {}


def probe_all(catalog) -> dict[tuple[str, str], tuple[float, str]]:
    out: dict[tuple[str, str], tuple[float, str]] = {}
    for _, _, eps in catalog:
        for e in eps:
            key = (e["method"], e["path"])
            if key in out:
                continue
            if e["path"] in MANUAL_MS and e["method"] == "GET":
                out[key] = MANUAL_MS[e["path"]]
                continue
            res = _probe_one(e["method"], e["path"])
            if res is not None:
                out[key] = res
    return out

# 지역 차원
N_SIDO = 17
N_SIGUNGU = 255
REGION_ALL = 1 + N_SIDO + N_SIGUNGU   # 전국+시도+시군구 = 273
REGION_SIDO = 1 + N_SIDO              # 전국+시도 = 18
N_COMPLEX = 64_142
N_REALTOR = 54_104

# estimate_full_cache.py 실측 (combos, avg_ms, MB, hours)
COST = {
    "/stats/tx-top-price": (16296, 23.3, 4.40),
    "/stats/tx-top-volume": (804, 14.8, 0.22),
    "/stats/tx-low-price": (37616, 7.8, 3.01),
    "/stats/tx-gap-rank": (9073, 1.6, 0.18),
    "/stats/tx-jeonse-rate": (824, 1.5, 0.02),
    "/stats/tx-price-change": (486, 0.9, 0.01),
    "/stats/tx-pyeong-price": (1118, 1.3, 0.02),
    "/stats/tx-turnover": (426, 1.3, 0.01),
    "/stats/tx-yield": (9785, 5.2, 1.76),
    "/stats/tx-record-high": (5486, 183.0, 3.29),
    "/stats/tx-asking-vs-real": (116242, 0.3, 1.16),
    "/stats/quick-deals": (140241, 11.7, 1914.30),
    "/stats/tx-region-pulse": (12875, 0.0, 0.01),
}

# 옵션 셋 (프런트 드롭다운과 1:1) — (표시문자열, 개수)
DAYS6 = ("7 · 30 · 90 · 180 · 365 · 전체", 6)
TRADE3 = ("매매 · 전세 · 월세", 3)
ASSET3 = ("전체 · 아파트 · 오피스텔", 3)
ASSET2 = ("아파트 · 오피스텔", 2)
DEAL3 = ("전체 · 중개 · 직거래", 3)
AREA6 = ("전체 · 10 · 20 · 30 · 40 · 50평+", 6)
P3 = ("6개월 · 1년 · 2년", 3)
ORD2 = ("내림차순 · 오름차순", 2)
REGION = (f"전국 · 시도{N_SIDO} · 시군구{N_SIGUNGU}", REGION_ALL)
REGION_S = (f"전국 · 시도{N_SIDO}", REGION_SIDO)

# cache: full=모든조합 / partial=기본+지역등 일부 / default=기본값1개 /
#        entity=엔티티별(미캐시) / dynamic=실시간(캐시불가)
def ep(path, desc, params, cache, cached_n, method="GET", combos=None, note=""):
    if combos is None:
        combos = 1
        for _, _, n in params:
            combos *= n
    return {
        "path": path, "desc": desc, "params": params, "cache": cache,
        "cached_n": cached_n, "method": method, "combos": combos, "note": note,
    }


SECTIONS = [
    ("전체 (Overview)", "/", [
        ep("/stats/recent-tx", "최근 실거래 신고 요약 카드", [], "default", 1),
        ep("/stats/top-complexes", "최근 거래량 상위 단지", [], "default", 1),
        ep("/stats/top-listings", "단지별 매물 수 top-N", [], "default", 1),
        ep("/stats/listing-trend", "일별 매물 수 추이 차트", [], "default", 1),
        ep("/stats/avg-price-trend", "일별 평균 호가 추이 (지역 필터)",
           [("지역", *REGION)], "full", REGION_ALL),
    ]),
    ("급매찾기 (QuickDeals)", "/quick-deals", [
        ep("/stats/quick-deals", "실거래 평균보다 싸게 나온 매물",
           [("거래유형", "매매 · 전세", 2), ("평형", "전체 · 10 · 20 · 30 · 40평↑", 5),
            ("지역", *REGION), ("기간", "90 · 180", 2),
            ("최소할인율", "5% · 10%", 2)],
           "partial", 216,
           note="경우의 수 축소판: 49,140 → 10,920 (평형 40↑통합·기간2·할인율2). 시군구 필터는 건당 무거워 라이브."),
    ]),
    ("가격 변동 (Changes)", "/changes", [
        ep("/stats/changes/summary", "지역별 매물·가격 변동 요약",
           [("지역", *REGION)], "full", REGION_ALL),
        ep("/stats/changes/region-rank", "지역 순위 (시도/시군구/동)",
           [("레벨", "시도 · 시군구 · 동", 3), ("거래", *TRADE3),
            ("면적", *AREA6), ("지역", *REGION_S)], "full", 972),
        ep("/stats/changes/movers", "변동 상위 단지",
           [("거래", *TRADE3), ("지역", *REGION_S)], "full", 54),
        ep("/stats/changes/events", "최근 가격변동 이벤트",
           [("거래", *TRADE3)], "default", 1),
        ep("/stats/changes/sido-list", "시도 드롭다운 목록", [], "full", 1),
        ep("/stats/sigungu-list", "시군구 드롭다운 (시도별)",
           [("시도", f"{N_SIDO}개", N_SIDO)], "full", N_SIDO),
    ]),
    ("실거래 통계 (TxStats)", "/tx-stats", [
        ep("/stats/tx-region-pulse", "시도별 실거래 신고 펄스",
           [("자산", *ASSET3)], "partial", 1, combos=3),
        ep("/stats/tx-top-price", "실거래 최고가 top N",
           [("기간", *DAYS6), ("거래", *TRADE3), ("자산", *ASSET3),
            ("거래방식", *DEAL3), ("면적", *AREA6)], "default", 1),
        ep("/stats/tx-record-high", "단지·타입별 신고가 경신",
           [("신고가시점", "30 · 90 · 180 · 365", 4), ("거래", *TRADE3),
            ("자산", *ASSET3), ("면적", *AREA6),
            ("경신간격", "전체 · 3 · 6 · 12개월", 4),
            ("정렬", "상승률 · 최신", 2)], "default", 1),
        ep("/stats/tx-top-volume", "단지별 거래량 top N",
           [("기간", *DAYS6), ("거래", *TRADE3), ("자산", *ASSET3),
            ("거래방식", *DEAL3), ("면적", *AREA6)], "default", 1),
        ep("/stats/tx-low-price", "평균보다 싼 거래 (증여 의심 등)",
           [("기간", "90 · 180 · 365 · 730", 4), ("할인율", "20 · 30 · 40 · 50%", 4),
            ("자산", *ASSET3), ("면적", *AREA6)], "default", 1),
        ep("/stats/tx-gap-rank", "갭투자 순위 (매매-전세)",
           [("기간", *P3), ("자산", *ASSET2), ("면적", *AREA6), ("정렬", *ORD2)],
           "default", 1),
        ep("/stats/tx-jeonse-rate", "전세율 순위",
           [("기간", *P3), ("자산", *ASSET2), ("면적", *AREA6), ("정렬", *ORD2)],
           "default", 1),
        ep("/stats/tx-price-change", "가격 변동률",
           [("비교기간", "30 · 90 · 180", 3), ("자산", *ASSET2),
            ("면적", *AREA6), ("정렬", *ORD2)], "default", 1),
        ep("/stats/tx-asking-vs-real", "호가 vs 실거래가 갭",
           [("기간", "90 · 180 · 365", 3), ("면적", *AREA6), ("정렬", *ORD2)],
           "default", 1),
        ep("/stats/tx-pyeong-price", "평당가 순위",
           [("기간", *P3), ("자산", *ASSET2), ("면적", *AREA6), ("정렬", *ORD2)],
           "default", 1),
        ep("/stats/tx-turnover", "거래회전율",
           [("기간", *P3), ("거래", "매매 · 전세", 2), ("자산", *ASSET2),
            ("면적", *AREA6)], "default", 1),
        ep("/stats/tx-yield", "월세수익률",
           [("기간", *P3), ("지역", *REGION_S), ("면적", *AREA6), ("자산", *ASSET2)],
           "default", 1),
    ]),
    ("중개사 (Realtor)", "/realtors", [
        ep("/stats/realtors/national", "전국 매물 보유 상위 중개사", [], "default", 1),
        ep("/stats/realtors/by-sido", "시도별 상위 중개사", [], "default", 1),
        ep("/stats/realtors/search", "중개사 검색 (이름·지역)",
           [("검색어", "자유 텍스트", 0)], "dynamic", 0,
           note="자유 텍스트 입력이라 조합 무한 — 캐시 불가, 실시간 처리"),
        ep("/realtor/{realtor_id}", "중개사 상세 페이지",
           [("중개사", f"{N_REALTOR:,}명", N_REALTOR)], "entity", 0,
           note="엔티티별. 현재 미캐시 — 페이지 진입 시 계산(첫 진입만 느림)"),
        ep("/realtor/{realtor_id}/reviews", "중개사 리뷰 목록",
           [("중개사", "사용자 생성", 0)], "dynamic", 0,
           method="GET", note="사용자 생성 데이터 — 캐시 불가"),
    ]),
    ("단지 (ComplexDetail)", "/complex/:no", [
        ep("/complex/{complex_no}/areas", "단지 면적타입 구성",
           [("단지", f"{N_COMPLEX:,}개", N_COMPLEX)], "entity", 0),
        ep("/complex/{complex_no}/realtors", "단지별 매물 보유 중개사",
           [("단지", f"{N_COMPLEX:,}개", N_COMPLEX)], "entity", 0),
        ep("/complex/{complex_no}/transactions", "단지별 실거래 이력",
           [("단지", f"{N_COMPLEX:,}개", N_COMPLEX)], "entity", 0),
    ]),
    ("의심 중개사 (Suspicious)", "/suspicious", [
        ep("/admin/suspicious-realtors", "vworld 미등록 의심 사무소", [], "default", 1),
    ]),
    ("동적 · 쓰기 · 인증 (캐시 안 함)", "—", [
        ep("/q", "범용 테이블 쿼리 (supabase stub)", [], "dynamic", 0, method="POST"),
        ep("/realtor/{realtor_id}/reviews", "일반리뷰 작성 (로그인 필요)", [],
           "dynamic", 0, method="POST"),
        ep("/realtor/{realtor_id}/reviews/verified", "인증리뷰 작성 (로그인 필요)", [],
           "dynamic", 0, method="POST"),
        ep("/admin/reviews/pending", "검수 대기 인증리뷰", [], "dynamic", 0),
        ep("/admin/reviews/{review_id}/document", "검수용 서류 보기", [], "dynamic", 0),
        ep("/admin/reviews/{review_id}/approve", "인증리뷰 승인", [], "dynamic", 0, method="POST"),
        ep("/admin/reviews/{review_id}/reject", "인증리뷰 거부", [], "dynamic", 0, method="POST"),
        ep("/health", "헬스체크", [], "dynamic", 0),
    ]),
]

CACHE_LABEL = {
    "full": ("모든 조합 캐시", "#1d7a3d", "#e6f4ea"),
    "partial": ("일부 캐시", "#8a6d00", "#fdf3d0"),
    "default": ("기본값만 캐시", "#a85b00", "#ffe0ce"),
    "entity": ("엔티티별·미캐시", "#5a4bbf", "#ece9fb"),
    "dynamic": ("실시간·캐시안함", "#5a6473", "#eef0f4"),
}


def combo_color(n: int) -> str:
    if n == 0:
        return "#9aa3b0"
    if n < 100:
        return "#1d7a3d"
    if n < 2000:
        return "#c08a00"
    return "#c0392b"


def fmt_cost(path: str) -> str:
    c = COST.get(path)
    if not c:
        return ""
    avg_ms, mb, hours = c
    t = f"{hours:.2f}h" if hours >= 0.1 else f"{hours*60:.0f}분"
    return (f'<span class="cost">⏱ {avg_ms/1000:.1f}s/건 · 전체 {t} · {mb:.0f}MB</span>')


def esc(s) -> str:
    return html.escape(str(s))


# ── 캐시 후(현재 서빙) 측정: HTTP 프로브 (HIT 면 캐시 응답시간) ──
print("probing live server (cache-after)...", flush=True)
MEAS = probe_all(SECTIONS)
print(f"  measured {len(MEAS)} endpoints", flush=True)

# ── 캐시 전(라이브) 측정: 엔드포인트 함수 직접 호출(캐시 미들웨어 우회) ──
#    각 페이지 초기로드 기본 파라미터(PROBE_QUERY)를 그대로 써서 진짜 쿼리 비용을 잰다.
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(ROOT))
import scripts.local_api as _la  # noqa: E402
_FUNCS = {r.path: r.endpoint for r in _la.app.routes if getattr(r, "endpoint", None)}


def _qs_to_kwargs(qs: str) -> dict:
    kw: dict = {}
    for pair in qs.lstrip("?").split("&"):
        if not pair:
            continue
        k, _, v = pair.partition("=")
        v = urllib.parse.unquote(v)
        try:
            vv: object = int(v)
        except ValueError:
            try:
                vv = float(v)
            except ValueError:
                vv = v
        kw[k] = vv
    return kw


def measure_before(method: str, path: str) -> float | None:
    """함수 직접 호출(캐시 우회) → 라이브 ms. GET·매핑된 함수만."""
    if method != "GET" or "{review_id}" in path:
        return None
    fn = _FUNCS.get(path)
    if fn is None:
        return None
    kwargs = _qs_to_kwargs(PROBE_QUERY.get(path, ""))
    if "{realtor_id}" in path:
        kwargs["realtor_id"] = SAMPLE_REALTOR
    if "{complex_no}" in path:
        kwargs["complex_no"] = SAMPLE_COMPLEX
    t0 = time.perf_counter()
    try:
        fn(**kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"  before ERR {path}: {e}", flush=True)
        return None
    return (time.perf_counter() - t0) * 1000


print("measuring cache-before (live, direct calls)...", flush=True)
BEFORE: dict[str, float] = {}
_seen: set[str] = set()
for _sec, _route, _eps in SECTIONS:
    for _e in _eps:
        if _e["path"] in _seen:
            continue
        _seen.add(_e["path"])
        _b = measure_before(_e["method"], _e["path"])
        if _b is not None:
            BEFORE[_e["path"]] = _b
            print(f"  {_e['path']}: "
                  + (f"{_b/1000:.1f}s" if _b >= 1000 else f"{_b:.0f}ms"), flush=True)

NEEDS_CACHE_MS = 3000.0  # 캐시 전 라이브가 이 이상이면 '캐시 필요'


def _fmt_ms(ms: float) -> str:
    return f"{ms/1000:.1f}s" if ms >= 1000 else f"{ms:.0f}ms"


def timing_badge(method: str, path: str) -> str:
    before = BEFORE.get(path)                       # 캐시 전 (라이브)
    m = MEAS.get((method, path))                    # 캐시 후 (현재 서빙)
    out: list[str] = []
    needs = before is not None and before >= NEEDS_CACHE_MS
    if before is not None:
        bcls = "t-live-slow" if before >= NEEDS_CACHE_MS else (
            "t-live" if before >= 1000 else "t-hit")
        out.append(f'<span class="timing {bcls}">캐시전 {_fmt_ms(before)}</span>')
    if m is not None:
        after_ms, cache = m
        acls = "t-hit" if cache == "hit" else "t-live"
        ico = " ⚡" if cache == "hit" else ""
        out.append(f'<span class="timing {acls}">캐시후 {_fmt_ms(after_ms)}{ico}</span>')
    if needs:
        out.append('<span class="needcache">🔴 캐시 필요</span>')
    return " ".join(out)


# ── 집계 ──────────────────────────────────────────────
stats_combos = sum(
    e["combos"] for _, _, eps in SECTIONS for e in eps
    if e["cache"] in ("full", "partial", "default") and e["method"] == "GET"
)
entity_combos = sum(
    e["combos"] for _, _, eps in SECTIONS for e in eps if e["cache"] == "entity"
)
# 실제 캐시된 항목 수 (api_cache.sqlite 행수) — 옛 가정값 대신 현재 상태 반영.
try:
    import sqlite3 as _sq3
    _cc = _sq3.connect(ROOT / "data" / "api_cache.sqlite")
    cached_now = _cc.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0]
    _cc.close()
except Exception:
    cached_now = sum(e["cached_n"] for _, _, eps in SECTIONS for e in eps)
n_endpoints = sum(len(eps) for _, _, eps in SECTIONS)
full_hours = sum(c[2] for c in COST.values())
# 캐시 전(라이브) ≥3s = '캐시 필요' 엔드포인트 수
needs_cache_n = sum(1 for b in BEFORE.values() if b >= NEEDS_CACHE_MS)
measured_before_n = len(BEFORE)

# ── HTML ──────────────────────────────────────────────
parts: list[str] = []
parts.append(f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>콕집 — 엔드포인트 경우의 수 사이트맵</title>
<style>
  :root {{ --bd:#e3e8ee; --mut:#6b7280; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,'Segoe UI','Malgun Gothic',sans-serif;
    margin:0; background:#f5f7fa; color:#1a1a1a; line-height:1.5; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:28px 20px 60px; }}
  h1 {{ font-size:22px; margin:0 0 4px; letter-spacing:-0.4px; }}
  .sub {{ color:var(--mut); font-size:13px; margin-bottom:22px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:12px; margin-bottom:28px; }}
  .card {{ background:#fff; border:1px solid var(--bd); border-radius:12px; padding:14px 16px; }}
  .card .lbl {{ color:var(--mut); font-size:12px; font-weight:500; }}
  .card .val {{ font-size:24px; font-weight:700; margin-top:3px; letter-spacing:-0.5px; }}
  .card .vsub {{ color:var(--mut); font-size:11px; margin-top:2px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px; font-size:12px; }}
  .pill {{ padding:3px 10px; border-radius:20px; font-weight:600; }}
  .section {{ margin-bottom:30px; }}
  .section-h {{ display:flex; align-items:baseline; gap:10px; margin:0 0 12px;
    padding-bottom:8px; border-bottom:2px solid var(--bd); }}
  .section-h h2 {{ font-size:16px; margin:0; }}
  .section-h .route {{ color:var(--mut); font-size:12px; font-family:monospace; }}
  .section-h .tot {{ margin-left:auto; font-size:12px; color:var(--mut); }}
  .ep {{ background:#fff; border:1px solid var(--bd); border-radius:10px;
    padding:12px 14px; margin-bottom:10px; }}
  .ep-top {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .method {{ font-family:monospace; font-size:10px; font-weight:700; padding:2px 6px;
    border-radius:5px; background:#e8f0ff; color:#1268d3; }}
  .method.POST {{ background:#fdecea; color:#c0392b; }}
  .path {{ font-family:monospace; font-size:13px; font-weight:600; }}
  .desc {{ color:#444; font-size:12px; margin-left:2px; }}
  .combo {{ margin-left:auto; font-size:13px; font-weight:700; }}
  .cache {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:6px; }}
  .params {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:9px; }}
  .param {{ font-size:11px; background:#f3f5f9; border:1px solid #e6eaf0;
    border-radius:6px; padding:3px 8px; }}
  .param b {{ color:#2c3a4d; }}
  .param .n {{ color:#1268d3; font-weight:700; }}
  .cost {{ display:inline-block; margin-top:8px; font-size:11px; color:#8a4b00;
    background:#fff6e8; border:1px solid #f0d9a8; border-radius:6px; padding:3px 8px; }}
  .note {{ margin-top:7px; font-size:11px; color:#a04000; }}
  .cached-n {{ font-size:11px; color:var(--mut); }}
  .formula {{ font-family:monospace; font-size:11px; color:var(--mut); }}
  .timing {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px;
    font-family:monospace; white-space:nowrap; }}
  .timing.t-hit {{ color:#1d7a3d; background:#e6f4ea; }}
  .timing.t-live {{ color:#1268d3; background:#e8f0ff; }}
  .timing.t-live-slow {{ color:#c0392b; background:#fdecea; }}
  .needcache {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px;
    color:#fff; background:#c0392b; white-space:nowrap; }}
  .callout {{ background:#fff8ef; border:1px solid #f0d9a8; border-left:4px solid #e0a020;
    border-radius:10px; padding:14px 16px; margin-bottom:24px; font-size:13px; line-height:1.65; }}
  .callout b {{ color:#7a4a00; }}
  .callout code {{ background:#f3f0e8; padding:1px 5px; border-radius:4px; font-size:12px; }}
</style></head><body><div class="wrap">
<h1>콕집 — 엔드포인트 경우의 수 사이트맵</h1>
<div class="sub">엔드포인트별 캐시 전(라이브)·후 응답시간 + 캐시 필요 판정 (3초 기준) · 현재 데이터 실측</div>
<div class="cards">
  <div class="card"><div class="lbl">엔드포인트</div><div class="val">{n_endpoints}</div>
    <div class="vsub">{len(SECTIONS)}개 영역</div></div>
  <div class="card"><div class="lbl">stats 전체 조합</div>
    <div class="val">{stats_combos:,}</div><div class="vsub">캐시 대상 경우의 수</div></div>
  <div class="card"><div class="lbl">현재 캐시</div>
    <div class="val">{cached_now:,}</div><div class="vsub">매일 사전계산</div></div>
  <div class="card" style="border-color:#e0b4ae"><div class="lbl">🔴 캐시 필요</div>
    <div class="val" style="color:#c0392b">{needs_cache_n}</div>
    <div class="vsub">캐시 전 ≥3초 / {measured_before_n}개 측정</div></div>
  <div class="card"><div class="lbl">단지·중개사 상세</div>
    <div class="val">{entity_combos:,}</div><div class="vsub">엔티티별 · 미캐시</div></div>
</div>
<div class="legend">""")

for key, (lbl, fg, bg) in CACHE_LABEL.items():
    parts.append(f'<span class="pill" style="color:{fg};background:{bg}">{lbl}</span>')
parts.append('<span class="pill" style="color:#c0392b;background:#fdecea">조합 ≥2000</span>'
             '<span class="pill" style="color:#c08a00;background:#fdf3d0">100~2000</span>'
             '<span class="pill" style="color:#1d7a3d;background:#e6f4ea">&lt;100</span>')
parts.append("</div>")
parts.append('<div class="legend" style="margin-top:-14px">'
             '<span class="pill" style="color:#444;background:#fff;border:1px solid var(--bd)">'
             '응답시간(프런트 기본 호출):</span>'
             '<span class="timing t-live">캐시전 = 라이브 쿼리(캐시 우회 직접호출)</span>'
             '<span class="timing t-hit">캐시후 ⚡ = 현재 서빙(HIT)</span>'
             '<span class="needcache">🔴 캐시 필요 = 캐시전 ≥3초</span></div>')

# ── 캐시 효율 콜아웃 (핵심 발견) ──────────────────────
n_hit = sum(1 for v in MEAS.values() if v[1] == "hit")
n_live = sum(1 for v in MEAS.values() if v[1] == "live")
slow = sorted(((p, ms) for (m, p), (ms, c) in MEAS.items() if c == "live"),
              key=lambda x: -x[1])[:5]
slow_txt = " · ".join(
    f'{p.split("/")[-1]} {ms/1000:.0f}s' if ms >= 1000 else f'{p.split("/")[-1]} {ms:.0f}ms'
    for p, ms in slow)
parts.append(f"""<div class="callout">
<b>⚠ 캐시 키 불일치 — 사전계산 캐시가 대부분 무용</b><br>
측정한 GET 호출 {n_hit + n_live}개 중 <b>캐시 HIT은 {n_hit}개뿐</b>, 나머지 {n_live}개는
실시간 계산입니다. 매일 빌드하는 캐시(1,826개)는 <code>/stats/tx-top-price</code> 처럼
<b>파라미터 없는 맨 경로</b>로 저장되는데, 프런트는 <code>?days=30&amp;trade=A1&amp;…</code>
같은 <b>명시적 기본 파라미터</b>를 붙여 보내 키가 어긋납니다. 값이 같아도 캐시를 못 탑니다.
quick-deals·changes 계열만 캐시할 때 같은 파라미터를 써서 HIT 합니다.<br>
<b>가장 느린 실제 페이지 호출:</b> {esc(slow_txt)}<br>
<span style="color:#7a5a00">→ 해결: build_api_cache 가 프런트와 동일한 쿼리스트링으로 캐시하도록 맞추면
이 페이지들이 전부 ⚡ 수 ms 로 떨어집니다.</span>
</div>""")

for title, route, eps in SECTIONS:
    sec_total = sum(e["combos"] for e in eps if e["cache"] != "dynamic")
    parts.append('<div class="section"><div class="section-h">'
                 f'<h2>{esc(title)}</h2><span class="route">{esc(route)}</span>'
                 f'<span class="tot">조합 합계 {sec_total:,}</span></div>')
    for e in eps:
        lbl, fg, bg = CACHE_LABEL[e["cache"]]
        combo_txt = "∞" if (e["combos"] == 0 and e["cache"] == "dynamic") else f'{e["combos"]:,}'
        cc = combo_color(e["combos"])
        parts.append('<div class="ep"><div class="ep-top">')
        parts.append(f'<span class="method {e["method"]}">{e["method"]}</span>')
        parts.append(f'<span class="path">{esc(e["path"])}</span>')
        parts.append(f'<span class="desc">{esc(e["desc"])}</span>')
        parts.append(f'<span class="combo" style="color:{cc}">{combo_txt}<span '
                     f'style="font-size:10px;color:#888;font-weight:400"> 조합</span></span>')
        parts.append(f'<span class="cache" style="color:{fg};background:{bg}">{lbl}</span>')
        tb = timing_badge(e["method"], e["path"])
        if tb:
            parts.append(tb)
        parts.append('</div>')
        if e["params"]:
            parts.append('<div class="params">')
            factors = []
            for name, opts, n in e["params"]:
                ntxt = "∞" if n == 0 else f"×{n}"
                parts.append(f'<span class="param"><b>{esc(name)}</b>: {esc(opts)} '
                             f'<span class="n">{ntxt}</span></span>')
                factors.append("∞" if n == 0 else str(n))
            parts.append('</div>')
            if len([f for f in factors if f != "1"]) > 1:
                parts.append(f'<div class="formula">= {" × ".join(factors)} = '
                             f'{combo_txt} 조합</div>')
        cost = fmt_cost(e["path"])
        if cost:
            parts.append(cost)
        if e["cached_n"] and e["cache"] in ("default", "partial"):
            parts.append(f'<div class="cached-n">현재 캐시: {e["cached_n"]:,} / '
                         f'{e["combos"]:,} 조합</div>')
        if e["note"]:
            parts.append(f'<div class="note">⚠ {esc(e["note"])}</div>')
        parts.append('</div>')
    parts.append('</div>')

parts.append("</div></body></html>")

OUT.write_text("".join(parts), encoding="utf-8")
print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
print(f"endpoints={n_endpoints}  stats_combos={stats_combos:,}  "
      f"cached_now={cached_now:,}  entity={entity_combos:,}")
