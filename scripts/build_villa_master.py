"""평가 가능한 모든 빌라 마스터 — rh 실거래(매매+전월세)의 고유 빌라 건물(지번)을
VWorld 지오코딩해 좌표를 붙인다. 전세 감별기 지도에서 '현재 매물'이 아니라
'평가 가능한 모든 빌라'를 표시하기 위함. 재실행 가능(status='pending'만 처리).

    python scripts/build_villa_master.py --populate     # 키 채우기(빠름)
    python scripts/build_villa_master.py --geocode --concurrency 24
"""
from __future__ import annotations

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
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collector.config import settings  # noqa: E402  (load_dotenv 실행)

KEY = os.getenv("VWORLD_KEY", "")
DOMAIN = "koczip.com"
DB = str(settings.local_db_path)

SCHEMA = """
CREATE TABLE IF NOT EXISTS villa_master (
  key        TEXT PRIMARY KEY,
  sgg_cd     TEXT, umd_nm TEXT, jibun TEXT, building TEXT,
  area_avg   REAL, tx_count INTEGER,
  lat        REAL, lng REAL,
  status     TEXT DEFAULT 'pending',   -- pending|ok|notfound|error
  geocoded_at TEXT
);
CREATE INDEX IF NOT EXISTS vm_latlng_idx ON villa_master(lat, lng);
CREATE INDEX IF NOT EXISTS vm_status_idx ON villa_master(status);
"""


# 글로벌 레이트캡 — 동시성과 무관하게 전체 호출을 일정 간격으로 분산(버스트 차단 방지).
# 라이브 감별기(같은 IP)용 여유를 남기려 ~6/s로 제한.
_RL_LOCK = threading.Lock()
_RL_NEXT = [0.0]
_MIN_INTERVAL = 0.16


def _ratelimit():
    with _RL_LOCK:
        slot = max(time.time(), _RL_NEXT[0])
        _RL_NEXT[0] = slot + _MIN_INTERVAL
    wait = slot - time.time()
    if wait > 0:
        time.sleep(wait)


def _get(url: str) -> dict:
    _ratelimit()
    req = urllib.request.Request(url, headers={"User-Agent": "koczip/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(addr: str, retries: int = 5):
    """주소→(lat,lng). NOT_FOUND→None, 차단/일시오류→백오프 재시도 후 'error'."""
    q = urllib.parse.urlencode({"service": "address", "request": "getcoord", "version": "2.0",
                                "crs": "epsg:4326", "address": addr, "format": "json",
                                "type": "parcel", "key": KEY})
    url = f"https://api.vworld.kr/req/address?{q}"
    for i in range(retries):
        try:
            d = _get(url)
            res = d.get("response", {})
            st = res.get("status")
            if st == "OK":
                pt = res["result"]["point"]
                return float(pt["y"]), float(pt["x"])   # lat, lng
            if st == "NOT_FOUND":
                return None
            if st == "ERROR":
                code = (res.get("error") or {}).get("code", "")
                if "OVER_REQUEST_LIMIT" in code:
                    return "quota"      # 일일한도 소진 → 상위에서 graceful 정지
            # 기타 ERROR/일시차단 → 백오프
        except Exception:
            pass
        time.sleep(min(0.6 * (2 ** i), 8) + (i * 0.1))
    return "error"


def populate(conn):
    conn.executescript(SCHEMA)
    print("[populate] rh 고유 빌라 건물 채우는 중…")
    conn.execute("""
        INSERT OR IGNORE INTO villa_master(key,sgg_cd,umd_nm,jibun,building,area_avg,tx_count)
        SELECT sgg_cd||'|'||umd_nm||'|'||jibun, sgg_cd, umd_nm, jibun, MAX(b), AVG(a), COUNT(*)
        FROM (
          SELECT sgg_cd,umd_nm,jibun, excl_use_ar a, NULLIF(mhouse_nm,'') b
            FROM rh_transactions WHERE jibun!='' AND sgg_cd!=''
          UNION ALL
          SELECT sgg_cd,umd_nm,jibun, excl_use_ar a, NULLIF(mhouse_nm,'') b
            FROM rh_rentals WHERE jibun!='' AND sgg_cd!=''
        ) GROUP BY sgg_cd,umd_nm,jibun
    """)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM villa_master").fetchone()[0]
    pend = conn.execute("SELECT COUNT(*) FROM villa_master WHERE status='pending'").fetchone()[0]
    print(f"[populate] 총 {n:,} 건물 (pending {pend:,})")


def run_geocode(conn, concurrency, shard=None):
    sido = {r[0][:2]: r[1] for r in conn.execute(
        "SELECT cortar_no,cortar_name FROM regions WHERE cortar_type='city'")}
    sgg = {r[0][:5]: r[1] for r in conn.execute(
        "SELECT cortar_no,cortar_name FROM regions WHERE cortar_type='dvsn'")}
    sql = "SELECT key,sgg_cd,umd_nm,jibun FROM villa_master WHERE status='pending'"
    if shard:                       # "r/n" → rowid % n == r (2키 분산 처리)
        r, n = shard.split("/")
        sql += f" AND rowid % {int(n)} = {int(r)}"
    rows = conn.execute(sql).fetchall()
    total = len(rows)
    print(f"[geocode] pending {total:,}  concurrency={concurrency}")
    if not total:
        return
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    def work(row):
        key, s, umd, jibun = row
        addr = f"{sido.get(s[:2], '')} {sgg.get(s, '')} {umd} {jibun}".strip()
        r = geocode(addr)
        if r == "quota":
            return key, None, None, "quota"
        if r == "error":
            return key, None, None, "error"
        if r:
            return key, r[0], r[1], "ok"
        return key, None, None, "notfound"

    buf = []
    hit_quota = False
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(work, r) for r in rows]
        for fut in as_completed(futs):
            key, lat, lng, st = fut.result()
            if st == "quota":           # 일일한도 소진 → 남은 건 pending 유지하고 정지
                hit_quota = True
                ex.shutdown(wait=False, cancel_futures=True)
                break
            buf.append((lat, lng, st, key))
            with lock:
                done[0] += 1
                if len(buf) >= 100:
                    conn.executemany("UPDATE villa_master SET lat=?,lng=?,status=?,"
                                     "geocoded_at=datetime('now') WHERE key=?", buf)
                    conn.commit(); buf = []
                if done[0] % 2000 == 0 or done[0] == total:
                    rate = done[0] / max(time.time() - t0, 0.001)
                    eta = (total - done[0]) / max(rate, 0.001)
                    print(f"  [{done[0]:,}/{total:,}] {rate:.0f}/s  ETA {eta/60:.1f}분")
    if buf:
        conn.executemany("UPDATE villa_master SET lat=?,lng=?,status=?,"
                         "geocoded_at=datetime('now') WHERE key=?", buf)
        conn.commit()
    ok = conn.execute("SELECT COUNT(*) FROM villa_master WHERE status='ok'").fetchone()[0]
    nf = conn.execute("SELECT COUNT(*) FROM villa_master WHERE status='notfound'").fetchone()[0]
    pend = conn.execute("SELECT COUNT(*) FROM villa_master WHERE status='pending'").fetchone()[0]
    tag = " [일일한도 소진 — 내일/다른키로 재개]" if hit_quota else ""
    print(f"[done] {time.time()-t0:.0f}s  ok={ok:,}  notfound={nf:,}  pending={pend:,}{tag}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--populate", action="store_true")
    p.add_argument("--geocode", action="store_true")
    p.add_argument("--concurrency", type=int, default=24)
    p.add_argument("--shard", help="r/n (2키 분산: 0/2, 1/2)")
    p.add_argument("--key", help="VWORLD_KEY 오버라이드(2번째 키)")
    a = p.parse_args()
    global KEY
    if a.key:
        KEY = a.key
    if not KEY:
        print("VWORLD_KEY 미설정"); return 1
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    if a.populate or not a.geocode:
        populate(conn)
    if a.geocode:
        run_geocode(conn, a.concurrency, a.shard)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
