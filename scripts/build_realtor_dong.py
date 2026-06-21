"""중개사 → 행정동(cortar_no) 매핑 빌드 — 사무소 소재지 기준 "우리동네 중개사" 용.

소스 우선순위:
  1) realtor_match.sys_regno → vworld_brokers(dong_name, sgg_cd) → regions(sec) cortar_no  (공식 등록주소)
  2) naver_realtors.address 의 지번 '○○동' 파싱 → regions(sec) cortar_no                  (fallback)

결과: realtor_dong(realtor_id PK, cortar_no, dong_name, sgg_cd, source). 데일리 루틴서 재빌드.
도로명만 있어 동을 못 얻는 건은 보류(추후 vworld geocode 보강).
"""
import sqlite3
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from collector.config import settings  # noqa: E402

DB = settings.local_db_path

_DONG_RE = re.compile(r"([가-힣]+(?:동|읍|면))(?:\s|\d|$)")


def main():
    c = sqlite3.connect(DB)
    c.execute("""
        CREATE TABLE IF NOT EXISTS realtor_dong(
          realtor_id TEXT PRIMARY KEY,
          cortar_no  TEXT,
          dong_name  TEXT,
          sgg_cd     TEXT,
          source     TEXT
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS realtor_dong_cortar_idx ON realtor_dong(cortar_no)")
    c.execute("DELETE FROM realtor_dong")

    # regions(sec=동): (cortar_name, sgg) → cortar_no. 동음이의는 sgg로 구분.
    region_map = {}
    for cortar_no, name in c.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='sec' AND length(cortar_no)=10"):
        region_map[(name, cortar_no[:5])] = cortar_no

    # 1) vworld 공식 등록 동(우선)
    n_vworld = 0
    rows = c.execute("""
        SELECT m.realtor_id, v.dong_name, v.sgg_cd
        FROM realtor_match m
        JOIN vworld_brokers v ON v.sys_regno = m.sys_regno
        WHERE m.realtor_id IS NOT NULL AND v.dong_name IS NOT NULL
    """).fetchall()
    for rid, dong, sgg in rows:
        cortar = region_map.get((dong, sgg))
        if cortar:
            c.execute("INSERT OR REPLACE INTO realtor_dong(realtor_id,cortar_no,dong_name,sgg_cd,source) "
                      "VALUES(?,?,?,?,'vworld')", (rid, cortar, dong, sgg))
            n_vworld += 1

    # 2) fallback: naver 주소 지번 '○○동' 파싱 (vworld로 못 채운 중개사만)
    n_addr = 0
    have = {r[0] for r in c.execute("SELECT realtor_id FROM realtor_dong")}
    for rid, addr in c.execute(
            "SELECT realtor_id, address FROM naver_realtors WHERE address IS NOT NULL"):
        if rid in have or not addr:
            continue
        m = _DONG_RE.search(addr)
        if not m:
            continue
        dong = m.group(1)
        # sgg 모르면 동이름만으로 유일 해석되는 경우만 채택(동음이의 위험 회피)
        cands = [v for (n, s), v in region_map.items() if n == dong]
        if len(cands) == 1:
            c.execute("INSERT OR REPLACE INTO realtor_dong(realtor_id,cortar_no,dong_name,sgg_cd,source) "
                      "VALUES(?,?,?,?,'naver_addr')", (rid, cands[0], dong, cands[0][:5]))
            n_addr += 1

    c.commit()
    total = c.execute("SELECT COUNT(*) FROM realtor_dong").fetchone()[0]
    dongs = c.execute("SELECT COUNT(DISTINCT cortar_no) FROM realtor_dong").fetchone()[0]
    print(f"realtor_dong: vworld {n_vworld} + naver주소 {n_addr} = 총 {total}건, {dongs}개 동")
    c.close()


if __name__ == "__main__":
    main()
