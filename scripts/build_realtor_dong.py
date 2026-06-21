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
    c.close()


if __name__ == "__main__":
    main()
