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
        "total_floor": _num(flr.get("totalFloorCount")),     # ⑥ 총 층수
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
    }


def fetch_and_extract(article_no: str, complex_no, creds, *, interface=None):
    """상세조회 + 추출 한 번에. 실패 시 None."""
    st, d = fetch_article_detail(article_no, complex_no, creds, interface=interface)
    if not d:
        return None
    return extract_checklist_fields(d)
