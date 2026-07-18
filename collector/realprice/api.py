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
# 비단지: 단독/다가구 매매·전월세(동 단위·연면적/대지면적). 지번 마스킹 → 토지가치 관점.
ENDPOINT_SH_TRADE = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade"
)
ENDPOINT_SH_RENT = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcSHRent/getRTMSDataSvcSHRent"
)
# 비단지: 상업업무용(상가·사무실) 매매. 지번+건물용도(buildingUse)+용도지역. 매매만(임대 실거래 없음).
ENDPOINT_NRG_TRADE = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"
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


# 전남광주통합특별시(2026-07-01 광주광역시+전라남도 통합) — data.go.kr이 이 지역을
# 새 시도코드 12로 서빙(옛 광주 29·전남 46 코드는 0 반환). 내부는 표준 29/46로 유지
# (과거 실거래·complexes·regions·rollup 전부 그 코드라 연속성 위해) → 표준코드로 요청이
# 오면 실제 조회만 12xxx로 하고, 응답 sggCd를 표준으로 되돌린다(투명 remap). 응답의
# aptSeq·umdNm은 여전히 옛 형식(예: aptSeq=29170-74)이라 deal_id 일치=재수집 중복 0.
_STD_TO_NEW = {
    "29110": "12210", "29140": "12240", "29155": "12270", "29170": "12300", "29200": "12330",
    "46110": "12110", "46130": "12130", "46150": "12150", "46170": "12170", "46230": "12190",
    "46710": "12710", "46720": "12720", "46730": "12730", "46770": "12740", "46780": "12750",
    "46790": "12760", "46800": "12770", "46810": "12780", "46820": "12790", "46830": "12800",
    "46840": "12810", "46860": "12820", "46870": "12830", "46880": "12840", "46890": "12850",
    "46900": "12860", "46910": "12870",
}


# 인천 행정구역 개편(2026-07-01) — 중구+동구 → 제물포구(28125)·영종구(28155),
# 서구 → 서구(28275)·검단구(28290). 옛 코드 28110/28140/28260은 202607부터 0 반환.
# 광주·전남과 달리 1:N 분할합병이라, 표준(옛) 코드 하나가 새 코드 여러 개를 조회한다.
# 제물포구(28125)는 옛 중구 원도심 + 옛 동구 전체가 섞임 → **aptSeq 접두(옛 구코드 유지 실측:
# 28125 응답의 aptSeq="28140-21" 등)**로 옛 구를 판별하고, aptSeq 없는 피드는 법정동명 폴백.
_OLD_DONGGU_UMDS = {"만석동", "화수동", "화평동", "송현동", "송림동", "창영동", "금곡동"}  # 옛 인천 동구
# 표준코드 → [(새코드, 필터)] — 필터: None=전부 수용 / "28110"·"28140"=그 옛 구 소속만
_STD_TO_NEW_MULTI = {
    "28110": [("28155", None), ("28125", "28110")],   # 옛 중구 = 영종구 전체 + 제물포구 中 중구계
    "28140": [("28125", "28140")],                    # 옛 동구 = 제물포구 中 동구계
    "28260": [("28275", None), ("28290", None)],      # 옛 서구 = 서구(잔여) + 검단구
}


def _old_incheon_gu(it: dict) -> str | None:
    """제물포구 레코드의 옛 구(28110 중구/28140 동구) 판별. aptSeq 접두 우선, 동명 폴백."""
    seq = str(it.get("aptSeq") or "")
    if seq.startswith("28110"):
        return "28110"
    if seq.startswith("28140"):
        return "28140"
    umd = (it.get("umdNm") or "").strip()
    if umd:
        return "28140" if umd in _OLD_DONGGU_UMDS else "28110"
    return None


def _fetch_pages(api_lawd: str, deal_ymd: str, endpoint: str, std_cd: str | None) -> Iterator[dict]:
    """단일 (실제 조회코드) 페이지 순회. std_cd가 있으면 응답 sggCd를 표준코드로 되돌린다."""
    page = 1
    while True:
        body = fetch_xml(api_lawd, deal_ymd, page_no=page, endpoint=endpoint)
        items, meta = parse_response(body)
        if not items:
            return
        if std_cd:
            for it in items:
                if it.get("sggCd"):
                    it["sggCd"] = std_cd
        yield from items
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


def fetch_all(lawd_cd: str, deal_ymd: str,
              endpoint: str = ENDPOINT) -> Iterator[dict]:
    """Yield every transaction for a 시군구·month, walking pages.

    Pass endpoint=ENDPOINT_RENT to read the rent feed instead of sale.
    """
    multi = _STD_TO_NEW_MULTI.get(lawd_cd)
    if multi:   # 인천 분할합병 — 새 코드 여러 개를 모아 표준코드로 수용
        for new_cd, want_old in multi:
            for it in _fetch_pages(new_cd, deal_ymd, endpoint, std_cd=lawd_cd):
                if want_old and _old_incheon_gu(it) != want_old:
                    continue   # 제물포구 혼합분 중 다른 옛 구 소속(그 구의 조회에서 수용됨)
                yield it
        return
    api_lawd = _STD_TO_NEW.get(lawd_cd, lawd_cd)   # 광주/전남은 12xxx로 실제 조회
    std_cd = lawd_cd if api_lawd != lawd_cd else None  # 응답 sggCd를 되돌릴 표준코드
    yield from _fetch_pages(api_lawd, deal_ymd, endpoint, std_cd)
