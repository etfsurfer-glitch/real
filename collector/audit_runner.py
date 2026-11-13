"""매물 표시·광고 점검 실행부 — 매물 1건을 상세·건축물대장과 함께 점검(collector/listing_audit.py 판정 엔진 호출).

라운지 '매물 점검'(scripts/local_api.py)과 콕집매물 전환 게이트(scripts/kok_sync.py)가 같은 기준을 쓰도록
local_api 에 있던 것을 그대로 옮겼다(2026-11-13). 판정 로직을 바꾸려면 listing_audit.py 를, 입력 병합·대장 보정은 여기를 고친다.
"""
from __future__ import annotations

from pathlib import Path

from collector.config import settings

NONRESI_LABEL = {"sangga": "상가", "office": "사무실", "villa": "빌라·연립", "house": "단독·다가구",
                 "land": "토지", "factory": "공장·창고", "building": "건물",
                 "knowledge": "지식산업센터", "redev": "재개발", "oneroom": "원룸"}


def _audit_keys():
    """점검용 키: (vworld, [data.go.kr 키...]). .env 직접 로드."""
    vw, dks = "", []
    try:
        for line in open(Path(settings.local_db_path).resolve().parent.parent / ".env"):
            if line.startswith("VWORLD_KEY="):
                vw = line.split("=", 1)[1].strip()
            elif line.startswith("DATA_GO_KR_SERVICE_KEY="):
                dks.insert(0, line.split("=", 1)[1].strip())
            elif line.startswith("DATA_GO_KR_SERVICE_KEY2="):
                dks.append(line.split("=", 1)[1].strip())
    except OSError:
        pass
    return vw, [k for k in dks if k]


def _audit_merge(r: dict, det: dict, *, saengsuk: bool, led: dict | None,
                 dong_set: bool = False, expos: list | None = None,
                 floors: list | None = None, swapped: bool = False) -> dict:
    """매물행(listings)+상세(네이버)+대장(led)+전유면적(expos) → 점검엔진 입력필드 병합.
    dong_set=True(단지형): 동별 총층·사용승인 집합으로 대조(오탐방지), 주차 대조는 생략(총괄표제부 필요)."""
    f = {
        "article_no": r.get("article_no"),
        "real_estate_type": r.get("real_estate_type"),
        "realestate_type_name": det.get("realestate_type") or r.get("real_estate_type_name"),
        "trade_type": det.get("trade_type") or r.get("trade_type"),
        "floor_info": det.get("floor_info") or r.get("floor_info"),
        "area_exclusive": r.get("area2_m2"),
        "price": r.get("deal_or_warrant_price"),
        "rent_price": r.get("rent_price"),                       # 월세(만원) — 무보증 월세는 price 가 비어 있다
        "building_name": det.get("building_name") or r.get("building_name"),
        "dong_name": r.get("dong_name"),
        "detail_address": r.get("detail_address"),
        "is_saengsuk": saengsuk,
        "total_floor": det.get("total_floor"),
        "movein_type": det.get("movein_type"),
        "movein_negotiable": det.get("movein_negotiable"),
        "movein_ymd": det.get("movein_ymd"),                     # ⑦ '즉시입주'인데 앞날짜면 허위
        "finance_price": det.get("finance_price"),               # ⑭ 융자금(만원, 주의 전용)
        "room_count": det.get("room_count"),
        "bathroom_count": det.get("bathroom_count"),
        "use_approve_ymd": det.get("use_approve_ymd") or r.get("use_approve_ymd"),
        # 값을 매물 필드가 아니라 광고의 '건축물 정보' 블록에서 가져왔으면 사유에 밝힌다
        "ua_source": det.get("_ua_source"),
        "parking_count": det.get("parking_count"),
        "parking_possible": det.get("parking_possible"),
        "monthly_management_cost": det.get("monthly_management_cost"),
        "admin_cost_info": det.get("admin_cost_info"),
        "violation_building": det.get("violation_building"),
        "unregistered_building": det.get("unregistered_building"),
        "direction": det.get("direction") or r.get("direction"),
        "direction_base": det.get("direction_base"),
        "corresponding_floor": det.get("corresponding_floor"),  # ⑬ 해당층(층별 용도 매칭)
        "led_floors": floors,                                    # ⑬ 건축물대장 층별개요
    }
    if led:
        # 총층·사용승인은 동별 집합 매칭(같은 지번 다동/단지내상가 오탐 방지 — 어느 동과도
        # 안 맞을 때만 불일치). 주차는 비단지만(단지형 주차는 총괄표제부 필요 → 생략).
        f["led_total_floor"] = led.get("grnd_flr_all") or led.get("grnd_flr")
        f["led_use_apr_day"] = led.get("use_apr_all") or led.get("use_apr_day")
        f["led_main_purps"] = led.get("main_purps")     # 대장 주용도(상가 대조 가능여부 판별)
        if not dong_set:
            f["led_parking"] = led.get("parking")
            # 총괄표제부에서 보정한 값이면 사유에 출처를 밝힌다
            f["led_parking_src"] = led.get("parking_src")
    if expos:
        f["led_expos_areas"] = expos
    # 단지내상가 오탐 판별용(listing_audit): 원본 매물 building_name 이 네이버 placeholder
    # '단지내상가'인지(det 가 실단지명으로 덮어써도 원본으로 판단) + 상가동 스왑 성공 여부.
    f["is_danji_shop"] = "단지내상가" in (r.get("building_name") or "")
    f["led_swapped"] = swapped
    return f


def _ledger_brief(led: dict | None) -> dict | None:
    """결과에 실을 건축물대장 기준값 요약(주용도·건물명·총층들·사용승인들·주차)."""
    if not led:
        return None
    return {
        "main_purps": led.get("main_purps"),
        "bld_nm": led.get("bld_nm"),
        "grnd_flr": led.get("grnd_flr_all") or ([led["grnd_flr"]] if led.get("grnd_flr") else []),
        "use_apr_day": led.get("use_apr_all") or ([led["use_apr_day"]] if led.get("use_apr_day") else []),
        "parking": led.get("parking"),
    }


_COMPLEX_KINDS = {"APT": "아파트", "OPST": "오피스텔", "ABYG": "아파트분양권",
                  "OBYG": "오피스텔분양권", "JGC": "재건축"}
_TRADE_LABEL_AUDIT = {"A1": "매매", "B1": "전세", "B2": "월세"}


def _audit_skip_result(r: dict, kind: str, *, delisted: bool) -> dict:
    """상세조회 불가 매물의 점검 제외 결과 — 광고 종료(내려감) 또는 일시 실패.
    빈 필드로 점검하면 전항목 '미표시 위반' 오탐 폭탄이 나므로 점검 자체를 건너뛴다(정확성)."""
    reason = ("광고 종료된 매물(네이버에서 내려감) — 점검 제외" if delisted
              else "상세조회 일시 실패 — 잠시 후 재점검 필요")
    return {
        "article_no": r.get("article_no"), "kind": kind,
        "building": r.get("complex_name") or r.get("building_name"),
        "is_saengsuk": False, "address": None,
        "naver_url": f"https://m.land.naver.com/article/info/{r.get('article_no')}",
        "ledger_matched": False, "ledger": None, "delisted": delisted,
        "findings": [{"no": 0, "item": "매물 상태", "status": "통과", "reason": reason}],
        "violation_count": 0, "warning_count": 0, "pass": True,
    }


def _audit_complex_one(r: dict, creds, dks) -> dict:
    """단지형 매물 1건 점검(상세조회+지번대장 확인)."""
    from collector.article_detail import fetch_and_extract
    from collector.listing_audit import audit_listing, is_saengsuk
    from collector.ondemand_ledger import ledger_for_jibun
    det = fetch_and_extract(r["article_no"], r["complex_no"], creds)
    if det is None or det.get("_delisted"):
        return _audit_skip_result(r, "단지형", delisted=bool(det))
    led = None
    if dks and r.get("cortar_no") and r.get("detail_address"):
        led = ledger_for_jibun(r["cortar_no"], r["detail_address"], dks)
    _mf = _audit_merge(r, det, saengsuk=is_saengsuk(r.get("complex_name")), led=led, dong_set=True)
    _mf["cp_autofilled"] = True
    res = audit_listing(_mf, cp_autofilled=True)
    res["_audit_input"] = _mf                            # 로그용 — 응답 직전에 뗀다
    res["kind"] = "단지형"
    res["building"] = r.get("complex_name")
    res["address"] = (det.get("exposure_address")
                      or " ".join(x for x in [r.get("dong_name"), r.get("detail_address")] if x) or None)
    res["naver_url"] = f"https://m.land.naver.com/article/info/{r['article_no']}"
    res["ledger_matched"] = bool(led)
    res["ledger"] = _ledger_brief(led)
    res["_mgmt"] = (("c", r.get("complex_no"), round(float(r.get("area2_m2") or 0))),
                    det.get("monthly_management_cost"))
    return res


def _audit_nonresi_one(r: dict, cat: str, creds, vw, dks) -> dict:
    """비단지 매물 1건 점검(상세+네이버 inline 건축물대장, 폴백=좌표 온디맨드, 전유면적)."""
    from collector.article_detail import fetch_and_extract
    from collector.listing_audit import audit_listing
    from collector.ondemand_ledger import (ledger_for_coord, expos_areas_for_coord,
                                           expos_areas_for_pnu, flr_ouln_for_pnu,
                                           commercial_for_pnu, title_sets_for_pnu,
                                           recap_for_pnu)
    det = fetch_and_extract(r["article_no"], None, creds)
    if det is None or det.get("_delisted"):
        return _audit_skip_result(r, NONRESI_LABEL.get(cat, cat), delisted=bool(det))
    # 대장: 네이버가 매물상세에 넣어주는 inline 대장(그 건물 정확·무료) 우선, 없으면 좌표 온디맨드.
    led = det.get("ledger_inline")
    expos = None
    if not led and vw and dks and r.get("latitude"):
        led = ledger_for_coord(r["latitude"], r["longitude"], vw, dks)
    # ② 전유면적 대조 — 집합건물(전유 표기 명확)만. pnu(inline 대장) 우선 = 좌표 없는 매물도
    #    커버 + vworld 1단계 절약. pnu 없으면 좌표 경로 폴백. 캐시(E키)는 두 경로 공유.
    if dks and cat in ("villa", "sangga", "office", "knowledge"):
        if led and led.get("pnu"):
            expos = expos_areas_for_pnu(led["pnu"], dks)
        elif vw and r.get("latitude"):
            expos = expos_areas_for_coord(r["latitude"], r["longitude"], vw, dks)
    # 상가·사무실 매물인데 대장이 주거/숙박 타워를 가리키면(단지내상가 등) → 같은 지번의
    # 별도 '상가동' 대장을 찾아 그 동 기준으로 대조(사용자 지시). 상가동 없으면 기존대로
    # 대조 생략(led_comparable=False 경로).
    _swapped = False
    if (cat in ("sangga", "office", "knowledge") and dks and led and led.get("pnu")
            and any(k in (led.get("main_purps") or "")
                    for k in ("공동주택", "아파트", "오피스텔", "숙박", "기숙사", "도시형생활"))):
        _pnu = led.get("pnu")
        comm = commercial_for_pnu(_pnu, dks)
        if comm:
            led = dict(comm, pnu=_pnu)
            _swapped = True
    # ⑥총층·⑨사용승인 any-match — 같은 지번 '전체 주건축물 동' 집합으로 대조.
    # 네이버 inline 대장이 한 동만 반환해 오탐 나던 문제(여의도 iM증권 A동 19층 매물이
    # B동 근생 2층과 대조돼 위반 오판, 2026-07-07). 상가동 스왑 케이스는 스왑 집합이
    # 이미 any-match라 병합하지 않음(주거타워 층수 섞이면 미탐 위험).
    if (not _swapped and dks and led and led.get("pnu") and not led.get("grnd_flr_all")):
        _ts = title_sets_for_pnu(led["pnu"], dks)
        if _ts:
            led = dict(led)
            # **합집합**이어야 한다. 전에는 표제부 집합으로 덮어써 inline 값을 버렸는데,
            # inline 은 네이버가 그 매물 건물로 매칭한 대장이고 광고가 쓴 바로 그 값이다.
            # 실측(2026-10-08) 2651420136: 광고·inline 모두 2016.10.12 인데 표제부 API 는
            # 2016.10.04 를 줬다. 덮어쓰니 '공부와 불일치' 오탐이 났다.
            if _ts.get("grnd_flr_all"):
                led["grnd_flr_all"] = sorted(
                    set(_ts["grnd_flr_all"]) | ({led["grnd_flr"]} if led.get("grnd_flr") else set()))
            if _ts.get("use_apr_all"):
                led["use_apr_all"] = sorted(
                    set(_ts["use_apr_all"]) | ({led["use_apr_day"]} if led.get("use_apr_day") else set()))
    # ⑬ 층별 용도(층별개요) — inline 대장의 pnu로 온디맨드(혼합건물 정밀 점검).
    floors = flr_ouln_for_pnu(led["pnu"], dks) if (dks and led and led.get("pnu")) else None
    # ⑩ 주차 보정 — 다동 건물은 주차가 **총괄표제부**에만 잡히고 동별 표제부는 전부 0 이다.
    #    표제부의 0 을 '공부상 주차 없음'으로 읽어 광고의 정상 표기를 위반으로 찍던 오탐이
    #    있었다(서초동 1619-7: 표제부 0 / 총괄표제부 15대, 광고 15대 — 2026-08-14).
    #    0 이거나 미확보일 때만 총괄표제부를 본다(있는 값은 건드리지 않는다).
    if dks and led and led.get("pnu") and not led.get("parking"):
        _rc = recap_for_pnu(led["pnu"], dks)
        if _rc and _rc.get("parking"):
            led = dict(led, parking=_rc["parking"], parking_src="총괄표제부")
        else:
            # 3차: 총괄표제부가 없는 **단일동 집합 신축**은 일반 표제부에만 주차가 있다
            # (방배동 860-1 에비뉴860: 인라인 0 / 총괄 null / 표제부 자주식 6, 2026-09-01).
            from collector.ondemand_ledger import title_parking_for_pnu
            _tp = title_parking_for_pnu(led["pnu"], dks)
            if _tp and _tp.get("parking"):
                led = dict(led, parking=_tp["parking"], parking_src="표제부")
    # ⑨ 사용승인일 2차 출처 — 네이버 광고 화면은 이 값을 매물 자체 필드가 아니라 '건축물 정보'
    #    블록(fin.land 단지/건물 API)에서 보여준다. new.land 매물상세에 그 필드가 없는 매물이
    #    있는데(제휴 전송이 시설정보를 빼먹은 경우 등) 그걸 '광고 미표시'로 찍어 멀쩡한 매물이
    #    위반으로 뜨는 오탐이 있었다(빌라 2643364583·2643352573, 2026-08-14).
    #    광고에 실제로 노출되는 값이 판정 기준이므로, 비어 있을 때만 2차 조회해 채운다.
    #    (대부분 매물은 1차에 값이 있어 이 경로를 타지 않는다 — 표본 8/8 정상)
    if not det.get("use_approve_ymd"):
        try:
            from collector.finland import building_for_article
            _fl = building_for_article(r["article_no"])
            if _fl and _fl.get("ok") and _fl.get("use_approve_ymd"):
                det = dict(det, use_approve_ymd=_fl["use_approve_ymd"], _ua_source="건축물 정보")
        except Exception:                                   # noqa: BLE001
            pass                                            # 브리지 장애는 점검을 막지 않는다
    _mf = _audit_merge(r, det, saengsuk=False, led=led, expos=expos, floors=floors, swapped=_swapped)
    res = audit_listing(_mf)
    # 콕집 전환용(응답에는 안 나감 — _audit_input 은 응답 직전에 뗀다): 노출 주소·PNU·관리비 부과 방식
    _mf["exposure_address"] = det.get("exposure_address")
    _mf["led_pnu"] = (led or {}).get("pnu")
    res["_audit_input"] = _mf                            # 로그용 — 응답 직전에 뗀다
    res["kind"] = NONRESI_LABEL.get(cat, cat)
    res["building"] = r.get("building_name")
    res["address"] = det.get("exposure_address") or None
    res["naver_url"] = f"https://m.land.naver.com/article/info/{r['article_no']}"
    res["ledger_matched"] = bool(led)
    res["ledger"] = _ledger_brief(led)
    res["_mgmt"] = ((cat, round(float(r.get("area2_m2") or 0))),
                    det.get("monthly_management_cost"))
    return res
