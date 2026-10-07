# -*- coding: utf-8 -*-
"""지역별 2026년(1~8월) 신규계약 전세비중 — §4 매물수/실매물수 교차검증용.
박스 실행: /opt/koczip/.venv/bin/python newshare.py  →  /tmp/newshare.json"""
import sqlite3, json
from collections import defaultdict
con = sqlite3.connect("/opt/koczip/data/naverreal.sqlite")

def reg(s):
    s = (s or "")[:2]
    return "서울" if s == "11" else ("수도권" if s in ("41", "28") else ("지방" if s.isdigit() else None))

a = defaultdict(lambda: [0, 0])  # region -> [jeonse, tot]
for sgg, mr in con.execute(
        "SELECT sgg_cd, monthly_rent FROM rentals "
        "WHERE deal_ymd>='2026-01-01' AND deal_ymd<='2026-08-31' AND contract_type LIKE '%신규%'"):
    r = reg(sgg)
    if r is None:
        continue
    for sc in (r, "전국"):
        a[sc][1] += 1
        if (mr or 0) == 0:
            a[sc][0] += 1

out = {sc: round(v[0] / v[1] * 100, 1) for sc, v in a.items()}
open("/tmp/newshare.json", "w").write(json.dumps(out, ensure_ascii=False))
print(out)
