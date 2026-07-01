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


def _to_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _floor_is_approx(floor_info: str | None) -> bool:
    """floor_info 가 저/중/고 표기인지. '중/15'→True, '3/15'→False."""
    if not floor_info:
        return False
    return floor_info.split("/")[0].strip() in ("저", "중", "고")


def _ledger_mismatch(val, led, *, digits=False) -> bool:
    """광고값 vs 대장값 불일치 여부. 대장 없으면 False(대조 생략). led는 스칼라 또는
    집합(단지형=동별 총층·사용승인). 집합이면 '어느 동과도 안 맞을 때'만 불일치(오탐방지).
    digits=True면 숫자만 비교(날짜 형식차 무시)."""
    if led is None or led == "" or led == []:
        return False

    def norm(x):
        s = str(x or "")
        return "".join(c for c in s if c.isdigit()) if digits else s.strip()

    v = norm(val)
    if not v:
        return False
    if isinstance(led, (list, set, tuple)):
        opts = {norm(x) for x in led if norm(x)}
        return bool(opts) and v not in opts
    lv = norm(led)
    return bool(lv) and v != lv


def _fmt_led(led) -> str:
    if isinstance(led, (list, set, tuple)):
        return "/".join(str(x) for x in led)
    return str(led)


def _fmt_ymd(s) -> str:
    """YYYYMMDD/YYYYMM → 'YYYY.MM.DD'/'YYYY.MM' 사용자 표기."""
    d = "".join(ch for ch in str(s or "") if ch.isdigit())
    if len(d) >= 8:
        return f"{d[:4]}.{d[4:6]}.{d[6:8]}"
    if len(d) >= 6:
        return f"{d[:4]}.{d[4:6]}"
    return str(s or "")


def _fmt_led_ymd(led) -> str:
    if isinstance(led, (list, set, tuple)):
        return "/".join(_fmt_ymd(x) for x in led)
    return _fmt_ymd(led)


# 주택·준주택(방수+욕실수 필요). 그 외 건축물(생숙·상가 등)은 욕실수만 표시 가능.
_RESIDENTIAL_TYPES = {"아파트", "오피스텔", "빌라/연립", "빌라단지-연립", "단독/다가구", "다세대"}
# 관리비 세부표시(정액 10만원↑ 비목구분) 의무 대상 = 공동주택·오피스텔(국토부 고시).
# 단독/다가구·상가·사무실·지식산업센터·토지 등은 제외(표시 의무 대상 아님).
_MGMT_DISPLAY_TYPES = {"아파트", "오피스텔", "빌라/연립", "빌라단지-연립", "다세대"}


def audit_listing(f: dict, *, cp_autofilled: bool = False) -> dict:
    """매물 1건 점검. f = listings + complexes + 상세추출 + is_saengsuk 병합 dict.

    cp_autofilled=True(단지형 아파트·오피): 면적·총층·사용승인·주차가 콘텐츠제공자(CP)
    자동입력이라 수기 오류가 없음 → 해당 4항목은 '단지정보 자동입력(확인)'으로 통과 처리.

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
    # 대장 대조 가능 여부: 빌라·단독·다세대는 건축물대장=그 건물 전체라 총층·주차 대조가 유효.
    # 상가·사무실·지식산업센터는 주상복합/대형 복합건물의 저층부라 대장이 전체 동(고층·전체주차)을
    # 가리켜, 광고(해당 상가부분)와 직접 대조하면 오탐(예: 단지내상가 총층 2 vs 대장 59). → 대조 생략.
    led_comparable = rtype in _RESIDENTIAL_TYPES

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

    # ② 면적(전용㎡) — 단지형=CP자동입력 / 비단지=건축물대장 전유면적 대조
    if cp_autofilled:
        add(2, "면적(전용㎡)", "통과", "단지정보 자동입력(확인)")
    elif not _has(f.get("area_exclusive")):
        add(2, "면적(전용㎡)", "위반", "전용면적(㎡) 미표시")
    else:
        expos = f.get("led_expos_areas")        # 대장 전유면적 목록(비단지 온디맨드)
        a = _to_float(f.get("area_exclusive"))
        if expos and a:
            tol = max(1.0, a * 0.03)             # ±1㎡ 또는 ±3%
            if any(abs(a - e) <= tol for e in expos):
                add(2, "면적(전용㎡)", "통과", "건축물대장 전유면적 일치")
            else:
                near = "/".join(f"{e:g}" for e in expos[:6])
                add(2, "면적(전용㎡)", "주의",
                    f"광고 전용 {a:g}㎡ ≠ 건축물대장 전유({near}㎡) — 면적 확인")
        else:
            add(2, "면적(전용㎡)", "통과")        # 대장 전유 조회불가/대형지번 → 표시여부만

    # ③ 가격
    add(3, "가격", "통과" if _has(f.get("price")) else "위반",
        "" if _has(f.get("price")) else "거래예정금액 미표시")

    # ④ 종류 + 위반건축물·미등기 표시 (네이버 기준 — 건축물대장 API엔 위반건축물 필드 없음)
    viol_b = f.get("violation_building") == "Y"
    unreg = f.get("unregistered_building") == "Y"
    if not _has(rtype):
        add(4, "중개대상물 종류", "위반", "종류 미표시")
    elif viol_b and unreg:
        add(4, "중개대상물 종류", "주의", "위반건축물·미등기 — 광고에 명시 필요")
    elif viol_b:
        add(4, "중개대상물 종류", "주의", "위반건축물 — 광고에 '위반건축물' 명시 필요")
    elif unreg:
        add(4, "중개대상물 종류", "주의", "미등기 건물 — 광고에 명시 필요")
    else:
        add(4, "중개대상물 종류", "통과")

    # ⑤ 거래형태
    add(5, "거래형태", "통과" if _has(f.get("trade_type")) else "위반",
        "" if _has(f.get("trade_type")) else "거래형태 미표시")

    # ⑥ 총 층수 (단지형=CP자동입력+대장값표시 / 비단지=대장 대조)
    led_tf = f.get("led_total_floor")
    if cp_autofilled:
        if led_tf:
            note = f"CP 자동입력(광고 {f.get('total_floor')}층) · 건축물대장 {_fmt_led(led_tf)}층"
            add(6, "총 층수", "통과",
                note + ("" if not _ledger_mismatch(f.get("total_floor"), led_tf) else " (동별 상이)"))
        else:
            add(6, "총 층수", "통과", "CP 자동입력(확인)")
    elif not _has(f.get("total_floor")):
        note = f" → 건축물대장 기준 총 {_fmt_led(led_tf)}층" if (led_tf and led_comparable) else ""
        add(6, "총 층수", "위반", "광고에 총 층수 미표시" + note)
    elif led_comparable and _ledger_mismatch(f.get("total_floor"), led_tf):
        add(6, "총 층수", "주의", f"광고 총층({f.get('total_floor')}) ≠ 건축물대장 기준 {_fmt_led(led_tf)}층")
    else:
        add(6, "총 층수", "통과", f"건축물대장 기준 {_fmt_led(led_tf)}층 일치" if (led_tf and led_comparable) else "")

    # ⑦ 입주가능일 — 미표시만 위반. '즉시입주'+'협의가능' 동시표기는 실무상 허용(주의 안 함).
    if not _has(f.get("movein_type")):
        add(7, "입주가능일", "위반", "입주가능일 미표시")
    else:
        add(7, "입주가능일", "통과")

    # ⑧ 방수/욕실수 (욕실수는 전 유형 필수, 방수는 주택·준주택)
    has_room, has_bath = _has(f.get("room_count")), _has(f.get("bathroom_count"))
    residential = (not saengsuk) and (
        rtype in _RESIDENTIAL_TYPES or f.get("real_estate_type") in ("APT", "OPST"))
    if residential:
        ok = has_room and has_bath
        add(8, "방수/욕실수", "통과" if ok else "위반",
            "" if ok else ("방 수 미표시" if has_bath else "방 수·욕실 수 미표시"))
    else:
        add(8, "욕실수", "통과" if has_bath else "위반",
            "" if has_bath else "욕실 수 미표시(필수)")

    # ⑨ 사용승인일 (대장 대조 — 오입력 적발. 단지형은 동별 집합 매칭)
    ua = f.get("use_approve_ymd")
    led_ua = f.get("led_use_apr_day")
    if cp_autofilled:
        if led_ua:
            add(9, "사용승인일", "통과",
                f"CP 자동입력(광고 {_fmt_ymd(ua) or '-'}) · 건축물대장 기준 {_fmt_led_ymd(led_ua)}")
        else:
            add(9, "사용승인일", "통과", "CP 자동입력(확인)")
    elif not _has(ua):
        note = f" → 건축물대장 기준 {_fmt_led_ymd(led_ua)}" if led_ua else ""
        add(9, "사용승인일", "위반", "광고에 사용승인일 미표시" + note)
    elif _ledger_mismatch(ua, led_ua, digits=True):
        add(9, "사용승인일", "주의",
            f"광고({_fmt_ymd(ua)}) ≠ 건축물대장 기준 {_fmt_led_ymd(led_ua)} — 오입력 확인")
    else:
        add(9, "사용승인일", "통과", f"건축물대장 기준 {_fmt_led_ymd(led_ua)} 일치" if led_ua else "")

    # ⑩ 주차 (대장 기준: 대장에 주차 없으면 '주차불가' 표시해야)
    led_pk = f.get("led_parking")              # 대장 총주차(None=미수집)
    pk_possible = f.get("parking_possible")    # 네이버 parkingPossibleYN
    if cp_autofilled:
        add(10, "주차", "통과", "CP 자동입력(확인)")
    elif led_comparable and led_pk is not None and (led_pk or 0) == 0 and pk_possible == "Y":
        add(10, "주차", "위반", "건축물대장상 주차대수 없음 → '주차불가' 표시 필요(대장 기준)")
    elif not _has(f.get("parking_count")):
        # 상가·사무실 등(led_comparable=False)은 대장 주차가 전체 동 값이라 참고표시 생략
        add(10, "주차", "위반", "광고에 주차대수 미표시"
            + (f" → 건축물대장 기준 총 {led_pk}대" if (led_pk and led_comparable) else ""))
    else:
        # 정확한 대수 대조는 같은 지번 다동 모호성으로 생략(표시여부·주차불가만 점검)
        add(10, "주차", "통과", f"건축물대장 총주차 {led_pk}대" if (led_pk and led_comparable) else "")

    # ⑪ 관리비 — 비목별 금액은 임대인(중개의뢰인) 고지에 의존하고, 미고지·확인불가 시
    #    표시 의무가 면제된다(국토부 고시 예외). 우리는 고지 여부를 알 수 없어 비목 미표시를
    #    '위반'으로 단정하지 않는다 → 위반 없음. 관리비 항목 입력 여부 + 이상치(오입력)만 점검.
    cost = f.get("monthly_management_cost")
    aci = f.get("admin_cost_info") or {}
    mgmt_target = (f.get("real_estate_type") in ("APT", "OPST", "ABYG", "OBYG", "JGC")
                   or rtype in _MGMT_DISPLAY_TYPES)
    ci = None
    if cost is not None and str(cost).strip() not in ("", "None"):
        try:
            ci = int(cost)
        except (ValueError, TypeError):
            ci = -1
    # administrationCostInfo(부과방식·내역·확인불가)나 정액값이 입력돼 있으면 관리비 항목 표시됨.
    has_cost_info = bool(aci.get("chargeCodeType") or aci.get("fixedFeeDetails")
                         or aci.get("chargeInputContent")) or (ci is not None and ci >= 0)
    if ci is not None and ci > 0 and (ci >= 2_000_000 or ci <= 1000):
        add(11, "관리비", "주의", f"관리비 이상치({ci:,}원) — 오입력 의심")
    elif has_cost_info:
        add(11, "관리비", "통과", "관리비 항목 표시됨(비목 세부는 임대인 고지 의존)")
    elif not mgmt_target:
        add(11, "관리비", "통과", "관리비 표시 의무 대상 아님(주택·오피스텔만)")
    else:
        add(11, "관리비", "주의", "관리비 미표기 — 광고에 관리비 항목 입력 권장")

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
