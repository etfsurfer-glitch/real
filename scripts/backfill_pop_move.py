# -*- coding: utf-8 -*-
"""지역 간 인구이동 수집 — 행안부 '지역별 인구이동 현황'(data.go.kr 15108093).

왜 필요한가: 실거래 자료에는 매수자 거주지가 없어 '어느 지역 수요가 어디로 갔나'를
말할 수 없었다. 이 API는 **전입지×전출지 매트릭스**를 월 단위로 주므로, 지역 간 이동을
숫자로 확인할 수 있다. 다만 이는 **전입신고 기반의 거주 이전**이지 투자 자금의 이동이
아니다 — 분석·기사에서 이 구분을 반드시 지킬 것.

API 제약(실측):
  · mvinAdmmCd(전입)·mvtAdmmCd(전출)·srchFrYm·srchToYm 모두 **필수**. 넷이 다 있어야
    파라미터로 인식된다(하나만 넣고 탐색하면 전부 무시돼 NO_MANDATORY 가 뜬다).
  · 조회 구간은 **최대 3개월**, 데이터는 **2022-10 이후**만.
  · lv: 1=시도 2=시군구 3=읍면동(기본) 4=단일시도.
  · 행정기관코드는 10자리. 우리 regions.cortar_no 시도코드와 그대로 일치(17/17 확인).

수집 범위는 시도×시도(17×17=289쌍)를 기본으로 한다. 분기(3개월) 단위로 끊어 호출하므로
2022-10~현재면 쌍당 약 15콜, 총 4천여 콜 — 키 하나 일일한도(1만) 안에 들어간다.

사용: backfill_pop_move.py [--from 202210] [--to 202606] [--lv 1] [--workers 4] [--max-calls 9000]
"""
import argparse
import datetime
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

API = "https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus"
# 메인 DB(24GB)는 매물 수집이 장시간 쓰기락을 쥐고 있어 붙으면 그대로 멈춘다(실측: run_collect
# 1시간+ 점유). 비단지 매물·좌표캐시와 같은 방식으로 **전용 DB**를 쓴다.
POP_DB = os.path.join(os.path.dirname(settings.local_db_path), "pop_move.sqlite")
FIRST_YM = "202210"          # API 제공 시작
WINDOW = 3                   # 조회 구간 상한(개월)
_RL_LOCK = threading.Lock()
_RL_NEXT = [0.0]
MIN_GAP = 0.12               # 초당 ~8콜. data.go.kr 은 여유 있지만 예의상 제한
_tls = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS pop_move(
  ym TEXT, mvt_cd TEXT, mvin_cd TEXT,      -- 전출지 → 전입지
  mvt_nm TEXT, mvin_nm TEXT,
  total INTEGER, male INTEGER, feml INTEGER,
  -- 10세 단위(부동산 수요는 연령대가 핵심). m20=20대 남, f30=30대 여 …
  m00 INTEGER, m10 INTEGER, m20 INTEGER, m30 INTEGER, m40 INTEGER,
  m50 INTEGER, m60 INTEGER, m70 INTEGER, m80 INTEGER,
  f00 INTEGER, f10 INTEGER, f20 INTEGER, f30 INTEGER, f40 INTEGER,
  f50 INTEGER, f60 INTEGER, f70 INTEGER, f80 INTEGER,
  lv TEXT,
  PRIMARY KEY(ym, mvt_cd, mvin_cd, lv));
CREATE INDEX IF NOT EXISTS pm_ym ON pop_move(ym);
CREATE INDEX IF NOT EXISTS pm_pair ON pop_move(mvt_cd, mvin_cd);
CREATE TABLE IF NOT EXISTS pop_move_progress(
  mvt_cd TEXT, mvin_cd TEXT, fr_ym TEXT, to_ym TEXT, lv TEXT, rows INTEGER, ts TEXT,
  PRIMARY KEY(mvt_cd, mvin_cd, fr_ym, lv));
"""


def _ratelimit():
    with _RL_LOCK:
        slot = max(time.time(), _RL_NEXT[0])
        _RL_NEXT[0] = slot + MIN_GAP
    w = slot - time.time()
    if w > 0:
        time.sleep(w)


def months(a: str, b: str) -> list:
    y, m = int(a[:4]), int(a[4:]); y2, m2 = int(b[:4]), int(b[4:])
    out = []
    while (y, m) <= (y2, m2):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def windows(a: str, b: str, size: int = WINDOW) -> list:
    ms = months(a, b)
    return [(ms[i], ms[min(i + size - 1, len(ms) - 1)]) for i in range(0, len(ms), size)]


class Quota(RuntimeError):
    pass


def fetch(mvin: str, mvt: str, fr: str, to: str, lv: str, key: str, retries: int = 3):
    p = {"serviceKey": key, "type": "json", "numOfRows": "100", "pageNo": "1",
         "mvinAdmmCd": mvin, "mvtAdmmCd": mvt, "srchFrYm": fr, "srchToYm": to, "lv": lv}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    for i in range(retries):
        try:
            _ratelimit()
            req = urllib.request.Request(url, headers={"User-Agent": "koczip/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                import json as _j
                d = _j.loads(r.read().decode("utf-8", "replace"))["Response"]
            msg = (d.get("head") or {}).get("resultMsg", "")
            if "LIMIT" in msg.upper() or "EXCEED" in msg.upper():
                raise Quota(msg)
            if msg != "NORMAL_SERVICE":
                return []          # 해당 조합에 데이터 없음(정상)
            it = d.get("items")
            if isinstance(it, dict):
                it = it.get("item")
            if isinstance(it, dict):
                it = [it]
            return it or []
        except Quota:
            raise
        except Exception:
            if i == retries - 1:
                return None        # 실패 — progress 미기록으로 다음 실행에서 재시도
            time.sleep(min(0.6 * (2 ** i), 5))
    return None


def _band(x: dict, sex: str, lo: int, hi: int) -> int:
    """연령 1세 컬럼을 10세 단위로 합산. 80은 80~110+ 전부."""
    tot = 0
    for a in range(lo, hi + 1):
        v = x.get(f"{sex}{a}AgeNmprCnt")
        try:
            tot += int(v or 0)
        except (TypeError, ValueError):
            pass
    return tot


def to_row(x: dict, lv: str) -> tuple:
    def i(k):
        try:
            return int(x.get(k) or 0)
        except (TypeError, ValueError):
            return 0
    mvt_nm = " ".join(v for v in (x.get("mvtCtpvNm"), x.get("mvtSggNm"), x.get("mvtDongNm")) if v)
    mvin_nm = " ".join(v for v in (x.get("mvinCtpvNm"), x.get("mvinSggNm"), x.get("mvinDongNm")) if v)
    bands = []
    for sex in ("male", "feml"):
        for lo in (0, 10, 20, 30, 40, 50, 60, 70):
            bands.append(_band(x, sex, lo, lo + 9))
        bands.append(_band(x, sex, 80, 110))
    return (x.get("statsYm"), x.get("mvtAdmmCd"), x.get("mvinAdmmCd"), mvt_nm, mvin_nm,
            i("totNmprCnt"), i("maleNmprCnt"), i("femlNmprCnt"), *bands, lv)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="fr", default=FIRST_YM)
    ap.add_argument("--to", dest="to", default="")
    ap.add_argument("--lv", default="1", help="1=시도 2=시군구 3=읍면동")
    ap.add_argument("--workers", type=int, default=8)   # 콜당 ~3.3초라 병렬이 필요
    ap.add_argument("--max-calls", type=int, default=9000)
    a = ap.parse_args()
    to_ym = a.to or (datetime.date.today().replace(day=1) - datetime.timedelta(days=1)).strftime("%Y%m")

    db = sqlite3.connect(POP_DB, timeout=90)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=90000")
    db.executescript(SCHEMA)

    # 시도 코드는 메인 DB에서 읽기전용으로만 가져온다(쓰기락과 무관)
    with sqlite3.connect(f"file:{settings.local_db_path}?mode=ro", uri=True) as mc:
        mc.execute("PRAGMA busy_timeout=20000")
        codes = [r[0] for r in mc.execute(
            "SELECT cortar_no FROM regions WHERE cortar_no LIKE '__00000000' ORDER BY cortar_no")]
    if a.lv != "1":
        print("[!] lv!=1 은 대상 코드 목록을 따로 지정해야 한다(시군구 250×250 은 과다). 종료.", flush=True)
        return 2
    print(f"[*] 시도 {len(codes)}개 · 구간 {a.fr}~{to_ym} · lv={a.lv} · DB={POP_DB}", flush=True)

    done = {(r[0], r[1], r[2]) for r in db.execute(
        "SELECT mvt_cd, mvin_cd, fr_ym FROM pop_move_progress WHERE lv=?", (a.lv,))}
    tasks = [(mvt, mvin, fr, to) for mvt in codes for mvin in codes
             for fr, to in windows(a.fr, to_ym) if (mvt, mvin, fr) not in done]
    print(f"[*] 남은 작업 {len(tasks):,} (완료 {len(done):,})", flush=True)
    if not tasks:
        print("[*] 이미 완료"); return 0

    # 키마다 활용신청이 따로라 이 API에 승인된 키만 골라야 한다.
    # (실측: 6키를 그냥 순환했더니 미승인 5개 탓에 82% 실패 — 실패율이 5/6과 정확히 일치했다)
    cand = [settings.data_go_kr_service_key]
    for i in range(2, 10):
        k = os.getenv(f"DATA_GO_KR_SERVICE_KEY{i}", "").strip()
        if k:
            cand.append(k)
    keys = []
    for i, k in enumerate(cand):
        probe = fetch(codes[0], codes[0], to_ym, to_ym, a.lv, k, retries=1)
        if probe is None:
            print(f"    KEY{i or ''} 미승인/오류 — 제외", flush=True)
        else:
            keys.append(k)
    if not keys:
        print("[!] 이 API에 승인된 키가 없다. data.go.kr 활용신청 확인 필요.", flush=True)
        return 2
    print(f"[*] 사용 가능한 키 {len(keys)}/{len(cand)}", flush=True)
    lock = threading.Lock()
    state = {"calls": 0, "rows": 0, "quota": False, "fail": 0}
    t0 = time.time()

    def work(t, key):
        mvt, mvin, fr, to = t
        items = fetch(mvin, mvt, fr, to, a.lv, key)
        return t, items

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, t, keys[i % len(keys)]): t for i, t in enumerate(tasks)}
        for fut in as_completed(futs):
            try:
                t, items = fut.result()
            except Quota:
                state["quota"] = True
                break
            mvt, mvin, fr, to = t
            with lock:
                state["calls"] += 1
                if items is None:
                    state["fail"] += 1
                    continue
                if items:
                    db.executemany(
                        "INSERT OR REPLACE INTO pop_move VALUES(" + ",".join("?" * 27) + ")",
                        [to_row(x, a.lv) for x in items])
                    state["rows"] += len(items)
                db.execute("INSERT OR REPLACE INTO pop_move_progress VALUES(?,?,?,?,?,?,?)",
                           (mvt, mvin, fr, to, a.lv, len(items), datetime.datetime.now().isoformat(timespec="seconds")))
                # 콜당 3.3초라 200콜마다 커밋하면 10분 넘게 아무것도 안 보인다 → 25콜마다
                if state["calls"] % 25 == 0:
                    db.commit()
                    el = time.time() - t0
                    rate = state["calls"] / max(el, .001)
                    eta = (len(tasks) - state["calls"]) / max(rate, .001) / 60
                    print(f"    {state['calls']:,}/{len(tasks):,}콜 · {state['rows']:,}행 · "
                          f"실패 {state['fail']} · {rate:.2f}콜/s · ETA {eta:.0f}분", flush=True)
                if state["calls"] >= a.max_calls:
                    break
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM pop_move WHERE lv=?", (a.lv,)).fetchone()[0]
    print(f"[*] 완료: {state['calls']:,}콜 · 신규 {state['rows']:,}행 · 누적 {n:,}행"
          + (" · 쿼터 소진" if state["quota"] else ""), flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
