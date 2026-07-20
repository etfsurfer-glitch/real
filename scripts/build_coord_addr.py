# -*- coding: utf-8 -*-
"""비단지 매물 좌표 → 지번주소 캐시(VWorld 역지오코딩).

배경(2026-07-20): 비단지(상가·사무실·빌라·단독·토지…) 매물은 네이버 원본에 지번이 없다
(detailAddress 공백, cortar_no만 옴). 그래서 매물장·중개사 세부페이지 주소가 '서울 마포구 합정동'
까지밖에 못 갔다. 반면 좌표(lat/lng)는 **100% 있다** → 역지오코딩으로 지번을 확보한다.

핵심: 매물이 아니라 **좌표 단위로 캐시**한다.
  · 같은 건물 매물이 좌표를 공유 → 매물 1,797,648건 = 고유좌표 515,863개(28.7%)로 3.5배 축소.
  · 좌표는 불변이라 한 번 받아두면 재조회 불필요. 매물이 내려가도 캐시는 계속 재사용된다.
  · 수집 루틴은 '아직 모르는 좌표'만 새로 적재 → 매일 소량만 처리하면 된다.

호출 한도(실측): VWorld 지오코더 키당 하루 약 40,000건(OVER_REQUEST_LIMIT), 속도 약 6건/초.
키 5개(VWORLD_KEY~KEY5) 순회 → 하루 약 20만 → 최초 51.6만 건은 3일이면 완료.
빌라 좌표 배치(build_villa_master.py)와 같은 방식: 한도 소진 시 남은 건 pending 유지하고 정지,
야간 크론이 다음 키·다음 날 이어서 처리.

사용:
  build_coord_addr.py --scan                      # 비단지 DB에서 새 좌표 적재(호출 0)
  build_coord_addr.py --geocode --key KEY [--concurrency 8] [--limit N]
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, ".")
from collector.config import settings                     # noqa: E402

DATA = os.path.dirname(settings.local_db_path)
CACHE_DB = os.path.join(DATA, "coord_addr.sqlite")
NONRESI = ["sangga", "office", "villa", "house", "land", "factory",
           "building", "knowledge", "redev", "oneroom"]
PREC = 5          # 좌표 반올림 자리(≈1.1m) — 건물 구분엔 충분하고 중복은 최대로 접힌다
BATCH = 2000      # 한 번에 제출할 future 수 — 51.5만을 통째로 제출하면 메모리 1GB+로 뜬다
# 호출 간격: 빌라 배치에서 검증된 값(0.16s≈6/s). 더 조이면(0.02s≈50/s) VWorld가 스로틀링해
# error 가 쌓인다(2026-07-20 실측: 50/s로 돌렸더니 1,888 ok 대비 error 211).
_RL_LOCK = threading.Lock()
_RL_NEXT = [0.0]
MIN_GAP = 0.16

SCHEMA = """
CREATE TABLE IF NOT EXISTS coord_addr(
  ckey TEXT PRIMARY KEY,            -- 'lat,lng' 반올림 키
  lat REAL, lng REAL,
  addr TEXT,                        -- VWorld 전체 지번주소 '서울특별시 강남구 역삼동 813-14'
  sido TEXT, sgg TEXT, dong TEXT,
  status TEXT DEFAULT 'pending',    -- pending / ok / notfound / error
  geocoded_at TEXT
);
CREATE INDEX IF NOT EXISTS ca_status ON coord_addr(status);
"""


def ckey(lat, lng) -> str:
    return f"{round(float(lat), PREC)},{round(float(lng), PREC)}"


def _open_cache() -> sqlite3.Connection:
    c = sqlite3.connect(CACHE_DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA journal_size_limit=268435456")
    c.execute("PRAGMA busy_timeout=60000")
    c.executescript(SCHEMA)
    return c


def scan(conn) -> None:
    """비단지 DB 현재 스냅샷의 고유 좌표를 pending 으로 적재(이미 있으면 무시)."""
    seen = {r[0] for r in conn.execute("SELECT ckey FROM coord_addr")}
    print(f"[scan] 기존 캐시 {len(seen):,}건", flush=True)
    add = []
    for cat in NONRESI:
        p = os.path.join(DATA, f"listings_{cat}.sqlite")
        if not os.path.exists(p):
            continue
        with sqlite3.connect(f"file:{p}?mode=ro", uri=True) as nc:
            nc.execute("PRAGMA busy_timeout=60000")
            snap = nc.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
            if not snap:
                continue
            n = 0
            for la, lo in nc.execute(
                    "SELECT DISTINCT latitude, longitude FROM listings "
                    "WHERE snapshot_date=? AND latitude IS NOT NULL AND longitude IS NOT NULL", (snap,)):
                k = ckey(la, lo)
                if k in seen:
                    continue
                seen.add(k)
                add.append((k, round(float(la), PREC), round(float(lo), PREC)))
                n += 1
        print(f"  {cat}: 신규 {n:,}", flush=True)
    if add:
        conn.executemany("INSERT OR IGNORE INTO coord_addr(ckey,lat,lng) VALUES(?,?,?)", add)
        conn.commit()
    pend = conn.execute("SELECT COUNT(*) FROM coord_addr WHERE status='pending'").fetchone()[0]
    tot = conn.execute("SELECT COUNT(*) FROM coord_addr").fetchone()[0]
    print(f"[scan] 신규 {len(add):,} 적재 · 총 {tot:,} (pending {pend:,})", flush=True)


def _ratelimit() -> None:
    """슬롯 예약식 — 락 안에서는 시각만 잡고 sleep은 밖에서(락 쥔 채 자면 전 스레드가 직렬화된다)."""
    with _RL_LOCK:
        slot = max(time.time(), _RL_NEXT[0])
        _RL_NEXT[0] = slot + MIN_GAP
    wait = slot - time.time()
    if wait > 0:
        time.sleep(wait)


def revgeo(lat, lng, key, retries: int = 4):
    """좌표→지번주소. ('ok', text, sido, sgg, dong) / 'notfound' / 'quota' / 'error'."""
    q = urllib.parse.urlencode({"service": "address", "request": "getAddress", "version": "2.0",
                                "crs": "epsg:4326", "point": f"{lng},{lat}", "format": "json",
                                "type": "parcel", "key": key})
    url = f"https://api.vworld.kr/req/address?{q}"
    for i in range(retries):
        try:
            _ratelimit()
            req = urllib.request.Request(url, headers={"User-Agent": "koczip/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read().decode("utf-8"))
            res = d.get("response", {})
            st = res.get("status")
            if st == "OK":
                it = (res.get("result") or [{}])[0]
                s = it.get("structure", {}) or {}
                return ("ok", it.get("text") or "", s.get("level1") or "",
                        s.get("level2") or "", s.get("level4L") or s.get("level4A") or "")
            if st == "NOT_FOUND":
                return "notfound"
            if st == "ERROR":
                code = (res.get("error") or {}).get("code", "") or ""
                text = (res.get("error") or {}).get("text", "") or ""
                if "OVER_REQUEST_LIMIT" in (code + text).upper():
                    return "quota"
        except Exception:
            pass
        time.sleep(min(0.5 * (2 ** i), 6))
    return "error"


def run_geocode(conn, key: str, concurrency: int, limit: int) -> bool:
    """pending 좌표를 역지오코딩. 한도 소진 시 True(=quota) 반환하고 남은 건 pending 유지."""
    sql = "SELECT ckey,lat,lng FROM coord_addr WHERE status IN ('pending','error')"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    total = len(rows)
    print(f"[geocode] 대상 {total:,}  concurrency={concurrency}", flush=True)
    if not total:
        return False
    lock = threading.Lock()
    done = [0]
    t0 = time.time()
    buf = []
    hit_quota = False

    def work(row):
        k, la, lo = row
        r = revgeo(la, lo, key)
        if r == "quota":
            return (k, None, None, None, None, "quota")
        if r == "notfound":
            return (k, None, None, None, None, "notfound")
        if r == "error":
            return (k, None, None, None, None, "error")
        _, text, sido, sgg, dong = r
        return (k, text, sido, sgg, dong, "ok")

    # BATCH 단위로 나눠 제출 — 전량 제출하면 future 수십만 개가 메모리를 잡아먹는다
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for start in range(0, total, BATCH):
            if hit_quota:
                break
            chunk = rows[start:start + BATCH]
            for fut in as_completed([ex.submit(work, r) for r in chunk]):
                k, text, sido, sgg, dong, st = fut.result()
                if st == "quota":
                    hit_quota = True
                    break
                buf.append((text, sido, sgg, dong, st, k))
                with lock:
                    done[0] += 1
                    if len(buf) >= 200:
                        conn.executemany("UPDATE coord_addr SET addr=?,sido=?,sgg=?,dong=?,status=?,"
                                         "geocoded_at=datetime('now') WHERE ckey=?", buf)
                        conn.commit(); buf = []
                    if done[0] % 5000 == 0:
                        rate = done[0] / max(time.time() - t0, 0.001)
                        print(f"  [{done[0]:,}/{total:,}] {rate:.1f}/s  ETA {(total-done[0])/max(rate,.001)/3600:.1f}시간", flush=True)
    if buf:
        conn.executemany("UPDATE coord_addr SET addr=?,sido=?,sgg=?,dong=?,status=?,"
                         "geocoded_at=datetime('now') WHERE ckey=?", buf)
    conn.commit()
    ok = conn.execute("SELECT COUNT(*) FROM coord_addr WHERE status='ok'").fetchone()[0]
    pend = conn.execute("SELECT COUNT(*) FROM coord_addr WHERE status IN ('pending','error')").fetchone()[0]
    tag = " [일일한도 소진 — 다음 키/내일 재개]" if hit_quota else ""
    print(f"[done] {time.time()-t0:.0f}s  처리 {done[0]:,} · ok 누적 {ok:,} · 남은 {pend:,}{tag}", flush=True)
    return hit_quota


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="비단지 DB에서 신규 좌표 적재(API 호출 없음)")
    ap.add_argument("--geocode", action="store_true")
    ap.add_argument("--key", default=os.getenv("VWORLD_KEY", ""))
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="이번 실행 최대 처리 좌표 수")
    a = ap.parse_args()
    conn = _open_cache()
    if a.scan:
        scan(conn)
    if a.geocode:
        if not a.key:
            print("[err] VWorld 키 없음(--key 또는 VWORLD_KEY)", flush=True)
            return 2
        run_geocode(conn, a.key, a.concurrency, a.limit)
    if not (a.scan or a.geocode):
        tot = conn.execute("SELECT COUNT(*) FROM coord_addr").fetchone()[0]
        for st, n in conn.execute("SELECT status, COUNT(*) FROM coord_addr GROUP BY status ORDER BY 2 DESC"):
            print(f"  {st:<9}{n:>9,}")
        print(f"  {'합계':<9}{tot:>9,}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
