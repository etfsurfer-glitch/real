import os, sys, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv; load_dotenv(".env")

KEYS = [os.getenv(k) for k in ("DATA_GO_KR_SERVICE_KEY","DATA_GO_KR_SERVICE_KEY2","DATA_GO_KR_SERVICE_KEY3") if os.getenv(k)]
FLR_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrFlrOulnInfo"

def parse_jibun(cortar, detail):
    da = str(detail).strip().split()[0]; plat="0"
    if da.startswith("산"): plat, da = "1", da[1:]
    da = da.replace("번지","")
    m = re.match(r"(\d+)(?:-(\d+))?", da)
    bun=int(m.group(1)); ji=int(m.group(2)) if m.group(2) else 0
    cn=str(cortar)
    return cn[:5], plat, f"{bun:04d}", f"{ji:04d}", cn[5:10]

def fetch_flr(sgg, plat, bun, ji, bjd):
    items=[]
    for pg in range(1,8):
        qs=urllib.parse.urlencode({"serviceKey":"__K__","sigunguCd":sgg,"bjdongCd":bjd,
            "platGbCd":plat,"bun":bun,"ji":ji,"numOfRows":"100","pageNo":str(pg)})
        got=False
        for k in KEYS:
            url=f"{FLR_URL}?{qs.replace('__K__', urllib.parse.quote(k, safe=''))}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={"Accept":"application/xml"}),timeout=25) as r:
                    root=ET.fromstring(r.read())
            except Exception as e:
                continue
            code=root.findtext(".//resultCode") or ""
            if "LIMIT" in (root.findtext(".//returnAuthMsg") or "").upper() or code.strip("0")=="22":
                continue  # 이 키 쿼터소진 → 다음 키
            new=root.findall(".//item"); items+=new
            total=int(root.findtext(".//totalCount") or 0); got=True
            if not new or len(items)>=total: return items, None
            break
        if not got: return items, "ALL_KEYS_LIMITED"
    return items, None

def g(it,t): return (it.findtext(t) or "").strip()

TESTS = [
    ("다산한강반도유보라(연결○)", "4136011200", "6234"),
    ("둔산동 크로바(연결×,지하有)", "3017011200", "1509"),
]
for name, cortar, detail in TESTS:
    print("="*60); print(name, f"[{cortar} {detail}]")
    sgg,plat,bun,ji,bjd = parse_jibun(cortar, detail)
    print(f"  조회: sgg={sgg} bjd={bjd} bun={bun} ji={ji}")
    items, err = fetch_flr(sgg,plat,bun,ji,bjd)
    if err: print("  ⚠", err, "(백필로 쿼터소진 — 나중 재시도)"); continue
    if not items: print("  대장 조회 0건"); continue
    # 동별로 지하층·주차장 집계
    dongs={}
    for it in items:
        dn=g(it,"dongNm") or "(동표기없음)"
        flrgb=g(it,"flrGbCdNm"); purps=g(it,"mainPurpsCdNm"); flrnm=g(it,"flrNoNm")
        atch=g(it,"mainAtchGbCdNm")  # 주건축물/부속건축물
        d=dongs.setdefault(dn, {"지하주차":False, "지하층":False, "floors":[], "atch":atch})
        if flrgb=="지하":
            d["지하층"]=True
            if "주차" in purps: d["지하주차"]=True
        d["floors"].append(f"{flrnm}/{purps}")
    print(f"  동 수: {len(dongs)}")
    for dn,d in list(dongs.items())[:25]:
        mark="🅿지하주차O" if d["지하주차"] else ("지하有(주차X)" if d["지하층"] else "지하無")
        print(f"    {dn:12} [{d['atch']}] {mark}  층:{','.join(d['floors'][:6])}")
