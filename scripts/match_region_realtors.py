"""비단지(상가·사무실·토지·공장·빌딩·빌라·단독) 전용 중개사 → vworld 정확매칭.

단지 디렉터리(naver_realtors)에 없어 한 번도 매칭 안 된 비단지 realtor_id를,
이름 + 대표 구(sgg) 정확일치 + vworld_brokers에서 그 (이름,구) 조합이 '유일'할 때만 매칭.
정확성 우선 — 모호하면(같은 이름+구가 vworld에 2곳 이상) 스킵.

기존 realtor_match 행은 절대 건드리지 않음(INSERT OR IGNORE, realtor_id PK).
소스 비단지 DB는 읽기 전용.

    python scripts/match_region_realtors.py             # dry-run(미리보기)
    python scripts/match_region_realtors.py --commit    # 실제 INSERT
"""
from __future__ import annotations
import argparse, re, sqlite3, sys, datetime
from collections import defaultdict
from pathlib import Path


def _norm(s: str) -> str:
    """법인 표기·공백 정규화 — '(주)미스터' == '주식회사 미스터'. 유일성 검증으로 정확성 보존."""
    return re.sub(r"\(주\)|\(유\)|주식회사|유한회사|\s", "", s or "")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collector.config import settings  # noqa: E402

DB = Path(str(settings.local_db_path))
REGION_DBS = ["listings_villa", "listings_house", "listings_sangga", "listings_office",
              "listings_land", "listings_factory", "listings_building"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    m = sqlite3.connect(DB)

    # 1) 이미 매칭된 realtor_id (스킵)
    matched = {r[0] for r in m.execute("SELECT realtor_id FROM realtor_match WHERE realtor_id IS NOT NULL")}

    # 2) 비단지 realtor_id → 이름 + sgg별 매물수 (현재 스냅샷, 전 카테고리 병합)
    info: dict[str, dict] = defaultdict(lambda: {"name": "", "sgg": defaultdict(int)})
    for db in REGION_DBS:
        p = DB.parent / f"{db}.sqlite"
        if not p.exists():
            continue
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            rows = c.execute(
                "SELECT realtor_id, realtor_name, substr(cortar_no,1,5) sgg, COUNT(*) n FROM listings "
                "WHERE realtor_id!='' AND realtor_name!='' AND cortar_no!='' "
                "AND snapshot_date=(SELECT MAX(snapshot_date) FROM listings) "
                "GROUP BY realtor_id, substr(cortar_no,1,5)").fetchall()
        except Exception:
            rows = []
        c.close()
        for rid, nm, sgg, n in rows:
            if rid in matched:
                continue
            if not info[rid]["name"]:
                info[rid]["name"] = nm
            info[rid]["sgg"][sgg] += n

    candidates = {rid: d for rid, d in info.items() if d["name"] and d["sgg"]}
    print(f"미매칭 비단지 중개사: {len(candidates):,}곳")

    # 3) vworld_brokers: (business_name, sgg_cd) → set(sys_regno). 유일할 때만 매칭 가능.
    vw: dict[tuple, set] = defaultdict(set)
    vw_meta: dict[str, tuple] = {}
    for sysno, bn, sgg, status in m.execute(
            "SELECT sys_regno, business_name, sgg_cd, status FROM vworld_brokers "
            "WHERE business_name IS NOT NULL AND sgg_cd IS NOT NULL"):
        vw[(_norm(bn), sgg)].add(sysno)
        vw_meta[sysno] = (bn, status)

    # 4) 정확매칭 — 대표 구(최다 매물 sgg)에서 이름 유일일치
    rows_to_insert = []
    ambiguous = noname = 0
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for rid, d in candidates.items():
        nm = d["name"]
        psgg = max(d["sgg"], key=d["sgg"].get)
        pcnt = d["sgg"][psgg]
        sysset = vw.get((_norm(nm), psgg))
        if not sysset:
            noname += 1
            continue
        if len(sysset) != 1:
            ambiguous += 1
            continue  # 같은 이름+구가 2곳+ → 정확성 위해 스킵
        sysno = next(iter(sysset))
        bn, status = vw_meta[sysno]
        rows_to_insert.append((rid, nm, psgg, pcnt, 0, sysno, bn, None, "region_exact", None, now, status))

    print(f"  정확매칭 가능: {len(rows_to_insert):,}곳 · 모호(스킵) {ambiguous:,} · vworld無 {noname:,}")
    if rows_to_insert[:5]:
        print("  샘플:")
        for r in rows_to_insert[:5]:
            print(f"    {r[1]} ({r[2]}) → sys {r[5]} / {r[6]}")

    if not a.commit:
        print("\n[dry-run] --commit 으로 실제 INSERT. 기존 행 미변경(INSERT OR IGNORE).")
        return 0

    before = m.execute("SELECT COUNT(*) FROM realtor_match").fetchone()[0]
    m.executemany(
        "INSERT OR IGNORE INTO realtor_match(realtor_id,naver_name,primary_sgg_cd,primary_sgg_count,"
        "total_listings,sys_regno,vworld_name,vworld_rep,match_type,candidates_json,matched_at,vworld_status) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows_to_insert)
    m.commit()
    after = m.execute("SELECT COUNT(*) FROM realtor_match").fetchone()[0]
    print(f"\n[commit] realtor_match {before:,} → {after:,} (+{after-before:,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
