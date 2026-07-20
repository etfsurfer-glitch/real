# -*- coding: utf-8 -*-
"""중개사 연결 정합성 감시 — 누락을 사용자보다 먼저 발견한다.

배경(2026-07-15): 같은 사무소가 화면마다 다른 쿼리·가정으로 조회돼 반복적으로 누락됐다.
  · 문정에이스 — 매물점검이 realtor_id=? 로만 조회(vw/CP 미고려)
  · 빌딩로드·다온에셋 — naver_realtors 없어 vworld 매칭 스킵 → 직원·업력 공백
  · 금천 참공인 — 검색 폴백이 무정렬 LIMIT로 잘림 + count가 단지형 기반
  · 등록번호 매칭 2,858곳 — 프로비저닝이 address 누락 → 동명 구분 불가
매번 제보로 발견하던 것을 **불변식(invariant)으로 매일 자동 점검**해 임계 초과 시 텔레그램 알림.

불변식(위반=누락 신호):
  ① 비단지 매물 N+ 인데 naver_realtors 프로필 없음      → 검색·상세 불가
  ② naver_realtors 주소 없음                          → 동명 사무소 구분 불가
  ③ 비단지 매물 N+ 인데 vworld 미연결                  → 직원·업력 공백
  ④ 단지형 매물 N+ 인데 vworld 미연결                  → 직원·업력 공백
  ⑤ CP귀속(vw) 사무소 프로필 미생성                    → 상세 진입 전까지 공백(온디맨드로 완화)
  ⑥ vw 사무소 직접귀속 비단지 매물이 조회에 안 뜸       → 세부·매물점검 누락(코드 회귀 감시)

⑥은 데이터 불변식이 아닌 **함수 불변식**: 2026-07-19 버그(귀속배치가 realtor_id=vw..를 세팅했는데
세부·매물점검 쿼리는 realtor_id NULL만 조회 → 5,870곳·129,418건 숨김)의 재발 감시. 직접귀속 비단지
매물이 있는 vw 사무소를 샘플링해 실제 `_collect_realtor_listings`가 그 매물을 되돌려주는지 검증한다.

사용: realtor_integrity_check.py [--min 20] [--quiet] [--notify]
  --notify 시 임계(BASELINE) 초과 항목만 텔레그램. 크론(daily)에서 --notify 로 실행.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, ".")
from collector.config import settings                       # noqa: E402

ATTR = "office_attribution.sqlite"
REG_SUM = ("(COALESCE(villa_n,0)+COALESCE(house_n,0)+COALESCE(sangga_n,0)+COALESCE(office_n,0)"
           "+COALESCE(land_n,0)+COALESCE(factory_n,0)+COALESCE(building_n,0)+COALESCE(knowledge_n,0)"
           "+COALESCE(redev_n,0)+COALESCE(oneroom_n,0))")

# 현실적 기준선 — 이 수치를 넘으면 "새로 터진 누락"으로 보고 알린다.
# (구조적으로 남는 잔여: 동일명 모호·vworld 미등록 신규 등은 0으로 못 만듦)
BASELINE = {"no_profile": 20, "no_addr": 30, "region_unlinked": 150, "complex_unlinked": 60,
            "vw_unprovisioned": 900, "vw_listing_hidden": 0}


def _check_vw_listing_surfacing(db, N: int, sample: int = 30):
    """⑥ 함수 불변식 — vw 사무소 직접귀속 비단지 매물이 실제 조회에 뜨는지.

    직접귀속(realtor_id LIKE 'vw%') 비단지 매물이 있는 사무소를 매물수 상위로 샘플링해
    `_collect_realtor_listings(rid, None, "")` 결과에 그 비단지 매물이 포함되는지 확인.
    쿼리 로직이 realtor_id NULL만 조회로 회귀하면 0으로 떨어져 여기서 잡힌다.
    반환: (숨김탐지 사무소 수, [샘플 (이름, 직접귀속수, 조회된수)])
    """
    from scripts import local_api as api    # 프로덕션 앱 모듈(박스 DB 경로 사용)
    parent = Path(settings.local_db_path).parent
    # 1) 비단지 DB 전수에서 vw 직접귀속 매물수 집계(현재 스냅샷)
    direct: dict = {}
    for fname in api._NONRESI_DB.values():
        p = parent / fname
        if not p.exists():
            continue
        try:
            with sqlite3.connect(f"file:{p}?mode=ro", uri=True) as nc:
                nc.execute("PRAGMA busy_timeout=30000")
                snap = "snapshot_date=(SELECT MAX(snapshot_date) FROM listings)"
                for rid, c in nc.execute(
                        f"SELECT realtor_id, COUNT(*) FROM listings WHERE realtor_id LIKE 'vw%' AND {snap} "
                        "GROUP BY realtor_id"):
                    direct[rid] = direct.get(rid, 0) + c
        except sqlite3.Error:
            continue
    cand = sorted((r for r in direct.items() if r[1] >= 1), key=lambda x: -x[1])[:sample]
    hidden, bad = 0, []
    for rid, dcnt in cand:
        try:
            got = api._collect_realtor_listings(rid, None, "")
        except Exception:
            continue
        nonresi_got = sum(1 for it in got if it.get("complex_no") is None)
        if nonresi_got == 0 and dcnt > 0:      # 직접귀속이 있는데 하나도 안 뜸 = 회귀
            hidden += 1
            nm = db.execute("SELECT realtor_name FROM naver_realtors WHERE realtor_id=?", (rid,)).fetchone()
            bad.append(((nm[0] if nm else rid), dcnt, nonresi_got))
    return hidden, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=20, help="매물 N건 이상만 점검(소규모 잡음 제외)")
    ap.add_argument("--notify", action="store_true", help="기준선 초과 시 텔레그램")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    N = a.min
    db = sqlite3.connect(f"file:{settings.local_db_path}?mode=ro", uri=True)
    db.execute("PRAGMA busy_timeout=60000")
    res: dict = {}
    samples: dict = {}

    # ① 매물 있는데 프로필 없음 → 검색 불가(가장 치명적: 다모아 641건 사례)
    res["no_profile"] = db.execute(
        f"SELECT COUNT(*) FROM realtor_region_counts rc LEFT JOIN naver_realtors nr ON nr.realtor_id=rc.realtor_id "
        f"WHERE nr.realtor_id IS NULL AND {REG_SUM}>=?", (N,)).fetchone()[0]
    samples["no_profile"] = db.execute(
        f"SELECT COALESCE(rn.realtor_name,rc.realtor_id), {REG_SUM} n FROM realtor_region_counts rc "
        f"LEFT JOIN naver_realtors nr ON nr.realtor_id=rc.realtor_id "
        f"LEFT JOIN realtor_names rn ON rn.realtor_id=rc.realtor_id "
        f"WHERE nr.realtor_id IS NULL AND {REG_SUM}>=? ORDER BY n DESC LIMIT 3", (N,)).fetchall()

    # ② 주소 없음 → 동명 구분 불가
    # 주소가 없어도 cortar_no가 있으면 검색결과에 지역(location)이 떠 식별 가능 → 둘 다 없을 때만 위반
    res["no_addr"] = db.execute(
        "SELECT COUNT(*) FROM naver_realtors WHERE (address IS NULL OR address='') "
        "AND (cortar_no IS NULL OR cortar_no='')").fetchone()[0]

    # ③ 비단지 매물 있는데 vworld 미연결 → 직원·업력 공백
    res["region_unlinked"] = db.execute(
        f"SELECT COUNT(*) FROM realtor_region_counts rc "
        f"LEFT JOIN realtor_match m ON m.realtor_id=rc.realtor_id AND m.sys_regno IS NOT NULL "
        f"WHERE m.realtor_id IS NULL AND {REG_SUM}>=?", (N,)).fetchone()[0]

    # ④ 단지형 매물 있는데 vworld 미연결
    res["complex_unlinked"] = db.execute(
        "SELECT COUNT(*) FROM (SELECT realtor_id, COUNT(*) n FROM listings_current "
        "WHERE realtor_id IS NOT NULL AND realtor_id<>'' GROUP BY realtor_id HAVING n>=?) t "
        "LEFT JOIN realtor_match m ON m.realtor_id=t.realtor_id AND m.sys_regno IS NOT NULL "
        "WHERE m.realtor_id IS NULL", (N,)).fetchone()[0]

    # ⑤ CP귀속(vw) 사무소 프로필 미생성(온디맨드 프로비저닝이라 치명도는 낮음)
    res["vw_unprovisioned"] = 0
    try:
        attr = sqlite3.connect(f"file:{Path(settings.local_db_path).parent / ATTR}?mode=ro", uri=True)
        sysregs = [x[0] for x in attr.execute("SELECT DISTINCT sys_regno FROM office_region_counts WHERE total>=?", (N,))]
        if sysregs:
            ph = ",".join("?" * len(sysregs))
            have = {x[0] for x in db.execute(
                f"SELECT realtor_id FROM naver_realtors WHERE realtor_id IN ({ph})", [f"vw{s}" for s in sysregs])}
            res["vw_unprovisioned"] = sum(1 for s in sysregs if f"vw{s}" not in have)
    except sqlite3.Error:
        pass

    # ⑥ vw 사무소 직접귀속 비단지 매물 조회 회귀(함수 불변식) — import·API 실패 시 조용히 스킵
    try:
        res["vw_listing_hidden"], samples["vw_listing_hidden"] = _check_vw_listing_surfacing(db, N)
    except Exception as e:
        if not a.quiet:
            print("  [skip] vw 매물 조회 점검 불가:", e)

    LABEL = {
        "no_profile": f"매물{N}+ 인데 프로필 없음(검색 불가)",
        "no_addr": "주소·지역 모두 없음(식별 불가)",
        "region_unlinked": f"비단지 매물{N}+ vworld 미연결(직원·업력 공백)",
        "complex_unlinked": f"단지형 매물{N}+ vworld 미연결",
        "vw_unprovisioned": "CP귀속 vw 프로필 미생성(온디맨드 커버)",
        "vw_listing_hidden": "vw 사무소 직접귀속 비단지 매물이 조회에 안 뜸(코드 회귀)",
    }
    over = []
    if not a.quiet:
        print("═══ 중개사 연결 정합성 ═══")
    for k, v in res.items():
        base = BASELINE.get(k, 0)
        flag = "⚠️ 초과" if v > base else "OK"
        if v > base:
            over.append(f"{LABEL[k]}: {v:,} (기준 {base:,})")
        if not a.quiet:
            print(f"  [{flag}] {LABEL[k]}: {v:,} / 기준 {base:,}")
            for s in samples.get(k, [])[:3]:
                print(f"        - {s[0][:24]} 매물 {s[1]}")
    if a.notify and over:
        try:
            from scripts.tg_notify import tg_send
            body = "\n".join("· " + x for x in over)
            top = "\n".join(f"   {s[0][:20]}({s[1]})" for s in samples.get("no_profile", [])[:3])
            tg_send(f"[콕집] 중개사 연결 누락 감지\n{body}" + (f"\n프로필없음 상위:\n{top}" if top else ""))
        except Exception as e:
            print("텔레그램 실패:", e)
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
