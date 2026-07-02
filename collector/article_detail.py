"""네이버 매물 상세(/api/articles/{articleNo}) 조회 + 중개대상물 표시·광고 점검용 필드 추출.

매물점검(중개사 라운지) 기능 전용. 매물 LIST(listings_current)에 없는 항목
(입주가능일·방수/욕실수·관리비)과 점검 보조필드(위반건축물·방향기준·주용도)를 확보한다.

★ 사용은 온디맨드: 중개사가 '매물점검'을 열 때 그 중개사의 매물만 상세조회(보통 수십~수백건).
   전체 매물(186만) 일괄수집 아님 — API/저장 부담 방지.
"""
from __future__ import annotations

from typing import Any

DETAIL_URL = "https://new.land.naver.com/api/articles/{article_no}"


def fetch_article_detail(article_no: str, complex_no, creds, *, interface: str | None = None):
    """단일 매물 상세 JSON. (status, dict) 반환. 실패 시 dict=None."""
    from collector.http import get_json
    params = {}
    if complex_no:
        params["complexNo"] = str(complex_no)
    st, data = get_json(DETAIL_URL.format(article_no=article_no), creds,
                        params=params, interface=interface)
    return st, (data if isinstance(data, dict) else None)


def extract_checklist_fields(detail: dict) -> dict[str, Any]:
    """상세 JSON → 중개대상물 표시·광고 점검 12항목 + 보조필드 정규화 dict.
    값이 없으면 None — 점검 엔진이 '미표시(위반후보)'로 판정."""
    ad = detail.get("articleDetail", {}) or {}
    fac = detail.get("articleFacility", {}) or {}
    flr = detail.get("articleFloor", {}) or {}
    add = detail.get("articleAddition", {}) or {}
    cost = detail.get("administrationCostInfo", {}) or {}

    def _num(v):
        try:
            return int(str(v)) if str(v).strip() not in ("", "-", "None") else None
        except (ValueError, TypeError):
            return None

    return {
        # ① 소재지 (지번·동·층)
        "exposure_address": ad.get("exposureAddress"),       # 노출 주소(지번/동까지)
        "detail_address": ad.get("detailAddress"),           # 상세 주소
        "building_name": ad.get("buildingName"),             # 동 명칭
        "floor_info": add.get("floorInfo"),                  # "중/15" 등 → 저/중/고 판별
        "corresponding_floor": flr.get("correspondingFloorCount"),  # 해당층
        # ⑥ 총 층수 — 건물(통임대) 매물은 totalFloorCount 대신 uppergroundFloorCount(지상층)에
        #    표기됨(광고 '지상층/지하층 5/B2'). 대장 대조도 지상층(grnd_flr) 기준이라 동일 의미.
        "total_floor": _num(flr.get("totalFloorCount")) or _num(flr.get("uppergroundFloorCount")),
        # ④ 종류/용도 + 위반·미등기
        "realestate_type": ad.get("realestateTypeName"),
        "principal_use": ad.get("principalUse"),             # 주용도(업무/숙박 등, 생숙 보조신호)
        "violation_building": ad.get("violationBuildingYN"), # 위반건축물
        "unregistered_building": ad.get("unregisteredBuildingYN"),  # 미등기
        # ⑤ 거래형태
        "trade_type": ad.get("tradeTypeName"),
        # ⑦ 입주가능일
        "movein_type": ad.get("moveInTypeName"),             # "즉시입주"/"2026년 06월 중순"
        "movein_ymd": ad.get("moveInPossibleYmd"),
        "movein_negotiable": ad.get("moveInDiscussionPossibleYN"),
        # ⑧ 방수/욕실수
        "room_count": _num(ad.get("roomCount")),
        "bathroom_count": _num(ad.get("bathroomCount")),
        # ⑨ 사용승인일 — 단지형=articleDetail, 비단지=articleFacility.buildingUseAprvYmd
        "use_approve_ymd": (ad.get("aptUseApproveYmd") or ad.get("useApproveYmd")
                            or fac.get("buildingUseAprvYmd")),
        # ⑩ 주차대수
        "parking_count": _num(ad.get("parkingCount")),
        "parking_per_household": ad.get("parkingPerHouseholdCount"),
        "parking_possible": ad.get("parkingPossibleYN"),
        # ⑪ 관리비
        "monthly_management_cost": _num(ad.get("monthlyManagementCost")),
        "admin_cost_info": cost or None,                     # 정액구분·포함비목 상세
        # ⑫ 방향 + 기준
        "direction": fac.get("directionTypeName") or add.get("direction"),
        "direction_base": fac.get("directionBaseTypeName"),  # "거실 기준" 등
        # ★ 네이버가 매물상세에 포함하는 건축물대장(비단지 대장대조용 — 좌표 온디맨드 대체)
        "ledger_inline": _inline_ledger(detail),
    }


def _inline_ledger(detail: dict):
    """매물상세의 articleBuildingRegister(네이버가 매칭한 그 건물의 건축물대장) → 점검용 대장 dict.
    좌표 온디맨드(vworld→data.go.kr)보다 해당 매물 건물에 정확하고 무료·무쿼터.
    led 형태(ondemand_ledger와 동일 키: main_purps/bld_nm/grnd_flr/use_apr_day/parking)."""
    br = detail.get("articleBuildingRegister") or {}
    if not br or br.get("serviceYn") == "N":
        return None
    fac = detail.get("articleFacility", {}) or {}
    ad = detail.get("articleDetail", {}) or {}

    def _i(v):
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    grnd = _i(br.get("grndFlrCnt"))
    park = _i(br.get("totalParkingCnt"))
    # 사용승인일: articleFacility의 8자리(YYYYMMDD)가 정확, 없으면 register의 useAprDay(YYYY.MM)
    use_apr = fac.get("buildingUseAprvYmd") or ("".join(c for c in str(br.get("useAprDay") or "")
                                                        if c.isdigit()) or None)
    purps = br.get("mainPurpsCdNm") or None
    if not (grnd or use_apr or purps):
        return None
    bld = br.get("exposureBldName")
    return {
        "main_purps": purps,
        "bld_nm": (bld if isinstance(bld, str) and bld else None) or ad.get("buildingName"),
        "grnd_flr": grnd,
        # 대장 주차 0은 '미기재'와 구분이 어려워 0은 None 처리(⑩ 주차 오탐 방지)
        "parking": park if park else None,
        "use_apr_day": use_apr,
        "pnu": br.get("pnu") or None,
        "_source": "naver_inline",
    }


def fetch_and_extract(article_no: str, complex_no, creds, *, interface=None):
    """상세조회 + 추출 한 번에. 반환 3상태:
    dict = 정상 / {"_delisted": True} = 광고 종료(200인데 본문이 error뿐 — 내려간 매물,
    빈 필드로 점검하면 전항목 '미표시 위반' 오탐 폭탄) / None = 일시 실패(네트워크 등)."""
    st, d = fetch_article_detail(article_no, complex_no, creds, interface=interface)
    if st != 200 or not d:
        return None
    if not (d.get("articleDetail") or {}).get("articleNo"):
        return {"_delisted": True}
    return extract_checklist_fields(d)
