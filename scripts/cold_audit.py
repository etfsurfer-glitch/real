"""콜드 상태 전 엔드포인트 실측 — 캐시 비운 상태에서 라이브 응답시간/상태/크기 측정.
캐시 전략 재설계용. 각 엔드포인트 1회 호출(첫 패스=콜드). 느린 순 정렬 출력."""
import time, json, urllib.request, urllib.parse

BASE = "http://127.0.0.1:8000"
CNO = "13814"        # 강남 대단지 샘플
RID = "0001plus"
# 서울 bbox
BB = {"swlat": 37.45, "nelat": 37.65, "swlng": 126.85, "nelng": 127.15}

# (그룹, 라벨, path, params)
T = [
 ("랜딩/개요", "recent-tx", "/stats/recent-tx", {"days": 7}),
 ("랜딩/개요", "freshness", "/stats/freshness", {}),
 ("랜딩/개요", "region-compare", "/stats/region-compare", {"days": 30, "trade": "A1"}),
 ("랜딩/개요", "tx-region-pulse", "/stats/tx-region-pulse", {"asset": "apt"}),
 ("TODAY", "today-deals(매매)", "/stats/today-deals", {"trade": "A1", "limit": 24}),
 ("TODAY", "today-deals(월세)", "/stats/today-deals", {"trade": "B2", "limit": 24}),
 ("TODAY", "today-listings-stats", "/stats/today-listings-stats", {}),
 ("급매", "quick-deals(전국)", "/stats/quick-deals", {"days": 90, "asset": "apt", "trade_type": "A1", "min_samples": 5}),
 ("급매", "quick-deals(서울시도)", "/stats/quick-deals", {"days": 90, "asset": "apt", "trade_type": "A1", "sido": "11", "min_samples": 5}),
 ("급매", "quick-deals(강남시군구)", "/stats/quick-deals", {"days": 90, "asset": "apt", "trade_type": "A1", "sigungu": "1168000000", "min_samples": 5}),
 ("지도", "complexes-in-bounds", "/stats/complexes-in-bounds", {**BB, "limit": 500}),
 ("지도", "quick-deals-map", "/stats/quick-deals-map", {**BB, "trade_type": "A1", "asset": "apt", "days": 90}),
 ("실거래통계", "tx-record-high", "/stats/tx-record-high", {"days": 90, "trade": "A1", "order": "premium", "limit": 300}),
 ("실거래통계", "tx-top-price", "/stats/tx-top-price", {"days": 30, "trade": "A1", "limit": 100}),
 ("실거래통계", "tx-top-volume", "/stats/tx-top-volume", {"days": 30, "trade": "A1", "limit": 100}),
 ("실거래통계", "tx-low-price", "/stats/tx-low-price", {"days": 180, "asset": "all", "limit": 300}),
 ("실거래통계", "tx-gap-rank", "/stats/tx-gap-rank", {"days": 365, "limit": 100}),
 ("실거래통계", "tx-jeonse-rate", "/stats/tx-jeonse-rate", {"days": 365, "limit": 100}),
 ("실거래통계", "tx-price-change", "/stats/tx-price-change", {"window_days": 90, "limit": 100}),
 ("실거래통계", "tx-asking-vs-real", "/stats/tx-asking-vs-real", {"days": 90, "limit": 200}),
 ("실거래통계", "tx-pyeong-price", "/stats/tx-pyeong-price", {"days": 365, "limit": 100}),
 ("실거래통계", "tx-turnover", "/stats/tx-turnover", {"days": 365, "trade": "A1", "limit": 100}),
 ("실거래통계", "tx-yield", "/stats/tx-yield", {"days": 365, "limit": 100}),
 ("저평가", "recovery", "/stats/recovery", {"days": 90, "limit": 200}),
 ("변동", "changes-summary", "/stats/changes/summary", {"days": 7}),
 ("변동", "changes-region-rank", "/stats/changes/region-rank", {"days": 7}),
 ("변동", "changes-movers", "/stats/changes/movers", {"days": 7}),
 ("변동", "changes-events", "/stats/changes/events", {"trade": "A1"}),
 ("변동", "listing-trend", "/stats/listing-trend", {"days": 60}),
 ("변동", "avg-price-trend", "/stats/avg-price-trend", {"days": 60}),
 ("취소거래", "cancelled-transactions", "/stats/cancelled-transactions", {"asset": "apt", "limit": 50}),
 ("취소거래", "cancelled-summary", "/stats/cancelled-summary", {"asset": "apt"}),
 ("단지상세", "complex/transactions", f"/complex/{CNO}/transactions", {"months": 24}),
 ("단지상세", "complex/areas", f"/complex/{CNO}/areas", {}),
 ("단지상세", "complex/realtors", f"/complex/{CNO}/realtors", {}),
 ("단지상세", "complex/quick-deals", f"/complex/{CNO}/quick-deals", {"trade_type": "A1"}),
 ("중개사", "realtor", f"/realtor/{RID}", {}),
 ("검색", "complexes/q", "/complexes", {"q": "래미안", "limit": 20}),
]


def hit(path, params):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=180) as r:
            body = r.read(); code = r.status
        return time.perf_counter() - t0, code, len(body)
    except urllib.error.HTTPError as e:
        return time.perf_counter() - t0, e.code, 0
    except Exception as e:
        return time.perf_counter() - t0, "ERR", 0


def main():
    res = []
    for grp, label, path, params in T:
        dt, code, sz = hit(path, params)
        res.append((dt, grp, label, code, sz))
        print(f"  {dt:6.2f}s  [{code}]  {grp:8s} {label:28s} {sz/1024:7.1f}KB", flush=True)
    print("\n===== 느린 순 =====")
    for dt, grp, label, code, sz in sorted(res, reverse=True):
        flag = "🔴" if dt >= 3 else ("🟡" if dt >= 1 else "🟢")
        print(f"  {flag} {dt:6.2f}s  {grp:8s} {label:28s} [{code}]")
    slow = [r for r in res if r[0] >= 3]
    med = [r for r in res if 1 <= r[0] < 3]
    print(f"\n느림(≥3s) {len(slow)}개 / 보통(1~3s) {len(med)}개 / 빠름(<1s) {len(res)-len(slow)-len(med)}개")


if __name__ == "__main__":
    main()
