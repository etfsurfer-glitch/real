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


class APIError(RuntimeError):
    pass


def fetch_xml(lawd_cd: str, deal_ymd: str, page_no: int = 1, num_rows: int = 1000,
              timeout: int = 20, retries: int = 3) -> bytes:
    """Single page fetch. Raises APIError on auth/format problems."""
    if not settings.data_go_kr_service_key:
        raise APIError("DATA_GO_KR_SERVICE_KEY missing in .env")
    qs = urllib.parse.urlencode({
        "serviceKey": settings.data_go_kr_service_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
    })
    url = f"{ENDPOINT}?{qs}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
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


def fetch_all(lawd_cd: str, deal_ymd: str) -> Iterator[dict]:
    """Yield every transaction for a 시군구·month, walking pages."""
    page = 1
    while True:
        body = fetch_xml(lawd_cd, deal_ymd, page_no=page)
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
