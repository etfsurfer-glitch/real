# -*- coding: utf-8 -*-
"""마스킹 상가 지번 복원 — 건축물대장 표제부 역매칭 (deal-locator-mcp 기법).

국토부 상업업무용 실거래의 지번 마스킹('1**')을 건축HUB 표제부에서
(연면적 ±0.6㎡ · 대지면적 ±2㎡ · 건축년도 ±1 · 지번 prefix+자릿수)가 모두 맞는
필지로 역매칭한다. ★유일해만 채택(후보 2개 이상=모호=버림) — 오귀속 0 원칙.
파일럿(강남 논현동): 유일특정 28/31(90%) · 모호 0.

- 격리: 결과·캐시는 별도 ledger_recover.sqlite (원본 nrg_transactions 불변)
  · title_cache(sgg,bjd): 동별 표제부 전수(90일 재사용) — API 절약
  · recovered(deal_id): 복원 지번·건물명
- 쿼터: getBrTitleInfo 키당 10,000/일 → 키 2개 × 9,000 예산, 재개형(캐시된 동 스킵)
- 우선순위: 최근 6개월 마스킹 거래 많은 동부터
사용: python3 scripts/ledger_jibun_recover.py [--once] [--daily-budget 18000]
"""
import argparse, json, sqlite3, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date

NV = "/opt/koczip/data/naverreal.sqlite"
DB = "/opt/koczip/data/ledger_recover.sqlite"
BASE = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
KEYS = [l.split("=", 1)[1].strip() for l in open("/opt/koczip/.env")
        if l.startswith(("DATA_GO_KR_SERVICE_KEY=", "DATA_GO_KR_SERVICE_KEY2="))]

def db_init():
    d = sqlite3.connect(DB, timeout=60)
    d.execute("PRAGMA journal_mode=WAL")
    d.execute("PRAGMA journal_size_limit=268435456")
    d.executescript("""
    CREATE TABLE IF NOT EXISTS title_cache(
      sgg TEXT, bjd TEXT, items TEXT, total INTEGER, fetched_at TEXT,
      PRIMARY KEY(sgg,bjd));
    CREATE TABLE IF NOT EXISTS recovered(
      deal_id TEXT PRIMARY KEY, sgg5 TEXT, dong TEXT, jibun TEXT,
      bld_nm TEXT, tot_area REAL, plat_area REAL, use_apr TEXT,
      matched_at TEXT DEFAULT (datetime('now')), asset TEXT DEFAULT 'nrg');
    CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, calls INTEGER);
    """)
    try:
        d.execute("ALTER TABLE recovered ADD COLUMN asset TEXT DEFAULT 'nrg'")
    except sqlite3.OperationalError:
        pass
    return d

def quota_left(d, budget):
    today = date.today().isoformat()
    r = d.execute("SELECT calls FROM quota WHERE day=?", (today,)).fetchone()
    return budget - (r[0] if r else 0)

def quota_add(d, n):
    today = date.today().isoformat()
    d.execute("INSERT INTO quota(day,calls) VALUES(?,?) ON CONFLICT(day) DO UPDATE SET calls=calls+?",
              (today, n, n))
    d.commit()

_ki = [0]
def fetch_dong(sgg, bjd, d, budget):
    """동 표제부 전수(캐시 우선). 반환: (items list, 사용한 호출수) 또는 (None, 0)=쿼터소진/오류."""
    r = d.execute("SELECT items, fetched_at FROM title_cache WHERE sgg=? AND bjd=? "
                  "AND fetched_at >= datetime('now','-90 days')", (sgg, bjd)).fetchone()
    if r:
        return json.loads(r[0]), 0
    rows, page, calls = [], 1, 0
    while True:
        if quota_left(d, budget) - calls <= 0:
            return None, calls
        p = {"serviceKey": KEYS[_ki[0] % len(KEYS)], "sigunguCd": sgg, "bjdongCd": bjd,
             "numOfRows": "100", "pageNo": str(page)}
        _ki[0] += 1
        try:
            req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(p),
                                         headers={"Accept": "application/xml"})
            xml = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
            root = ET.fromstring(xml)
        except Exception:
            time.sleep(3)
            return None, calls          # 이 동은 다음 사이클에 재시도
        calls += 1
        code = root.findtext(".//resultCode") or ""
        if code not in ("00", ""):
            time.sleep(3)
            return None, calls
        items = root.findall(".//item")
        for it in items:
            g = lambda k: (it.findtext(k) or "").strip()
            rows.append([g("bun"), g("ji"), g("totArea"), g("platArea"), g("useAprDay"), g("bldNm"), g("mainPurpsCdNm")])
        total = int(root.findtext(".//totalCount") or 0)
        if page * 100 >= total or not items:
            d.execute("INSERT OR REPLACE INTO title_cache(sgg,bjd,items,total,fetched_at) "
                      "VALUES(?,?,?,?,datetime('now'))", (sgg, bjd, json.dumps(rows), total))
            d.commit()
            return rows, calls
        page += 1
        time.sleep(0.12)

def match_one(jib, ba, pa, by, ledger):
    prefix = jib.rstrip("*")
    digits = len(jib)
    cands = []
    for bun, ji, ta, pl, apr, nm, purps in ledger:
        try: ta_f = float(ta)
        except Exception: continue
        if ba is None or abs(ta_f - ba) > 0.6:
            continue
        if pa:
            try:
                if abs(float(pl) - pa) > 2.0: continue
            except Exception:
                continue
        yr = apr[:4] if apr else ""
        if by and yr.isdigit() and abs(int(yr) - by) > 1:
            continue
        try: bn = str(int(bun))
        except Exception: continue
        if len(bn) != digits or (prefix and not bn.startswith(prefix)):
            continue
        cands.append((bn, ji, ta_f, pl, apr, nm))
    if len(cands) != 1:
        return None                      # 0=미발견, 2+=모호 → 채택 안 함
    bn, ji, ta_f, pl, apr, nm = cands[0]
    try: ji_n = int(ji or 0)
    except Exception: ji_n = 0
    return (bn + (f"-{ji_n}" if ji_n else ""), nm, ta_f, float(pl or 0), apr)

def match_sh(tfa, pa, by, ledger):
    """단독·다가구 — 지번 힌트 없이 strict 3속성 유일해만(연면적±0.3·대지±1.0·건축년 정확)."""
    cands = []
    for bun, ji, ta, pl, apr, nm, purps in ledger:
        try: ta_f = float(ta)
        except Exception: continue
        if abs(ta_f - tfa) > 0.3:
            continue
        if pa:
            try:
                if abs(float(pl) - pa) > 1.0: continue
            except Exception:
                continue
        yr = apr[:4] if apr else ""
        if yr.isdigit() and int(yr) != by:
            continue
        cands.append((bun, ji, ta_f, pl, apr, nm))
        if len(cands) > 1:
            return None
    if len(cands) != 1:
        return None
    bn_raw, ji, ta_f, pl, apr, nm = cands[0]
    try: bn = str(int(bn_raw))
    except Exception: return None
    try: ji_n = int(ji or 0)
    except Exception: ji_n = 0
    return (bn + (f"-{ji_n}" if ji_n else ""), nm, ta_f, float(pl or 0), apr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--daily-budget", type=int, default=18000)
    a = ap.parse_args()
    d = db_init()
    nv = sqlite3.connect(f"file:{NV}?mode=ro", uri=True)
    nv.execute("PRAGMA busy_timeout=60000")

    while True:
        # 대상 동: 미복원 마스킹 거래 수(최근 6개월 가중) 내림차순
        donerows = set(r[0] for r in d.execute("SELECT deal_id FROM recovered"))
        dongs = {}
        for did, s5, u, j, ba, pa, by, recent in nv.execute("""
            SELECT deal_id, substr(sgg_cd,1,5), umd_nm, jibun, building_ar, plottage_ar, build_year,
                   (deal_ymd>=date('now','-6 months'))
            FROM nrg_transactions WHERE jibun LIKE '%*%' AND is_cancelled=0
              AND building_ar>0 AND build_year>0"""):
            if did in donerows:
                continue
            key = (s5, u)
            e = dongs.setdefault(key, {"deals": [], "sh": [], "w": 0})
            e["deals"].append((did, j, ba, pa, by))
            e["w"] += 2 if recent else 1
        for did, s5, u, tfa, pa, by, recent in nv.execute("""
            SELECT deal_id, substr(sgg_cd,1,5), umd_nm, total_floor_ar, plottage_ar, build_year,
                   (deal_ymd>=date('now','-6 months'))
            FROM sh_transactions WHERE is_cancelled=0 AND total_floor_ar>0 AND build_year>0"""):
            if did in donerows:
                continue
            key = (s5, u)
            e = dongs.setdefault(key, {"deals": [], "sh": [], "w": 0})
            e.setdefault("sh", []).append((did, tfa, pa, by))
            e["w"] += 2 if recent else 1
        if not dongs:
            print("전 대상 처리 완료", flush=True)
            break
        # bjdong 코드 매핑(법정동코드 뒤 5자리)
        bjd_map = {}
        for cno, nm in nv.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_no NOT LIKE '%00000'"):
            bjd_map[(cno[:5], nm)] = cno[5:]
        order = sorted(dongs.items(), key=lambda kv: -kv[1]["w"])
        n_nrg = sum(len(v["deals"]) for _, v in dongs.items())
        n_sh = sum(len(v.get("sh", [])) for _, v in dongs.items())
        print(f"잔여 동 {len(order):,} · 상가 {n_nrg:,}·단독 {n_sh:,} · 오늘쿼터 잔여 {quota_left(d, a.daily_budget):,}", flush=True)

        progressed = False
        rec = miss = 0
        for (s5, u), e in order:
            bjd = bjd_map.get((s5, u))
            if not bjd:
                # 법정동 코드 미해석(행정개편 등) — recovered에 못 넣으니 스킵 마킹 없이 통과
                continue
            if quota_left(d, a.daily_budget) <= 0:
                print(f"일일 쿼터 소진 — 내일 재개 (복원 {rec}·미발견/모호 {miss})", flush=True)
                if a.once:
                    return
                time.sleep(3600)
                progressed = True
                break
            ledger, used = fetch_dong(s5, bjd, d, a.daily_budget)
            if used:
                quota_add(d, used)
            if ledger is None:
                continue
            progressed = True
            batch = []
            for did, j, ba, pa, by in e["deals"]:
                m = match_one(j, ba, pa, by, ledger)
                if m:
                    batch.append((did, s5, u, m[0], m[1], m[2], m[3], m[4], "nrg"))
                    rec += 1
                else:
                    # 미발견/모호 — 재시도 방지 위해 jibun=NULL로 기록
                    batch.append((did, s5, u, None, None, None, None, None, "nrg"))
                    miss += 1
            for did, tfa, pa, by in e.get("sh", []):
                m = match_sh(tfa, pa, by, ledger)
                if m:
                    batch.append((did, s5, u, m[0], m[1], m[2], m[3], m[4], "sh"))
                    rec += 1
                else:
                    batch.append((did, s5, u, None, None, None, None, None, "sh"))
                    miss += 1
            d.executemany("INSERT OR REPLACE INTO recovered(deal_id,sgg5,dong,jibun,bld_nm,tot_area,plat_area,use_apr,asset) "
                          "VALUES(?,?,?,?,?,?,?,?,?)", batch)
            d.commit()
        n_ok = d.execute("SELECT COUNT(*) FROM recovered WHERE jibun IS NOT NULL").fetchone()[0]
        n_all = d.execute("SELECT COUNT(*) FROM recovered").fetchone()[0]
        print(f"사이클 종료 — 이번 복원 {rec}·미발견/모호 {miss} · 누적 복원 {n_ok:,}/{n_all:,}", flush=True)
        if a.once or not progressed:
            break

if __name__ == "__main__":
    main()
