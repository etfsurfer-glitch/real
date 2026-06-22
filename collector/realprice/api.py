"""국토부 실거래가 API client (data.go.kr RTMSDataSvcAptTradeDev).

Free tier limit: 10,000 calls/day. We typically need ~255 calls/day
(시군구 단위) so plenty of headroom for backfill.
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Iterator

from ..config import settings

ENDPOINT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
)
ENDPOINT_RENT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
)
ENDPOINT_OFFI_TRADE = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"
)
ENDPOINT_OFFI_RENT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent"
)
# 아파트 분양권/입주권 전매 실거래 (신축·재건축 신규공급 세그먼트). 매매 API와 동일한
# XML 구조·쿼리파라미터(LAWD_CD/DEAL_YMD)라 fetch_all(endpoint=...) 그대로 재사용.
ENDPOINT_SILV = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade"
)
# 비단지: 연립다세대(빌라) 매매·전월세. 단지 매칭 안 함 — 지번+건물명(mhouseNm)으로 지역 집계.
ENDPOINT_RH_TRADE = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"
)
ENDPOINT_RH_RENT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent"
)


class APIError(RuntimeError):
    pass


# ── 회로차단기 ──────────────────────────────────────────────────────
# data.go.kr 서버측 장애(502/timeout)가 나면 한 요청당 최대 ~66s(3retry×20s+sleep)
# 걸려 1,530 task 가 수 시간 헛돈다. 연속 실패가 임계치를 넘으면 차단(circuit open)
# 해서 이후 요청은 즉시 실패시킨다 → 그 backfill 단계가 수분 내 끝나고 daily_run 은
# 매칭·롤업·캐시로 진행. 프로세스 단위 상태라 다음 run(새 프로세스)에서 자동 리셋.
import threading as _threading
_CB_THRESHOLD = 15
_cb_lock = _threading.Lock()
_cb_fail_streak = 0
_cb_tripped = False


def circuit_open() -> bool:
    return _cb_tripped


def _cb_record(ok: bool) -> None:
    global _cb_fail_streak, _cb_tripped
    with _cb_lock:
        if ok:
            _cb_fail_streak = 0
        else:
            _cb_fail_streak += 1
            if _cb_fail_streak >= _CB_THRESHOLD:
                _cb_tripped = True


def fetch_xml(lawd_cd: str, deal_ymd: str, page_no: int = 1, num_rows: int = 1000,
              timeout: int = 20, retries: int = 3,
              endpoint: str = ENDPOINT) -> bytes:
    """Single page fetch. Raises APIError on auth/format problems.

    The 매매 (sale) and 전월세 (rent) APIs share the same shape and query
    parameters, so callers pick endpoint=ENDPOINT_RENT to hit the rent feed.
    """
    if not settings.data_go_kr_service_key:
        raise APIError("DATA_GO_KR_SERVICE_KEY missing in .env")
    if _cb_tripped:  # 차단 상태 → 즉시 실패(대기·재시도 없이)
        raise APIError("data.go.kr 연속 장애로 차단(circuit open) — 회복 후 재시도")
    qs = urllib.parse.urlencode({
        "serviceKey": settings.data_go_kr_service_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
    })
    url = f"{endpoint}?{qs}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            _cb_record(True)
            return data
        except Exception as e:  # noqa: BLE001
            last_err = e
            if _cb_tripped:  # 다른 스레드가 차단 → 더 기다리지 말고 즉시 중단
                break
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    _cb_record(False)
    raise APIError(f"fetch failed after {retries} attempts: {last_err}")


def parse_response(xml_bytes: bytes) -> tuple[list[dict], dict]:
    """Parse XML envelope; raise on error code, return (items, meta)."""
    root = ET.fromstring(xml_bytes)
    err = root.find(".//errMsg")
    if err is not None:
        auth = root.find(".//returnAuthMsg")
        msg = err.text or ""
        if auth is not None:
            msg += f" ({auth.text})"
        raise APIError(f"API error envelope: {msg}")
    header = root.find(".//header")
    rc = header.findtext("resultCode") if header is not None else ""
    rm = header.findtext("resultMsg") if header is not None else ""
    if rc and rc.lstrip("0"):
        raise APIError(f"resultCode={rc} {rm}")
    items = [
        {child.tag: (child.text or "").strip() for child in it}
        for it in root.iter("item")
    ]
    meta = {}
    body = root.find(".//body")
    if body is not None:
        for k in ("numOfRows", "pageNo", "totalCount"):
            meta[k] = body.findtext(k)
    return items, meta


def fetch_all(lawd_cd: str, deal_ymd: str,
              endpoint: str = ENDPOINT) -> Iterator[dict]:
    """Yield every transaction for a 시군구·month, walking pages.

    Pass endpoint=ENDPOINT_RENT to read the rent feed instead of sale.
    """
    page = 1
    while True:
        body = fetch_xml(lawd_cd, deal_ymd, page_no=page, endpoint=endpoint)
        items, meta = parse_response(body)
        if not items:
            return
        yield from items
        # Stop when we've fetched all rows or got a short page.
        try:
            total = int(meta.get("totalCount") or 0)
        except ValueError:
            total = 0
        try:
            num_rows = int(meta.get("numOfRows") or 1000)
        except ValueError:
            num_rows = 1000
        if total and page * num_rows >= total:
            return
        if len(items) < num_rows:
            return
        page += 1
        if page > 50:  # safety
            return
