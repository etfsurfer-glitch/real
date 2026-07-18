# -*- coding: utf-8 -*-
"""아파트 매매 실거래 과거분 백필 (2006-01 ~ 2023-05) — 부동산타임머신용.

전략(2026-07-18 실증):
- 국토부 API는 과거 거래를 '현행' 시군구 코드로 소급 재매핑해 서빙(마산합포 2008,
  세종 2010, remap 12xxx 2006 모두 확인) → 현행 표준 250개 코드 × 월로 전 기간 커버.
- 광주·전남 remap, 인천 분할합병은 collector.realprice.api.fetch_all이 투명 처리.
- 원본은 격리 스테이징(/mnt/backup/koczip_hist/realprice_hist.sqlite)에만 저장.
  루트 디스크 90%라 본 DB(naverreal.sqlite) 병합 금지 — 본 DB에는 월×시군구 집계
  (tx_hist_monthly, 완결 월만)만 기록. 원본 병합은 디스크 증설 후 별도 결정.
- 일일 콜 예산(기본 8,000 — 쿼터 10,000에서 일일수집 ~255 제외 여유) 소진 시 저장 후
  종료, 다음 실행(타이머)이 체크포인트에서 재개. 월은 최신→과거 순(차트가 뒤로 자람).

Run(박스): python3 /opt/koczip/scripts/backfill_realprice_hist.py [--max-calls N] [--dry]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/opt/koczip")

from collector.realprice import api as rp_api  # noqa: E402
from collector.realprice.api import APIError, fetch_all  # noqa: E402

MAIN_DB = "/opt/koczip/data/naverreal.sqlite"
HIST_DIR = Path("/mnt/backup/koczip_hist")
HIST_DB = HIST_DIR / "realprice_hist.sqlite"
FIRST_YM = "200601"
LAST_YM = "202305"   # 본 DB transactions가 2023-06부터 — 경계 중복 없음

# 멀티키 병렬: 워커(스레드)마다 자기 키로 조회 — fetch_xml을 스레드로컬 키 주입형으로 교체.
# 키2(DATA_GO_KR_SERVICE_KEY2)는 시작 시 검증 실패(미신청 403 등)면 자동 제외.
import os
import threading
import urllib.parse
import urllib.request

_tls = threading.local()
_calls_lock = threading.Lock()
_calls = {"n": 0}


def _keyed_fetch_xml(lawd_cd, deal_ymd, page_no=1, num_rows=1000,
                     timeout=20, retries=3, endpoint=rp_api.ENDPOINT):
    key = getattr(_tls, "key", None) or rp_api.settings.data_go_kr_service_key
    qs = urllib.parse.urlencode({
        "serviceKey": key, "LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd,
        "pageNo": str(page_no), "numOfRows": str(num_rows),
    })
    url = f"{endpoint}?{qs}"
    with _calls_lock:
        _calls["n"] += 1
    _tls.calls = getattr(_tls, "calls", 0) + 1
    time.sleep(0.25)   # 키별 스로틀(워커당 초당 최대 4콜)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise APIError(f"fetch failed after {retries} attempts: {last}")


rp_api.fetch_xml = _keyed_fetch_xml


def _validate_key(key: str) -> bool:
    try:
        qs = urllib.parse.urlencode({"serviceKey": key, "LAWD_CD": "11680",
                                     "DEAL_YMD": "200601", "numOfRows": "1"})
        req = urllib.request.Request(f"{rp_api.ENDPOINT}?{qs}",
                                     headers={"Accept": "application/xml"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return b"<resultCode>000" in r.read()
    except Exception:
        return False


def _tg(msg: str) -> None:
    try:
        sys.path.insert(0, "/opt/koczip/scripts")
        from tg_notify import tg_send  # type: ignore
        tg_send(msg)
    except Exception:
        pass


def _months() -> list[str]:
    out = []
    y, m = int(LAST_YM[:4]), int(LAST_YM[4:])
    while f"{y}{m:02d}" >= FIRST_YM:
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out   # 최신 → 과거


def _regions() -> list[str]:
    with sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True) as c:
        rows = c.execute(
            "SELECT DISTINCT substr(cortar_no,1,5) FROM regions "
            "WHERE cortar_no LIKE '_____00000' AND cortar_no NOT LIKE '__00000000' "
            "ORDER BY 1"
        ).fetchall()
    return [r[0] for r in rows]


def _open_hist() -> sqlite3.Connection:
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(HIST_DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA journal_size_limit=268435456")
    c.execute("""CREATE TABLE IF NOT EXISTS hist(
        sgg_cd TEXT, umd TEXT, apt_nm TEXT, apt_seq TEXT, jibun TEXT,
        deal_ymd TEXT, amount INTEGER, floor INTEGER, area REAL,
        build_year INTEGER, is_cancelled INTEGER, dealing TEXT, apt_dong TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS h_ym ON hist(substr(deal_ymd,1,7))")
    c.execute("""CREATE TABLE IF NOT EXISTS progress(
        ym TEXT, sgg TEXT, total INTEGER, rows INTEGER, ts TEXT,
        PRIMARY KEY(ym, sgg))""")
    return c


def _to_row(it: dict, std_sgg: str) -> tuple:
    amt = int((it.get("dealAmount") or "0").replace(",", "").strip() or 0) * 10000
    y = (it.get("dealYear") or "").strip()
    mo = (it.get("dealMonth") or "").strip().zfill(2)
    d = (it.get("dealDay") or "").strip().zfill(2)
    deal_ymd = f"{y}-{mo}-{d}"
    cancelled = 1 if (it.get("cdealType") or "").strip() == "O" else 0

    def _f(k):
        v = (it.get(k) or "").strip()
        return v or None

    try:
        area = float(_f("excluUseAr") or 0) or None
    except ValueError:
        area = None
    try:
        floor = int(_f("floor") or 0)
    except ValueError:
        floor = None
    try:
        by = int(_f("buildYear") or 0) or None
    except ValueError:
        by = None
    return (std_sgg, _f("umdNm"), _f("aptNm"), _f("aptSeq"), _f("jibun"),
            deal_ymd, amt, floor, area, by, cancelled, _f("dealingGbn"), _f("aptDong"))


def _publish_month(hist: sqlite3.Connection, ym: str) -> None:
    """완결된 월의 집계를 본 DB tx_hist_monthly에 기록(해제 제외). 'ALL'=전국."""
    m = f"{ym[:4]}-{ym[4:]}"
    rows = hist.execute(
        "SELECT sgg_cd, COUNT(*), CAST(AVG(amount) AS INT) FROM hist "
        "WHERE substr(deal_ymd,1,7)=? AND is_cancelled=0 AND amount>0 GROUP BY sgg_cd",
        (m,),
    ).fetchall()
    nat = hist.execute(
        "SELECT COUNT(*), CAST(AVG(amount) AS INT) FROM hist "
        "WHERE substr(deal_ymd,1,7)=? AND is_cancelled=0 AND amount>0", (m,),
    ).fetchone()
    with sqlite3.connect(MAIN_DB, timeout=60) as main:
        main.execute("PRAGMA journal_size_limit=1073741824")
        main.execute("""CREATE TABLE IF NOT EXISTS tx_hist_monthly(
            ym TEXT, sgg_cd TEXT, n INTEGER, avg_amount INTEGER,
            PRIMARY KEY(ym, sgg_cd))""")
        main.executemany(
            "INSERT OR REPLACE INTO tx_hist_monthly VALUES (?,?,?,?)",
            [(m, r[0], r[1], r[2]) for r in rows] + [(m, "ALL", nat[0], nat[1])],
        )
    print(f"[publish] {m}: 전국 {nat[0]:,}건 평균 {int((nat[1] or 0)/1e4):,}만", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=8000)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    regions = _regions()
    months = _months()
    hist = _open_hist()
    done = {(r[0], r[1]) for r in hist.execute("SELECT ym, sgg FROM progress")}
    hist.close()
    total_cells = len(months) * len(regions)

    # 키 구성: 기존 키 + (검증 통과한) 추가 키들(KEY2~KEY9) — 워커 1개/키
    keys = [rp_api.settings.data_go_kr_service_key]
    for i in range(2, 10):
        kx = os.getenv(f"DATA_GO_KR_SERVICE_KEY{i}", "").strip()
        if not kx:
            continue
        if _validate_key(kx):
            keys.append(kx)
        else:
            print(f"[warn] KEY{i} 검증 실패(활용신청 미승인?) — 제외", flush=True)
    # 키별 일일 예산: 키1은 일일수집 몫을 남기고, 추가 키는 전량 사용
    budgets = [args.max_calls] + [9500] * (len(keys) - 1)
    print(f"대상 {len(months)}개월 × {len(regions)}시군구 = {total_cells:,}셀, "
          f"완료 {len(done):,} · 키 {len(keys)}개(예산 {'+'.join(map(str, budgets))})", flush=True)
    if args.dry:
        return 0

    done_lock = threading.Lock()
    pub_lock = threading.Lock()
    published: set[str] = set()
    state = {"budget_hit": False, "quota": False}

    def month_complete(ym: str) -> bool:
        return all((ym, sg) in done for sg in regions)

    def worker(idx: int) -> None:
        _tls.key = keys[idx]
        _tls.calls = 0
        wh = _open_hist()   # 워커별 커넥션(WAL)
        wh.execute("PRAGMA busy_timeout=30000")
        my_regions = [sg for i, sg in enumerate(regions) if i % len(keys) == idx]
        for ym in months:
            for sgg in my_regions:
                if (ym, sgg) in done:
                    continue
                if _tls.calls >= budgets[idx]:
                    state["budget_hit"] = True
                    wh.close()
                    return
                try:
                    rows = [_to_row(it, sgg) for it in fetch_all(sgg, ym)]
                except APIError as e:
                    msg = str(e)
                    if "LIMIT" in msg.upper() or "EXCEED" in msg.upper():
                        state["quota"] = True
                        wh.close()
                        return
                    print(f"[skip] {ym} {sgg}: {msg[:100]}", flush=True)
                    continue   # progress 미기록 → 다음 실행에서 재시도
                wh.executemany("INSERT INTO hist VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                wh.execute("INSERT OR REPLACE INTO progress VALUES (?,?,?,?,?)",
                           (ym, sgg, len(rows), len(rows), datetime.now().isoformat(timespec="seconds")))
                wh.commit()
                with done_lock:
                    done.add((ym, sgg))
                    complete = month_complete(ym)
                if complete:
                    with pub_lock:
                        if ym not in published:
                            published.add(ym)
                            try:
                                _publish_month(wh, ym)
                            except Exception as pe:  # noqa: BLE001
                                print(f"[publish-err] {ym}: {pe}", flush=True)
        wh.close()

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(len(keys))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    budget_hit = state["budget_hit"] or state["quota"]
    if state["quota"]:
        _tg(f"⏸ 실거래 백필: 일일 쿼터 도달({_calls['n']:,}콜) — 내일 재개")
    hist = _open_hist()   # 이하 보정·집계용

    # 이번 실행에서 새로 완결된 월 중 publish 누락분 보정(재시작 안전)
    with sqlite3.connect(MAIN_DB, timeout=60) as main:
        main.execute("""CREATE TABLE IF NOT EXISTS tx_hist_monthly(
            ym TEXT, sgg_cd TEXT, n INTEGER, avg_amount INTEGER, PRIMARY KEY(ym, sgg_cd))""")
        pub = {r[0] for r in main.execute("SELECT DISTINCT ym FROM tx_hist_monthly")}
    for ym in months:
        m = f"{ym[:4]}-{ym[4:]}"
        if m not in pub and all((ym, sgg) in done for sgg in regions):
            _publish_month(hist, ym)

    pct = len(done) / total_cells * 100
    remain = total_cells - len(done)
    msg = (f"실거래 과거분 백필: {pct:.1f}% ({len(done):,}/{total_cells:,}셀) · "
           f"이번 실행 {_calls['n']:,}콜"
           + (" · 예산 소진, 내일 재개" if budget_hit or remain else " · ✅ 전체 완료"))
    print(msg, flush=True)
    _tg(("⏳ " if remain else "✅ ") + msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
