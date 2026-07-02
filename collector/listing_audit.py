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


def _ymd_mismatch(val, led) -> bool:
    """사용승인일 대조 — 자릿수 다르면(예: 광고 19911130 vs 대장 199111) 짧은 쪽 길이만큼
    앞자리(연월) 비교. '위반' 판정에 쓰이므로 형식 차이 오탐을 원천 차단. led는 스칼라
    또는 동별 집합(어느 동과도 안 맞을 때만 불일치)."""
    if led is None or led == "" or led == []:
        return False

    def digits(x):
        return "".join(c for c in str(x or "") if c.isdigit())

    v = digits(val)
    if not v:
        return False
    opts = led if isinstance(led, (list, set, tuple)) else [led]
    norms = [digits(x) for x in opts if digits(x)]
    if not norms:
        return False
    for lv in norms:
        n = min(len(v), len(lv))
        if n >= 6 and v[:n] == lv[:n]:      # 최소 연월(6자리) 이상 일치하면 같은 날짜로 인정
            return False
    return True


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
# 건축물대장 주용도가 이 중 하나면 '고층 주거/숙박 타워'(상가는 그 저층부) → 상가·사무실 총층·
# 주차 대조 부적합(아파트 단지내상가·주상복합 59층). 저층 유형(단독·연립·다세대)은 제외 —
# 상가주택·저층상가는 대장=그 독립건물이라 총층 대조가 유효하므로 skip-list에 넣지 않는다.
_RESIDENTIAL_LEDGER_PURPS = ("공동주택", "아파트", "오피스텔", "숙박", "기숙사", "도시형생활")
# 주거용 유형 판별 — 상세(det)는 '빌라', DB는 '빌라/연립'처럼 표기가 달라 정확일치가 놓친다.
# 부분일치로 흡수. _MGMT_KEYWORDS 는 관리비 표시대상(단독/다가구 제외 — 고시상 단독주택 예외).
_RESIDENTIAL_KEYWORDS = ("아파트", "오피스텔", "빌라", "연립", "다세대", "단독", "다가구")
_MGMT_KEYWORDS = ("아파트", "오피스텔", "빌라", "연립", "다세대")


def _is_residential(rtype) -> bool:
    return bool(rtype) and any(k in str(rtype) for k in _RESIDENTIAL_KEYWORDS)


def _purps_cat(purps) -> str:
    """건축물대장 용도 → 대분류(주거/업무/상업/숙박/기타)."""
    p = str(purps or "")
    if any(k in p for k in ("주택", "공동주택", "다세대", "연립", "다가구", "아파트", "기숙사")):
        return "주거"
    if "숙박" in p:
        return "숙박"
    if "업무" in p or "사무" in p:
        return "업무"
    if any(k in p for k in ("근린생활", "판매", "소매", "점포", "음식", "위락", "운동", "문화",
                            "집회", "의료", "교육", "학원", "세차", "제조", "공장", "창고")):
        return "상업"
    return "기타"


def _listing_cat(rtype, real_estate_type) -> str:
    """매물 유형 → 대분류(주거/업무/상업/기타). 층별 용도 대조용."""
    if _is_residential(rtype) or real_estate_type in ("APT", "OPST", "ABYG", "OBYG", "JGC"):
        return "주거"
    r = str(rtype or "")
    if "사무" in r or "지식산업" in r:
        return "업무"
    if any(k in r for k in ("상가", "점포", "판매", "근린")):
        return "상업"
    return "기타"


def _floor_summary(floors) -> str:
    """층별 용도 목록 → 요약(용도×지상지하별 층 묶음). 예 '근린생활(1~3층)·주택(4~5층)'."""
    seq = sorted(floors, key=lambda z: (0 if z.get("flr_gb") == "지상" else 1, z.get("flr_no") or 0))
    groups: dict = {}
    order: list = []
    for x in seq:
        key = (x.get("purps") or "?", x.get("flr_gb") or "")   # 지상/지하 분리(범위 안 섞임)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(x.get("flr_no_nm") or "")
    out = []
    for key in order[:7]:
        u = list(dict.fromkeys(groups[key]))
        label = u[0] if len(u) == 1 else (f"{u[0]}~{u[-1]}" if len(u) > 2 else "/".join(u))
        out.append(f"{key[0]}({label})")
    return " · ".join(out)


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
    # 대장 대조 가능 여부:
    #  · 빌라·단독·다세대 = 대장이 그 건물 전체 → 대조 유효.
    #  · 상가·사무실·지산 = 대장 주용도로 판별. 주거/숙박 타워(주상복합·단지내상가)면 대장이
    #    전체 동(예 59층·주차1302)을 가리켜 광고(상가 저층부)와 대조시 오탐 → 생략. 근린생활·
    #    판매·업무 등 상업용 대장이면 그 상가건물이 맞으므로 대조 유지(독립 근린상가 등 살림).
    _led_purps = f.get("led_main_purps") or ""
    if _is_residential(rtype):
        led_comparable = True
    else:
        led_comparable = not any(k in _led_purps for k in _RESIDENTIAL_LEDGER_PURPS)

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
        add(6, "총 층수", "위반",
            f"광고 총층({f.get('total_floor')}) ≠ 건축물대장 기준 {_fmt_led(led_tf)}층 — 공부와 불일치")
    else:
        add(6, "총 층수", "통과", f"건축물대장 기준 {_fmt_led(led_tf)}층 일치" if (led_tf and led_comparable) else "")

    # ⑦ 입주가능일 — 미표시만 위반. '즉시입주'+'협의가능' 동시표기는 실무상 허용(주의 안 함).
    if not _has(f.get("movein_type")):
        add(7, "입주가능일", "위반", "입주가능일 미표시")
    else:
        add(7, "입주가능일", "통과")

    # ⑧ 방수/욕실수 — 주거용(주택·오피스텔) 표시 의무. 상가·사무실·지산·토지·생숙 등 비주거는 제외.
    residential = (not saengsuk) and (
        _is_residential(rtype) or f.get("real_estate_type") in ("APT", "OPST"))
    if residential:
        has_room, has_bath = _has(f.get("room_count")), _has(f.get("bathroom_count"))
        ok = has_room and has_bath
        add(8, "방수/욕실수", "통과" if ok else "위반",
            "" if ok else ("방 수 미표시" if has_bath else "방 수·욕실 수 미표시"))
    else:
        add(8, "방수/욕실수", "통과", "비주거 — 방수·욕실수 표시 의무 대상 아님")

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
    elif _ymd_mismatch(ua, led_ua):
        add(9, "사용승인일", "위반",
            f"광고({_fmt_ymd(ua)}) ≠ 건축물대장 기준 {_fmt_led_ymd(led_ua)} — 공부와 불일치")
    else:
        add(9, "사용승인일", "통과", f"건축물대장 기준 {_fmt_led_ymd(led_ua)} 일치" if led_ua else "")

    # ⑩ 주차 — 세부기준상 '주차대수(공부 기준 숫자)' 명시가 원칙(전문가 확인: '가능'만은
    #    신고 시 적발 대상). ①공부상 0인데 가능/대수 표시 = 공부 불일치 위반 ②'가능'만
    #    표시(대수 없음) = 위반 ③'불가' 표시 = 통과 ④정보 전무 = 위반.
    led_pk = f.get("led_parking")              # 대장 총주차(None=미확보, 0=공부상 없음)
    pk_possible = f.get("parking_possible")    # 네이버 parkingPossibleYN
    _led_note = f" (건축물대장 기준 총 {led_pk}대)" if (led_pk and led_comparable) else ""
    if cp_autofilled:
        add(10, "주차", "통과", "CP 자동입력(확인)")
    elif pk_possible == "N":
        add(10, "주차", "통과", "주차 불가로 표시됨")     # 주차불가 명시 = 유효한 표시
    elif led_comparable and led_pk == 0 and (pk_possible == "Y" or _has(f.get("parking_count"))):
        add(10, "주차", "위반",
            "건축물대장상 주차대수 0 — '주차 가능' 표시는 공부와 불일치(주차불가로 표시 필요)")
    elif not _has(f.get("parking_count")):
        # 상가·사무실 등(led_comparable=False)은 대장 주차가 전체 동 값이라 참고표시 생략.
        if pk_possible == "Y":
            add(10, "주차", "위반",
                "주차 '가능'만 표시 — 주차대수(건축물대장 기준 숫자) 명시 필요" + _led_note)
        else:
            add(10, "주차", "위반", "광고에 주차 정보 미표시" + _led_note)
    else:
        # 정확한 대수 대조는 같은 지번 다동 모호성으로 생략(표시여부·공부0 불일치만 점검)
        add(10, "주차", "통과", f"건축물대장 총주차 {led_pk}대" if (led_pk and led_comparable) else "")

    # ⑪ 관리비 — 비목별 금액은 임대인(중개의뢰인) 고지에 의존하고, 미고지·확인불가 시
    #    표시 의무가 면제된다(국토부 고시 예외). 우리는 고지 여부를 알 수 없어 비목 미표시를
    #    '위반'으로 단정하지 않는다 → 위반 없음. 관리비 항목 입력 여부 + 이상치(오입력)만 점검.
    cost = f.get("monthly_management_cost")
    aci = f.get("admin_cost_info") or {}
    mgmt_target = (f.get("real_estate_type") in ("APT", "OPST", "ABYG", "OBYG", "JGC")
                   or any(k in str(rtype) for k in _MGMT_KEYWORDS))
    ci = None
    if cost is not None and str(cost).strip() not in ("", "None"):
        try:
            ci = int(cost)
        except (ValueError, TypeError):
            ci = -1
    # administrationCostInfo(부과방식·내역·확인불가)나 정액값이 입력돼 있으면 관리비 항목 표시됨.
    has_cost_info = bool(aci.get("chargeCodeType") or aci.get("fixedFeeDetails")
                         or aci.get("chargeInputContent")) or (ci is not None and ci >= 0)
    # 이상치 상한: 주거용 2백만(세대 관리비) / 비주거 2천만(통건물·대형상가는 수백만이 정상).
    _hi = 2_000_000 if residential else 20_000_000
    if ci is not None and ci > 0 and (ci >= _hi or ci <= 1000):
        add(11, "관리비", "주의", f"관리비 이상치({ci:,}원) — 오입력 의심")
    elif has_cost_info:
        add(11, "관리비", "통과", "관리비 항목 표시됨(비목 세부는 임대인 고지 의존)")
    elif not mgmt_target:
        add(11, "관리비", "통과", "관리비 표시 의무 대상 아님(주택·오피스텔만)")
    else:
        add(11, "관리비", "주의", "관리비 미표기 — 광고에 관리비 항목 입력 권장")

    # ⑫ 방향 — 방향 자체는 표시 의무. '방향 기준(거실/안방 등) 함께표시'는 주거용건축물만
    #    (비주거는 주된 출입구 방향으로 표시하면 됨 → 기준 미표시 주의 안 함).
    if not _has(f.get("direction")):
        add(12, "방향", "위반", "방향 미표시")
    elif residential and not _has(f.get("direction_base")):
        add(12, "방향", "주의", "방향 기준(거실/안방 등) 미표시")
    else:
        add(12, "방향", "통과")

    # ⑬ 층별 용도(건축물대장 층별개요) — 혼합건물 정밀 점검. 매물 해당층 실제 용도 대조.
    #    주거↔비주거 불일치만 '주의'(용도위반 의심·광고오류). 층별 용도 요약은 항상 표시.
    floors = f.get("led_floors")
    if floors:
        summary = _floor_summary(floors)
        try:
            cflr = int(f.get("corresponding_floor")) if f.get("corresponding_floor") not in (None, "") else None
        except (ValueError, TypeError):
            cflr = None
        matched = [x for x in floors if x.get("flr_gb") == "지상" and x.get("flr_no") == cflr] if cflr else []
        lcat = _listing_cat(rtype, f.get("real_estate_type"))
        fcats = {_purps_cat(x.get("purps")) for x in matched}
        mpur = "/".join(dict.fromkeys(x.get("purps") for x in matched if x.get("purps")))
        if not matched or lcat == "기타" or not fcats:
            add(13, "층별 용도", "통과", f"건축물대장 층별 — {summary}")
        elif lcat == "주거" and "주거" not in fcats:
            add(13, "층별 용도", "주의",
                f"광고는 주거인데 건축물대장 {cflr}층 용도는 ‘{mpur}’({'/'.join(fcats)}) — 용도 확인 필요 · {summary}")
        elif lcat in ("상업", "업무") and fcats == {"주거"}:
            add(13, "층별 용도", "주의",
                f"광고는 {lcat}인데 건축물대장 {cflr}층은 ‘{mpur}’(주거) — 용도 확인 필요 · {summary}")
        else:
            add(13, "층별 용도", "통과", f"{cflr}층 용도 ‘{mpur}’ · {summary}")

    # 토지·임야는 건축물이 아님 — 명시사항은 소재지·면적·가격·종류·거래형태뿐.
    # 건축물 전용 항목(층·총층·입주·방욕·사용승인·주차·관리비·방향)은 해당 없음 처리(오탐 방지).
    if any(k in str(rtype) for k in ("토지", "임야")):
        _land_na = {1, 6, 7, 8, 9, 10, 11, 12, 13}
        for x in findings:
            if x["no"] in _land_na and x["item"] != "소재지·지번/동" and x["status"] != "통과":
                x["status"], x["reason"] = "통과", "토지 — 건축물 항목 해당 없음"

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
