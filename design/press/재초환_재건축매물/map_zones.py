"""서울시 정비사업 추진현황(26년 6월말, 열린데이터광장 OA-22856) 재건축 구역 → 우리 단지 연결. 박스에서 실행.

연결 기준: 같은 자치구·법정동 + 구역 위치 지번의 본번 == 단지 지번 본번(재건축·아파트 단지).
안 되면 같은 동 안에서 구역명과 단지명이 겹치는 단지. 결과와 미연결 목록을 출력한다.
Run: /opt/koczip/.venv/bin/python3 map_zones.py zones.json → zone_map.json
"""
import json, re, sqlite3, sys
sys.path.insert(0, "/opt/koczip")
from collector.realprice.matching import base_normalize

zones = [z for z in json.load(open(sys.argv[1])) if z["type"] in ("공동주택재건축", "아파트지구재건축")]

# 사람이 확인한 연결(구역 하나에 단지 여러 개·같은 지번을 여러 단지가 쓰는 곳·위치 표기가 달라 못 찾는 곳)
MANUAL = {
    "압구정아파트지구특별계획구역1": ["728", "742"],                                  # 미성1·2차
    "압구정아파트지구특별계획구역2": ["3037"],                                        # 신현대 9·11·12차
    "압구정아파트지구특별계획구역3": ["712", "705", "495", "708", "724", "514", "107189", "114923"],  # 현대1~7·10·13·14차·대림빌라트·현대빌라트
    "압구정아파트지구특별계획구역4": ["8617", "497", "498", "500"],                   # 현대8차·한양3·4·6차
    "압구정아파트지구특별계획구역5": ["494", "496"],                                  # 한양1·2차
    "압구정아파트지구특별계획구역6": ["499", "501", "502"],                           # 한양5·7·8차
    "한강맨션아파트": ["503"], "한강삼익아파트": ["862"], "왕궁아파트": ["765"],
    "일원개포한신": ["943"], "개포우성7차": ["978"],
    "여의도삼부아파트": ["745"], "여의도장미아파트": ["751"], "여의도공작아파트": ["739"],
    "경우현(개포경남,우성3차,현대1차)": ["28", "667", "1317"], "논현동현": [],  # 동현은 아래 이름으로
    "수정아파트": ["958"], "목동14단지": ["669"], "신길동삼성아파트": ["718"],
    "청담삼성진흥": ["733", "100285"], "여의도광장아파트38-1번지": ["740"], "망우1(염광아파트)": ["8370"],
    "신림미성아파트": ["1054"], "미성동건영아파트": ["52"],
}
c = sqlite3.connect("file:/opt/koczip/data/naverreal.sqlite?mode=ro", uri=True)
gu = {r[1]: r[0] for r in c.execute("SELECT cortar_no, cortar_name FROM regions WHERE length(cortar_no)=10 AND cortar_no LIKE '11%' AND cortar_no LIKE '%00000'")}
cx = c.execute("SELECT c.complex_no, c.complex_name, c.real_estate_type, c.cortar_no, c.detail_address, r.cortar_name, c.total_household_count "
               "FROM complexes c JOIN regions r ON r.cortar_no=c.cortar_no WHERE c.cortar_no LIKE '11%' AND c.real_estate_type IN ('APT','JGC')").fetchall()
def bonbun(s):
    m = re.search(r"(\d+)(?:-\d+)?\s*$", s or "")
    return m.group(1) if m else None
out, miss = [], []
names = {x[0]: x[1] for x in cx}
for z in zones:
    if z["name"] in MANUAL and MANUAL[z["name"]]:
        out.append({**z, "complex_nos": MANUAL[z["name"]], "cx_names": [names.get(n, n) for n in MANUAL[z["name"]]], "how": "수동"})
        continue
    loc = (z["jibun"] or "").replace(" ", "")
    loc = re.sub(r"^(서울특별시|서울시)?" + re.escape(z["gu"] or "") , "", loc)
    m = re.match(r"([가-힣]+동\d+가|[가-힣]+\d+가|[가-힣]+동|[가-힣]+가)(?:산)?(\d+)", loc)
    dong, bb = (m.group(1), m.group(2)) if m else (None, None)
    if dong and re.search(r"\d동$", dong):          # 행정동(중곡4동) → 법정동(중곡동)
        dong = re.sub(r"\d+동$", "동", dong)
    gcode = gu.get(z["gu"], "")[:5]
    hits = [x for x in cx if x[3][:5] == gcode and dong and x[5] == dong and bonbun(x[4]) == bb]
    how = "지번"
    if not hits:
        zn = base_normalize(re.sub(r"(아파트|재건축|정비사업|주택|구역|지구)", "", z["name"]))
        hits = [x for x in cx if x[3][:5] == gcode and (not dong or x[5] == dong) and len(zn) >= 2 and x[2] == "JGC"
                and (zn in base_normalize(x[1]) or (len(base_normalize(x[1])) >= 3 and base_normalize(x[1]) in zn))]
        how = "이름"
    if hits:
        # 재건축 유형 단지 우선(같은 지번에 새 아파트가 있으면 뺀다)
        j = [x for x in hits if x[2] == "JGC"]
        hits = j or hits
        if len(hits) > 1:   # 같은 지번에 여러 단지 → 구역명과 두 글자 이상 겹치는 단지만
            zn = re.sub(r"(아파트|재건축|정비사업|주택|구역|지구|\(.*?\))", "", z["name"])
            bi = {zn[i:i + 2] for i in range(len(zn) - 1)}
            k = [x for x in hits if any(b in x[1] for b in bi)]
            hits = k or hits
        out.append({**z, "complex_nos": [x[0] for x in hits], "cx_names": [x[1] for x in hits], "how": how})
    else:
        miss.append(z)
json.dump(out, open("zone_map.json", "w"), ensure_ascii=False, indent=0)
print("구역", len(zones), "연결", len(out), "미연결", len(miss))
import collections
print("단계별 연결", collections.Counter(o["stage"] for o in out).most_common())
print("단계별 미연결", collections.Counter(o["stage"] for o in miss).most_common())
for o in out:
    if o["how"] == "이름" or len(o["complex_nos"]) > 2:
        print("  확인", o["gu"], o["name"], o["jibun"], o["stage"], "→", o["cx_names"][:4], o["how"])
for z in miss[:60]:
    print("  미연결", z["gu"], z["name"], z["jibun"], z["stage"])
