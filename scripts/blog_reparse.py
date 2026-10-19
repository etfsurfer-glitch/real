# -*- coding: utf-8 -*-
"""저장된 본문(body)으로 재파싱한다. 네트워크를 타지 않는다.

blog_tables.py 를 고쳤을 때 쓴다. 글을 다시 긁지 않으므로 네이버에 부담이 없고,
파서 개선 효과를 같은 표본에서 바로 비교할 수 있다.

  python3 scripts/blog_reparse.py            # 전체 재파싱(덮어쓰기)
  python3 scripts/blog_reparse.py --dry      # 쓰지 않고 수율만 센다
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import zlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blog_tables as T                                      # noqa: E402
from blog_building import DB, PAT, db_init, store            # noqa: E402

import re                                                    # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--seed", help="이 빌딩만")
    a = ap.parse_args()

    d = db_init()
    q = ("SELECT p.url, p.seed_name, p.place_id, p.title, p.blogger, p.posted_raw, "
         "p.fetched_on, b.tables, b.text FROM post p JOIN body b USING(url)")
    if a.seed:
        q += " WHERE p.seed_name=?"
    rows = d.execute(q, (a.seed,) if a.seed else ()).fetchall()
    if not rows:
        print("저장된 본문이 없다. 먼저 blog_building.py 를 돌려야 한다.")
        return 1

    k = Counter()
    for url, seed, pid, title, blogger, praw, fetched, tabs, txt in rows:
        tabs = zlib.decompress(tabs).decode()
        txt = zlib.decompress(txt).decode()
        rev = {"title": title, "name": blogger, "date": praw}
        if a.dry:
            p = T.parse(tabs)
            k[T.kind(tabs + "\n" + txt, p)] += 1
            k["spec"] += len(p["spec"]); k["unit"] += len(p["unit"])
            k["floor_area"] += len(p["floor_area"]); k["floor_price"] += len(p["floor_price"])
            k["text"] += sum(1 for pat in PAT.values() if re.search(pat, txt))
            continue
        kind, n, nf = store(d, url, seed, pid, rev, tabs, txt, fetched)
        k[kind] += 1
        k["atoms"] += n
        k["floor"] += nf
    if not a.dry:
        d.commit()
    print(f"글 {len(rows)}건 재파싱{' (dry)' if a.dry else ''} · {dict(k)}")
    d.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
