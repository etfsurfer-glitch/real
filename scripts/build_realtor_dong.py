"""중개사 사무소 → 행정동(cortar_no) 매핑 — "우리동네 중개사"용.

vworld 등록 중개사(공식 개설등록) 전체를 사무소 소재 동에 매핑한다. naver 매물 매칭 여부와
무관하게 그 동의 '모든' 등록 중개사를 보여주기 위함(매물 없어도 직원·업력 있는 실제 사무소).

realtor_dong(sys_regno PK, cortar_no, realtor_id, dong_name, sgg_cd):
  - vworld_brokers.dong_name + sgg_cd → regions(sec) cortar_no  (공식 등록주소, 93% 해석)
  - realtor_id: realtor_match 로 naver 매칭된 경우만(매물수·상세링크용, nullable)
도로명만 있어 dong_name 없는 건은 보류.
"""
import sqlite3
import sys

sys.path.insert(0, ".")
from collector.config import settings  # noqa: E402

DB = settings.local_db_path


def main():
    c = sqlite3.connect(DB)
    c.execute("DROP TABLE IF EXISTS realtor_dong")
    c.execute("""
        CREATE TABLE realtor_dong(
          sys_regno  TEXT PRIMARY KEY,
          cortar_no  TEXT,
          realtor_id TEXT,
          dong_name  TEXT,
          sgg_cd     TEXT
        )""")
    # vworld 등록 중개사 전체 → cortar (사무소 소재 동). realtor_id 는 매칭시.
    c.execute("""
        INSERT OR IGNORE INTO realtor_dong(sys_regno, cortar_no, realtor_id, dong_name, sgg_cd)
        SELECT v.sys_regno, r.cortar_no, m.realtor_id, v.dong_name, v.sgg_cd
        FROM vworld_brokers v
        JOIN regions r ON r.cortar_name = v.dong_name
                      AND substr(r.cortar_no,1,5) = v.sgg_cd
                      AND r.cortar_type = 'sec'
        LEFT JOIN realtor_match m ON m.sys_regno = v.sys_regno
        WHERE v.dong_name IS NOT NULL
    """)
    c.execute("CREATE INDEX realtor_dong_cortar_idx ON realtor_dong(cortar_no)")
    c.execute("CREATE INDEX realtor_dong_rid_idx ON realtor_dong(realtor_id)")
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM realtor_dong").fetchone()[0]
    dongs = c.execute("SELECT COUNT(DISTINCT cortar_no) FROM realtor_dong").fetchone()[0]
    matched = c.execute("SELECT COUNT(*) FROM realtor_dong WHERE realtor_id IS NOT NULL").fetchone()[0]
    print(f"realtor_dong(office): {total}곳 / {dongs}개 동 / naver매칭 {matched}곳")

    # 비단지(빌라·단독·상가·사무실·토지·공장·빌딩) realtor_id별 매물수 집계 — 랭킹 매물 범위(scope)용.
    # 소스 비단지 DB는 읽기 전용(ATTACH), 파생 집계 테이블만 재생성.
    base = DB.parent
    REGION = [("villa", "listings_villa.sqlite"), ("house", "listings_house.sqlite"),
              ("sangga", "listings_sangga.sqlite"), ("office", "listings_office.sqlite"),
              ("land", "listings_land.sqlite"), ("factory", "listings_factory.sqlite"),
              ("building", "listings_building.sqlite")]
    present = []
    for alias, fn in REGION:
        p = base / fn
        if p.exists():
            c.execute(f"ATTACH '{p.as_posix()}' AS {alias}")
            present.append(alias)
    TYPES = ["villa", "house", "sangga", "office", "land", "factory", "building"]
    cols = [t + "_n" for t in TYPES]
    coldefs = ", ".join(f"{c0} INT DEFAULT 0" for c0 in cols)

    def _branch(alias: str, per_sido: bool) -> str:
        counts = ", ".join((f"COUNT(*) {c}" if t == alias else f"0 {c}") for t, c in zip(TYPES, cols))
        sido_sel = "substr(cortar_no,1,2) sido, " if per_sido else ""
        whe = " AND cortar_no!=''" if per_sido else ""
        grp = ", substr(cortar_no,1,2)" if per_sido else ""
        return (f"SELECT realtor_id, {sido_sel}{counts} FROM {alias}.listings "
                f"WHERE realtor_id!=''{whe} AND snapshot_date=(SELECT MAX(snapshot_date) FROM {alias}.listings) "
                f"GROUP BY realtor_id{grp}")

    sums = ", ".join(f"SUM({c0})" for c0 in cols)
    c.execute("DROP TABLE IF EXISTS realtor_region_counts")
    c.execute(f"CREATE TABLE realtor_region_counts(realtor_id TEXT PRIMARY KEY, {coldefs})")
    if present:
        union = " UNION ALL ".join(_branch(a, False) for a in present)
        c.execute(f"INSERT INTO realtor_region_counts(realtor_id,{','.join(cols)}) "
                  f"SELECT realtor_id,{sums} FROM ({union}) GROUP BY realtor_id")
    c.execute("DROP TABLE IF EXISTS realtor_region_sido")
    c.execute(f"CREATE TABLE realtor_region_sido(realtor_id TEXT, sido TEXT, {coldefs}, PRIMARY KEY(realtor_id,sido))")
    if present:
        union_s = " UNION ALL ".join(_branch(a, True) for a in present)
        c.execute(f"INSERT INTO realtor_region_sido(realtor_id,sido,{','.join(cols)}) "
                  f"SELECT realtor_id,sido,{sums} FROM ({union_s}) GROUP BY realtor_id,sido")
    c.execute("CREATE INDEX IF NOT EXISTS rrs_sido_idx ON realtor_region_sido(sido)")
    # 단지형(listings_current) 시도×중개사 카운트 미리 집계 — by-sido 랭킹 라이브 풀스캔(2s) 제거.
    c.execute("DROP TABLE IF EXISTS realtor_complex_sido")
    c.execute("""
        CREATE TABLE realtor_complex_sido AS
        SELECT substr(c.cortar_no,1,2) sido, l.realtor_id, COUNT(*) n
        FROM listings_current l JOIN complexes c ON c.complex_no=l.complex_no
        WHERE l.realtor_id IS NOT NULL AND l.realtor_id!='' AND c.cortar_no IS NOT NULL
        GROUP BY substr(c.cortar_no,1,2), l.realtor_id
    """)
    c.execute("CREATE INDEX IF NOT EXISTS rcs_sido_idx ON realtor_complex_sido(sido)")
    # 통합 중개사명(naver_realtors + 비단지 매물명) — 랭킹 이름 표시용.
    c.execute("DROP TABLE IF EXISTS realtor_names")
    c.execute("CREATE TABLE realtor_names(realtor_id TEXT PRIMARY KEY, realtor_name TEXT)")
    c.execute("INSERT OR REPLACE INTO realtor_names SELECT realtor_id, realtor_name FROM naver_realtors "
              "WHERE realtor_id IS NOT NULL AND realtor_name IS NOT NULL")
    for alias in present:
        c.execute(f"INSERT OR IGNORE INTO realtor_names SELECT realtor_id, MAX(realtor_name) "
                  f"FROM {alias}.listings WHERE realtor_id!='' AND realtor_name!='' GROUP BY realtor_id")
    c.commit()
    rc = c.execute("SELECT COUNT(*) FROM realtor_region_counts").fetchone()[0]
    tot = c.execute("SELECT SUM(villa_n+house_n+sangga_n+office_n+land_n+factory_n+building_n) FROM realtor_region_counts").fetchone()[0]
    print(f"realtor_region_counts(비단지 집계): {rc}곳 · 매물 {tot:,}")
    c.close()


if __name__ == "__main__":
    main()
