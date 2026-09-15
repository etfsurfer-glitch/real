# -*- coding: utf-8 -*-
"""비단지 region 매물(realtor_id 빈값) → 중개사무소 정확 귀속.

문제: 상가·사무실·지산 등 CP 제휴(cpid=SERVE 등) 매물은 네이버가 realtorId를 안 줘
attribution='region'(빈 id)로 수집됨 → 사무소별 매물수가 0으로 보임(2026-07-14 문정에이스 사례).

해결(정확성 담보): 매물 상세 API의 establishRegistrationNo(등록번호)로 vworld_brokers에
매칭. **등록번호=공식 유일키**, 추가로 대표명 일치까지 확인(이중검증). 표본 17곳 중 등록번호
매칭 14곳 전부 대표명도 일치 확인(2026-07-14).

방식: 사무소(정규화이름+시군구) 단위로 1건만 상세조회(매물 다수가 같은 사무소 공유) →
등록번호 → vworld ra_regno 매칭 → sys_regno 확정. 결과를 office_attribution.sqlite에 저장.
그 뒤 매물을 (정규화이름+시군구)로 이 맵에 조인해 sys_regno별 매물수 집계.

격리: 메인/비단지 매물 DB는 읽기전용. 쓰기는 office_attribution.sqlite 만.
사용: build_region_office_attribution.py [--limit N] [--workers 6] [--refresh] [--cat office,sangga]
크론(daily) 증분: checked_at 최근 14일 이내면 스킵.
"""
import argparse
import datetime
import glob
import json
import os
import sqlite3
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, ".")
from collector.creds import ensure_creds                      # noqa: E402
from collector.http import get_json                            # noqa: E402
from collector.realtor_matching import normalize_name, normalize_regno  # noqa: E402

DATA = os.environ.get("KOCZIP_DATA", "data")
MAIN = os.path.join(DATA, "naverreal.sqlite")
ATTR = os.path.join(DATA, "office_attribution.sqlite")
ART_URL = "https://new.land.naver.com/api/articles/{}"
CATS = ["villa", "oneroom", "house", "sangga", "office",
        "knowledge", "redev", "building", "factory", "land"]
STALE_DAYS = 14


def _init(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS region_office_attribution (
      norm_name TEXT NOT NULL, sgg5 TEXT NOT NULL,
      sample_name TEXT,                 -- 대표적 네이버 표기(참고)
      ra_regno TEXT, sys_regno TEXT,    -- vworld 매칭 결과(NULL=무매칭)
      business_name TEXT, representative TEXT,
      confirm TEXT,                     -- regno_rep | regno | none
      n_listings INTEGER DEFAULT 0,
      checked_at TEXT,
      PRIMARY KEY (norm_name, sgg5));
    CREATE INDEX IF NOT EXISTS idx_roa_sys ON region_office_attribution(sys_regno);
    CREATE TABLE IF NOT EXISTS office_region_counts (
      sys_regno TEXT PRIMARY KEY,
      total INTEGER, by_cat TEXT, updated_at TEXT);
    """)


def gather_offices(cats):
    """비단지 DB에서 (정규화이름, sgg5) 사무소 단위 집계 — 빈 realtor_id만.
    반환 {(norm,sgg5): {"listings": n, "sample": name, "art": 대표article, "art_cat": cat}}."""
    offices = {}
    for cat in cats:
        path = os.path.join(DATA, f"listings_{cat}.sqlite")
        if not os.path.exists(path):
            continue
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            snap = c.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
            if not snap:
                continue
            for name, sgg, n, art in c.execute(
                "SELECT realtor_name, substr(cortar_no,1,5) sgg, COUNT(*) n, MIN(article_no) art "
                "FROM listings WHERE (realtor_id IS NULL OR realtor_id='') "
                "AND realtor_name IS NOT NULL AND realtor_name<>'' AND snapshot_date=? "
                "GROUP BY realtor_name, sgg", (snap,)):
                nm = normalize_name(name)
                if not nm or not sgg:
                    continue
                k = (nm, sgg)
                o = offices.setdefault(k, {"listings": 0, "sample": name, "art": art,
                                           "art_cat": cat, "by_cat": {}})
                o["listings"] += n
                o["by_cat"][cat] = o["by_cat"].get(cat, 0) + n
                if o["art"] is None:
                    o["art"] = art; o["art_cat"] = cat
        finally:
            c.close()
    return offices


def load_vworld():
    """ra_regno(정규화) → (sys_regno, business_name, representative). 영업+폐업 모두(등록번호는 유일)."""
    c = sqlite3.connect(f"file:{MAIN}?mode=ro", uri=True)
    idx = {}
    try:
        for sys_regno, ra, name, rep in c.execute(
                "SELECT sys_regno, ra_regno, business_name, representative FROM vworld_brokers WHERE ra_regno IS NOT NULL"):
            k = normalize_regno(ra)
            if k:
                idx.setdefault(k, (sys_regno, name, rep))
    finally:
        c.close()
    return idx


def fetch_regno(art, creds):
    """article 상세 → (ra_regno_norm, representativeName). 실패 None."""
    try:
        st, d = get_json(ART_URL.format(art), creds=creds)
        ar = (d or {}).get("articleRealtor") or {}
        reg = ar.get("establishRegistrationNo")
        return (normalize_regno(reg) if reg else None, ar.get("representativeName"))
    except Exception:
        return (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="이번 실행 처리 사무소 수 제한(증분)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--refresh", action="store_true", help="checked_at 무시하고 전량 재조회")
    ap.add_argument("--cat", default="", help="쉼표구분 카테고리(기본 전체)")
    a = ap.parse_args()
    cats = [c.strip() for c in a.cat.split(",") if c.strip()] or CATS

    db = sqlite3.connect(ATTR)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA journal_size_limit=1073741824")
    _init(db)

    print("[*] 사무소 수집(비단지 region 매물)...", flush=True)
    offices = gather_offices(cats)
    print(f"    사무소(이름+sgg): {len(offices):,}  매물합: {sum(o['listings'] for o in offices.values()):,}", flush=True)

    try:
        db.execute("ALTER TABLE region_office_attribution ADD COLUMN by_cat TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 있음

    # 최신 매물수·카테고리 내역은 항상 갱신(가벼움)
    for (nm, sgg), o in offices.items():
        db.execute(
            "INSERT INTO region_office_attribution(norm_name,sgg5,sample_name,n_listings,by_cat) VALUES(?,?,?,?,?) "
            "ON CONFLICT(norm_name,sgg5) DO UPDATE SET n_listings=excluded.n_listings, "
            "sample_name=excluded.sample_name, by_cat=excluded.by_cat",
            (nm, sgg, o["sample"], o["listings"], json.dumps(o["by_cat"], ensure_ascii=False)))
    db.commit()

    # 조회 대상: 아직 확정 안 됐거나 stale(등록번호 미확보만 재시도)
    cutoff = (datetime.date.today() - datetime.timedelta(days=STALE_DAYS)).isoformat()
    todo = []
    for (nm, sgg), o in offices.items():
        row = db.execute("SELECT sys_regno, checked_at FROM region_office_attribution WHERE norm_name=? AND sgg5=?",
                         (nm, sgg)).fetchone()
        if not a.refresh and row and row[1] and row[1] >= cutoff:
            continue  # 최근 확인됨
        todo.append((nm, sgg, o["art"]))
    if a.limit:
        todo.sort(key=lambda x: -offices[(x[0], x[1])]["listings"])  # 매물 많은 곳 우선
        todo = todo[:a.limit]
    print(f"[*] 상세조회 대상: {len(todo):,} 사무소 (workers={a.workers})", flush=True)

    vw = load_vworld()
    creds = ensure_creds()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    done = regno_rep = regno_only = nomatch = 0

    def work(item):
        nm, sgg, art = item
        reg, rep = fetch_regno(art, creds)
        return (nm, sgg, reg, rep)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, it): it for it in todo}
        for fut in as_completed(futs):
            nm, sgg, reg, rep = fut.result()
            sys_regno = ra = bname = brep = None
            confirm = "none"
            if reg and reg in vw:
                sys_regno, bname, brep = vw[reg]
                ra = reg
                # 대표명 일치 = 이중검증(등록번호+이름)
                confirm = "regno_rep" if (rep and brep and rep.strip() == (brep or "").strip()) else "regno"
                if confirm == "regno_rep":
                    regno_rep += 1
                else:
                    regno_only += 1
            else:
                nomatch += 1
            db.execute(
                "UPDATE region_office_attribution SET ra_regno=?, sys_regno=?, business_name=?, "
                "representative=?, confirm=?, checked_at=? WHERE norm_name=? AND sgg5=?",
                (ra, sys_regno, bname, brep, confirm, now, nm, sgg))
            done += 1
            if done % 200 == 0:
                db.commit()
                print(f"    {done}/{len(todo)}  regno+대표 {regno_rep} · 등록번호만 {regno_only} · 무매칭 {nomatch}", flush=True)
    db.commit()
    print(f"[*] 조회완료 {done}: 등록번호+대표 {regno_rep} · 등록번호만 {regno_only} · 무매칭 {nomatch}", flush=True)

    # sys_regno별 매물수 집계 재빌드(확정된 사무소만) — 총계 + 카테고리별
    print("[*] office_region_counts 재빌드...", flush=True)
    per_sys = defaultdict(int)
    per_sys_cat: dict = defaultdict(lambda: defaultdict(int))
    for sys_regno, n, bc in db.execute(
            "SELECT sys_regno, n_listings, by_cat FROM region_office_attribution WHERE sys_regno IS NOT NULL"):
        per_sys[sys_regno] += n
        if bc:
            for cat, cn in json.loads(bc).items():
                per_sys_cat[sys_regno][cat] += cn
    db.execute("DELETE FROM office_region_counts")
    db.executemany(
        "INSERT INTO office_region_counts(sys_regno,total,by_cat,updated_at) VALUES(?,?,?,?)",
        [(s, n, json.dumps(dict(per_sys_cat.get(s, {})), ensure_ascii=False), now) for s, n in per_sys.items()])
    db.commit()
    matched_offices = db.execute("SELECT COUNT(*) FROM region_office_attribution WHERE sys_regno IS NOT NULL").fetchone()[0]
    matched_listings = sum(per_sys.values())
    print(f"[*] 귀속 완료: {matched_offices:,} 사무소 · {matched_listings:,} 매물 → sys_regno {len(per_sys):,}개", flush=True)
    db.close()


if __name__ == "__main__":
    main()
