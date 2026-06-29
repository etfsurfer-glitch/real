"""중개대상물 인터넷 표시·광고 점검 엔진 (한국부동산원 체크리스트 기준).

순수 판정 로직 — 매물 통합필드(dict) 입력 → 항목별 findings 반환. DB/네트워크 없음.
중개사 라운지 '매물점검' 기능에서 사용. 상세필드는 collector.article_detail 로 확보.

판정: 통과 / 주의(권장·조건부) / 위반(과태료 위험: 필수항목 누락 등).
"""
from __future__ import annotations


def is_saengsuk(complex_name: str | None) -> bool:
    """네이버 단지명 표기 기반 생활숙박시설 판정(1순위 신호). [[naverreal-building-ledger]]"""
    return bool(complex_name) and "생활숙박" in complex_name


def _has(v) -> bool:
    """표시값 존재 여부(빈값·'-'·0·None 은 미표시로 간주)."""
    return v is not None and str(v).strip() not in ("", "-", "0", "None")


def _floor_is_approx(floor_info: str | None) -> bool:
    """floor_info 가 저/중/고 표기인지. '중/15'→True, '3/15'→False."""
    if not floor_info:
        return False
    return floor_info.split("/")[0].strip() in ("저", "중", "고")


# 주택·준주택(방수+욕실수 필요). 그 외 건축물(생숙·상가 등)은 욕실수만 표시 가능.
_RESIDENTIAL_TYPES = {"아파트", "오피스텔", "빌라/연립", "빌라단지-연립", "단독/다가구", "다세대"}


def audit_listing(f: dict) -> dict:
    """매물 1건 점검. f = listings + complexes + 상세추출 + is_saengsuk 병합 dict.

    필요 키: article_no, real_estate_type/realestate_type_name, trade_type, floor_info,
    area_exclusive, price, total_floor, movein_type, room_count, bathroom_count,
    use_approve_ymd, parking_count, monthly_management_cost, admin_cost_info,
    direction, direction_base, violation_building, detail_address, building_name,
    dong_name, is_saengsuk.
    """
    findings: list[dict] = []

    def add(no, item, status, reason=""):
        findings.append({"no": no, "item": item, "status": status, "reason": reason})

    saengsuk = bool(f.get("is_saengsuk"))
    rtype = f.get("realestate_type_name") or f.get("real_estate_type")

    # ① 소재지 (지번·동·층)
    floor = f.get("floor_info")
    if not _has(floor):
        add(1, "소재지·층", "위반", "층 미표시")
    elif saengsuk and _floor_is_approx(floor):
        add(1, "소재지·층", "위반",
            f"생활숙박시설은 정확한 층 명시 필수(현재 '{floor.split('/')[0]}' 표기)")
    elif _floor_is_approx(floor):
        add(1, "소재지·층", "주의", "저/중/고 표기 — 준주택은 의뢰인 요청 시에만 허용")
    else:
        add(1, "소재지·층", "통과")
    if not (_has(f.get("detail_address")) or _has(f.get("building_name")) or _has(f.get("dong_name"))):
        add(1, "소재지·지번/동", "주의", "지번·동 정보 부족")

    # ② 면적(전용㎡)
    add(2, "면적(전용㎡)", "통과" if _has(f.get("area_exclusive")) else "위반",
        "" if _has(f.get("area_exclusive")) else "전용면적(㎡) 미표시")

    # ③ 가격
    add(3, "가격", "통과" if _has(f.get("price")) else "위반",
        "" if _has(f.get("price")) else "거래예정금액 미표시")

    # ④ 종류 (+ 위반건축물 표시)
    if not _has(rtype):
        add(4, "중개대상물 종류", "위반", "종류 미표시")
    elif f.get("violation_building") == "Y":
        add(4, "중개대상물 종류", "주의", "위반건축물 — 광고에 '위반건축물' 명시 필요")
    else:
        add(4, "중개대상물 종류", "통과")

    # ⑤ 거래형태
    add(5, "거래형태", "통과" if _has(f.get("trade_type")) else "위반",
        "" if _has(f.get("trade_type")) else "거래형태 미표시")

    # ⑥ 총 층수
    add(6, "총 층수", "통과" if _has(f.get("total_floor")) else "위반",
        "" if _has(f.get("total_floor")) else "총 층수 미표시")

    # ⑦ 입주가능일
    add(7, "입주가능일", "통과" if _has(f.get("movein_type")) else "위반",
        "" if _has(f.get("movein_type")) else "입주가능일 미표시")

    # ⑧ 방수/욕실수
    has_room, has_bath = _has(f.get("room_count")), _has(f.get("bathroom_count"))
    residential = (not saengsuk) and (
        rtype in _RESIDENTIAL_TYPES or f.get("real_estate_type") in ("APT", "OPST"))
    if residential:
        ok = has_room and has_bath
        add(8, "방수/욕실수", "통과" if ok else "위반",
            "" if ok else "방 수·욕실 수 미표시")
    else:
        add(8, "욕실수", "통과" if has_bath else "위반",
            "" if has_bath else "욕실 수 미표시")

    # ⑨ 사용승인일
    add(9, "사용승인일", "통과" if _has(f.get("use_approve_ymd")) else "위반",
        "" if _has(f.get("use_approve_ymd")) else "사용승인일 미표시")

    # ⑩ 주차대수
    add(10, "주차대수", "통과" if _has(f.get("parking_count")) else "위반",
        "" if _has(f.get("parking_count")) else "주차대수 미표시")

    # ⑪ 관리비 (정액 월 10만원 이상이면 총액+비목별 세부 표시 필요)
    cost = f.get("monthly_management_cost")
    try:
        cost_i = int(cost) if cost not in (None, "") else 0
    except (ValueError, TypeError):
        cost_i = 0
    if cost_i >= 100000:
        ok = bool(f.get("admin_cost_info"))
        add(11, "관리비", "통과" if ok else "위반",
            "" if ok else "정액 월 10만원 이상 — 총액·비목별 세부금액 표시 필요")
    else:
        add(11, "관리비", "통과")

    # ⑫ 방향 (+ 기준)
    if not _has(f.get("direction")):
        add(12, "방향", "위반", "방향 미표시")
    elif not _has(f.get("direction_base")):
        add(12, "방향", "주의", "방향 기준(거실/주출입구 등) 미표시")
    else:
        add(12, "방향", "통과")

    viol = sum(1 for x in findings if x["status"] == "위반")
    warn = sum(1 for x in findings if x["status"] == "주의")
    return {
        "article_no": f.get("article_no"),
        "is_saengsuk": saengsuk,
        "findings": findings,
        "violation_count": viol,
        "warning_count": warn,
        "pass": viol == 0,
    }
