# -*- coding: utf-8 -*-
"""활동로그 90일 비식별화 — 개인정보처리방침(접속기록 3개월) 이행.

원칙: '집계를 먼저 굳히고, 그 다음 지운다'.
1) 확정일(KST 그저께까지)의 일별 통계를 daily_stats / daily_page_stats 에 적재(멱등).
2) 90일 지난 event_log 행에서 식별정보만 NULL 처리(탈퇴 비식별화와 동일 열:
   user_id·member_no·email·ip·user_agent·detail). ts·kind·path·query·ref 등
   익명 행동 데이터는 유지 — 통계·트렌드는 계속 산출 가능.
   해당 날짜 집계가 굳어 있지 않으면 그 날짜는 건드리지 않는다(순서 보장).

Run(박스): cd /opt/koczip && .venv/bin/python scripts/log_anonymize.py [--dry]
Cron: 매일 08:10.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "/opt/koczip")
os.chdir("/opt/koczip")

LOGS_DB = Path(os.getenv("LOGS_DB_PATH", "/opt/koczip/data/logs.sqlite"))
RETENTION_DAYS = 90
# 개인정보취급자(관리자)의 개인정보처리시스템 접속기록은 안전성 확보조치 고시상 1년 이상 보관.
ADMIN_RETENTION_DAYS = 365
# 관리자 접속기록 식별 조건 — 관리 행위(kind='admin') + 관리자 콘솔 접근(/admin/*)
_ADMIN_COND = "(kind='admin' OR path LIKE '/admin/%')"
ID_COLS = "user_id=NULL, member_no=NULL, email=NULL, ip=NULL, user_agent=NULL, detail=NULL"
CHUNK = 50_000


def _open() -> sqlite3.Connection:
    c = sqlite3.connect(LOGS_DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA journal_size_limit=268435456")
    return c


def materialize(c: sqlite3.Connection, dry: bool) -> int:
    """확정일(KST 그저께 이하) 중 아직 없는 날짜의 집계를 굳힌다. 반환=신규 적재 일수."""
    c.execute("""CREATE TABLE IF NOT EXISTS daily_stats(
        d TEXT PRIMARY KEY, events INTEGER, visitors INTEGER, login_users INTEGER,
        logins INTEGER, pageviews INTEGER, ai_asks INTEGER, complex_views INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_page_stats(
        d TEXT, label TEXT, views INTEGER, visitors INTEGER, PRIMARY KEY(d, label))""")
    done = {r[0] for r in c.execute("SELECT d FROM daily_stats")}
    days = [r[0] for r in c.execute(
        "SELECT DISTINCT date(ts,'+9 hours') FROM event_log "
        "WHERE date(ts,'+9 hours') <= date('now','+9 hours','-2 days') ORDER BY 1")]
    todo = [d for d in days if d not in done]
    if dry or not todo:
        return len(todo)
    from scripts.local_api import _page_label   # top-pages와 동일 라벨링
    for d in todo:
        row = c.execute(
            "SELECT COUNT(*), COUNT(DISTINCT ip), COUNT(DISTINCT user_id), "
            "SUM(kind='login'), "
            "SUM(kind IN ('view','view_complex','view_realtor')), "
            "SUM(kind LIKE 'ai%'), SUM(kind='view_complex') "
            "FROM event_log WHERE date(ts,'+9 hours')=?", (d,)).fetchone()
        c.execute("INSERT OR REPLACE INTO daily_stats VALUES (?,?,?,?,?,?,?,?)",
                  (d, row[0], row[1], row[2], row[3] or 0, row[4] or 0, row[5] or 0, row[6] or 0))
        agg: dict = {}
        for p, n, v in c.execute(
            "SELECT path, COUNT(*), COUNT(DISTINCT ip) FROM event_log "
            "WHERE date(ts,'+9 hours')=? AND kind IN ('view','view_complex','view_realtor') "
            "AND path LIKE '/%' GROUP BY path", (d,)):
            lbl = _page_label(p)
            if lbl == p:   # 알려진 페이지가 아님(API·봇) — top-pages와 동일하게 제외
                continue
            a = agg.setdefault(lbl, [0, 0])
            a[0] += n
            a[1] += v
        c.executemany("INSERT OR REPLACE INTO daily_page_stats VALUES (?,?,?,?)",
                      [(d, k, x[0], x[1]) for k, x in agg.items()])
        c.commit()
    return len(todo)


def _anonymize_pass(c, cutoff: str, admin: bool, dry: bool) -> int:
    """cutoff 이전 행의 식별정보 NULL 처리(집계 굳은 날짜만).
    admin=True → 관리자 접속기록만(1년 보관 후), False → 일반 로그(관리자 제외, 90일)."""
    scope = _ADMIN_COND if admin else f"NOT {_ADMIN_COND}"
    id_cond = ("(ip IS NOT NULL OR user_agent IS NOT NULL OR user_id IS NOT NULL "
               "OR email IS NOT NULL OR member_no IS NOT NULL OR detail IS NOT NULL)")
    pending = c.execute(
        f"SELECT COUNT(*) FROM event_log WHERE ts < ? AND {scope} AND {id_cond} "
        "AND date(ts,'+9 hours') IN (SELECT d FROM daily_stats)", (cutoff,)).fetchone()[0]
    if dry or not pending:
        return pending
    total = 0
    while True:
        cur = c.execute(
            f"UPDATE event_log SET {ID_COLS} WHERE rowid IN ("
            f"  SELECT rowid FROM event_log WHERE ts < ? AND {scope} AND {id_cond} "
            "  AND date(ts,'+9 hours') IN (SELECT d FROM daily_stats) LIMIT ?)",
            (cutoff, CHUNK))
        c.commit()
        total += cur.rowcount
        if cur.rowcount < CHUNK:
            break
    return total


def anonymize(c: sqlite3.Connection, dry: bool) -> tuple:
    """일반 로그 90일 + 관리자 접속기록 365일 비식별화. 반환=(일반, 관리자) 처리 행수."""
    cut90 = c.execute(f"SELECT datetime('now','-{RETENTION_DAYS} days')").fetchone()[0]
    cut365 = c.execute(f"SELECT datetime('now','-{ADMIN_RETENTION_DAYS} days')").fetchone()[0]
    n_user = _anonymize_pass(c, cut90, admin=False, dry=dry)
    n_admin = _anonymize_pass(c, cut365, admin=True, dry=dry)
    return n_user, n_admin


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    c = _open()
    try:
        n_days = materialize(c, args.dry)
        n_user, n_admin = anonymize(c, args.dry)
    finally:
        c.close()
    tag = "[dry] " if args.dry else ""
    print(f"{tag}집계 굳힘 {n_days}일 · 일반 비식별화 {n_user:,}행(90일) · 관리자 접속기록 비식별화 {n_admin:,}행(365일)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
