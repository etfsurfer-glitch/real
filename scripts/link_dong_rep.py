# -*- coding: utf-8 -*-
"""법정동 + 대표자명 유일일치로 미연결 중개사를 vworld 에 연결한다.

왜 필요한가
  신축 단지 내 상가에 입점한 신규 사무소는 네이버에 등록번호가 비어 있고
  (2026-10-01 기준 미연결 61곳 중 54곳), 사무소명도
  '곰단지내02-522-4145부동산중개디에이치방배' 처럼 단지명·전화를 붙여 지어서
  vworld 공식 등록명과 아예 다르다. 등록번호·이름 매칭이 구조적으로 안 된다.
  기존 step4_addr_rep 은 _addr_key 가 도로명(로/길) 패턴을 요구하는데, 이 사무소들의
  네이버 주소는 지번주소('서초구 방배동 946-8')라 vworld 도로명 주소와 만나지 못한다.

안전장치 (오귀속 0 원칙)
  ① 같은 시군구 ② 같은 대표자명 ③ 폐업 제외
  ④ **네이버 주소 문자열**과 **vworld 주소 문자열**에 같은 법정동명이 들어 있을 것
  ⑤ 그 조합이 vworld 에서 유일
  ⑥ 상호명 부분일치 — 일반어(공인중개사·부동산·사무소…)를 걷어낸 핵심어가 2자 이상 겹칠 것

  ⑥ 이 없으면 읍·면·대동처럼 넓은 구역에서 동명이인이 그대로 붙는다.
  실제로 '엄지부동산(배방읍) → 탕정단지내대박(배방읍)', '부여(염리동) → 행운(염리동)'
  같은 전혀 다른 사무소가 잡혔다.

  대표자명+시군구만으로는 절반이 오귀속이었다. 중개사가 사무소를 옮긴 경우가 잦다.
  주의: naver_realtors.cortar_no 는 옛 등록지가 남아 있는 경우가 있어 단독으로 쓰면 안 된다.
  이민재 — 주소는 '평택시 고덕동 2619-1'인데 cortar_no 는 장안동을 가리켜, 코드만 믿으면
  이전 전 사무소(브레인최고)에 붙는다. 그래서 **양쪽 주소 원문**에서 동명을 확인한다.

사용
  python scripts/link_dong_rep.py           # dry-run, 아무것도 쓰지 않음
  python scripts/link_dong_rep.py --apply   # 적용
"""
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from collector.realtor_matching import apply_match_locks  # noqa: E402

DB = "/opt/koczip/data/naverreal.sqlite"
APPLY = "--apply" in sys.argv
MIN_N = 1          # 매물 수 하한. 알림 지표는 20+ 기준이나 연결 자체는 전부 해준다.

SQL = """
WITH t AS (SELECT realtor_id, COUNT(*) n FROM listings_current
           WHERE realtor_id IS NOT NULL AND realtor_id <> '' GROUP BY realtor_id HAVING n >= ?),
     u AS (SELECT t.realtor_id, t.n, nr.realtor_name, nr.representative_name rep,
                  substr(nr.cortar_no,1,5) sgg5, nr.address naddr,
                  (SELECT umd_nm FROM bjd WHERE code10 = nr.cortar_no) dong
           FROM t
           LEFT JOIN realtor_match m ON m.realtor_id = t.realtor_id AND m.sys_regno IS NOT NULL
           LEFT JOIN naver_realtors nr ON nr.realtor_id = t.realtor_id
           WHERE m.realtor_id IS NULL
             AND nr.representative_name IS NOT NULL AND nr.representative_name <> ''
             AND nr.cortar_no IS NOT NULL AND nr.address IS NOT NULL)
SELECT u.realtor_id, u.n, u.realtor_name, u.rep, u.dong,
       v.sys_regno, v.business_name, v.address vaddr, v.status vstatus
FROM u
JOIN vworld_brokers v
  ON v.sgg_cd = u.sgg5 AND v.representative = u.rep
 AND COALESCE(v.status,'') NOT LIKE '%폐업%'
WHERE u.dong IS NOT NULL
  AND u.naddr LIKE '%' || u.dong || '%'          -- 네이버 주소 원문에도 그 동이 있어야(코드 노후 방지)
  AND v.address LIKE '%' || u.dong || '%'        -- vworld 주소 원문에도 같은 동
  AND 1 = (SELECT COUNT(*) FROM vworld_brokers v2
           WHERE v2.sgg_cd = u.sgg5 AND v2.representative = u.rep
             AND COALESCE(v2.status,'') NOT LIKE '%폐업%'
             AND v2.address LIKE '%' || u.dong || '%')
ORDER BY u.n DESC
"""


# 상호에서 업종 일반어를 걷어내고 남는 핵심어. 이게 겹쳐야 같은 사무소로 본다.
_GENERIC = re.compile(
    r"공인중개사사무소|공인중개사무소|공인중개사|공인중개|중개사사무소|중개인사무소|"
    r"중개사무소|중개법인|부동산중개|부동산|중개사|사무소|주식회사|\(주\)")
_NONWORD = re.compile(r"[^0-9A-Za-z가-힣]")


def core_name(s: str) -> str:
    return _NONWORD.sub("", _GENERIC.sub("", s or "")).lower()


def name_ok(a: str, b: str) -> bool:
    """핵심어가 2자 이상 한쪽에 포함되면 동일 사무소로 인정."""
    ca, cb = core_name(a), core_name(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    short, long_ = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    return len(short) >= 2 and short in long_


def main():
    uri = "file:%s?mode=ro" % DB
    con = sqlite3.connect(uri if not APPLY else DB, uri=not APPLY, timeout=120)
    con.row_factory = sqlite3.Row
    raw = con.execute(SQL, (MIN_N,)).fetchall()
    rows = [r for r in raw if name_ok(r["realtor_name"], r["business_name"])]
    dropped = [r for r in raw if r not in rows]

    print("후보 %d곳 → 상호 핵심어 불일치 %d곳 제외 → 연결 대상 %d곳\n"
          % (len(raw), len(dropped), len(rows)), flush=True)
    if dropped:
        print("  [제외]")
        for r in dropped:
            print("    %-30s %-4s %-9s ✗ %-30s"
                  % ((r["realtor_name"] or "")[:30], r["rep"], r["dong"],
                     (r["business_name"] or "")[:30]), flush=True)
        print()
    for r in rows:
        print("  매물%-5s %-30s %-4s %-9s → %-30s %s"
              % (r["n"], (r["realtor_name"] or "")[:30], r["rep"], r["dong"],
                 (r["business_name"] or "")[:30], r["sys_regno"]), flush=True)

    if not APPLY:
        print("\n(dry-run — 아무것도 쓰지 않았습니다. 적용하려면 --apply)")
        return 0

    now = datetime.now().isoformat(timespec="seconds")
    for r in rows:
        con.execute(
            "INSERT INTO realtor_match(realtor_id, sys_regno, vworld_name, vworld_rep, "
            "                          match_type, matched_at, vworld_status) "
            "VALUES (?,?,?,?,'dong_rep',?,?) "
            "ON CONFLICT(realtor_id) DO UPDATE SET "
            "  sys_regno=excluded.sys_regno, vworld_name=excluded.vworld_name, "
            "  vworld_rep=excluded.vworld_rep, match_type=excluded.match_type, "
            "  matched_at=excluded.matched_at, vworld_status=excluded.vworld_status",
            (r["realtor_id"], r["sys_regno"], r["business_name"], r["rep"], now, r["vstatus"]))
    con.commit()
    print("\n적용 %d곳 (match_type=dong_rep)" % len(rows))
    # 관리자 수동 교정(realtor_match_lock)을 마지막에 되살린다.
    apply_match_locks(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
