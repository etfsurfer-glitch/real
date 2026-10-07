"""아카이브 통합 조회 — 운영(핫) + 아카이브(과거)를 한 번에 보는 분석 전용 경로.

배경
  2026-09-25 계층화로 오래된 파티션이 /mnt/backup/archive.sqlite 로 옮겨졌다.
  라이브 API 는 최근 데이터만 보므로 아카이브가 필요 없다(코드 전수확인 완료).
  장기 통계 분석만 '핫 + 아카이브'를 합쳐 봐야 한다 — 그 용도의 도구다.

왜 운영 DB 에 뷰를 만들지 않는가  ★중요
  뷰가 attach 된 DB(arc.xxx)를 참조하면, 아카이브를 붙이지 않은 연결에서는
  "no such table: arc.xxx" 로 깨진다. 라이브 API 커넥션이 정확히 그 경우라
  운영 전체가 멈춘다. 그래서 뷰는 이 분석 연결 안에서만 사는 TEMP VIEW 로 만든다.

중복 처리
  articles 는 재등록(삭제됐던 article_no 가 부활)으로 핫·아카이브 양쪽에 있을 수 있다.
  이때는 최신 상태인 '핫'을 정본으로 보고 아카이브 쪽을 제외한다.
  article_events(event_id 증가)·complex_daily_agg(날짜 파티션)는 겹치지 않는다.

사용법
  # 대화형 파이썬에서
  from scripts.archive_query import connect
  con = connect(); con.execute("SELECT COUNT(*) FROM articles_all").fetchone()

  # CLI
  python scripts/archive_query.py --info
  python scripts/archive_query.py "SELECT substr(event_date,1,7) m, COUNT(*) FROM article_events_all GROUP BY m ORDER BY m"

주의: 아카이브는 느린 블록스토리지(vdb)에 있다. 전체 스캔 쿼리는 수 분 걸릴 수 있다.
      이 도구는 읽기 전용이다 — 쓰기는 불가능하게 열린다.
"""
import sqlite3
import sys

DB = "/opt/koczip/data/naverreal.sqlite"
ARC = "/mnt/backup/archive.sqlite"

# 테이블 → 중복 제거에 쓸 키(없으면 단순 UNION ALL)
TABLES = {
    "articles": "article_no",
    "article_events": None,
    "complex_daily_agg": None,
}


def connect(db=DB, arc=ARC):
    """핫+아카이브를 합친 <테이블>_all TEMP VIEW 가 준비된 읽기전용 연결을 돌려준다."""
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    con.execute("ATTACH DATABASE ? AS arc", ("file:%s?mode=ro" % arc,))
    have_arc = {r[0] for r in con.execute(
        "SELECT name FROM arc.sqlite_master WHERE type='table'")}
    for t, key in TABLES.items():
        if t not in have_arc:
            con.execute("CREATE TEMP VIEW %s_all AS SELECT * FROM main.%s" % (t, t))
            continue
        # SELECT * 컬럼 수가 다르면 UNION ALL 이 깨진다 — 먼저 확인
        n_hot = len(con.execute("SELECT * FROM main.%s LIMIT 0" % t).description)
        n_arc = len(con.execute("SELECT * FROM arc.%s LIMIT 0" % t).description)
        if n_hot != n_arc:
            raise RuntimeError("스키마 불일치: %s 핫 %d컬럼 / 아카이브 %d컬럼" % (t, n_hot, n_arc))
        if key:
            sql = ("CREATE TEMP VIEW %s_all AS "
                   "SELECT * FROM main.%s "
                   "UNION ALL "
                   "SELECT * FROM arc.%s a WHERE NOT EXISTS "
                   "(SELECT 1 FROM main.%s m WHERE m.%s = a.%s)"
                   % (t, t, t, t, key, key))
        else:
            sql = ("CREATE TEMP VIEW %s_all AS SELECT * FROM main.%s "
                   "UNION ALL SELECT * FROM arc.%s" % (t, t, t))
        con.execute(sql)
    return con


def info(con):
    print("=== 아카이브 통합 조회 ===")
    print("  핫      : %s" % DB)
    print("  아카이브: %s  (느린 vdb — 전체 스캔은 수 분)" % ARC)
    print()
    print("  %-22s %14s %14s" % ("테이블(_all 로 조회)", "핫", "아카이브"))
    for t in TABLES:
        h = con.execute("SELECT COUNT(*) FROM main.%s" % t).fetchone()[0]
        try:
            a = con.execute("SELECT COUNT(*) FROM arc.%s" % t).fetchone()[0]
        except sqlite3.Error:
            a = 0
        print("  %-22s %14s %14s" % (t + "_all", format(h, ","), format(a, ",")))
    print()
    for t, col in (("articles", "last_seen_date"), ("article_events", "event_date"),
                   ("complex_daily_agg", "snapshot_date")):
        try:
            hm = con.execute("SELECT MIN(%s),MAX(%s) FROM main.%s" % (col, col, t)).fetchone()
            am = con.execute("SELECT MIN(%s),MAX(%s) FROM arc.%s" % (col, col, t)).fetchone()
            print("  %-18s 핫 %s~%s / 아카이브 %s~%s" % (t, hm[0], hm[1], am[0], am[1]))
        except sqlite3.Error:
            pass


def main():
    args = [a for a in sys.argv[1:]]
    con = connect()
    if not args or args[0] == "--info":
        info(con)
        return 0
    cur = con.execute(args[0])
    cols = [d[0] for d in cur.description] if cur.description else []
    if cols:
        print(" | ".join(cols))
        print("-" * 60)
    for row in cur:
        print(" | ".join("" if v is None else str(v) for v in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
