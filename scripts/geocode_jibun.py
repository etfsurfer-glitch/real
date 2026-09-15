# -*- coding: utf-8 -*-
"""빌라(rh)·상가(nrg) 실거래 지번 → 좌표 정방향 지오코딩(VWorld getcoord, PARCEL).
coord_jibun(역지오코딩 파생, dong+jibun)에 없는 지번을 채워 실거래 지도 커버리지를 100%로.

- 대상: rh_transactions + nrg_transactions 의 distinct (sgg_cd5, umd_nm, jibun)
- 결과: coord_addr.sqlite 의 coord_jibun_fwd(sgg5,dong,jibun,lat,lng,status)
  · status='ok'|'fail' — fail 도 기록해 다음 실행에서 재시도 안 함(--retry-fail 로 재시도)
- 키 5개 라운드로빈 + 스레드 병렬 + 속도제한(--rps, 기본 12 — 과속 시 VWorld가 연결을 끊음).
- fail 은 NOT_FOUND(진짜 없는 주소)만. 스로틀/서버오류(ERROR·예외)는 기록 안 해 다음 실행에서 재시도.
사용: python3 geocode_jibun.py [--limit N] [--workers 4] [--rps 12] [--retry-fail]
"""
import argparse, json, os, sqlite3, sys, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

NV = "/opt/koczip/data/naverreal.sqlite"
CA = "/opt/koczip/data/coord_addr.sqlite"
API = "https://api.vworld.kr/req/address"

def load_keys():
    """(keys, domain). VWORLD_KEY(1번)는 도메인 등록형 무제한 키 — domain 파라미터와 함께
    쓰면 일일쿼터·스로틀이 사실상 없음(실측 err 0%). 기본은 무제한 키 단독 사용."""
    keys, domain = [], None
    for line in open("/opt/koczip/.env"):
        line = line.strip()
        if line.startswith("VWORLD_DOMAIN="):
            domain = line.split("=", 1)[1].strip()
        elif line.startswith("VWORLD_KEY"):
            keys.append(line.split("=", 1)[1].strip())
    if not keys:
        sys.exit("VWORLD_KEY 없음")
    return keys, (domain or "koczip.com")

def region_names(nv):
    """sgg5 → (시도명, 시군구명). 세종처럼 시도=시군구 중복이면 시군구 생략."""
    # 광주전남 통합개편(2026-07-01)의 시도 '표시명'은 VWorld가 인식 못 한다
    # ("전남광주통합특별시 (전남권)" → NOT_FOUND). 지오코딩 쿼리엔 실제 행정명을 쓴다.
    _SIDO_GEO = {"46": "전라남도", "29": "광주광역시"}
    m = {}
    sido = {r[0][:2]: r[1] for r in nv.execute(
        "SELECT cortar_no, cortar_name FROM regions WHERE cortar_no LIKE '__00000000'")}
    for cno, cname in nv.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_no LIKE '_____00000' AND cortar_no NOT LIKE '__00000000'"):
        s5 = cno[:5]
        sd = _SIDO_GEO.get(s5[:2]) or sido.get(s5[:2], "")
        m[s5] = (sd, cname)
    return m

def targets(nv, ca):
    have = set()
    for d, j in ca.execute("SELECT dong, jibun FROM coord_jibun"):
        have.add((d, j))
    done = set()
    for s, d, j in ca.execute("SELECT sgg5, dong, jibun FROM coord_jibun_fwd"):
        done.add((s, d, j))
    out = []
    # 매매 실거래(transactions)는 단지매칭 좌표에 의존하므로, 단지 미매칭분(주로 네이버 단지DB에
    # 없는 시골 아파트)만 지번 지오코딩 대상에 추가한다 — 매칭분은 이미 단지 좌표를 갖는다.
    for t, extra in (("rh_transactions", ""),
                     ("nrg_transactions", ""),
                     ("transactions", "AND matched_complex_no IS NULL AND is_cancelled=0"),
                     ("offi_transactions", "AND matched_complex_no IS NULL AND is_cancelled=0")):
        for s, d, j in nv.execute(
                f"SELECT DISTINCT substr(sgg_cd,1,5), umd_nm, jibun FROM {t} "
                f"WHERE jibun IS NOT NULL AND jibun<>'' AND umd_nm IS NOT NULL {extra}"):
            if (d, j) in have or (s, d, j) in done:
                continue
            out.append((s, d, j))
    # 건축물대장 역매칭으로 복원된 마스킹 지번(ledger_recover.recovered)도 좌표 확보 대상
    try:
        lr = sqlite3.connect("file:/opt/koczip/data/ledger_recover.sqlite?mode=ro", uri=True)
        for s, d, j in lr.execute("SELECT DISTINCT sgg5, dong, jibun FROM recovered WHERE jibun IS NOT NULL"):
            if (d, j) in have or (s, d, j) in done:
                continue
            out.append((s, d, j))
        lr.close()
    except Exception:
        pass
    # 중복 제거(두 테이블 겹침)
    return sorted(set(out))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rps", type=float, default=10.0)
    ap.add_argument("--retry-fail", action="store_true")
    ap.add_argument("--key-idx", default="", help="사용할 키 번호(1부터, 콤마) — 미지정 시 전부")
    ap.add_argument("--reverse", action="store_true", help="목록 역순 처리(다른 러너와 양끝 분담)")
    a = ap.parse_args()

    keys, vw_domain = load_keys()
    if a.key_idx:
        idx = [int(x) - 1 for x in a.key_idx.split(",") if x.strip()]
        keys = [keys[i] for i in idx if 0 <= i < len(keys)]
        print(f"키 {len(keys)}개만 사용: {a.key_idx}", flush=True)
    vw_domain = None   # domain 파라미터는 라이브 API 전용 키 태우는 위험 — 배치는 미사용
    nv = sqlite3.connect(f"file:{NV}?mode=ro", uri=True)
    nv.execute("PRAGMA busy_timeout=60000")
    ca = sqlite3.connect(CA, timeout=30)
    ca.execute("PRAGMA journal_mode=WAL")
    ca.execute("CREATE TABLE IF NOT EXISTS coord_jibun_fwd("
               "sgg5 TEXT, dong TEXT, jibun TEXT, lat REAL, lng REAL, status TEXT, "
               "geocoded_at TEXT DEFAULT (datetime('now')), PRIMARY KEY(sgg5,dong,jibun))")
    if a.retry_fail:
        ca.execute("DELETE FROM coord_jibun_fwd WHERE status='fail'")
        ca.commit()

    names = region_names(nv)
    todo = targets(nv, ca)
    if a.reverse:
        todo = todo[::-1]
    if a.limit:
        todo = todo[:a.limit]
    print(f"대상 지번: {len(todo):,}", flush=True)

    lock = threading.Lock()
    stats = {"ok": 0, "fail": 0, "err": 0, "n": 0}
    buf = []
    ki = [0]

    gap = a.workers / max(a.rps, 1.0)   # 워커당 요청 간격 → 전체 rps 상한

    def geocode(item):
        s5, dong, jibun = item
        if "*" in jibun:                 # 원본 마스킹 지번 — 정밀 좌표 불가(API 호출 낭비 방지)
            return (s5, dong, jibun, None, None, "fail")
        sd, sg = names.get(s5, ("", ""))
        parts = [sd]
        if sg and sg not in sd and sd not in sg:
            parts.append(sg)
        parts += [dong, jibun]
        addr = " ".join(p for p in parts if p)
        with lock:
            k = keys[ki[0] % len(keys)]; ki[0] += 1
        params = {
            "service": "address", "request": "getcoord", "version": "2.0",
            "crs": "epsg:4326", "type": "PARCEL", "refine": "true", "simple": "false",
            "format": "json", "address": addr, "key": k}
        if vw_domain:
            params["domain"] = vw_domain
        q = urllib.parse.urlencode(params)
        time.sleep(gap)
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=12) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            resp = d.get("response", {})
            st = resp.get("status")
            if st == "OK":
                pt = resp["result"]["point"]
                return (s5, dong, jibun, float(pt["y"]), float(pt["x"]), "ok")
            if st == "NOT_FOUND":        # 진짜 없는 주소만 영구 fail
                return (s5, dong, jibun, None, None, "fail")
            return (s5, dong, jibun, None, None, "err")   # ERROR(스로틀 등) → 재시도 대상
        except Exception:
            return (s5, dong, jibun, None, None, "err")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for res in ex.map(geocode, todo):
            s5, dong, jibun, lat, lng, st = res
            with lock:
                stats["n"] += 1
                if st == "err":
                    stats["err"] += 1   # 네트워크 오류는 기록 안 함(다음 실행에서 재시도)
                else:
                    stats[st] += 1
                    buf.append((s5, dong, jibun, lat, lng, st))
                if len(buf) >= 500:
                    ca.executemany("INSERT OR REPLACE INTO coord_jibun_fwd(sgg5,dong,jibun,lat,lng,status) VALUES(?,?,?,?,?,?)", buf)
                    ca.commit(); buf.clear()
                if stats["n"] >= 300 and stats["err"] / stats["n"] > 0.6:
                    print(f"⚠ err율 {100*stats['err']/stats['n']:.0f}% — 키 보호 위해 중단(다음 실행에서 재시도)", flush=True)
                    break
                if stats["n"] % 2000 == 0:
                    el = time.time() - t0
                    print(f"  {stats['n']:,}/{len(todo):,} ok={stats['ok']:,} fail={stats['fail']:,} err={stats['err']:,} "
                          f"{stats['n']/el:.1f}/s ETA {int((len(todo)-stats['n'])/(stats['n']/el)/60)}분", flush=True)
    if buf:
        ca.executemany("INSERT OR REPLACE INTO coord_jibun_fwd(sgg5,dong,jibun,lat,lng,status) VALUES(?,?,?,?,?,?)", buf)
        ca.commit()
    print(f"완료: {stats['n']:,}건 · ok {stats['ok']:,} · fail {stats['fail']:,} · err {stats['err']:,} · {int(time.time()-t0)}s", flush=True)

if __name__ == "__main__":
    main()
