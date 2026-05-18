"""Naver new.land API endpoints used by the spike.

References (NAVER_API_PORTING.md):
  §2.1  /api/articles/complex/{complexNo}              — articles per complex
  §2.3  /api/complexes/single-markers/2.0              — complex markers in bbox
        /api/regions/list                              — region children (Bearer required)
        /api/regions/complexes                         — complex list by cortarNo
"""
from __future__ import annotations

from typing import Iterator

from .http import get_json

REAL_ESTATE_DEFAULT = "APT:ABYG:JGC:PBJT"  # 아파트+분양권+재건축+분양완료
TRADE_TYPES = ("A1", "B1", "B2")  # 매매, 전세, 월세


def list_region_children(cortar_no: str, creds: dict) -> list[dict]:
    url = "https://new.land.naver.com/api/regions/list"
    status, data = get_json(url, creds, params={"cortarNo": cortar_no})
    if status != 200 or not isinstance(data, dict):
        raise RuntimeError(f"regions/list({cortar_no}) -> {status}: {data!r}"[:300])
    return data.get("regionList", [])


def find_child(children: list[dict], keyword: str) -> dict | None:
    for c in children:
        if keyword in (c.get("cortarName") or ""):
            return c
    return None


def complexes_in_region(cortar_no: str, creds: dict) -> list[dict]:
    """List complexes for a leaf cortarNo (동 단위)."""
    url = "https://new.land.naver.com/api/regions/complexes"
    status, data = get_json(
        url,
        creds,
        params={
            "cortarNo": cortar_no,
            "realEstateType": "APT:PRE:JGC:ABYG:OBYG",
            "order": "date",
        },
    )
    if status != 200 or not isinstance(data, dict):
        raise RuntimeError(f"regions/complexes({cortar_no}) -> {status}: {data!r}"[:300])
    # Response shape historically: { complexList: [...] }
    return data.get("complexList") or data.get("list") or []


def articles_for_complex(
    complex_no: str,
    trade: str,
    creds: dict,
    real_estate_type: str = REAL_ESTATE_DEFAULT,
    max_pages: int = 100,
) -> Iterator[dict]:
    url = f"https://new.land.naver.com/api/articles/complex/{complex_no}"
    page = 1
    while page <= max_pages:
        params = {
            "realEstateType": real_estate_type,
            "tradeType": trade,
            "priceMin": 0, "priceMax": 900000000,
            "areaMin": 0, "areaMax": 900000000,
            "sameAddressGroup": "false",
            "page": page,
            "complexNo": complex_no,
        }
        status, data = get_json(url, creds, params=params)
        if status != 200 or not isinstance(data, dict):
            break
        items = (
            data.get("articleList")
            or (data.get("body") or {}).get("list")
            or []
        )
        if not items:
            break
        yield from items
        if not data.get("isMoreData", False) or len(items) < 20:
            break
        page += 1
