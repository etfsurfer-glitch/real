# -*- coding: utf-8 -*-
"""매물 보유 중개사의 **검색 가능성 보장** — 프로필(naver_realtors) 누락 메우기.

문제(2026-07-15 realtor_integrity_check 탐지): 비단지 매물을 수백 건 보유한 사무소가
naver_realtors 프로필이 없어 **검색에 아예 안 뜸**(다모아 641건·청춘 548건·도시 329건).
원인: 프로필은 ①네이버 중개사 크롤 ②vworld 매칭 성공 시 프로비저닝 — 둘 다 실패하면 공백.
vworld 매칭(등록번호/이름)은 오귀속 방지로 실패할 수 있는데, 그 실패가 **검색 실종으로 전이**됐다.

원칙 분리: **신원 연결(vworld·직원/업력)은 실패해도, 검색 가능성은 보장한다.**
매물 + 상호(realtor_names)가 있으면 최소 프로필을 만든다(지역=매물 최빈 cortar).
vworld 연결은 나중에 성공하면 match/직원·업력이 얹힌다(멱등, 기존 행 미변경).

사용: ensure_realtor_profiles.py [--min 1] [--dry]
"""
import argparse
import datetime
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from collector.config import settings                       # noqa: E402

DATA = os.environ.get("KOCZIP_DATA", str(settings.local_db_path.parent))
CATS = ["villa", "oneroom", "house", "sangga", "office",
        "knowledge", "redev", "building", "factory", "land"]
REG_SUM = ("(COALESCE(villa_n,0)+COALESCE(house_n,0)+COALESCE(sangga_n,0)+COALESCE(office_n,0)"
           "+COALESCE(land_n,0)+COALESCE(factory_n,0)+COALESCE(building_n,0)+COALESCE(knowledge_n,0)"
           "+COALESCE(redev_n,0)+COALESCE(oneroom_n,0))")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=1, help="매물 N건 이상만")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    db = sqlite3.connect(settings.local_db_path, timeout=60)
    db.execute("PRAGMA busy_timeout=60000")

    # 대상: 비단지 매물 있고, 상호 알고, 프로필 없는 사무소
    targets = db.execute(
        f"SELECT rc.realtor_id, rn.realtor_name, {REG_SUM} n FROM realtor_region_counts rc "
        f"JOIN realtor_names rn ON rn.realtor_id=rc.realtor_id "
        f"LEFT JOIN naver_realtors nr ON nr.realtor_id=rc.realtor_id "
        f"WHERE nr.realtor_id IS NULL AND rn.realtor_name IS NOT NULL AND rn.realtor_name<>'' "
        f"AND {REG_SUM}>=? ORDER BY n DESC", (a.min,)).fetchall()
    if not targets:
        print("[*] 대상 없음 — 프로필 공백 사무소 0")
        return
    want = {t[0] for t in targets}
    print(f"[*] 프로필 없는 매물보유 사무소: {len(targets):,} (최대 {targets[0][2]}건 · {targets[0][1]})", flush=True)

    # 지역: 각 사무소 매물의 최빈 cortar_no (검색결과 소재지 표시용)
    cort: dict = defaultdict(Counter)
    for cat in CATS:
        p = os.path.join(DATA, f"listings_{cat}.sqlite")
        if not os.path.exists(p):
            continue
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            snap = c.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
            if not snap:
                continue
            for rid, ct in c.execute(
                    "SELECT realtor_id, cortar_no FROM listings WHERE realtor_id IS NOT NULL "
                    "AND realtor_id<>'' AND cortar_no IS NOT NULL AND snapshot_date=?", (snap,)):
                if rid in want:
                    cort[rid][ct] += 1
        finally:
            c.close()

    now = datetime.datetime.now().isoformat(timespec="seconds")
    made = 0
    for rid, name, n in targets:
        top = cort[rid].most_common(1)
        cortar = top[0][0] if top else None
        if a.dry:
            print(f"    [dry] {name[:22]} ({rid}) 매물{n} cortar={cortar}")
            continue
        db.execute(
            "INSERT OR IGNORE INTO naver_realtors(realtor_id, realtor_name, cortar_no, raw_json, fetched_at) "
            "VALUES(?,?,?,?,?)",
            (rid, name, cortar, '{"source":"profile_ensure"}', now))
        made += 1
        if made % 200 == 0:
            db.commit()
    db.commit()
    print(f"[*] 프로필 생성: {made:,} (검색 가능해짐 — vworld 연결은 별도로 성공 시 직원·업력 부착)")
    db.close()


if __name__ == "__main__":
    main()
