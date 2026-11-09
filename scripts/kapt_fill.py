"""K-apt 관리비 밤 배치 — 연결된 단지의 빠진 달을 채우고, 최근 30일 안에 조회된 단지를 새로 연결한다.

서비스별 일일 한도(개발계정 5,000)가 작아서, 한도 안에서 되는 만큼만 하고 멈춘다. 우선순위:
① 이미 연결된 단지의 빠진 달(최근 15개월) ② 최근 열린 콕집매물 단지(logs 의 /kok/listings/R… 조회)를 새로 연결.
실행: python scripts/kapt_fill.py  (daily_run step 11e)
"""
from __future__ import annotations
import os, sqlite3, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scripts.local_api as api  # noqa: E402

BUDGET_CMN = 4200          # 밤에 쓸 cmn 호출 상한(낮 온디맨드 몫 500은 남겨 둔다)


def main() -> int:
    t0 = time.time()
    with api._kapt_db() as c:
        used = api._KAPT_DAILY_CAP - api._kapt_quota_left(c, "cmn")
        codes = [r[0] for r in c.execute("SELECT DISTINCT kapt_code FROM kapt_map WHERE kapt_code IS NOT NULL")]
    filled = 0; months = 0
    for code in codes:
        with api._kapt_db() as c:
            have = {r[0] for r in c.execute("SELECT ym FROM kapt_month WHERE kapt_code=? AND (complete=1 OR fetched_at>?)", (code, api._kapt_days_ago(7)))}
        for ym in api._kapt_recent_yms(15):
            if ym in have:
                continue
            with api._kapt_db() as c:
                if api._KAPT_DAILY_CAP - api._kapt_quota_left(c, "cmn") >= BUDGET_CMN:
                    print(f"budget reached: filled {filled} complexes / {months} months in {time.time()-t0:.0f}s"); return 0
            if api._kapt_fetch_month(code, ym) is None:
                print("fetch failed (quota/network) — stop"); return 0
            months += 1
        filled += 1
    # 새로 연결: 최근 30일 콕집매물 상세가 열린 단지
    new = 0
    try:
        lp = api.DB_PATH.parent / "logs.sqlite"
        with sqlite3.connect(f"file:{lp}?mode=ro", uri=True) as lc, api._open_db() as d, api._kapt_db() as c:
            arts = [r[0].split("/kok/listings/R", 1)[1].split("?")[0] for r in lc.execute(
                "SELECT DISTINCT path FROM event_log WHERE ts>datetime('now','-30 days') AND path LIKE '/kok/listings/R%'")]
            cxs = set()
            for a in arts:
                r = d.execute("SELECT complex_no FROM listings_current WHERE article_no=?", (a,)).fetchone()
                if r:
                    cxs.add(r[0])
            for cx in cxs:
                if c.execute("SELECT 1 FROM kapt_map WHERE complex_no=?", (cx,)).fetchone():
                    continue
                if api._kapt_match(d, c, cx):
                    new += 1
    except Exception as e:  # noqa: BLE001
        print("link step:", e)
    print(f"done: {filled} complexes complete, {months} months fetched, {new} newly linked, cmn used before={used}, {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
