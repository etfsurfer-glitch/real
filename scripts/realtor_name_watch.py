"""중개사 상호 변경 감시 — 네이버 개명분을 하루 한 번 모아 vworld(공부상)로 대조한다.

왜 필요한가
-----------
daily_run 의 `fetch_naver_realtors --only-missing` 은 **행이 이미 있으면 영원히 건너뛴다**.
그래서 사무소가 상호를 바꿔도 naver_realtors 는 처음 수집한 이름 그대로 남는다.
표시용 realtor_names 는 naver_realtors 에서 만들어지므로 목록·검색에는 옛 상호가 뜨고,
상세 페이지는 listings_current 의 이름을 직접 읽어 새 상호가 뜬다 →
**같은 사무소가 화면마다 다른 이름으로 보인다**(2026-10-16 중개사 제보로 발견, 3,209곳).

무엇을 하나
-----------
① 감지 — 오늘 매물에 찍힌 상호 vs naver_realtors 에 저장된 상호를 비교.
         띄어쓰기·괄호·하이픈만 다른 건 제외(실제 개명이 아니다).
② 기록 — realtor_name_change 에 쌓는다(이력이 남아야 오판을 되짚을 수 있다).
③ 대조 — 바뀐 사무소의 **시군구만** vworld list 크롤로 새로 받아 공부상 상호와 맞춰 본다.
         전수 크롤(월 1회)과 달리 몇 개 시군구만 돌므로 싸다.
④ 반영 — 네이버 프로필을 그 사무소들만 다시 받아 naver_realtors 를 갱신.
         realtor_names 는 뒤이어 도는 build_realtor_dong 이 알아서 따라온다.

판정(status)
  confirmed    공부상 상호도 새 이름과 같다 → 진짜 개명
  ad_only      공부상은 옛 이름 그대로 → 네이버 광고명만 바꾼 것
  vworld_other 공부상이 둘 중 어느 쪽도 아님 → 등록 미반영이거나 매칭 의심
  no_vworld    매칭된 공부상 기록이 없음

어느 쪽이든 화면에는 **네이버 최신 상호**를 쓴다(이용자가 네이버에서 보는 이름과 맞춰야
한다). vworld 대조는 '진짜 개명인지'를 가려 운영자가 이상 건을 찾아보게 하는 장치다.

사용:
  python scripts/realtor_name_watch.py                 # 감지 → vworld 대조 → 반영
  python scripts/realtor_name_watch.py --dry-run       # 감지만, 아무것도 안 바꿈
  python scripts/realtor_name_watch.py --no-vworld     # vworld 크롤 건너뛰고 반영만
  python scripts/realtor_name_watch.py --max-sgg 40    # 크롤할 시군구 상한
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collector.config import settings  # noqa: E402

# 띄어쓰기·괄호·하이픈·가운뎃점만 다른 건 같은 상호로 본다.
# (같은 스냅샷에서도 한 사무소가 '영 부동산중개'/'영부동산중개' 처럼 섞어 쓴다)
_NOISE = re.compile(r"[\s()\-·,.]")


def norm(s: str | None) -> str:
    return _NOISE.sub("", s or "")


def open_db() -> sqlite3.Connection:
    c = sqlite3.connect(settings.local_db_path, timeout=60.0)
    c.execute("PRAGMA busy_timeout = 60000")
    return c


def ensure_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS realtor_name_change(
          realtor_id   TEXT PRIMARY KEY,
          old_name     TEXT,
          new_name     TEXT,
          listings     INTEGER,
          sgg_cd       TEXT,
          vworld_name  TEXT,
          status       TEXT,          -- confirmed | ad_only | vworld_other | no_vworld
          first_seen   TEXT,
          checked_at   TEXT,
          applied_at   TEXT)
    """)
    c.execute("CREATE INDEX IF NOT EXISTS rnc_status ON realtor_name_change(status, checked_at)")
    # 기준선 — '지난번에 본 매물 상호'. 이것과 오늘을 비교해야 변경이 들어온 날만 잡힌다.
    c.execute("""
        CREATE TABLE IF NOT EXISTS realtor_name_seen(
          realtor_id   TEXT PRIMARY KEY,
          listing_name TEXT,
          seen_at      TEXT)
    """)
    c.commit()


def detect(c: sqlite3.Connection) -> list[dict]:
    """**어제 본 매물 상호**와 오늘 매물 상호를 비교해, 오늘 바뀐 것만 돌려준다.

    프로필 상호(naver_realtors)와 비교하면 안 된다 — 네이버는 사무소 프로필 상호와
    매물에 찍는 상호를 **따로** 주며, 둘은 영영 같아지지 않는다(실측: 다시 받아도
    1,504곳이 그대로 다름). 그걸 기준으로 삼으면 매일 같은 1,504곳을 헛되이 재수집한다.
    우리가 잡아야 하는 건 '네이버에서 상호 변경이 들어온 날'이므로, 기준은 지난번에
    본 매물 상호다.
    """
    cur = c.execute("""
        SELECT l.realtor_id, MAX(l.realtor_name), COUNT(*)
        FROM listings_current l
        WHERE l.realtor_id IS NOT NULL AND l.realtor_name IS NOT NULL
              AND l.realtor_name <> ''
        GROUP BY l.realtor_id
    """).fetchall()
    seen = {r[0]: r[1] for r in c.execute(
        "SELECT realtor_id, listing_name FROM realtor_name_seen")}
    sgg = {r[0]: r[1] for r in c.execute(
        "SELECT realtor_id, primary_sgg_cd FROM realtor_match WHERE primary_sgg_cd IS NOT NULL")}

    out = []
    for rid, new_name, n in cur:
        prev = seen.get(rid)
        if prev is None:              # 처음 보는 사무소 — 기준선만 깔고 넘어간다
            continue
        if norm(prev) == norm(new_name):
            continue                  # 띄어쓰기 차이뿐 — 개명 아님
        out.append({"realtor_id": rid, "old": prev, "new": new_name,
                    "n": n, "sgg": sgg.get(rid)})
    out.sort(key=lambda r: -r["n"])
    return out


def remember(c: sqlite3.Connection) -> int:
    """오늘 본 매물 상호를 기준선으로 저장. 다음 실행의 비교 대상이 된다."""
    now = datetime.now().isoformat(timespec="seconds")
    c.execute("""
        INSERT INTO realtor_name_seen(realtor_id, listing_name, seen_at)
        SELECT realtor_id, MAX(realtor_name), ?
        FROM listings_current
        WHERE realtor_id IS NOT NULL AND realtor_name IS NOT NULL AND realtor_name <> ''
        GROUP BY realtor_id
        ON CONFLICT(realtor_id) DO UPDATE SET
          listing_name=excluded.listing_name, seen_at=excluded.seen_at
    """, (now,))
    n = c.total_changes
    c.commit()
    return n


def crawl_vworld(sggs: list[str], max_sgg: int) -> int:
    """바뀐 사무소가 속한 시군구만 vworld list 재크롤. 반환=exit code."""
    use = sggs[:max_sgg]
    if not use:
        return 0
    print(f"[*] vworld 재크롤 시군구 {len(use)}개 (전체 {len(sggs)}개 중)", flush=True)
    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-u", str(ROOT / "scripts/crawl_vworld_brokers.py"),
         "--list", "--sgg", ",".join(use), "--parallel", "3"],
        cwd=str(ROOT))
    return r.returncode


def classify(c: sqlite3.Connection, rows: list[dict]) -> None:
    """realtor_match 로 이어진 공부상 상호와 맞춰 status 를 매긴다."""
    vw = {r[0]: r[1] for r in c.execute("""
        SELECT m.realtor_id, b.business_name
        FROM realtor_match m JOIN vworld_brokers b ON b.sys_regno = m.sys_regno
    """)}
    for r in rows:
        v = vw.get(r["realtor_id"])
        r["vworld"] = v
        if not v:
            r["status"] = "no_vworld"
        elif norm(v) == norm(r["new"]):
            r["status"] = "confirmed"
        elif norm(v) == norm(r["old"]):
            r["status"] = "ad_only"
        else:
            r["status"] = "vworld_other"


def record(c: sqlite3.Connection, rows: list[dict]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    for r in rows:
        c.execute("""
            INSERT INTO realtor_name_change
              (realtor_id, old_name, new_name, listings, sgg_cd, vworld_name,
               status, first_seen, checked_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(realtor_id) DO UPDATE SET
              old_name=excluded.old_name, new_name=excluded.new_name,
              listings=excluded.listings, sgg_cd=excluded.sgg_cd,
              vworld_name=excluded.vworld_name, status=excluded.status,
              checked_at=excluded.checked_at
        """, (r["realtor_id"], r["old"], r["new"], r["n"], r["sgg"],
              r.get("vworld"), r.get("status"), now, now))
    c.commit()


def apply_names(rows: list[dict], batch: int = 200) -> None:
    """바뀐 사무소의 네이버 프로필만 다시 받는다(상호뿐 아니라 주소·전화도 함께 최신화)."""
    ids = [r["realtor_id"] for r in rows]
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        print(f"[*] 프로필 재수집 {i + 1}~{i + len(chunk)} / {len(ids)}", flush=True)
        subprocess.run(
            [str(ROOT / ".venv/bin/python"), "-u",
             str(ROOT / "scripts/fetch_naver_realtors_direct.py"),
             "--ids", ",".join(chunk), "--parallel", "6"],
            cwd=str(ROOT))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="감지만 하고 아무것도 바꾸지 않는다")
    p.add_argument("--no-vworld", action="store_true", help="vworld 재크롤을 건너뛴다")
    p.add_argument("--max-sgg", type=int, default=60, help="재크롤할 시군구 상한")
    p.add_argument("--limit", type=int, help="반영할 사무소 수 상한(매물 많은 순)")
    a = p.parse_args()

    c = open_db()
    ensure_table(c)

    rows = detect(c)
    print(f"[*] 상호 변경 감지: {len(rows):,}곳", flush=True)
    if not rows:
        if not a.dry_run:
            remember(c)          # 첫 실행이면 여기서 기준선이 깔린다
        return 0
    if a.limit:
        rows = rows[:a.limit]

    if not a.no_vworld:
        sggs = sorted({r["sgg"] for r in rows if r["sgg"]})
        crawl_vworld(sggs, a.max_sgg)

    classify(c, rows)
    tally: dict[str, int] = {}
    for r in rows:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print("[*] 판정:", " · ".join(f"{k} {v:,}" for k, v in sorted(tally.items())), flush=True)

    for r in rows[:10]:
        print(f"    {r['status']:<12} 매물{r['n']:>4}  {r['old']}  →  {r['new']}")

    if a.dry_run:
        print("[*] --dry-run: 기록·반영 생략")
        return 0

    record(c, rows)
    apply_names(rows)
    remember(c)                  # 오늘 본 이름을 기준선으로 — 같은 건이 내일 또 잡히지 않게
    c.execute("UPDATE realtor_name_change SET applied_at=? WHERE realtor_id IN (%s)"
              % ",".join("?" * len(rows)),
              [datetime.now().isoformat(timespec="seconds")] + [r["realtor_id"] for r in rows])
    c.commit()
    print(f"[*] 반영 완료 {len(rows):,}곳 — realtor_names 는 뒤이어 도는 build_realtor_dong 이 따라온다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
