"""중개대상물 인터넷 표시·광고 점검 엔진 (한국부동산원 체크리스트 기준).

순수 판정 로직 — 매물 통합필드(dict) 입력 → 항목별 findings 반환. DB/네트워크 없음.
중개사 라운지 '매물점검' 기능에서 사용. 상세필드는 collector.article_detail 로 확보.

판정: 통과 / 주의(권장·조건부) / 위반(과태료 위험: 필수항목 누락 등).
"""
from __future__ import annotations


def is_saengsuk(complex_name: str | None) -> bool:
    """네이버 단지명 표기 기반 생활숙박시설 판정(1순위 신호). [[naverreal-building-ledger]]"""
    return bool(complex_name) and "생활숙박" in complex_name


def _has_parking(v) -> bool:
    """주차대수 표시 여부. _has 와 달리 **0 을 유효한 표시로 본다**.

    _has 는 0 을 미표시로 보는데(면적·층·방수에는 맞다) 주차대수는 다르다.
    '0대'는 '주차 없음'을 밝힌 것이라 세부기준이 요구하는 표시를 충족한다.
    실측: 을지로3가 빌딩 2648738735 — 네이버 parkingCount=0, 상세설명 '주차대수: 0대',
    대장도 0대인데 '광고에 주차 정보 미표시' 위반으로 떴다(2026-10-08 민원).
    """
    if v is None:
        return False
    return str(v).strip() not in ("", "-", "None")


def _has(v) -> bool:
    """표시값 존재 여부(빈값·'-'·0·None 은 미표시로 간주)."""
    return v is not None and str(v).strip() not in ("", "-", "0", "None")


def _fmt_manwon(v) -> str:
    """만원 단위 숫자 → '1억 2,000만원' 표기(융자금 사유 문구용)."""
    try:
        n = int(float(v))
    except (ValueError, TypeError):
        return str(v)
    if n >= 10000:
        eok, man = divmod(n, 10000)
        return f"{eok}억" + (f" {man:,}만원" if man else "")
    return f"{n:,}만원"


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
    # 광고 사용승인일이 '일=00'(YYYYMM00 — 년·월만 표기, 일 미상)이면 년월까지만 대조한다.
    # 대장 일자와 '일'만 다른 것을 '공부 불일치'로 오판하지 않기 위함(년월이 틀리면 여전히
    # 걸린다). 기존 '자릿수 다르면 짧은 쪽까지' 규칙과 동일한 취지(6자리 년월 표기와 일관).
    if len(v) == 8 and v[6:8] == "00":
        v = v[:6]
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
_RESIDENTIAL_TYPES = {"아파트", "오피스텔", "빌라/연립", "빌라단지-연립", "단독/다가구", "다세대", "방", "원룸"}
# 관리비 세부표시(정액 10만원↑ 비목구분) 의무 대상 = 공동주택·오피스텔(국토부 고시).
# 단독/다가구·상가·사무실·지식산업센터·토지 등은 제외(표시 의무 대상 아님).
_MGMT_DISPLAY_TYPES = {"아파트", "오피스텔", "빌라/연립", "빌라단지-연립", "다세대"}
# (구)타워 대조 skip-list는 폐지 — 상가동 스왑(_audit_nonresi_one) + '전체 총층이 정답값'
# 기준(전문가 확인)으로 대체. 대장 대조는 항상 수행.
# 주거용 유형 판별 — 상세(det)는 '빌라', DB는 '빌라/연립'처럼 표기가 달라 정확일치가 놓친다.
# 부분일치로 흡수. _MGMT_KEYWORDS 는 관리비 표시대상(단독/다가구 제외 — 고시상 단독주택 예외).
_RESIDENTIAL_KEYWORDS = ("아파트", "오피스텔", "빌라", "연립", "다세대", "단독", "다가구", "원룸")
_MGMT_KEYWORDS = ("아파트", "오피스텔", "빌라", "연립", "다세대")


def _is_residential(rtype) -> bool:
    return bool(rtype) and any(k in str(rtype) for k in _RESIDENTIAL_KEYWORDS)


def _lacks_room_fields(rtype) -> bool:
    """네이버 '건물'(통건물) 유형은 입력 폼에 방 수·방향 기준 칸이 아예 없다.

    실측(2026-10-23) 표본 26건 전부 두 값이 비어 있었고, 같은 DB의 '상가주택' 14건은
    14건 모두 채워져 있었다 — 중개사가 안 쓴 게 아니라 쓸 칸이 없는 것이다. 고칠 수
    없는 항목은 지적하지 않는다(상업용 방향을 점검에서 뺀 2026-10-13 결정과 같은 기준).
    욕실 수는 '건물'에도 들어오므로 그대로 본다.
    """
    return str(rtype or "").strip() == "건물"


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


def _mixed_home(f) -> bool:
    """상가주택·건물처럼 한 동에 상가와 주거가 섞인 매물이 '주거'인가.

    광고가 가리키는 층이 있으면(해당층 숫자) 그 층의 대장 용도로 가르고,
    통건물(해당층 '-')이면 층별개요에 주택이 하나라도 있으면 주거로 본다(사용자 결정).
    실측(2026-10-12) 2650379876: 1층 일반음식점 + 2~4층 다가구주택, 광고 방 16·욕실 12
    — 통건물 매매라 주거가 섞여 있고 중개사도 방 수를 적었다.
    """
    floors = f.get("led_floors") or []
    if not floors:
        return False
    home = lambda r: (_purps_cat(r.get("purps")) == "주거"
                      or _purps_cat(r.get("etc")) == "주거")
    cf = str(f.get("corresponding_floor") or "").strip()
    if cf.isdigit():
        same = [r for r in floors
                if r.get("flr_gb") == "지상" and str(r.get("flr_no")) == str(int(cf))]
        return any(home(r) for r in same)
    return any(home(r) for r in floors)          # 통건물 — 주택이 하나라도 있으면 주거


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
    dong_name, is_saengsuk, movein_negotiable, movein_ymd, finance_price.
    """
    findings: list[dict] = []

    def add(no, item, status, reason=""):
        findings.append({"no": no, "item": item, "status": status, "reason": reason})

    saengsuk = bool(f.get("is_saengsuk"))
    rtype = f.get("realestate_type_name") or f.get("real_estate_type")
    # 대장 대조 — 항상 수행(전문가 확인 기준): 광고 총층은 '그 매물이 속한 건물 전체' 기준.
    #  · 단지내상가에 별도 상가동이 있으면 상위(_audit_nonresi_one)에서 대장을 상가동으로 교체.
    #  · 상가동이 없는 복합타워(예: 숙박59층 저층 상가)는 타워 전체 총층이 정답값 →
    #    광고가 상가부(2층)만 적었으면 공부 불일치 위반이 맞음.
    led_comparable = True
    # 단지내상가 오탐 방지: 상가·사무실 매물인데 대장이 '이 상가를 담지 않은 건물'을 가리키면
    # (단지내상가의 상가동은 대개 다른 지번이라 상위의 상가동 스왑도 실패) ⑥⑨⑩ 대장 대조를
    # 생략한다 — 아파트동/오피스텔/업무타워 값으로 위반 오판을 막는다.
    #  · 판별: 층별개요에 상업/업무/숙박층이 하나라도 있으면 그 상가는 이 건물 안에 있다
    #    (주상복합 저층 근생·standalone 상가/사무실) → 그대로 대조(복합타워 규칙 유지).
    #  · 층별개요에 상업층이 없고 + (대장 주용도가 비상업 건물[공동주택·오피스텔·숙박 등]
    #    이거나 building_name 이 네이버 placeholder '단지내상가')면 → 대조 생략.
    #    ('단지내상가' placeholder 는 업무시설 타워 등에 오매칭돼도 커버 — 단지내상가는 상가동 별도)
    #  · 상가동 스왑이 성공(led_swapped)했으면 led 는 이미 올바른 상가동이므로 그대로 대조.
    _has_comm_floor = any(_purps_cat(x.get("purps")) in ("상업", "업무", "숙박")
                          for x in (f.get("led_floors") or []))
    _resi_bld = any(k in (f.get("led_main_purps") or "") for k in
                    ("공동주택", "아파트", "연립주택", "다세대주택", "오피스텔",
                     "숙박", "기숙사", "도시형생활", "준주택"))
    if (not cp_autofilled
            and not f.get("led_swapped")
            and _listing_cat(rtype, f.get("real_estate_type")) in ("상업", "업무")
            and not _has_comm_floor
            and (_resi_bld or f.get("is_danji_shop"))):
        led_comparable = False

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
            elif _listing_cat(rtype, f.get("real_estate_type")) in ("업무", "상업") \
                    and a <= max(expos) * 1.03:
                # 사무실·상가는 한 전유호를 여러 임차인에게 **쪼개 임대**하는 것이 보통이라
                # 광고 전용면적이 전유면적과 같을 이유가 없다. 실측(2026-10-07): 트윈트리빌딩
                # A동 301호 전유 850.56㎡ 중 473㎡만 임대, 전용률(51.8%)은 301호와 소수점
                # 넷째 자리까지 일치 — 정상 광고인데 '불일치'로 잡혔다.
                # 전유보다 **큰** 경우만 잡는다. 그건 쪼개서는 나올 수 없는 수치다.
                add(2, "면적(전용㎡)", "통과", "분할 임대 가능 유형 — 대장 전유 범위 안")
            else:
                # 가장 '작은' 6개가 아니라 광고 면적에 **가까운** 6개를 보여 준다.
                # 작은 순으로 보여 주면 473㎡ 사무실에 9.8㎡ 근생을 들이대는 꼴이 된다.
                near = "/".join(f"{e:g}" for e in sorted(expos, key=lambda e: abs(e - a))[:6])
                over = " (대장 전유 최대값보다 큼)" if a > max(expos) * 1.03 else ""
                add(2, "면적(전용㎡)", "주의",
                    f"광고 전용 {a:g}㎡ ≠ 건축물대장 전유(가까운 값 {near}㎡){over} — 면적 확인")
        else:
            add(2, "면적(전용㎡)", "통과")        # 대장 전유 조회불가/대형지번 → 표시여부만

    # ③ 가격
    # 월세(B2)·단기임대(B3)는 보증금이 없어도(무보증) 월세가 표시돼 있으면 거래예정금액을 밝힌 것이다.
    # 실측(2026-11-12) 동빙고동 빌라 2657867143: 무보증 월세 550만원인데 보증금 칸만 보고 위반으로 떴다.
    _rent_ok = f.get("trade_type") in ("B2", "B3") and _has(f.get("rent_price"))
    _price_ok = _has(f.get("price")) or _rent_ok
    add(3, "가격", "통과" if _price_ok else "위반",
        ("무보증 월세 — 월세 표시" if _rent_ok and not _has(f.get("price")) else "")
        if _price_ok else "거래예정금액 미표시")

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
        # 광고 총층이 공부(대장)보다 '큰' 역전은 축소 위반과 성격이 다르다 — 대개 대장이 더
        # 작은 상가동/근생동에 오매칭(예: 21층 건물인데 옆 2층 근생동 대장)됐거나 광고 과다
        # 표기다. 하드 위반이 아니라 확인용 주의로 낮춘다.
        _adf = _to_float(f.get("total_floor"))
        _leds = led_tf if isinstance(led_tf, (list, set, tuple)) else [led_tf]
        _maxled = max((x for x in (_to_float(y) for y in _leds) if x is not None), default=None)
        if _adf is not None and _maxled is not None and _adf > _maxled:
            add(6, "총 층수", "주의",
                f"광고 총층({f.get('total_floor')})이 건축물대장({_fmt_led(led_tf)}층)보다 큼 — "
                f"대장 매칭(상가동 오인) 또는 광고 과다표기 확인 필요")
        else:
            add(6, "총 층수", "위반",
                f"광고 총층({f.get('total_floor')}) ≠ 건축물대장 기준 {_fmt_led(led_tf)}층 — 공부와 불일치")
    else:
        add(6, "총 층수", "통과", f"건축물대장 기준 {_fmt_led(led_tf)}층 일치" if (led_tf and led_comparable) else "")

    # ⑦ 입주가능일 — 「중개대상물의 표시·광고 명시사항 세부기준」 제6조 제7호.
    #    본문 : 실제 입주가 가능한 **세부 날짜**를 표시하되, ‘즉시입주’ 문구로 갈음 가능.
    #    단서 : **거래당사자가 합의에 따라 조정할 수 있는 경우에 한해** 세부 날짜를
    #           입주가능 월의 초순·중순·하순으로 표시 가능.
    #    → ‘협의가능’은 **초/중/하순 표기를 허용받기 위한 조건**이지 즉시입주에 붙는
    #      수식이 아니다. 그래서 ‘즉시입주 + 협의가능’은 어느 허용 형식도 아니다.
    #
    #    판정 잣대는 조문 형식론보다 **‘소비자가 입주 시점을 알 수 있는가’** 가 단단하다.
    #    국토부 수시모니터링(접수 2,257건 → 적발 681건, 명시의무 위반 411건)은 입주일을
    #    ‘협의 가능’ 류로 적은 것을 명시의무 위반으로 봤고, 같은 사례에서 주차의 ‘가능’만
    #    표시한 것도 함께 걸었다 — 주차 쪽은 이 엔진이 ⑩에서 이미 위반으로 잡는 항목이다.
    #    ‘즉시입주 협의 가능’은 지금인지 나중인지 갈리지 않아 같은 계열이다. 반면
    #    ‘2026년 12월 중순 협의 가능’은 시점이 특정돼 있어 불분명하지 않다.
    #    (단서의 조건은 ‘합의로 조정 가능한 상황인가’라는 **사실**이지 ‘협의가능’을 적으라는
    #     요구가 아니다. 그래서 초/중/하순에 협의가능이 없다고 위반으로 몰면 안 된다 —
    #     체크 안 함은 사실의 부재가 아니라 정보의 부재이고, 우리는 그 사실을 알 수 없다.)
    #
    #    ★ 판정 대상은 **광고에 실제로 찍히는 문자열**이다. 네이버는 moveInTypeName 을
    #      그대로 보여주지 않는다 — moveInPossibleYmd 가 8자리 날짜면 **그 날짜**를 찍고,
    #      'NOW' 일 때만 ‘즉시입주’ 로 찍는다. moveInTypeName='즉시입주' 는 '날짜 미지정'을
    #      뜻하는 내부 코드(MV001)일 뿐이다. fin.land 광고 화면 실측(2026-10-13):
    #        MV001 + NOW      + 협의 → "즉시입주 협의 가능"          ← 이것만 위반
    #        MV001 + NOW      + 없음 → "즉시입주"                     허용(본문 후단)
    #        MV001 + 20261124 + 협의 → "2026년 11월 24일 협의 가능"   허용(세부 날짜)
    #        MV001 + 20270129 + 없음 → "2027년 01월 29일"             허용(본문 원칙)
    #        MID              + 협의 → "2026년 12월 중순 협의 가능"   허용(단서)
    #      moveInTypeName 만 보고 판정하면 날짜가 멀쩡히 찍힌 광고까지 잡는다(오탐).
    #    ⚠ moveInDiscussionPossibleYN 은 'Y' 가 아니라 '협의가능' 문자열로 온다.
    _mv = str(f.get("movein_type") or "")
    _mv_nego = str(f.get("movein_negotiable") or "").strip() in ("Y", "협의가능")
    _mv_ymd = str(f.get("movein_ymd") or "").strip()
    _mv_dated = len(_mv_ymd) == 8 and _mv_ymd.isdigit()      # 광고에 날짜가 찍힌다
    _shows_imm = ("즉시" in _mv) and not _mv_dated           # 광고에 ‘즉시입주’로 찍힌다
    if not _has(_mv):
        add(7, "입주가능일", "위반", "입주가능일 미표시")
    elif _shows_imm and _mv_nego:
        add(7, "입주가능일", "위반",
            "광고에 ‘즉시입주 협의 가능’으로 표시돼 소비자가 입주 시점을 알 수 없습니다 — "
            "불분명한 표현이라 명시의무 위반(과태료)입니다. 바로 들어갈 수 있으면 ‘협의가능’ "
            "체크를 풀어 ‘즉시입주’로만 두고, 날짜를 맞춰 줄 생각이면 입주 가능 월의 "
            "초순·중순·하순을 고르세요")
    else:
        add(7, "입주가능일", "통과")

    # ⑧ 방 수 및 욕실 수 — 고시 제6조제8호 "건축물 현황도 등을 통해 확인한 방 수 및
    #    욕실 수를 표시하여야 한다". ※ 2024-748 개정으로 주택이 아닌 것은 방·욕실 수 표시가
    #    선택이 됐다 — 아래 비주거 분기 참고(아래 10-12 기준 중 비주거 부분은 폐기). 건축물대장엔 화장실 개수 항목이 없어 대조는 불가 → 표시 여부만 본다.
    #
    #    운영 기준(2026-10-12 결정) — **포인트는 욕실(화장실)이다.**
    #      · 주거   : 방·욕실 둘 다 입력해야 통과
    #      · 비주거 : 욕실만 보면 된다. 방 수는 사무실·상가에서 적을 내용이 없어
    #                 아무도 쓰지 않는다(실측 120건 중 사무실·상가·지산 입력 0건).
    #                 욕실 미입력은 위반 — 68%가 적는 항목을 빼먹은 것이다.
    #      · 통건물 : '건물' 유형은 방 수 칸 자체가 없다 → 욕실만 본다(_lacks_room_fields).
    #                 주택이 섞인 통건물이라도 방 수를 요구하면 고칠 수 없는 지적이 된다.
    #      · 욕실 0 : **비주거만** 주의. 아무 생각 없이 0 을 넣는 경우가 대부분이고,
    #                 건물 밖 공용화장실이라 0 이라는 소명도 드물지만 가능하다.
    #                 **주거의 욕실 0 은 위반** — 사람이 사는 집에 화장실 0 개는 없다.
    #    심각도는 위반 > 주의 > 통과 순으로 가린다.
    #
    #    ⚠ 미입력과 0 은 반드시 구분한다. 네이버는 미입력을 '-'(→ None), 실제 0 을
    #    '0'(→ 0)으로 따로 보낸다. _has 는 0 을 미표시로 보므로 여기서는 쓰지 않는다.
    residential = (not saengsuk) and (
        _is_residential(rtype) or f.get("real_estate_type") in ("APT", "OPST"))
    # 상가주택·건물은 한 동에 상가와 주거가 섞인다 — 해당층(통건물이면 전체) 용도로 가른다.
    if not residential and not saengsuk and any(k in str(rtype) for k in ("상가주택", "건물")):
        residential = _mixed_home(f)
    _entered = lambda v: v is not None and str(v).strip() not in ("", "-", "None")
    has_room, has_bath = _entered(f.get("room_count")), _entered(f.get("bathroom_count"))
    bath0 = has_bath and _to_float(f.get("bathroom_count")) == 0
    # 통건물('건물')은 방 수 칸이 없다 — 주거가 섞여 있어도 욕실만 본다(_lacks_room_fields).
    room_required = residential and not _lacks_room_fields(rtype)
    if room_required and not (has_room and has_bath):
        add(8, "방수/욕실수", "위반",
            "방 수 미표시" if has_bath else
            ("욕실 수 미표시" if has_room else "방 수·욕실 수 미표시"))
    elif residential and not has_bath:
        add(8, "방수/욕실수", "위반", "욕실 수(화장실) 미표시")
    elif residential and bath0:
        # 주거는 욕실이 0 일 수 없다 — 비주거의 '0 은 주의'를 여기엔 적용하지 않는다
        # (2026-10-12 결정). 사람이 사는 집에 화장실 0 개는 성립하지 않는다.
        add(8, "방수/욕실수", "위반", "욕실 수 0개 — 주거는 욕실이 0일 수 없습니다")
    elif not residential:
        # 2024-748 개정(2025-01-01 시행): 주택이 아닌 중개대상물은 방 수·욕실 수 표시 의무가 없다(선택).
        # 10-12 운영 기준(비주거 욕실 미입력=위반)은 개정 전 조문 기준이라 폐기(2026-11-13 사용자 확인).
        add(8, "방수/욕실수", "통과", "비주거 — 방·욕실 수는 표시 선택 항목(2024 개정)")
    else:
        add(8, "방수/욕실수", "통과", "" if room_required else "욕실 수 표시됨")

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
        note = f" → 건축물대장 기준 {_fmt_led_ymd(led_ua)}" if (led_ua and led_comparable) else ""
        add(9, "사용승인일", "위반", "광고에 사용승인일 미표시" + note)
    elif led_comparable and _ymd_mismatch(ua, led_ua):
        add(9, "사용승인일", "위반",
            f"광고({_fmt_ymd(ua)}) ≠ 건축물대장 기준 {_fmt_led_ymd(led_ua)} — 공부와 불일치")
    else:
        # ua_source='건축물 정보': 매물 입력값이 아니라 광고 화면의 건축물 정보 블록에서 확인한 값.
        # 중개사가 '난 입력했는데 왜 위반이냐'로 오해하지 않게 어디서 확인했는지 밝힌다.
        src = f.get("ua_source")
        base = f"건축물대장 기준 {_fmt_led_ymd(led_ua)} 일치" if (led_ua and led_comparable) else ""
        if src:
            note = f"광고 ‘{src}’에 {_fmt_ymd(ua)} 노출"
            add(9, "사용승인일", "통과", f"{note} · {base}" if base else note)
        else:
            add(9, "사용승인일", "통과", base)

    # ⑩ 주차 — 세부기준상 '주차대수(공부 기준 숫자)' 명시가 원칙(전문가 확인: '가능'만은
    #    신고 시 적발 대상). ①공부상 0인데 가능/대수 표시 = 공부 불일치 위반 ②'가능'만
    #    표시(대수 없음) = 위반 ③'불가' 표시 = 통과 ④정보 전무 = 위반.
    # 대장 총주차. **0 은 '주차 없음'이 아니라 '미기재'로 본다.**
    # 실측(2026-10-08): 비단지 표본의 15%가 대장 0이었고 그 전부가 광고엔 대수가 있었다.
    #   · 2649138617 — 21층 업무시설, 광고 122대, 표제부 옥내·옥외 자주식·기계식 **네 칸 모두 0**
    #   · 2652683110 — 4층 건물, 광고 8대, 역시 네 칸 모두 0
    # 21층 업무시설에 주차 0대는 성립하지 않는다. 대장 주차란이 비어 있는 것이다.
    # 총괄표제부 보정은 2동 이상일 때만 쓸 수 있어(단독 동은 총괄표제부 자체가 없다)
    # 단독 동 건물에서는 보정이 영영 안 걸린다. 그래서 0 은 아예 근거로 쓰지 않는다.
    led_pk = f.get("led_parking") or None       # 0 → None(미확보)
    pk_possible = f.get("parking_possible")    # 네이버 parkingPossibleYN
    # 총괄표제부에서 보정한 값이면 어디서 확인했는지 밝힌다(중개사가 근거를 되짚을 수 있게).
    _pk_src = f.get("led_parking_src") or "건축물대장"
    _led_note = f" ({_pk_src} 기준 총 {led_pk}대)" if (led_pk and led_comparable) else ""
    if cp_autofilled:
        add(10, "주차", "통과", "CP 자동입력(확인)")
    elif pk_possible == "N":
        add(10, "주차", "통과", "주차 불가로 표시됨")     # 주차불가 명시 = 유효한 표시
    elif _to_float(f.get("parking_count")) == 0 and _has_parking(f.get("parking_count")):
        # 0대 = '주차 없음'을 밝힌 유효한 표시. 공부상 0이면 오히려 일치다.
        add(10, "주차", "통과",
            "주차 0대로 표시됨" + ("(건축물대장도 0대)" if (led_comparable and led_pk == 0) else ""))
    elif not _has_parking(f.get("parking_count")):
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
    #
    #    상업용(상가·사무실·지식산업센터)은 기준이 전부 주출입구로 정해져 있다(입력 폼에 기준
    #    선택란 없음, 2026-11-12 사용자 확인) → 기준은 묻지 않고 방향 값만 본다. 방향이 빈 광고가
    #    실제로 있어(상가 2.2%·사무실 0.5%) '플랫폼이 막는다'는 10-13 전제는 틀렸다 → 없으면 위반.
    if _listing_cat(rtype, f.get("real_estate_type")) in ("상업", "업무"):
        if _has(f.get("direction")):
            add(12, "방향", "통과", "상업용 — 주출입구 기준")
        else:
            add(12, "방향", "위반", "방향 미표시(상업용은 주출입구 기준 방향)")
    elif not _has(f.get("direction")):
        add(12, "방향", "위반", "방향 미표시")
    elif residential and _lacks_room_fields(rtype):
        add(12, "방향", "통과", "통건물 — 기준 선택란 없음(주출입구 기준)")
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
            if not led_comparable:
                # 이 지번 대장은 주거동 — 단지내상가의 상가동은 별도 지번이라 이 건물 층 용도는
                # 이 매물과 무관하다. 오탐 방지로 위반/주의 없이 참고 표시만.
                add(13, "층별 용도", "통과",
                    f"단지내상가 — 이 지번 건축물대장은 주거동(상가동 대장 별도) · {summary}")
            else:
                add(13, "층별 용도", "주의",
                    f"광고는 {lcat}인데 건축물대장 {cflr}층은 ‘{mpur}’(주거) — 용도 확인 필요 · {summary}")
        else:
            add(13, "층별 용도", "통과", f"{cflr}층 용도 ‘{mpur}’ · {summary}")

    # ⑭ 융자금 — **필수 입력 항목이 아니다.** 그런데 '시세 대비 30% 미만' 식으로 적어 두는
    #    사례가 있고, 한 번 적은 값은 상환·추가대출로 현재 융자 상태와 쉽게 달라진다.
    #    달라진 값을 그대로 두면 그때부터 허위·과장 표시가 된다.
    #    필수가 아닌 항목이니 '위반'으로 몰지 않고 **'주의'로만** 알린다
    #    (2026-10-13 광고검수 결정 — 가장 안전한 선택은 '표시 안함').
    _fin = _to_float(f.get("finance_price"))
    if _fin and _fin > 0:
        add(14, "융자금", "주의",
            f"융자금 {_fmt_manwon(_fin)} 표시됨 — 상환·추가대출로 현재 상태와 달라질 수 있습니다. "
            "필수 항목이 아니므로 ‘표시 안함’이 가장 안전합니다")

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
