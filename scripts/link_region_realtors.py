# -*- coding: utf-8 -*-
"""상업 전문 region-중개사(naver_realtors 미수집)를 vworld에 이름+시도로 안전 연결.

문제(2026-07-14): 빌딩·상가·사무실 전문 법인 중 상당수는 realtor_id·매물은 있으나
네이버 중개사 프로필이 미수집(naver_realtors 없음) → match_clean이 처리 자체를 안 함
→ 전국/건물 매물랭킹에서 직원수·개업연도·소재지가 "-"(빌딩로드부동산중개 등 5,361곳).
등록번호는 CP(NEONET 등) 상세가 안 줘서 불가.

해결: (정규화이름 + 시도)로 vworld_brokers에 **유일 영업** 매칭될 때만 안전 연결.
동일명 2+는 오귀속 위험이라 건너뜀(오귀속 0 원칙). 연결 시:
  ① naver_realtors 프로비저닝(realtor_id, 상호, 대표, 주소, 등록번호, cortar=vworld sgg)
  ② realtor_match(realtor_id → sys_regno, match_type='namematch_region')
→ 전국/우리동네 랭킹의 직원수(vworld_employees)·개업연도(registered_ymd)·소재지 자동 노출.

멱등: 이미 naver_realtors/realtor_match 있으면 스킵. 월간 vworld 갱신 뒤 실행 권장.
"""
import datetime
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from collector.config import settings                       # noqa: E402
from collector.realtor_matching import normalize_name       # noqa: E402


def main():
    db = sqlite3.connect(settings.local_db_path, timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    db.row_factory = sqlite3.Row

    # vworld 인덱스: (시도2, 정규화이름) → [(sys_regno, name, rep, addr, ra_regno, sgg_cd)...] (영업만)
    vw = defaultdict(list)
    for r in db.execute("SELECT sys_regno, sgg_cd, business_name, representative, address, ra_regno, status "
                        "FROM vworld_brokers WHERE status='영업'"):
        nm = normalize_name(r["business_name"])
        if nm and r["sgg_cd"]:
            vw[(r["sgg_cd"][:2], nm)].append(r)

    # 대상: realtor_region_counts에 있고 naver_realtors에 없는 realtor_id + 상호
    targets = db.execute("""
        SELECT rc.realtor_id, COALESCE(rn.realtor_name, rc.realtor_id) nm
        FROM realtor_region_counts rc
        LEFT JOIN naver_realtors nr ON nr.realtor_id=rc.realtor_id
        LEFT JOIN realtor_names rn ON rn.realtor_id=rc.realtor_id
        WHERE nr.realtor_id IS NULL
    """).fetchall()

    # 각 대상 주 시도(realtor_region_sido 최다 매물)
    sido_of = {}
    for rid, sd in db.execute(
        "SELECT realtor_id, sido FROM realtor_region_sido ORDER BY "
        "(villa_n+house_n+sangga_n+office_n+land_n+factory_n+building_n+knowledge_n+redev_n+oneroom_n) DESC"):
        sido_of.setdefault(rid, sd)

    now = datetime.datetime.now().isoformat(timespec="seconds")
    linked = ambig = zero = 0
    for t in targets:
        rid, name = t["realtor_id"], t["nm"]
        nm = normalize_name(name)
        sd = (sido_of.get(rid) or "")[:2]
        if not nm or not sd:
            zero += 1; continue
        cands = vw.get((sd, nm), [])
        if len(cands) != 1:
            if len(cands) > 1:
                ambig += 1
            else:
                zero += 1
            continue
        v = cands[0]
        # ① naver_realtors 프로비저닝(멱등)
        db.execute(
            "INSERT OR IGNORE INTO naver_realtors(realtor_id, realtor_name, representative_name, "
            "address, establish_registration_no, cortar_no, raw_json, fetched_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (rid, name, v["representative"], v["address"], v["ra_regno"],
             v["sgg_cd"] + "00000", '{"source":"vworld_namematch"}', now))
        # ② realtor_match 연결(멱등)
        db.execute(
            "INSERT INTO realtor_match(realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at) "
            "VALUES(?,?,?,?,'namematch_region',?) "
            "ON CONFLICT(realtor_id) DO UPDATE SET sys_regno=excluded.sys_regno, "
            "vworld_name=excluded.vworld_name, vworld_rep=excluded.vworld_rep, "
            "match_type=excluded.match_type, matched_at=excluded.matched_at "
            "WHERE realtor_match.sys_regno IS NULL",   # 기존 정식매칭은 덮지 않음
            (rid, v["sys_regno"], v["business_name"], v["representative"], now))
        linked += 1
        if linked % 500 == 0:
            db.commit()
            print(f"  linked {linked} …", flush=True)
    db.commit()
    print(f"[*] 이름매칭 연결: {linked:,} · 모호(스킵) {ambig:,} · 무매칭 {zero:,} / 대상 {len(targets):,}")
    db.close()


if __name__ == "__main__":
    main()
