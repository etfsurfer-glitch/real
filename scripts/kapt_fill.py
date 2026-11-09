"""K-apt 관리비 밤 배치 — 전국 아파트 단지를 K-apt 단지에 연결하고 최근 12개월 관리비를 미리 채운다.

운영계정(서비스별 일 100,000, 코드 상한 95,000) 기준. 우선순위:
① 이미 연결된 단지의 빠진 달 ② 최근 30일 안에 콕집매물 상세가 열린 단지(logs) 연결+채움
③ 전국 훑기: 아직 안 본 아파트 단지를 세대수 큰 순으로 연결(같은 법정동 이름·세대수)하고 12개월 채움.
공용관리비 호출이 BUDGET_CMN 에 닿거나 MAX_SEC 가 지나면 멈춘다. 남는 쿼터는 낮에 열리는 단지의 온디맨드 몫.
실행: python scripts/kapt_fill.py  (daily_run step 11e)
"""
from __future__ import annotations
import os, sqlite3, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scripts.local_api as api  # noqa: E402

BUDGET_CMN = 90000         # 밤에 쓸 공용관리비 호출 상한(상한 95,000 중 5,000은 낮 온디맨드 몫)
MONTHS = 12                # 단지당 채울 달 수(화면이 보여 주는 최대)
MAX_SEC = 100 * 60         # 배치 벽시계 상한
_t0 = time.time()
_fail_streak = 0
_long_waits = 0


def _cmn_used() -> int:
    with api._kapt_db() as c:
        return api._KAPT_DAILY_CAP - api._kapt_quota_left(c, "cmn")


def _stop_reason() -> str | None:
    if _cmn_used() >= BUDGET_CMN:
        return "budget"
    if time.time() - _t0 > MAX_SEC:
        return "time"
    return None


def _fetch(code: str, ym: str) -> bool:
    """한 달 받기. 일시 오류(제공기관 HTTP 오류·429)면 쉬었다가 다시. 세 번 연속 실패면 False."""
    global _fail_streak
    for _ in range(3):
        if api._kapt_fetch_month(code, ym) is not None:
            _fail_streak = 0
            return True
        with api._kapt_db() as c:
            if api._kapt_quota_left(c, "cmn") < len(api._KAPT_CMN):
                return False
        _fail_streak += 1
        if _fail_streak >= 3:
            # 제공기관이 통째로 내려간 때(자정 무렵 정비 등): 10분씩 최대 3번 기다려 본다
            global _long_waits
            if _long_waits >= 3 or time.time() - _t0 > MAX_SEC - 600:
                return False
            _long_waits += 1; _fail_streak = 0
            print(f"  provider down? waiting 10 min ({_long_waits}/3)", flush=True)
            time.sleep(600)
        else:
            time.sleep(30)
        api._KAPT_SKIP.clear()
    return False


def _fill(code: str) -> tuple[int, bool]:
    """연결된 단지의 빠진 달을 채운다 → (받은 달 수, 계속해도 되는지)."""
    with api._kapt_db() as c:
        have = {r[0] for r in c.execute("SELECT ym FROM kapt_month WHERE kapt_code=? AND (complete=1 OR fetched_at>?)", (code, api._kapt_days_ago(7)))}
    n = 0
    for ym in api._kapt_recent_yms(MONTHS):
        if ym in have:
            continue
        if _stop_reason():
            return n, False
        if not _fetch(code, ym):
            return n, False
        n += 1
    return n, True


def main() -> int:
    used0 = _cmn_used()
    months = 0; topped = 0; linked_views = 0; swept = 0; matched = 0
    stop = None

    # ① 이미 연결된 단지의 빠진 달
    with api._kapt_db() as c:
        codes = [r[0] for r in c.execute("SELECT DISTINCT kapt_code FROM kapt_map WHERE kapt_code IS NOT NULL")]
    for code in codes:
        n, ok = _fill(code)
        months += n; topped += 1 if n else 0
        if not ok:
            stop = _stop_reason() or "fetch"; break

    # ② 최근 30일 콕집매물 상세가 열린 단지 → 연결 + 채움
    if not stop:
        try:
            lp = api.DB_PATH.parent / "logs.sqlite"
            with sqlite3.connect(f"file:{lp}?mode=ro", uri=True) as lc, api._open_db() as d, api._kapt_db() as c:
                arts = [r[0].split("/kok/listings/R", 1)[1].split("?")[0] for r in lc.execute(
                    "SELECT DISTINCT path FROM event_log WHERE ts>datetime('now','-30 days') AND path LIKE '/kok/listings/R%'")]
                cxs: set[str] = set()
                for a in arts:
                    r = d.execute("SELECT complex_no FROM listings_current WHERE article_no=?", (a,)).fetchone()
                    if r:
                        cxs.add(r[0])
                for cx in cxs:
                    if c.execute("SELECT 1 FROM kapt_map WHERE complex_no=?", (cx,)).fetchone():
                        continue
                    code = api._kapt_match(d, c, cx)
                    if code:
                        linked_views += 1
                        api._kapt_basis(c, code)
                        n, ok = _fill(code)
                        months += n
                        if not ok:
                            stop = _stop_reason() or "fetch"; break
        except Exception as e:  # noqa: BLE001
            print("link step:", e)

    # ③ 전국 훑기 — 아직 판단 안 한 아파트 단지를 세대수 큰 순으로
    if not stop:
        with api._open_db() as d, api._kapt_db() as c:
            seen = {r[0] for r in c.execute("SELECT complex_no FROM kapt_map WHERE kapt_code IS NOT NULL OR updated_at>?", (api._kapt_days_ago(30),))}
            todo = [r[0] for r in d.execute(
                "SELECT complex_no FROM complexes WHERE real_estate_type='APT' AND cortar_no IS NOT NULL AND cortar_no<>'' "
                "ORDER BY COALESCE(total_household_count,0) DESC") if r[0] not in seen]
            print(f"sweep: {len(todo)} complexes to look at")
            for cx in todo:
                stop = _stop_reason()
                if stop:
                    break
                code = api._kapt_match(d, c, cx)
                swept += 1
                if not code:
                    continue
                matched += 1
                api._kapt_basis(c, code)
                n, ok = _fill(code)
                months += n
                if not ok:
                    stop = _stop_reason() or "fetch"; break
                if matched % 50 == 0:
                    print(f"  … swept {swept}, matched {matched}, months {months}, cmn used {_cmn_used()}, {time.time()-_t0:.0f}s", flush=True)

    with api._kapt_db() as c:
        total_linked = c.execute("SELECT COUNT(*) FROM kapt_map WHERE kapt_code IS NOT NULL").fetchone()[0]
        total_judged = c.execute("SELECT COUNT(*) FROM kapt_map").fetchone()[0]
    print(f"done({stop or 'all'}): topped {topped}, viewed-linked {linked_views}, swept {swept} matched {matched}, months {months}, "
          f"cmn used {used0}→{_cmn_used()}, linked total {total_linked}/{total_judged}, {time.time()-_t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
