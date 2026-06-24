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

    # 비단지(빌라·단독·상가·사무실) realtor_id별 매물수 집계 — 랭킹 매물 범위(scope)용.
    base = DB.parent
    for alias, fn in (("villa", "listings_villa.sqlite"), ("house", "listings_house.sqlite"),
                      ("sangga", "listings_sangga.sqlite"), ("office", "listings_office.sqlite")):
        p = base / fn
        if p.exists():
            c.execute(f"ATTACH '{p.as_posix()}' AS {alias}")
    c.execute("CREATE TABLE IF NOT EXISTS realtor_region_counts("
              "realtor_id TEXT PRIMARY KEY, villa_n INT DEFAULT 0, house_n INT DEFAULT 0, "
              "sangga_n INT DEFAULT 0, office_n INT DEFAULT 0)")
    c.execute("DELETE FROM realtor_region_counts")
    c.execute("""
        INSERT INTO realtor_region_counts(realtor_id, villa_n, house_n, sangga_n, office_n)
        SELECT realtor_id, SUM(v), SUM(h), SUM(s), SUM(o) FROM (
          SELECT realtor_id, COUNT(*) v,0 h,0 s,0 o FROM villa.listings  WHERE realtor_id!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM villa.listings)  GROUP BY realtor_id
          UNION ALL SELECT realtor_id,0,COUNT(*),0,0 FROM house.listings  WHERE realtor_id!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM house.listings)  GROUP BY realtor_id
          UNION ALL SELECT realtor_id,0,0,COUNT(*),0 FROM sangga.listings WHERE realtor_id!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM sangga.listings) GROUP BY realtor_id
          UNION ALL SELECT realtor_id,0,0,0,COUNT(*) FROM office.listings WHERE realtor_id!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM office.listings) GROUP BY realtor_id
        ) GROUP BY realtor_id
    """)
    # 시도별 비단지 집계(랭킹 by-sido scope용)
    c.execute("CREATE TABLE IF NOT EXISTS realtor_region_sido(realtor_id TEXT, sido TEXT, "
              "villa_n INT DEFAULT 0, house_n INT DEFAULT 0, sangga_n INT DEFAULT 0, office_n INT DEFAULT 0, "
              "PRIMARY KEY(realtor_id,sido))")
    c.execute("DELETE FROM realtor_region_sido")
    c.execute("""
        INSERT INTO realtor_region_sido(realtor_id,sido,villa_n,house_n,sangga_n,office_n)
        SELECT realtor_id, sido, SUM(v),SUM(h),SUM(s),SUM(o) FROM (
          SELECT realtor_id, substr(cortar_no,1,2) sido, COUNT(*) v,0 h,0 s,0 o FROM villa.listings  WHERE realtor_id!='' AND cortar_no!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM villa.listings)  GROUP BY realtor_id, substr(cortar_no,1,2)
          UNION ALL SELECT realtor_id, substr(cortar_no,1,2) sido,0,COUNT(*),0,0 FROM house.listings  WHERE realtor_id!='' AND cortar_no!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM house.listings)  GROUP BY realtor_id, substr(cortar_no,1,2)
          UNION ALL SELECT realtor_id, substr(cortar_no,1,2) sido,0,0,COUNT(*),0 FROM sangga.listings WHERE realtor_id!='' AND cortar_no!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM sangga.listings) GROUP BY realtor_id, substr(cortar_no,1,2)
          UNION ALL SELECT realtor_id, substr(cortar_no,1,2) sido,0,0,0,COUNT(*) FROM office.listings WHERE realtor_id!='' AND cortar_no!='' AND snapshot_date=(SELECT MAX(snapshot_date) FROM office.listings) GROUP BY realtor_id, substr(cortar_no,1,2)
        ) GROUP BY realtor_id, sido
    """)
    c.execute("CREATE INDEX IF NOT EXISTS rrs_sido_idx ON realtor_region_sido(sido)")
    # 통합 중개사명(naver_realtors + 비단지 매물명) — 랭킹 이름 표시용.
    c.execute("CREATE TABLE IF NOT EXISTS realtor_names(realtor_id TEXT PRIMARY KEY, realtor_name TEXT)")
    c.execute("DELETE FROM realtor_names")
    c.execute("INSERT OR REPLACE INTO realtor_names SELECT realtor_id, realtor_name FROM naver_realtors "
              "WHERE realtor_id IS NOT NULL AND realtor_name IS NOT NULL")
    for alias in ("sangga", "office", "villa", "house"):
        c.execute(f"INSERT OR IGNORE INTO realtor_names SELECT realtor_id, MAX(realtor_name) "
                  f"FROM {alias}.listings WHERE realtor_id!='' AND realtor_name!='' GROUP BY realtor_id")
    c.commit()
    rc = c.execute("SELECT COUNT(*) FROM realtor_region_counts").fetchone()[0]
    print(f"realtor_region_counts(비단지 집계): {rc}곳")
    c.close()


if __name__ == "__main__":
    main()
