"""전국 법정동(읍면동 레벨) 목록 구축 → all_cortars 테이블.

비단지 수집이 '단지 보유 동'만 돌면 시골 면(面) 지역 토지·전원주택이 구조적으로
누락된다(2026-07-05 매물맛집 토지 12건 사각 발견). 네이버 지역 API를
시도→시군구→읍면동으로 훑어 전체 동 목록을 만들어 수집 범위를 전국으로 확장.
지역 개편은 드물어 분기 1회 재실행이면 충분. 사용: python scripts/build_all_cortars.py
"""
import sys
import time
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collector.http import get_json          # noqa: E402
from collector.creds import ensure_creds     # noqa: E402

REGION_URL = "https://new.land.naver.com/api/regions/list"


def _children(cortar: str, creds) -> list[tuple[str, str]]:
    st, d = get_json(REGION_URL, creds, params={"cortarNo": cortar})
    if st != 200 or not isinstance(d, dict):
        return []
    return [(r.get("cortarNo"), r.get("cortarName")) for r in (d.get("regionList") or [])]


def main() -> None:
    creds = ensure_creds()
    sidos = _children("0000000000", creds)
    print(f"시도 {len(sidos)}개")
    rows = []
    for scode, sname in sidos:
        sggs = _children(scode, creds)
        for gcode, gname in sggs:
            dongs = _children(gcode, creds)
            for dcode, dname in dongs:
                rows.append((dcode, f"{sname} {gname} {dname}"))
            time.sleep(0.15)
        print(f"  {sname}: 시군구 {len(sggs)} · 누적 동 {len(rows)}")
    db = sqlite3.connect(ROOT / "data" / "naverreal.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS all_cortars (cortar_no TEXT PRIMARY KEY, name TEXT, built_at TEXT)")
    db.executemany("INSERT OR REPLACE INTO all_cortars(cortar_no, name, built_at) "
                   "VALUES(?,?,date('now'))", rows)
    db.commit()
    print(f"all_cortars: {len(rows):,}개 동 저장")


if __name__ == "__main__":
    main()
