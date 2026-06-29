"""비단지 매물 온디맨드 건축물대장 조회 — 좌표 → 지번 → 표제부.

비단지(빌라·단독·상가)는 지번이 없고 좌표(lat/lon)만 있음. 매물점검 시 그 매물 좌표로
vworld 역지오코딩→지번→건축물대장 표제부를 조회해 기준값(용도·총층·사용승인일·주차)을 얻는다.
중개사 점검 단위(소량)라 온디맨드. 지번키로 캐시(같은 건물 재조회 방지).

단지형(아파트·오피)은 CP 자동입력이라 대장 불필요 — 이 모듈은 비단지 전용.
"""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

VW_URL = "https://api.vworld.kr/req/address"
BR_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"

_cache: dict[str, dict | None] = {}   # 지번키 → 대장 ref (프로세스 캐시)


def coord_to_jibun(lat, lon, vworld_key) -> tuple[str, str, str, str] | None:
    """좌표 → (법정동코드10, platGbCd, bun4, ji4). vworld 역지오코딩(PARCEL). 실패 None."""
    if not lat or not lon:
        return None
    q = {"service": "address", "request": "getAddress", "version": "2.0",
         "crs": "epsg:4326", "point": f"{lon},{lat}", "format": "json",
         "type": "PARCEL", "key": vworld_key}
    try:
        r = json.loads(urllib.request.urlopen(VW_URL + "?" + urllib.parse.urlencode(q), timeout=15)
                       .read().decode("utf-8"))
        resp = r.get("response", {})
        if resp.get("status") != "OK" or not resp.get("result"):
            return None
        res = resp["result"][0]
        ld = res.get("structure", {}).get("level4LC") or ""
        text = res.get("text", "")
    except Exception:
        return None
    if len(ld) < 10:
        return None
    plat = "1" if "산 " in text or re.search(r"\s산\d", text) else "0"
    m = re.search(r"(\d+)(?:-(\d+))?\s*(?:번지)?\s*$", text.strip())
    if not m:
        return None
    bun = m.group(1).zfill(4)
    ji = (m.group(2) or "0").zfill(4)
    return ld[:5], plat, bun, ji, ld[5:10]  # (sgg, platGb, bun, ji, bjd)  ※순서주의 아래서 정리


def _int(v):
    try:
        return int(float(str(v))) if str(v).strip() not in ("", "-") else None
    except (ValueError, TypeError):
        return None


def ledger_ref(sgg, bjd, plat, bun, ji, datago_keys) -> dict | None:
    """건축물대장 표제부 → 기준값 dict. 비단지 건물 1동 가정(주건축물·연면적최대 우선).
    datago_keys: 키 리스트(또는 str). 키별 일일쿼터라 429(소진) 시 다음 키로 폴백."""
    if isinstance(datago_keys, str):
        datago_keys = [datago_keys]
    base = {"sigunguCd": sgg, "bjdongCd": bjd, "platGbCd": plat,
            "bun": bun, "ji": ji, "numOfRows": "20", "pageNo": "1"}
    t = None
    for key in datago_keys:
        try:
            t = urllib.request.urlopen(
                urllib.request.Request(
                    BR_URL + "?" + urllib.parse.urlencode({"serviceKey": key, **base}),
                    headers={"Accept": "application/xml"}), timeout=20
            ).read().decode("utf-8")
            if "resultCode>00" in t:
                break
            t = None
        except urllib.error.HTTPError as e:
            if e.code == 429:        # 쿼터 소진 → 다음 키
                t = None
                continue
            return None
        except Exception:
            return None
    if not t:
        return None
    try:
        root = ET.fromstring(t)
    except ET.ParseError:
        return None
    items = root.findall(".//item")
    if not items:
        return None

    def g(it, tag):
        return (it.findtext(tag) or "").strip()

    # 주건축물(mainAtchGbCd=0) 우선, 없으면 연면적 최대
    mains = [it for it in items if g(it, "mainAtchGbCd") == "0"] or items
    pick = max(mains, key=lambda it: float(g(it, "totArea") or 0))
    park = sum(filter(None, (_int(g(pick, k)) for k in
              ("indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"))))
    return {
        "main_purps": g(pick, "mainPurpsCdNm"),
        "etc_purps": g(pick, "etcPurps"),
        "grnd_flr": _int(g(pick, "grndFlrCnt")),
        "use_apr_day": g(pick, "useAprDay"),
        "parking": park or None,
        "bld_nm": g(pick, "bldNm"),
        "tot_area": float(g(pick, "totArea") or 0) or None,
        "n_records": len(items),
    }


def ledger_for_coord(lat, lon, vworld_key, datago_keys) -> dict | None:
    """좌표 → 건축물대장 기준값(캐시). 비단지 매물점검 대조용. datago_keys=키 리스트/str."""
    j = coord_to_jibun(lat, lon, vworld_key)
    if not j:
        return None
    sgg, plat, bun, ji, bjd = j
    ck = f"{sgg}{bjd}{plat}{bun}{ji}"
    if ck in _cache:
        return _cache[ck]
    ref = ledger_ref(sgg, bjd, plat, bun, ji, datago_keys)
    if ref is not None:
        ref["jibun_key"] = ck
    _cache[ck] = ref
    return ref
