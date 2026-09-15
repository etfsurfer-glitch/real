# -*- coding: utf-8 -*-
"""coord_addr(역지오코딩 캐시)에서 (동,지번)→좌표 테이블 구축 — 빌라·상가 실거래 지도 매핑용.
coord_addr.addr 예: '서울특별시 강남구 역삼동 813-14' → dong=역삼동, jibun=813-14."""
import sqlite3
db = sqlite3.connect("/opt/koczip/data/coord_addr.sqlite")
db.execute("PRAGMA journal_mode=WAL")
key = {}
for dong, addr, lat, lng, sgg in db.execute(
        "SELECT dong, addr, lat, lng, sgg FROM coord_addr WHERE status='ok' AND addr IS NOT NULL"):
    if not dong:
        continue
    parts = addr.split()
    if len(parts) < 2:
        continue
    jibun = parts[-1]
    if not jibun[:1].isdigit():
        continue
    key[(dong, jibun)] = (lat, lng, sgg)   # 대표 1(마지막 유지)
db.execute("DROP TABLE IF EXISTS coord_jibun")
db.execute("CREATE TABLE coord_jibun (dong TEXT, jibun TEXT, lat REAL, lng REAL, sgg TEXT, PRIMARY KEY(dong,jibun))")
db.executemany("INSERT OR REPLACE INTO coord_jibun(dong,jibun,lat,lng,sgg) VALUES(?,?,?,?,?)",
               [(d, j, v[0], v[1], v[2]) for (d, j), v in key.items()])
db.execute("CREATE INDEX IF NOT EXISTS cj_idx ON coord_jibun(dong,jibun)")
db.commit()
n = db.execute("SELECT COUNT(*) FROM coord_jibun").fetchone()[0]
print(f"coord_jibun 구축: {n:,}개 (동,지번)→좌표")
for r in db.execute("SELECT * FROM coord_jibun LIMIT 3"):
    print("  ", r)
