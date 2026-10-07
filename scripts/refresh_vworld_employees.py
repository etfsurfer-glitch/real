# -*- coding: utf-8 -*-
"""vworld 소속직원 명단 전수 재크롤 + 퇴사자 정리.

왜 필요한가 (2026-10-01 민원)
  vworld_employees 는 2026-05 수집분에서 멈춰 있었다. 월간 갱신(vworld_refresh_monthly.sh)
  은 `--list`(사무소 목록)만 돌고 직원 크롤이 빠져 있었다.

  더 큰 문제는 upsert 전용이라는 것이다. crawl_vworld_brokers.upsert_employee 는
  ON CONFLICT ... DO UPDATE 만 하고 DELETE 를 하지 않는다. vworld 는 현직만 반환하므로
  (전 행이 status='영업') 퇴사자는 소스에서 사라질 뿐인데, 우리 테이블에는 영구히 남는다.
  → "소속직원 명단이 안 맞다"는 민원의 직접 원인.

동작
  ① 시작 시각 기록 → ② 전수 크롤(--skip-done 쓰지 않음. 기존 행은 fetched_at 갱신)
  ③ 이번 실행에서 새로 받은 행이 있는 시군구에 한해, 갱신되지 않은 묵은 행을 삭제

안전장치
  · 크롤이 실패해 0행인 시군구는 건드리지 않는다(통째로 지워지는 사고 방지).
  · 어떤 시군구든 삭제 비율이 PURGE_MAX_RATIO 를 넘으면 그 시군구는 건너뛰고 경고한다
    (소스 장애로 일부만 내려온 경우 대량 삭제 방지).
  · --dry-run 으로 삭제 예정만 볼 수 있다.
"""
import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path("/opt/koczip")
DB = ROOT / "data/naverreal.sqlite"
PY = ROOT / ".venv/bin/python"
PURGE_MAX_RATIO = 0.5      # 한 시군구에서 절반 넘게 사라지면 비정상으로 보고 보류


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--sido", help="시도코드 2자리. 생략 시 전국")
    ap.add_argument("--dry-run", action="store_true", help="크롤만 하고 삭제는 안 함")
    ap.add_argument("--skip-crawl", action="store_true", help="크롤 없이 정리만")
    ap.add_argument("--since", help="정리 기준 시각(ISO). --skip-crawl 로 이전 크롤분을 정리할 때 "
                                    "그 크롤의 시작 시각을 준다. 생략하면 현재 시각(=아무것도 안 지워짐)")
    a = ap.parse_args()

    started = a.since or datetime.now().isoformat(timespec="seconds")
    if a.since:
        print("[*] 정리 기준 시각(지정): %s" % started, flush=True)
    else:
        print("[*] 시작 %s" % started, flush=True)

    if not a.skip_crawl:
        cmd = [str(PY), "-u", "scripts/crawl_vworld_brokers.py", "--employees",
               "--parallel", str(a.parallel)]
        if a.sido:
            cmd += ["--sido", a.sido]
        print("[*] 크롤: %s" % " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
        print("[*] 크롤 exit=%d" % rc, flush=True)
        if rc != 0:
            print("[!] 크롤 실패 — 정리 단계를 건너뛴다(묵은 데이터 유지가 안전)")
            return rc

    con = sqlite3.connect(str(DB), timeout=600)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")

    rows = con.execute(
        "SELECT sgg_cd, "
        "       SUM(CASE WHEN fetched_at >= ? THEN 1 ELSE 0 END) fresh, "
        "       SUM(CASE WHEN fetched_at <  ? THEN 1 ELSE 0 END) stale "
        "FROM vworld_employees GROUP BY sgg_cd", (started, started)).fetchall()

    tot_fresh = sum(r["fresh"] for r in rows)
    tot_stale = sum(r["stale"] for r in rows)
    print("\n[*] 갱신 %s행 · 미갱신 %s행 · 시군구 %d개"
          % (format(tot_fresh, ","), format(tot_stale, ","), len(rows)), flush=True)

    purge, held, untouched = [], [], []
    for r in rows:
        if r["fresh"] == 0:
            untouched.append(r["sgg_cd"])          # 크롤 실패 — 손대지 않음
            continue
        if r["stale"] == 0:
            continue
        ratio = r["stale"] / (r["fresh"] + r["stale"])
        (held if ratio > PURGE_MAX_RATIO else purge).append((r["sgg_cd"], r["stale"], ratio))

    if untouched:
        print("[!] 크롤 결과 0행이라 건드리지 않은 시군구 %d개: %s"
              % (len(untouched), ", ".join(untouched[:10])), flush=True)
    for sgg, n, ratio in held:
        print("[!] 삭제 보류 %s — 묵은행 %s (%.0f%%, 기준 %.0f%% 초과)"
              % (sgg, format(n, ","), ratio * 100, PURGE_MAX_RATIO * 100), flush=True)

    n_del = sum(n for _, n, _ in purge)
    print("\n[*] 삭제 대상: %s행 / %d개 시군구" % (format(n_del, ","), len(purge)), flush=True)
    if a.dry_run:
        print("(dry-run — 삭제하지 않음)")
        return 0

    for sgg, _, _ in purge:
        con.execute("DELETE FROM vworld_employees WHERE sgg_cd=? AND fetched_at < ?",
                    (sgg, started))
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    after = con.execute("SELECT COUNT(*) n, COUNT(DISTINCT sys_regno) o FROM vworld_employees").fetchone()
    print("[*] 정리 후: 직원 %s행 · 사무소 %s곳"
          % (format(after["n"], ","), format(after["o"], ",")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
