#!/usr/bin/env python3
"""중개사 매칭 잠금 — 손으로 바로잡은 매칭을 배치가 덮지 못하게 고정한다.

매칭 배치(match_clean.py)는 매일 realtor_match 를 통째로 지우고 다시 만든다.
여기에 적어 두지 않은 수동 교정은 다음 실행에서 사라진다.

  목록      python3 scripts/realtor_match_lock.py list
  잠금      python3 scripts/realtor_match_lock.py set <realtor_id> <sys_regno> --reason "사유" [--by 이름]
  매칭없음  python3 scripts/realtor_match_lock.py set <realtor_id> none --reason "사유"
  해제      python3 scripts/realtor_match_lock.py unset <realtor_id>
  점검      python3 scripts/realtor_match_lock.py check      # 잠금과 현재 상태가 어긋나는지
  적용      python3 scripts/realtor_match_lock.py apply      # 지금 바로 반영
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import (  # noqa: E402
    apply_match_locks,
    ensure_match_lock_table,
)


def db() -> sqlite3.Connection:
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    ensure_match_lock_table(c)
    return c


def cmd_list(c, _a) -> int:
    rows = c.execute(
        "SELECT l.*, m.naver_name, m.primary_sgg_cd, m.total_listings, v.business_name, v.representative, v.sgg_cd "
        "FROM realtor_match_lock l "
        "LEFT JOIN realtor_match m ON m.realtor_id=l.realtor_id "
        "LEFT JOIN vworld_brokers v ON v.sys_regno=l.sys_regno ORDER BY l.locked_at DESC"
    ).fetchall()
    if not rows:
        print("잠금 없음")
        return 0
    print("%-20s %-16s %-26s %-22s %-8s %s" % ("realtor_id", "sys_regno", "네이버 상호", "사무소", "매물", "사유"))
    for r in rows:
        print("%-20s %-16s %-26s %-22s %-8s %s" % (
            r["realtor_id"][:20], r["sys_regno"] or "(매칭없음)",
            (r["naver_name"] or "")[:26], (r["business_name"] or "")[:22],
            r["total_listings"] if r["total_listings"] is not None else "-", r["reason"] or ""))
    print("\n총 %d건" % len(rows))
    return 0


def cmd_set(c, a) -> int:
    rid = a.realtor_id
    sr = "" if a.sys_regno.lower() in ("none", "null", "-", "매칭없음") else a.sys_regno.strip()
    if sr:
        v = c.execute(
            "SELECT business_name, representative, sgg_cd FROM vworld_brokers WHERE sys_regno=?", (sr,)
        ).fetchone()
        if not v:
            print("!! vworld에 없는 sys_regno: %s" % sr)
            return 2
    nr = c.execute(
        "SELECT realtor_name, representative_name, address FROM naver_realtors WHERE realtor_id=?", (rid,)
    ).fetchone()
    if not nr:
        print("!! naver_realtors에 없는 realtor_id: %s" % rid)
        return 2
    now = datetime.now().isoformat(timespec="seconds")
    c.execute(
        "INSERT INTO realtor_match_lock(realtor_id, sys_regno, match_type, reason, locked_by, locked_at) "
        "VALUES(?,?,?,?,?,?) ON CONFLICT(realtor_id) DO UPDATE SET "
        "sys_regno=excluded.sys_regno, match_type=excluded.match_type, reason=excluded.reason, "
        "locked_by=excluded.locked_by, locked_at=excluded.locked_at",
        (rid, sr or None, "manual" if sr else "manual_none", a.reason, a.by, now))
    c.commit()
    print("잠금: %s (%s) → %s" % (rid, nr["realtor_name"], ("%s %s(%s)" % (sr, v["business_name"], v["representative"])) if sr else "매칭없음"))
    apply_match_locks(c)
    return 0


def cmd_unset(c, a) -> int:
    n = c.execute("DELETE FROM realtor_match_lock WHERE realtor_id=?", (a.realtor_id,)).rowcount
    c.commit()
    print("해제 %d건 — 다음 매칭 배치부터 자동 매칭으로 돌아간다" % n)
    return 0


def cmd_apply(c, _a) -> int:
    apply_match_locks(c)
    return 0


def cmd_check(c, _a) -> int:
    """잠금과 현재 매칭/활동지역이 어긋나는지 본다. 계정이 다른 사무소로 이사한 경우를 잡는다."""
    rows = c.execute(
        "SELECT l.realtor_id, l.sys_regno, l.reason, m.sys_regno cur, m.primary_sgg_cd pc, "
        "       m.naver_name, m.total_listings li, v.sgg_cd vc, v.business_name, v.representative vrep, "
        "       n.representative_name nrep "
        "FROM realtor_match_lock l "
        "LEFT JOIN realtor_match m ON m.realtor_id=l.realtor_id "
        "LEFT JOIN vworld_brokers v ON v.sys_regno=l.sys_regno "
        "LEFT JOIN naver_realtors n ON n.realtor_id=l.realtor_id"
    ).fetchall()
    bad = 0
    for r in rows:
        w = []
        if (r["cur"] or "") != (r["sys_regno"] or ""):
            w.append("현재 매칭이 잠금과 다름(%s)" % (r["cur"] or "없음"))
        if r["pc"] and r["vc"] and str(r["pc"]) != str(r["vc"]):
            w.append("활동 시군구 %s ≠ 사무소 %s — 계정이 이사했을 수 있음" % (r["pc"], r["vc"]))
        if r["nrep"] and r["vrep"] and r["nrep"].replace(" ", "") != r["vrep"].replace(" ", ""):
            w.append("대표 네이버[%s] vs vworld[%s]" % (r["nrep"], r["vrep"]))
        if w:
            bad += 1
            print("  ! %-18s %-24s 매물%-5s %s" % (r["realtor_id"][:18], (r["naver_name"] or "")[:24],
                                                  r["li"], " / ".join(w)))
    print("잠금 %d건 중 확인 필요 %d건" % (len(rows), bad))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("set")
    s.add_argument("realtor_id"); s.add_argument("sys_regno")
    s.add_argument("--reason", default=""); s.add_argument("--by", default="admin")
    u = sub.add_parser("unset"); u.add_argument("realtor_id")
    sub.add_parser("apply")
    sub.add_parser("check")
    a = ap.parse_args()
    c = db()
    try:
        return {"list": cmd_list, "set": cmd_set, "unset": cmd_unset,
                "apply": cmd_apply, "check": cmd_check}[a.cmd](c, a)
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
