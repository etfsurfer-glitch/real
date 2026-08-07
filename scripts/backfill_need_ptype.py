#!/usr/bin/env python3
"""기존 고객 요건에 '물건 종류'를 채운다 — 1회성.

요건에 종류 칸이 생기기 전에 쌓인 행은 전부 비어 있다. 비어 있으면 매칭이 종류를
못 거르고(상가 손님에게 아파트), 원장에서도 무엇을 구하는 손님인지 안 보인다.
채우는 규칙은 API 와 같은 함수(_need_ptype)를 그대로 쓴다 — 두 벌로 갈리면
나중에 결과가 달라진다.

    python3 scripts/backfill_need_ptype.py [--apply]

--apply 없이 돌리면 무엇이 어떻게 채워지는지만 보여 준다.
"""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_api as L  # noqa: E402


def main(apply: bool) -> int:
    path = L.DB_PATH.parent / "reviews.sqlite"
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM biz_needs WHERE ptype IS NULL OR ptype=''").fetchall()
    print(f"빈 요건 {len(rows)}건")
    done = 0
    for r in rows:
        nd = dict(r)
        pt = L._need_ptype(con, nd)
        src = ("매물" if nd.get("listing_id") else "단지" if nd.get("complex_no") else "원문")
        line = (nd.get("address") or nd.get("dong") or "")[:20]
        raw = (nd.get("raw_text") or "").replace("\n", " ")[:44]
        print(f"  #{nd['id']:>4} {nd.get('kind') or '':<4} {line:<20} → "
              f"{pt or '(못 정함)':<8} [{src}] {raw}")
        if pt and apply:
            con.execute("UPDATE biz_needs SET ptype=? WHERE id=?", (pt, nd["id"]))
            done += 1
    if apply:
        con.commit()
        print(f"채움 {done}건")
    else:
        print("(미리보기 — 실제로 쓰려면 --apply)")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
