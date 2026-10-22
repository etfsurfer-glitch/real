# -*- coding: utf-8 -*-
"""도로명만 등록된 중개사무소 → 법정동 (VWorld 주소정제).

왜 필요한가
  '우리동네 중개사'는 사무소가 어느 동에 있는지를 알아야 한다. build_realtor_dong 은
  ① vworld 의 dong_name ② vworld 주소 원문의 동명 ③ 매칭된 네이버 계정의 cortar_no
  로 푸는데, 도로명만 등록되고 네이버 매칭도 없는 사무소는 세 단계 모두 단서가 없다
  (2026-10-22 전국 대조에서 12,787곳). 주소는 있으니 주소를 물어보면 된다.

어떻게
  VWorld getcoord(refine=true) 는 정제 결과에 structure.level3 로 **법정동명**을 준다.
  좌표를 거쳐 역지오코딩할 필요가 없다. 그 이름을 regions(sec) 에서 찾아 cortar_no 로 바꾼다.
    "서울특별시 종로구 종로39길 47 3층" → level3='효제동' → 1111010700

오귀속 0 원칙
  ① 응답의 시군구명(level2)이 그 사무소의 시군구와 같아야 한다 — 동명은 시군구를 넘나들며
     겹친다('중앙동'은 전국에 여럿). 시군구가 다르면 버린다.
  ② level3 가 그 시군구 regions(sec) 에 실제로 있어야 한다.
  둘 중 하나라도 어긋나면 기록하지 않는다. 억지로 채우지 않는다.

기록
  coord_addr.sqlite 의 broker_dong_fwd(sys_regno PK, …, status)
  · status='ok'  — 법정동 확정
  · status='fail' — VWorld 가 NOT_FOUND 로 답했거나 가드 탈락. 다음 실행에서 재시도 안 함
                    (--retry-fail 로 재시도)
  · 스로틀·서버오류·예외는 아무것도 기록하지 않는다 → 다음 실행에서 자동 재시도

사용
  python3 scripts/geocode_broker_dong.py                 # 전체(미해결 전부)
  python3 scripts/geocode_broker_dong.py --limit 300      # 일일 점증
  python3 scripts/geocode_broker_dong.py --retry-fail
"""
import argparse
import json
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from collector.icn_remap import ICN_DONG_REMAP  # noqa: E402

NV = "/opt/koczip/data/naverreal.sqlite"
CA = "/opt/koczip/data/coord_addr.sqlite"
API = "https://api.vworld.kr/req/address"

DDL = """
CREATE TABLE IF NOT EXISTS broker_dong_fwd(
    sys_regno   TEXT PRIMARY KEY,
    sgg_cd      TEXT,
    cortar_no   TEXT,
    dong_name   TEXT,
    lat         REAL,
    lng         REAL,
    status      TEXT,
    geocoded_at TEXT DEFAULT (datetime('now'))
)
"""


def load_keys():
    keys = []
    for line in open("/opt/koczip/.env"):
        line = line.strip()
        if line.startswith("VWORLD_KEY"):
            keys.append(line.split("=", 1)[1].strip())
    if not keys:
        sys.exit("VWORLD_KEY 없음")
    return keys


def sgg_remap(nv):
    """광주·전남 통합코드(12xxx) → regions 가 쓰는 29xxx·46xxx. 시군구 이름으로 1:1."""
    by_name = {}
    for no, nm in nv.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn' "
                             "AND (cortar_no LIKE '29%' OR cortar_no LIKE '46%')"):
        by_name.setdefault(nm, []).append(no[:5])
    out = {}
    for sgg5, nm in nv.execute("SELECT DISTINCT sgg5, sgg_nm FROM bjd WHERE code10 LIKE '12%'"):
        hit = by_name.get(nm)
        if hit and len(hit) == 1:
            out[sgg5] = hit[0]
    return out


def load_regions(nv):
    """(시군구5 → 시군구명, (시군구5, 동명) → cortar_no)."""
    sgg_name, sec, name_of = {}, {}, {}
    for no, nm in nv.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn'"):
        sgg_name[no[:5]] = nm
    for no, nm in nv.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='sec'"):
        sec[(no[:5], nm)] = no
        name_of[no] = nm
    # 인천 2026-07 개편 — vworld 는 소멸한 중·동·서구(28110·28140·28260)로 등록해 두는데
    # regions 는 신설구(제물포·영종·서해·검단)만 들고 있다. '중구 운서동'을 중구에서 찾으면
    # 없어서 가드②가 통째로 버린다(2026-10-22, 인천 75곳). 검증된 옛동→신동 표로 옛 구
    # 번호에도 같은 동을 달아 둔다. 표에 있는 동만 달리므로 다른 구가 섞일 여지는 없다.
    for old, new in ICN_DONG_REMAP.items():
        nm = name_of.get(new)
        if nm:
            sec.setdefault((old[:5], nm), new)
    return sgg_name, sec


def targets(nv, ca, remap):
    """realtor_dong 이 못 푼 사무소 — 주소가 있고 아직 안 물어본 것."""
    done = {r[0] for r in ca.execute("SELECT sys_regno FROM broker_dong_fwd")}
    out = []
    for sys_regno, sgg_cd, address in nv.execute(
            "SELECT v.sys_regno, v.sgg_cd, v.address FROM vworld_brokers v "
            "WHERE v.sys_regno NOT IN (SELECT sys_regno FROM realtor_dong) "
            "  AND v.address IS NOT NULL AND v.address <> ''"):
        if sys_regno in done:
            continue
        out.append((sys_regno, remap.get(sgg_cd, sgg_cd), address))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rps", type=float, default=10.0, help="전체 초당 요청 상한")
    ap.add_argument("--retry-fail", action="store_true")
    a = ap.parse_args()

    keys = load_keys()
    nv = sqlite3.connect(f"file:{NV}?mode=ro", uri=True, timeout=300)
    nv.execute("PRAGMA busy_timeout=60000")
    ca = sqlite3.connect(CA, timeout=60)
    ca.execute("PRAGMA journal_mode=WAL")
    ca.execute("PRAGMA journal_size_limit=1073741824")
    ca.execute(DDL)
    if a.retry_fail:
        ca.execute("DELETE FROM broker_dong_fwd WHERE status='fail'")
        ca.commit()

    remap = sgg_remap(nv)
    sgg_name, sec = load_regions(nv)
    todo = targets(nv, ca, remap)
    if a.limit:
        todo = todo[:a.limit]
    print(f"대상 사무소: {len(todo):,}", flush=True)
    if not todo:
        return 0

    lock = threading.Lock()
    stat = {"ok": 0, "fail": 0, "err": 0, "n": 0, "guard_sgg": 0, "guard_dong": 0, "road": 0, "parcel": 0}
    buf, ki = [], [0]
    gap = a.workers / max(a.rps, 1.0)

    def ask(addr, kind, key):
        params = {"service": "address", "request": "getcoord", "version": "2.0",
                  "crs": "epsg:4326", "type": kind, "refine": "true", "simple": "false",
                  "format": "json", "address": addr, "key": key}
        with urllib.request.urlopen(API + "?" + urllib.parse.urlencode(params), timeout=15) as r:
            return json.loads(r.read().decode("utf-8", "replace")).get("response", {})

    def work(item):
        sys_regno, eff_sgg, addr = item
        with lock:
            key = keys[ki[0] % len(keys)]
            ki[0] += 1
        time.sleep(gap)
        resp, used = None, None
        try:
            for kind in ("ROAD", "PARCEL"):      # 도로명 우선, 아니면 지번으로 한 번 더
                resp = ask(addr, kind, key)
                used = kind
                if resp.get("status") == "OK":
                    break
                if resp.get("status") != "NOT_FOUND":
                    return (sys_regno, eff_sgg, None, None, None, None, "err", used)
        except Exception:
            return (sys_regno, eff_sgg, None, None, None, None, "err", used)

        if (resp or {}).get("status") != "OK":
            return (sys_regno, eff_sgg, None, None, None, None, "fail", used)
        ref = resp.get("refined") or {}
        st = ref.get("structure") or {}
        lv2, lv3 = (st.get("level2") or "").strip(), (st.get("level3") or "").strip()
        want = sgg_name.get(eff_sgg) or ""
        if want and lv2 and lv2 != want:          # 가드① 시군구가 다르면 버린다
            return (sys_regno, eff_sgg, None, None, None, None, "guard_sgg", used)
        cortar = sec.get((eff_sgg, lv3))
        if not cortar:                            # 가드② 그 시군구에 없는 동이면 버린다
            return (sys_regno, eff_sgg, None, None, None, None, "guard_dong", used)
        pt = (resp.get("result") or {}).get("point") or {}
        try:
            lat, lng = float(pt["y"]), float(pt["x"])
        except Exception:
            lat = lng = None
        return (sys_regno, eff_sgg, cortar, lv3, lat, lng, "ok", used)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for sys_regno, eff, cortar, dong, lat, lng, status, used in ex.map(work, todo):
            with lock:
                stat["n"] += 1
                if used:
                    stat["road" if used == "ROAD" else "parcel"] += 1
                if status == "err":
                    stat["err"] += 1              # 기록 안 함 → 다음 실행 재시도
                else:
                    if status in ("guard_sgg", "guard_dong"):
                        stat[status] += 1
                        stat["fail"] += 1
                        status = "fail"
                    else:
                        stat[status] += 1
                    buf.append((sys_regno, eff, cortar, dong, lat, lng, status))
                if len(buf) >= 300:
                    ca.executemany("INSERT OR REPLACE INTO broker_dong_fwd"
                                   "(sys_regno,sgg_cd,cortar_no,dong_name,lat,lng,status) "
                                   "VALUES(?,?,?,?,?,?,?)", buf)
                    ca.commit()
                    buf.clear()
                if stat["n"] >= 200 and stat["err"] / stat["n"] > 0.6:
                    print("⚠ err율 %.0f%% — 키 보호 위해 중단(다음 실행에서 재시도)"
                          % (100.0 * stat["err"] / stat["n"]), flush=True)
                    break
                if stat["n"] % 1000 == 0:
                    el = time.time() - t0
                    print("  %6d/%d  확정 %d · 실패 %d · 오류 %d  (%.0f건/분)"
                          % (stat["n"], len(todo), stat["ok"], stat["fail"], stat["err"],
                             60.0 * stat["n"] / max(el, 1)), flush=True)
    if buf:
        ca.executemany("INSERT OR REPLACE INTO broker_dong_fwd"
                       "(sys_regno,sgg_cd,cortar_no,dong_name,lat,lng,status) "
                       "VALUES(?,?,?,?,?,?,?)", buf)
        ca.commit()
    print("[*] 완료 %d — 법정동 확정 %d · 실패 %d(시군구 불일치 %d · 동 없음 %d) · 오류 %d"
          % (stat["n"], stat["ok"], stat["fail"], stat["guard_sgg"], stat["guard_dong"], stat["err"]),
          flush=True)
    print("    조회 방식: 도로명 %d · 지번 폴백 %d" % (stat["road"], stat["parcel"]), flush=True)
    ca.close()
    nv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
