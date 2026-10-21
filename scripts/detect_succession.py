#!/usr/bin/env python3
"""사무소 승계 탐지 — 같은 자리에 새 등록번호가 생겼는데 계정이 옛 번호에 붙어 있는 경우.

중개사무소는 대표가 바뀌면 같은 자리·같은 상호라도 '새 등록번호'로 다시 등록된다.
우리 vworld 적재분에는 폐업 상태가 없어서 옛 번호가 영원히 '영업'으로 남고,
네이버 계정은 옛 번호에 붙은 채 굳는다. 매칭이 조용히 틀어지는 가장 흔한 경로다.

같은 건물 + 같은 상호 핵심어 + 더 늦은 등록일 로 후보를 잡고,
네이버 계정의 대표자명이 '누구와 같은지' 로 성격을 가른다.

  A 승계   계정 대표 = 새 사무소 대표  → 계정을 새 번호로 옮기면 된다
  B 이사   계정 대표 = 옛 사무소 대표 '이면서' 활동 지역이 그 자리를 떠났다
           → 계정 주인이 딴 데로 갔다. 새 번호엔 다른 계정이 와야 한다
  C 보류   둘 다 아님 / 대표 정보 없음

대표가 옛 사무소와 같고 활동 지역도 그대로면 승계가 아니다. 같은 건물에 비슷한
상호의 다른 사무소가 생긴 것뿐이고 현재 매칭이 맞다 — 후보에서 뺀다.

주소는 '건물'까지만 보고 호실은 보조 신호로 쓴다. 상호는 괄호 안 전화번호와
업종 접미어를 떼고 비교한다. (새봄(02-823-3060)공인중개사사무소 ↔ 새봄공인중개사사무소)

  점검   python3 scripts/detect_succession.py
  저장   python3 scripts/detect_succession.py --save      # review 테이블에 기록
  적용   python3 scripts/detect_succession.py --apply     # A등급만 매칭 잠금으로 고정
"""
from __future__ import annotations

import argparse
import collections
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import ensure_match_lock_table  # noqa: E402

SUFFIX = ("공인중개사사무소", "공인중개사무소", "부동산중개사무소", "부동산공인중개사사무소",
          "공인중개사", "부동산중개법인", "부동산중개", "중개사무소", "중개법인",
          "사무소", "부동산", "중개")


def biz_key(name: str | None) -> str:
    """상호 핵심어. 괄호(전화번호)·숫자·구두점·업종 접미어를 뗀다."""
    s = re.sub(r"\([^)]*\)", "", name or "")
    s = re.sub(r"[0-9\-\s,.·()]", "", s)
    for _ in range(3):              # '…부동산공인중개사사무소' 처럼 접미어가 겹쳐 붙는다
        for suf in SUFFIX:
            if s.endswith(suf) and len(s) > len(suf):
                s = s[: -len(suf)]
                break
        else:
            break
    return s


def bldg_key(addr: str | None) -> str:
    """건물까지만. '…로 91 상가동 지하1층 비103-2호' 와 '…로 91 … 103-2호(흑석동)' 를 같게 본다."""
    a = re.sub(r"\([^)]*\)", " ", addr or "")
    a = re.sub(r"\s+", " ", a).strip()
    m = re.search(r"^(.*?(?:로|길)\s*\d+(?:-\d+)?)(?!\d)", a)
    if m:
        return re.sub(r"\s", "", m.group(1))
    m = re.search(r"^(.*?[동리]\s*\d+(?:-\d+)?)(?!\d)", a)
    return re.sub(r"\s", "", m.group(1)) if m else re.sub(r"\s", "", a)[:24]


def unit_key(addr: str | None) -> str:
    """호실 번호. 'B103-2호' '비103-2호' '103-2호' 를 같게 본다."""
    m = re.findall(r"(?:비|[Bb])?(\d+(?:-\d+)?)\s*호", addr or "")
    return m[-1] if m else ""


def rep_key(name: str | None) -> str:
    s = re.sub(r"\s", "", (name or "")).upper()
    return s


def rep_same(a: str | None, b: str | None) -> bool:
    """대표자 동일 판정. 로마자 이름은 줄임형(CHOI GRACE)과 전체형(CHOI GRACE CHRISTINA …)을 같게 본다."""
    x, y = rep_key(a), rep_key(b)
    if not x or not y:
        return False
    if x == y:
        return True
    if re.search(r"[A-Z]", x) and re.search(r"[A-Z]", y):
        return x.startswith(y) or y.startswith(x)
    return False


def open_db(ro: bool = True) -> sqlite3.Connection:
    uri = "file:%s%s" % (settings.local_db_path, "?mode=ro" if ro else "")
    c = sqlite3.connect(uri, uri=True, timeout=30.0)
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    return c


def find_candidates(c: sqlite3.Connection) -> list[dict]:
    brokers = c.execute(
        "SELECT sys_regno, ra_regno, business_name, representative, address, registered_ymd, sgg_cd "
        "FROM vworld_brokers"
    ).fetchall()
    groups: dict[tuple[str, str], list] = collections.defaultdict(list)
    for b in brokers:
        bk, nk = bldg_key(b["address"]), biz_key(b["business_name"])
        if len(bk) < 8 or len(nk) < 2:
            continue
        groups[(bk, nk)].append(b)

    # 계정이 붙어 있는 사무소
    att: dict[str, list] = collections.defaultdict(list)
    for r in c.execute(
        "SELECT m.sys_regno, m.realtor_id, m.naver_name, m.total_listings, m.primary_sgg_cd, "
        "       m.match_type, n.representative_name nrep, n.establish_registration_no nregno "
        "FROM realtor_match m LEFT JOIN naver_realtors n ON n.realtor_id=m.realtor_id "
        "WHERE m.sys_regno IS NOT NULL AND m.sys_regno<>''"
    ):
        att[r["sys_regno"]].append(r)

    locked = {r[0] for r in c.execute("SELECT realtor_id FROM realtor_match_lock")} \
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='realtor_match_lock'").fetchone() else set()

    out = []
    for (bk, nk), g in groups.items():
        if len(g) < 2:
            continue
        g = sorted(g, key=lambda b: (b["registered_ymd"] or ""))
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                old, new = g[i], g[j]
                if (old["registered_ymd"] or "") >= (new["registered_ymd"] or ""):
                    continue
                accs = att.get(old["sys_regno"], [])
                if not accs or att.get(new["sys_regno"]):
                    continue              # 옛쪽에만 계정이 있고 새쪽은 비어 있어야 후보
                same_unit = unit_key(old["address"]) and unit_key(old["address"]) == unit_key(new["address"])
                for a in accs:
                    if a["realtor_id"] in locked:
                        continue
                    moved = bool(a["primary_sgg_cd"] and old["sgg_cd"]
                                 and str(a["primary_sgg_cd"]) != str(old["sgg_cd"]))
                    if rep_same(a["nrep"], new["representative"]):
                        grade, why = "A", "계정 대표 = 새 사무소 대표"
                    elif rep_same(a["nrep"], old["representative"]):
                        if not moved:
                            continue      # 옛 사무소에 그대로 있다 — 승계 아님, 현재 매칭이 맞다
                        grade, why = "B", "계정 대표 = 옛 사무소 대표인데 활동 지역이 떠남"
                    else:
                        grade, why = "C", "대표 불일치/불명"
                    out.append(dict(
                        grade=grade, why=why, same_unit=bool(same_unit),
                        realtor_id=a["realtor_id"], naver_name=a["naver_name"],
                        nrep=a["nrep"], nregno=a["nregno"], listings=a["total_listings"] or 0,
                        match_type=a["match_type"], primary_sgg=a["primary_sgg_cd"],
                        old_regno=old["sys_regno"], old_name=old["business_name"],
                        old_rep=old["representative"], old_ymd=(old["registered_ymd"] or "")[:10],
                        new_regno=new["sys_regno"], new_name=new["business_name"],
                        new_rep=new["representative"], new_ymd=(new["registered_ymd"] or "")[:10],
                        new_sgg=new["sgg_cd"], bldg=bk, biz=nk))
    out.sort(key=lambda r: ({"A": 0, "B": 1, "C": 2}[r["grade"]], -r["listings"]))
    return out


REVIEW_DDL = """
CREATE TABLE IF NOT EXISTS realtor_succession_review(
    realtor_id TEXT, old_regno TEXT, new_regno TEXT, grade TEXT, why TEXT,
    naver_name TEXT, nrep TEXT, listings INTEGER, same_unit INTEGER,
    old_name TEXT, old_rep TEXT, old_ymd TEXT,
    new_name TEXT, new_rep TEXT, new_ymd TEXT,
    detected_at TEXT, status TEXT DEFAULT 'open',
    PRIMARY KEY(realtor_id, new_regno)
)
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", action="store_true", help="review 테이블에 기록")
    ap.add_argument("--apply", action="store_true", help="A등급을 매칭 잠금으로 고정(--save 포함)")
    ap.add_argument("--limit", type=int, default=25, help="화면 출력 개수")
    a = ap.parse_args()

    c = open_db(ro=not (a.save or a.apply))
    rows = find_candidates(c)
    byg = collections.Counter(r["grade"] for r in rows)
    print("승계 후보 %d건 — A 승계 %d · B 계정이사 %d · C 보류 %d"
          % (len(rows), byg["A"], byg["B"], byg["C"]))
    print("  걸린 매물: %s건" % f'{sum(r["listings"] for r in rows):,}')
    for g, label in (("A", "승계 — 계정을 새 등록번호로 옮기면 된다"),
                     ("B", "계정 이사 — 계정 주인이 딴 곳으로 갔다"),
                     ("C", "보류 — 대표 정보로 가릴 수 없음")):
        sel = [r for r in rows if r["grade"] == g]
        if not sel:
            continue
        print("\n[%s] %s — %d건 (매물 %s)" % (g, label, len(sel), f'{sum(x["listings"] for x in sel):,}'))
        for r in sel[: a.limit]:
            print("   %-18s %-24s 매물%-5s %s"
                  % (r["realtor_id"][:18], (r["naver_name"] or "")[:24], r["listings"],
                     "호실일치" if r["same_unit"] else ""))
            print("      옛 %s %-22s %s (%s)" % (r["old_regno"], (r["old_name"] or "")[:22], r["old_rep"], r["old_ymd"]))
            print("      새 %s %-22s %s (%s)  계정대표[%s]"
                  % (r["new_regno"], (r["new_name"] or "")[:22], r["new_rep"], r["new_ymd"], r["nrep"]))
        if len(sel) > a.limit:
            print("   … 외 %d건" % (len(sel) - a.limit))

    if a.save or a.apply:
        c.execute(REVIEW_DDL)
        now = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            c.execute(
                "INSERT INTO realtor_succession_review(realtor_id, old_regno, new_regno, grade, why, "
                " naver_name, nrep, listings, same_unit, old_name, old_rep, old_ymd, new_name, new_rep, new_ymd, detected_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(realtor_id,new_regno) DO UPDATE SET grade=excluded.grade, why=excluded.why, "
                " listings=excluded.listings, detected_at=excluded.detected_at",
                (r["realtor_id"], r["old_regno"], r["new_regno"], r["grade"], r["why"],
                 r["naver_name"], r["nrep"], r["listings"], int(r["same_unit"]),
                 r["old_name"], r["old_rep"], r["old_ymd"], r["new_name"], r["new_rep"], r["new_ymd"], now))
        c.commit()
        print("\n[*] review 테이블 기록 %d건" % len(rows))

    if a.apply:
        ensure_match_lock_table(c)
        n = 0
        for r in [x for x in rows if x["grade"] == "A"]:
            c.execute(
                "INSERT INTO realtor_match_lock(realtor_id, sys_regno, match_type, reason, locked_by, locked_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(realtor_id) DO NOTHING",
                (r["realtor_id"], r["new_regno"], "manual",
                 "승계 탐지: %s(%s) → %s(%s), 같은 자리 신규 등록번호"
                 % (r["old_name"], r["old_rep"], r["new_name"], r["new_rep"]),
                 "detect_succession", datetime.now().isoformat(timespec="seconds")))
            n += c.total_changes and 1 or 0
        c.commit()
        from collector.realtor_matching import apply_match_locks
        apply_match_locks(c)
        print("[*] A등급 잠금 생성 완료")
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
