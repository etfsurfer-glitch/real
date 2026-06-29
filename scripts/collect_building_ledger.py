"""건축물대장 표제부(getBrTitleInfo) 전체 단지 수집 — 매물점검 기준값/생숙판정용.

★ 격리: naverreal.sqlite 는 ★읽기전용★(단지 지번 읽기). 결과는 별도 building_ledger.sqlite.
★ 불안정 API 대응: probe 게이트(살아있을 때만 bulk), 죽으면 대기(쿼터 낭비 방지),
   재개형(status='done' 스킵), 일일쿼터 9,500(10k 한도), journal_size_limit.

매물점검에서 단지의 총층수·면적·주용도(생숙)·사용승인일·주차를 '건축물대장 기준값'으로 제공.

사용:  python scripts/collect_building_ledger.py            # 백그라운드 데몬(완료까지)
       python scripts/collect_building_ledger.py --once    # 한 세션(쿼터까지)만
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
LEDGER_DB = os.path.join(DATA_DIR, "building_ledger.sqlite")
SRC_DB = str(settings.local_db_path)
BASE = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
DAILY_QUOTA = 9500          # getBrTitleInfo 10,000/일 한도 — 마진
PROBE = {"sigunguCd": "11680", "bjdongCd": "10100", "numOfRows": "1", "pageNo": "1"}


def _key() -> str:
    for line in open(os.path.join(".", ".env")):
        if line.startswith("DATA_GO_KR_SERVICE_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DATA_GO_KR_SERVICE_KEY 없음")


KEY = _key()


def _call(params: dict, timeout=20) -> str | None:
    """단일 호출. 정상 XML(resultCode 00) 문자열 or None(빈응답/에러)."""
    p = {"serviceKey": KEY, **params}
    try:
        url = BASE + "?" + urllib.parse.urlencode(p)
        b = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
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


def init_ledger():
    c = sqlite3.connect(LEDGER_DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA journal_size_limit=1073741824")
    c.executescript("""
        CREATE TABLE IF NOT EXISTS building_ledger(
          complex_no TEXT, mgm_pk TEXT, bld_nm TEXT, main_purps TEXT, etc_purps TEXT,
          grnd_flr INTEGER, ugrnd_flr INTEGER, tot_area REAL, arch_area REAL, plat_area REAL,
          use_apr_day TEXT, parking_total INTEGER, strct TEXT,
          plat_plc TEXT, new_plat_plc TEXT, collected_at TEXT,
          PRIMARY KEY(complex_no, mgm_pk));
        CREATE TABLE IF NOT EXISTS ledger_status(
          complex_no TEXT PRIMARY KEY, status TEXT, n_records INTEGER DEFAULT 0,
          is_saengsuk INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0,
          last_attempt TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS ledger_quota(day TEXT PRIMARY KEY, calls INTEGER DEFAULT 0);
    """)
    c.commit()
    return c


def parse_jibun(cortar_no: str, detail_address: str):
    """cortar_no(법정동10) + detail_address('23-4'/'23'/'산23-4') → (sgg5,bjd5,bun4,ji4)."""
    if not cortar_no or len(cortar_no) < 10 or not detail_address:
        return None
    da = detail_address.strip().split()[0]            # '23-4 외' → '23-4'
    if da.startswith("산"):
        da = da[1:]                                   # 산번지(특수지) — 본/부번만 취함
    parts = da.split("-")
    try:
        bun = int(parts[0]); ji = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    except (ValueError, IndexError):
        return None
    if bun <= 0:
        return None
    return cortar_no[:5], cortar_no[5:10], f"{bun:04d}", f"{ji:04d}"


def collect_one(lc, complex_no, cortar_no, detail_address) -> str:
    """한 단지 표제부 수집·저장. 반환 상태: done | pending | skip_addr."""
    j = parse_jibun(cortar_no, detail_address)
    if not j:
        return "skip_addr"
    sgg, bjd, bun, ji = j
    # 한 필지 표제부 전수(numOfRows=50). 불안정하니 3회 재시도.
    txt = None
    for _ in range(3):
        txt = _call({"sigunguCd": sgg, "bjdongCd": bjd, "bun": bun, "ji": ji,
                     "numOfRows": "50", "pageNo": "1"})
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
    saeng = 0
    lc.execute("DELETE FROM building_ledger WHERE complex_no=?", (complex_no,))
    for it in items:
        mp = _g(it, "mainPurpsCdNm")
        if "생활숙박" in (mp + _g(it, "etcPurps")):
            saeng = 1
        park = sum(filter(None, (_int(_g(it, k)) for k in
                   ("indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"))))
        lc.execute(
            "INSERT OR REPLACE INTO building_ledger VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (complex_no, _g(it, "mgmBldrgstPk"), _g(it, "bldNm"), mp, _g(it, "etcPurps"),
             _int(_g(it, "grndFlrCnt")), _int(_g(it, "ugrndFlrCnt")),
             float(_g(it, "totArea") or 0) or None, float(_g(it, "archArea") or 0) or None,
             float(_g(it, "platArea") or 0) or None, _g(it, "useAprDay"),
             park or None, _g(it, "strctCdNm"), _g(it, "platPlc"), _g(it, "newPlatPlc"), now))
    lc.execute("UPDATE ledger_status SET status='done', n_records=?, is_saengsuk=?, last_attempt=? WHERE complex_no=?",
               (len(items), saeng, now, complex_no))
    return "done"


def main(once=False):
    lc = init_ledger()
    # 대상 단지(지번 있는 것) 로드 + status 시드
    src = sqlite3.connect(f"file:{SRC_DB}?mode=ro", uri=True)
    rows = src.execute(
        "SELECT complex_no, cortar_no, detail_address FROM complexes "
        "WHERE detail_address IS NOT NULL AND detail_address!=''").fetchall()
    src.close()
    for cno, _ct, _da in rows:
        lc.execute("INSERT OR IGNORE INTO ledger_status(complex_no, status) VALUES(?, 'todo')", (cno,))
    lc.commit()
    addr = {r[0]: (r[1], r[2]) for r in rows}
    print(f"[*] 전체 단지 {len(rows):,} / 시작", flush=True)

    consec_fail = 0
    while True:
        pending = [r[0] for r in lc.execute(
            "SELECT complex_no FROM ledger_status WHERE status IN ('todo','pending') "
            "ORDER BY status DESC LIMIT 500")]  # pending 우선 재시도
        if not pending:
            print("[done] 전 단지 수집 완료", flush=True)
            break
        day = time.strftime("%Y-%m-%d")
        used = lc.execute("SELECT calls FROM ledger_quota WHERE day=?", (day,)).fetchone()
        used = used[0] if used else 0
        if used >= DAILY_QUOTA:
            if once:
                print(f"[once] 일일쿼터 {used} 도달 — 종료", flush=True); break
            # 다음날까지 대기
            print(f"[quota] {day} 쿼터 {used} 소진 — 자정까지 대기", flush=True)
            time.sleep(min(3600, max(300, 86400 - int(time.time()) % 86400)))
            continue
        # probe 게이트 — 살아있을 때만 bulk
        lc.execute("INSERT INTO ledger_quota(day,calls) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET calls=calls+1", (day,))
        if not _call(PROBE):
            consec_fail += 1
            lc.commit()
            print(f"[down] API 빈응답 — {min(600, 60*consec_fail)}s 대기(쿼터 보존)", flush=True)
            time.sleep(min(600, 60 * consec_fail))
            continue
        consec_fail = 0
        # API 살아있음 → 배치 수집
        done_n = 0
        for cno in pending:
            u = lc.execute("SELECT calls FROM ledger_quota WHERE day=?", (day,)).fetchone()[0]
            if u >= DAILY_QUOTA:
                break
            lc.execute("INSERT INTO ledger_quota(day,calls) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET calls=calls+1", (day,))
            ct, da = addr.get(cno, (None, None))
            st = collect_one(lc, cno, ct, da)
            if st != "done":
                lc.execute("UPDATE ledger_status SET status=?, attempts=attempts+1, last_attempt=? WHERE complex_no=?",
                           (st, time.strftime("%Y-%m-%dT%H:%M:%S"), cno))
                if st == "pending":      # 연속 pending = API 다시 죽음 → probe로
                    consec_fail += 1
                    if consec_fail >= 5:
                        lc.commit(); break
            else:
                done_n += 1; consec_fail = 0
            if (done_n % 25) == 0:
                lc.commit()
        lc.commit()
        tot_done = lc.execute("SELECT COUNT(*) FROM ledger_status WHERE status='done'").fetchone()[0]
        saeng_n = lc.execute("SELECT COUNT(*) FROM ledger_status WHERE is_saengsuk=1").fetchone()[0]
        today_calls = lc.execute("SELECT calls FROM ledger_quota WHERE day=?", (day,)).fetchone()[0]
        print(f"[progress] done {tot_done:,}/{len(rows):,}  생숙 {saeng_n}  (오늘호출 {today_calls})", flush=True)
    lc.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="한 세션(쿼터까지)만")
    a = ap.parse_args()
    main(once=a.once)
