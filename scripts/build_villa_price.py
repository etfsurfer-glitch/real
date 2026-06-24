"""빌라 공동주택 공시가격 캐싱 — villa_master(좌표 완료) 건물별로 VWorld 공동주택가격을
받아 villa_price(호별, 최신연도만)에 저장. pnu는 법정동코드+지번으로 직접 구성(지오코더 불필요).
공시가격은 연 1회 공고라 한 번 받으면 다음 공고까지 재사용. 키당 일일한도 → 며칠/여러키.

    python scripts/build_villa_price.py --concurrency 8 --key <KEY>
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collector.config import settings  # noqa: E402

KEY = os.getenv("VWORLD_KEY", "")
DOMAIN = "koczip.com"
DB = str(settings.local_db_path)

_RL_LOCK = threading.Lock(); _RL_NEXT = [0.0]; _MIN_INTERVAL = 0.16


def _ratelimit():
    with _RL_LOCK:
        slot = max(time.time(), _RL_NEXT[0]); _RL_NEXT[0] = slot + _MIN_INTERVAL
    w = slot - time.time()
    if w > 0:
        time.sleep(w)


def _get(url, retries=4):
    for i in range(retries):
        try:
            _ratelimit()
            req = urllib.request.Request(url, headers={"User-Agent": "koczip/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(min(0.6 * (2 ** i), 8))
    return None


def build_pnu(ldcode: str, jibun: str):
    """법정동코드(10) + 특수지(1) + 본번(4) + 부번(4)."""
    jb = (jibun or "").strip()
    filar = "1"
    if jb.startswith("산"):
        filar = "2"; jb = jb[1:].strip()
    if "-" in jb:
        bon, bu = jb.split("-", 1)
    else:
        bon, bu = jb, "0"
    bon = "".join(ch for ch in bon if ch.isdigit())
    bu = "".join(ch for ch in bu if ch.isdigit())
    if not bon:
        return None
    return f"{ldcode}{filar}{int(bon):04d}{int(bu or 0):04d}"


def pnu_from_coords(lng, lat):
    """좌표 → pnu (LP_PA_CBND_BUBUN). 동코드 매핑 실패한 건물용 폴백."""
    if not (lng and lat):
        return None
    q = urllib.parse.urlencode({"service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
                                "key": KEY, "domain": DOMAIN, "crs": "EPSG:4326",
                                "geomFilter": f"POINT({lng} {lat})", "size": "1", "format": "json"})
    d = _get(f"https://api.vworld.kr/req/data?{q}")
    if not d:
        return None
    try:
        feats = d["response"]["result"]["featureCollection"]["features"]
        if feats:
            p = feats[0].get("properties", {})
            return p.get("pnu") or p.get("PNU")
    except Exception:
        pass
    return None


def fetch_price(pnu):
    """getApartHousingPriceAttr → 최신연도 호별 [(se,dong,floor,ho,area,gongsi,year,code,mt)]. 'quota'/'error'."""
    q = urllib.parse.urlencode({"key": KEY, "domain": DOMAIN, "pnu": pnu,
                                "format": "json", "numOfRows": "1000", "pageNo": "1"})
    d = _get(f"https://api.vworld.kr/ned/data/getApartHousingPriceAttr?{q}")
    if d is None:
        return "error"
    root = next(iter(d.values())) if d else {}
    if isinstance(root, dict) and root.get("resultCode") == "INCORRECT_KEY":
        return "error"
    # OVER_REQUEST_LIMIT 감지
    txt = json.dumps(d, ensure_ascii=False)
    if "OVER_REQUEST_LIMIT" in txt:
        return "quota"
    f = root.get("field", []) if isinstance(root, dict) else []
    if not isinstance(f, list):
        f = [f] if f else []
    if not f:
        return []  # 공동주택 없음(단독 등)
    yrs = [u.get("stdrYear", "") for u in f if u.get("stdrYear")]
    maxyr = max(yrs) if yrs else None
    out = []
    for u in f:
        if u.get("stdrYear") != maxyr or not u.get("pblntfPc"):
            continue
        out.append((u.get("aphusSeCodeNm"), u.get("dongNm"), u.get("floorNm"), u.get("hoNm"),
                    float(u.get("prvuseAr") or 0), int(u["pblntfPc"]), maxyr,
                    u.get("aphusCode"), u.get("stdrMt"), u.get("aphusNm")))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--key")
    a = p.parse_args()
    global KEY
    if a.key:
        KEY = a.key
    if not KEY:
        print("KEY 없음"); return 1
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL"); conn.execute("PRAGMA busy_timeout=60000")
    ld = {(r[0][:5], r[1]): r[0] for r in conn.execute(
        "SELECT cortar_no,cortar_name FROM regions WHERE cortar_type='sec'")}
    rows = conn.execute("SELECT key,sgg_cd,umd_nm,jibun,lat,lng FROM villa_master "
                        "WHERE status='ok' AND price_status IN ('pending','noldcode')").fetchall()
    total = len(rows)
    print(f"[price] pending {total:,}  conc={a.concurrency}")
    if not total:
        return 0
    lock = threading.Lock(); done = [0]; t0 = time.time(); hit_quota = [False]

    def work(row):
        key, sgg, umd, jibun, lat, lng = row
        ldc = ld.get((sgg, umd))
        pnu = build_pnu(ldc, jibun) if ldc else None
        if not pnu:                       # 동코드 매핑 실패 → 좌표로 pnu 폴백
            pnu = pnu_from_coords(lng, lat)
        if not pnu:
            return key, None, "noldcode", []
        r = fetch_price(pnu)
        if r == "quota":
            return key, pnu, "quota", []
        if r == "error":
            return key, pnu, "error", []
        return key, pnu, ("ok" if r else "empty"), r

    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        futs = [ex.submit(work, r) for r in rows]
        pbuf = []; ubuf = []
        for fut in as_completed(futs):
            key, pnu, st, units = fut.result()
            if st == "quota":
                hit_quota[0] = True; ex.shutdown(wait=False, cancel_futures=True); break
            for u in units:  # u=(se,dong,floor,ho,area,gongsi,year,code,mt,aphusNm)
                ubuf.append((pnu, u[9], u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7], u[8]))
            pbuf.append((pnu, st, key))
            with lock:
                done[0] += 1
                if len(pbuf) >= 100:
                    conn.executemany("UPDATE villa_master SET pnu=?,price_status=? WHERE key=?", pbuf)
                    if ubuf:
                        conn.executemany(
                            "INSERT INTO villa_price(pnu,aphus_nm,se_nm,dong,floor,ho,area_m2,gongsi,year,aphus_code,stdr_mt) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?)", ubuf)
                    conn.commit(); pbuf = []; ubuf = []
                if done[0] % 2000 == 0 or done[0] == total:
                    rate = done[0] / max(time.time() - t0, .001)
                    print(f"  [{done[0]:,}/{total:,}] {rate:.0f}/s ETA {(total-done[0])/max(rate,.001)/60:.0f}분")
        if pbuf:
            conn.executemany("UPDATE villa_master SET pnu=?,price_status=? WHERE key=?", pbuf)
            if ubuf:
                conn.executemany(
                    "INSERT INTO villa_price(pnu,aphus_nm,se_nm,dong,floor,ho,area_m2,gongsi,year,aphus_code,stdr_mt) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)", ubuf)
            conn.commit()
    ok = conn.execute("SELECT COUNT(*) FROM villa_master WHERE price_status='ok'").fetchone()[0]
    em = conn.execute("SELECT COUNT(*) FROM villa_master WHERE price_status='empty'").fetchone()[0]
    print(f"[done] {time.time()-t0:.0f}s ok={ok:,} empty={em:,}{' [일일한도]' if hit_quota[0] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
