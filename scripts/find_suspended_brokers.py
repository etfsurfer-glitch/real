"""매칭 안 된 realtor의 vworld 정지 사무소 찾기.

vworld 사무소 list 크롤은 영업중만 default로 반환하지만,
직원 검색(svcCode=118)에 대표자명 좁혀서 검색하면 정지 사무소도 나옴.

unmatched realtor 중 카테고리 D (표준 등록번호인데 vworld 미등록)에 대해
vworld 직원 검색으로 정지 사무소 lookup.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import addr_sgg_key  # noqa: E402
from collector.vworld import LIST_URL, _GOVIEW_RE  # noqa: E402

# sigungu name → sgg code map
SGG_NAME_TO_CODE: dict = {}


def load_sgg_map(conn):
    for r in conn.execute("SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='dvsn'"):
        SGG_NAME_TO_CODE[r[1]] = r[0][:5]


def search_employee(client, sido_cd, sigungu_cd, rep_name):
    """직원 검색에서 대표자명으로 사무소 찾기. 정지/휴업/폐업도 함께."""
    data = {
        "sidoCd": sido_cd,
        "sigunguCd": sigungu_cd,
        "v_rdealer_nm": rep_name,
        "pageIndex": "1",
        "recordCountPerPage": "20",
        "svcCode": "118",
    }
    r = client.post(LIST_URL, data=data, timeout=30.0)
    r.raise_for_status()
    rows = []
    # tbody 파싱 (employee mode)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "lxml")
    tbody = soup.select_one("table tbody")
    if not tbody:
        return rows
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue
        link = tr.find("a", href=_GOVIEW_RE)
        # 정지/휴업/폐업 사무소는 link가 없을 수 있음 — 그래도 row 정보 활용
        sys_regno = ra_regno = sgg = None
        if link:
            gv = _GOVIEW_RE.search(link.get("href", ""))
            if gv:
                sgg, ra_regno, sys_regno = gv.group(1), gv.group(2), gv.group(3)
        emp_name = tds[1].get_text(strip=True)
        biz_name = tds[2].get_text(strip=True)
        role = tds[3].get_text(strip=True)
        position = tds[4].get_text(strip=True)
        status_span = tds[5].find("span")
        status_title = status_span.get("title") if status_span else None
        status_text = status_span.get_text(strip=True) if status_span else tds[5].get_text(strip=True)
        # 헤더 row(emp_name=='성명') 제외
        if emp_name in ("성명", "성 명", ""):
            continue
        rows.append({
            "sys_regno": sys_regno, "ra_regno": ra_regno, "sgg_cd": sgg,
            "business_name": biz_name, "employee_name": emp_name,
            "role": role, "position": position,
            "status": status_text, "status_title": status_title,
        })
    return rows


def main():
    conn = sqlite3.connect(settings.local_db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    load_sgg_map(conn)

    # 대상: match_type='none', 등록번호 있음, 주소·대표자 있음
    # match_type='none' 전체 — 카테고리 B/C/D 모두
    targets = conn.execute(
        """
        SELECT m.realtor_id, m.naver_name, m.primary_sgg_cd, m.total_listings,
               nr.representative_name, nr.address, nr.establish_registration_no
        FROM realtor_match m
        JOIN naver_realtors nr ON nr.realtor_id = m.realtor_id
        WHERE m.match_type='none'
          AND nr.representative_name IS NOT NULL
          AND nr.address IS NOT NULL
        ORDER BY COALESCE(m.total_listings, 0) DESC
        """
    ).fetchall()
    print(f"[*] candidates to check: {len(targets)}", flush=True)

    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0", "Referer": LIST_URL},
        timeout=30.0,
        follow_redirects=True,
    )
    client.get(LIST_URL)

    found = []
    started = time.time()
    for i, t in enumerate(targets, 1):
        # naver_realtors.address → sgg_key → vworld sgg_cd
        sgg_key = addr_sgg_key(t["address"])
        if not sgg_key:
            continue
        # 시군구 찾기: regions에서 cortar_name 부분 일치
        sgg_name = sgg_key.split("-")[-1]
        sgg_code = SGG_NAME_TO_CODE.get(sgg_name)
        if not sgg_code:
            # also try with prefix variants
            for k, v in SGG_NAME_TO_CODE.items():
                if k == sgg_name or k.endswith(sgg_name):
                    sgg_code = v
                    break
        if not sgg_code:
            continue
        sido_cd = sgg_code[:2]
        try:
            rows = search_employee(client, sido_cd, sgg_code, t["representative_name"])
        except Exception as e:
            if i <= 5:
                print(f"  err {t['realtor_id']}: {e}", flush=True)
            continue
        # status가 '영업'이 아닌 행 찾기
        suspended = [r for r in rows if r["status"] != "영업"]
        if suspended:
            for s in suspended:
                found.append({
                    "naver": {
                        "realtor_id": t["realtor_id"], "name": t["naver_name"],
                        "rep": t["representative_name"], "listings": t["total_listings"],
                        "regno": t["establish_registration_no"], "addr": t["address"],
                    },
                    "vworld_suspended": s,
                })
                print(f"  ✓ {t['realtor_id']} {t['naver_name']}  → {s['business_name']} ({s['status_title']})", flush=True)
        if i % 20 == 0:
            print(f"  [{i}/{len(targets)}]  found={len(found)}  ({(time.time()-started):.0f}s)", flush=True)
        time.sleep(0.3)

    out_path = Path("D:/auto/naverreal/suspended_brokers.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(found, f, ensure_ascii=False, indent=2)
    print(f"\nfound: {len(found)}  saved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
