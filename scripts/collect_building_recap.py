"""건축물대장 총괄표제부(getBrRecapTitleInfo) 전체 단지 수집 — 주차(대장 총주차) 확보용.

집합(다동)단지는 주차가 동별 표제부가 아니라 '총괄표제부'에 기재된다(getBrTitleInfo로는
주차 누락). 매물점검 ⑩주차(주차가능여부·총주차대수=대장 기준)에 필수.

★ 키1 전용 — 키2는 이 오퍼레이션 미인증(401). 표제부 수집기(collect_building_ledger,
   키1+키2)와 별도 오퍼레이션이라 쿼터 독립 → 병렬 가동 가능.
★ 격리: naverreal.sqlite 읽기전용. 결과는 building_ledger.sqlite 의 building_recap 테이블.
★ 단일동 건물은 총괄표제부 없음(totalCount=0) → 'done'(레코드 없음)으로 처리, 표제부 주차로 보완.
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, ".")
from collector.config import settings  # noqa: E402

DATA_DIR = os.path.dirname(str(settings.local_db_path))
# ★별도 DB — 표제부 수집기(building_ledger.sqlite)와 동시쓰기 락충돌 방지.
LEDGER_DB = os.path.join(DATA_DIR, "building_recap.sqlite")
SRC_DB = str(settings.local_db_path)
BASE = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"
DAILY_QUOTA = 9500
PROBE = {"sigunguCd": "11680", "bjdongCd": "10300", "platGbCd": "0",
         "bun": "0012", "ji": "0000", "numOfRows": "1", "pageNo": "1"}


def _key1() -> str:
    for line in open(os.path.join(".", ".env")):
        if line.startswith("DATA_GO_KR_SERVICE_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DATA_GO_KR_SERVICE_KEY 없음")


KEY = _key1()


def _call(params, timeout=20) -> str | None:
    p = {"serviceKey": KEY, **params}
    try:
        url = BASE + "?" + urllib.parse.urlencode(p)
        b = urllib.request.urlopen(
            urllib.request.Request(url, headers={"Accept": "application/xml"}),
            timeout=timeout).read()
        t = b.decode("utf-8", "replace")
        return t if (t.strip() and "resultCode>00" in t) else None
    except Exception:
        return None


def _g(it, tag):
    return (it.findtext(tag) or "").strip()


def _int(v):
    try:
        return int(float(str(v))) if str(v).strip() not in ("", "-") else None
    except (ValueError, TypeError):
        return None


def parse_jibun(cortar_no, detail_address):
    if not cortar_no or len(cortar_no) < 10 or not detail_address:
        return None
    da = detail_address.strip().split()[0]
    if da.startswith("산"):
        da = da[1:]
    parts = da.split("-")
    try:
        bun = int(parts[0]); ji = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    except (ValueError, IndexError):
        return None
    if bun <= 0:
        return None
    return cortar_no[:5], cortar_no[5:10], f"{bun:04d}", f"{ji:04d}"


def init_db():
    c = sqlite3.connect(LEDGER_DB, timeout=30)
    c.execute("PRAGMA busy_timeout=10000")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA journal_size_limit=1073741824")
    c.executescript("""
        CREATE TABLE IF NOT EXISTS building_recap(
          complex_no TEXT PRIMARY KEY, main_purps TEXT, tot_park INTEGER,
          tot_area REAL, hhld_cnt INTEGER, use_apr_day TEXT, main_bld_cnt INTEGER,
          collected_at TEXT);
        CREATE TABLE IF NOT EXISTS recap_status(
          complex_no TEXT PRIMARY KEY, status TEXT, has_recap INTEGER DEFAULT 0,
          attempts INTEGER DEFAULT 0, last_attempt TEXT);
        CREATE TABLE IF NOT EXISTS recap_quota(day TEXT PRIMARY KEY, calls INTEGER DEFAULT 0);
    """)
    c.commit()
    return c


def collect_one(lc, cno, cortar, da) -> str:
    j = parse_jibun(cortar, da)
    if not j:
        return "skip_addr"
    sgg, bjd, bun, ji = j
    txt = None
    for _ in range(3):
        txt = _call({"sigunguCd": sgg, "bjdongCd": bjd, "platGbCd": "0",
                     "bun": bun, "ji": ji, "numOfRows": "5", "pageNo": "1"})
        if txt:
            break
        time.sleep(0.8)
    if not txt:
        return "pending"
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        return "pending"
    items = root.findall(".//item")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if items:
        it = items[0]   # 총괄표제부는 단지당 1건
        park = _int(_g(it, "totPkngCnt")) or sum(filter(None, (
            _int(_g(it, k)) for k in
            ("indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"))))
        lc.execute(
            "INSERT OR REPLACE INTO building_recap VALUES(?,?,?,?,?,?,?,?)",
            (cno, _g(it, "mainPurpsCdNm"), park or None,
             float(_g(it, "totArea") or 0) or None, _int(_g(it, "hhldCnt")),
             _g(it, "useAprDay"), _int(_g(it, "mainBldCnt")), now))
        lc.execute("UPDATE recap_status SET status='done', has_recap=1, last_attempt=? WHERE complex_no=?", (now, cno))
    else:
        # 단일동 등 총괄표제부 없음 — done 처리(표제부 주차로 보완)
        lc.execute("UPDATE recap_status SET status='done', has_recap=0, last_attempt=? WHERE complex_no=?", (now, cno))
    return "done"


def main(once=False):
    lc = init_db()
    src = sqlite3.connect(f"file:{SRC_DB}?mode=ro", uri=True)
    rows = src.execute(
        "SELECT complex_no, cortar_no, detail_address FROM complexes "
        "WHERE detail_address IS NOT NULL AND detail_address!=''").fetchall()
    src.close()
    for cno, _c, _d in rows:
        lc.execute("INSERT OR IGNORE INTO recap_status(complex_no, status) VALUES(?, 'todo')", (cno,))
    lc.commit()
    addr = {r[0]: (r[1], r[2]) for r in rows}
    print(f"[recap] 전체 단지 {len(rows):,} / 시작", flush=True)
    consec = 0
    while True:
        pending = [r[0] for r in lc.execute(
            "SELECT complex_no FROM recap_status WHERE status IN ('todo','pending') "
            "ORDER BY status DESC LIMIT 500")]
        if not pending:
            print("[recap done] 전 단지 완료", flush=True); break
        day = time.strftime("%Y-%m-%d")
        used = lc.execute("SELECT calls FROM recap_quota WHERE day=?", (day,)).fetchone()
        used = used[0] if used else 0
        if used >= DAILY_QUOTA:
            if once:
                print(f"[recap once] 쿼터 {used} — 종료", flush=True); break
            print(f"[recap quota] {day} {used} 소진 — 자정 대기", flush=True)
            time.sleep(min(3600, max(300, 86400 - int(time.time()) % 86400))); continue
        lc.execute("INSERT INTO recap_quota(day,calls) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET calls=calls+1", (day,))
        if not _call(PROBE):
            consec += 1; lc.commit()
            print(f"[recap down] 빈응답 — {min(600,60*consec)}s 대기", flush=True)
            time.sleep(min(600, 60 * consec)); continue
        consec = 0
        done_n = 0
        for cno in pending:
            u = lc.execute("SELECT calls FROM recap_quota WHERE day=?", (day,)).fetchone()[0]
            if u >= DAILY_QUOTA:
                break
            lc.execute("INSERT INTO recap_quota(day,calls) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET calls=calls+1", (day,))
            ct, da = addr.get(cno, (None, None))
            st = collect_one(lc, cno, ct, da)
            if st != "done":
                lc.execute("UPDATE recap_status SET status=?, attempts=attempts+1, last_attempt=? WHERE complex_no=?",
                           (st, time.strftime("%Y-%m-%dT%H:%M:%S"), cno))
                if st == "pending":
                    consec += 1
                    if consec >= 5:
                        lc.commit(); break
            else:
                done_n += 1; consec = 0
            if done_n % 25 == 0:
                lc.commit()
        lc.commit()
        td = lc.execute("SELECT COUNT(*) FROM recap_status WHERE status='done'").fetchone()[0]
        hr = lc.execute("SELECT COUNT(*) FROM recap_status WHERE has_recap=1").fetchone()[0]
        tc = lc.execute("SELECT calls FROM recap_quota WHERE day=?", (day,)).fetchone()[0]
        print(f"[recap progress] done {td:,}/{len(rows):,}  총괄있음 {hr:,}  (오늘 {tc})", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    main(once=ap.parse_args().once)
