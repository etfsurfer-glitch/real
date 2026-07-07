"""숨김 ID 중개사 매핑 적용 — 네이버에서 중개사 ID를 비공개한 사무소의 매물 귀속.

일부 사무소는 네이버에 realtor_id를 숨겨(목록 API에서 None) 매물이 상호만 남는다.
hidden_realtor_map(상호+지역 프리픽스 → 우리 realtor_id)으로 수집 직후 귀속시켜
매물장·랭킹·점검에서 그 사무소 매물로 보이게 한다.

사례(2026-07-03): 속초 청솔공인중개사사무소(구소라) — ID 숨김, 매물 44건이
realtor_id NULL로 수집됨. 상세 API의 등록번호·전화로 본인 확인 후 매핑.
daily_run(step 8 뒤)·collect_listings(step 8 뒤)에서 호출.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "naverreal.sqlite"

SEED = [
    # (매물 상호, 법정동코드 프리픽스, 귀속 realtor_id, 메모)
    ("청솔공인중개사사무소", "51210", "vw512102026000009",
     "속초 청솔(구소라) — 네이버 ID 숨김. 등록번호 51210-2026-00009·전화 010-6304-0794 확인"),
]


def main() -> None:
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS hidden_realtor_map (
            realtor_name  TEXT NOT NULL,
            cortar_prefix TEXT NOT NULL,
            realtor_id    TEXT NOT NULL,
            note          TEXT,
            PRIMARY KEY (realtor_name, cortar_prefix))""")
        for nm, pfx, rid, note in SEED:
            c.execute("INSERT OR IGNORE INTO hidden_realtor_map VALUES (?,?,?,?)", (nm, pfx, rid, note))
        total = 0
        maps = c.execute("SELECT realtor_name, cortar_prefix, realtor_id FROM hidden_realtor_map").fetchall()
        for nm, pfx, rid in maps:
            cur = c.execute(
                "UPDATE listings_current SET realtor_id=? "
                "WHERE realtor_id IS NULL AND realtor_name=? AND complex_no IN "
                "(SELECT complex_no FROM complexes WHERE cortar_no LIKE ?)",
                (rid, nm, pfx + "%"))
            if cur.rowcount:
                print(f"  [단지형] {nm}({pfx}) → {rid}: {cur.rowcount}건")
            total += cur.rowcount
        c.commit()
    # 비단지 전체 DB(상가·사무실·빌라·단독·원룸·토지·건물·공장·지산·재개발)도 동일 귀속
    import glob as _glob
    for path_s in sorted(_glob.glob(str(DB.parent / "listings_*.sqlite"))):
        path = Path(path_s)
        dbf = path.name
        with sqlite3.connect(path) as rc:
            for nm, pfx, rid in maps:
                cur = rc.execute(
                    "UPDATE listings SET realtor_id=? WHERE (realtor_id IS NULL OR realtor_id='') "
                    "AND realtor_name=? AND cortar_no LIKE ?", (rid, nm, pfx + "%"))
                if cur.rowcount:
                    print(f"  [{dbf.split('_')[1].split('.')[0]}] {nm}({pfx}) → {rid}: {cur.rowcount}건")
                total += cur.rowcount
            rc.commit()
    print(f"hidden_realtor_map 적용: {total}건")


if __name__ == "__main__":
    main()
