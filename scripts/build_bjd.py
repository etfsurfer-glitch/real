# 법정동 전수표 구축 — VWorld 행정구역 검색으로 시도 → 시군구(일반구·신설구 포함) → 읍면동.
# regions(네이버 cortar)에 없는 일반구·신설구 때문에 지번 주소를 못 풀던 것을 메운다.
import json, os, sqlite3, sys, time, urllib.parse as up, urllib.request as ur

KEY = ""
for line in open("/opt/koczip/.env"):
    if line.startswith("VWORLD_KEY="):
        KEY = line.split("=", 1)[1].strip()
BASE = "https://api.vworld.kr/req/search"

def search(q, cat, page=1, size=100):
    qs = up.urlencode({"service": "search", "request": "search", "version": "2.0",
                       "size": size, "page": page, "query": q, "type": "district",
                       "category": cat, "format": "json", "key": KEY})
    for i in range(4):
        try:
            d = json.loads(ur.urlopen(f"{BASE}?{qs}", timeout=20).read())["response"]
            if d.get("status") != "OK":
                return [], 0
            return d["result"]["items"], int(d["record"]["total"])
        except Exception:
            time.sleep(1.0 * (i + 1))
    return [], 0

def all_pages(q, cat):
    items, total = search(q, cat, 1)
    got = list(items)
    page = 2
    while len(got) < total and page <= 40:
        more, _ = search(q, cat, page)
        if not more:
            break
        got += more
        page += 1
    return got

db = sqlite3.connect("/opt/koczip/data/naverreal.sqlite")
db.execute("""CREATE TABLE IF NOT EXISTS bjd(
    code10 TEXT PRIMARY KEY, sgg5 TEXT, sido_nm TEXT, sgg_nm TEXT, umd_nm TEXT,
    built_at TEXT DEFAULT (datetime('now')))""")
db.execute("CREATE INDEX IF NOT EXISTS bjd_umd ON bjd(umd_nm)")
db.execute("CREATE INDEX IF NOT EXISTS bjd_sgg ON bjd(sgg_nm)")

# 시도는 고정 목록으로 — admCodeList 는 파라미터를 붙이면 키를 거부한다.
# 옛 이름과 새 이름(2026-07 광주+전남 통합)을 함께 넣는다. 없는 것은 0건으로 넘어간다.
SIDO = ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "대전광역시", "울산광역시",
        "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도",
        "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
        "광주광역시", "전남광주통합특별시"]
sidos = [{"admCodeNm": x} for x in SIDO]
print(f"시도 {len(sidos)}개", flush=True)

n_sgg = n_umd = 0
for sd in sidos:
    sido_nm = sd["admCodeNm"]
    sggs = all_pages(sido_nm, "L2")
    n_sgg += len(sggs)
    for sg in sggs:
        title = sg["title"]                       # '경기도 수원시 장안구'
        sgg_nm = title[len(sido_nm):].strip() or title
        umds = all_pages(title, "L4")
        rows = []
        for u in umds:
            code = u["id"]
            code10 = (code + "00")[:10] if len(code) == 8 else code.ljust(10, "0")
            umd_nm = u["title"][len(title):].strip()
            if umd_nm:
                rows.append((code10, code10[:5], sido_nm, sgg_nm, umd_nm))
        db.executemany("INSERT OR REPLACE INTO bjd(code10,sgg5,sido_nm,sgg_nm,umd_nm) "
                       "VALUES(?,?,?,?,?)", rows)
        n_umd += len(rows)
    db.commit()
    print(f"  {sido_nm}: 시군구 {len(sggs)} · 누적 읍면동 {n_umd}", flush=True)
print(f"완료 — 시군구 {n_sgg} · 읍면동 {n_umd}")
print("표본:", db.execute("SELECT * FROM bjd WHERE umd_nm='정자동' LIMIT 3").fetchall())
