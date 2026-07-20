# -*- coding: utf-8 -*-
"""realtor_id는 있으나 vworld 미매칭인 지역중개사를 **매물 상세 등록번호**로 정확 매칭.

문제(2026-07-14): 전국/건물 매물랭킹에서 일반명 사무소(복드림·키움·대한·큰길 등)가
직원수·개업연도 "-"로 뜸. 이름+시도 매칭은 동명이 수십 곳이라 오귀속 위험으로 스킵됨
(link_region_realtors.py). 등록번호가 있으면 유일 특정되지만, 그동안 naver 지역중개사
매물 상세의 establishRegistrationNo를 안 썼음.

**오귀속 사고 방지 재설계(2026-07-20)**: 매물 1건 상세의 등록번호는 그 사무소 자체
번호가 아닐 수 있다(공동중개·CP로 다른 사무소 등록번호가 실려 옴). 실제로 도원부동산은
매물 6건이 등록번호 둘로 갈렸고, (단지내)큰은 자체번호(강서)와 매물상세번호(서초 딴 사무소)가
달랐다. → 단일매물 매칭은 오귀속을 낳는다. 5중 안전장치로 교체:
  ① 자체 등록번호 우선   — naver_realtors.establish_registration_no 있으면 그것(권위). 없을 때만 매물상세.
  ② 전 매물 일관        — 자체번호 없으면 매물 여러 건(samples) 상세 등록번호가 전원 동일(≥MIN_CONSIST)해야.
  ③ vworld 유일        — 등록번호가 vworld_brokers에 정확히 1곳만 매핑(중복번호는 배제).
  ④ 대표 이중검증       — naver 대표 == vworld 대표(정규화).
  ⑤ 표준14자리|상호정확  — 표준 등록번호(시군구5+년4+일련5)거나 상호가 정규화 동일(구형번호 안전판).

매칭 시:
  ① naver_realtors.establish_registration_no = vworld ra_regno(정규형) 기록
     → **match_clean.step1_regno가 매일 자동 재도출**(realtor_match를 매일 truncate·재빌드해도 생존).
  ② realtor_match(match_type='regno_region') 즉시 upsert(기존 정식매칭 미덮음).
→ 랭킹의 직원수(vworld_employees)·개업연도(registered_ymd)·소재지 자동 노출. **오귀속 0**.

빈 realtor_id CP매물은 build_region_office_attribution.py가 별도 처리(vw{sys_regno} 귀속).
멱등: 이미 매칭된 id·최근 확인분은 스킵(region_regno_check). 상세 실패(CP=NEONET 등)는 checked 기록.
사용: link_region_realtors_regno.py [--limit N] [--workers 6] [--samples 5] [--refresh]
"""
import argparse
import datetime
import os
import re
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, ".")
from collector.config import settings                          # noqa: E402
from collector.creds import ensure_creds                        # noqa: E402
from collector.http import get_json                             # noqa: E402
from collector.realtor_matching import normalize_name           # noqa: E402

DATA = os.environ.get("KOCZIP_DATA", os.path.dirname(settings.local_db_path))
MAIN = settings.local_db_path
CATS = ["villa", "oneroom", "house", "sangga", "office",
        "knowledge", "redev", "building", "factory", "land"]
ART_URL = "https://new.land.naver.com/api/articles/{}"
STALE_DAYS = 30
MIN_CONSIST = 3   # 자체번호 없을 때: 매물 상세 등록번호가 최소 이만큼 '전원 동일'해야 인정(공동중개 오염 차단)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _init(db):
    # 시도이력(멱등 재시도 절약): 등록번호 못 받은 사무소도 checked 기록
    db.executescript("""
    CREATE TABLE IF NOT EXISTS region_regno_check (
      realtor_id TEXT PRIMARY KEY,
      ra_regno TEXT, sys_regno TEXT, confirm TEXT, checked_at TEXT);
    """)


def load_vworld(db):
    """digits(ra_regno) → [(sys_regno, sgg_cd, business_name, representative, ra_regno, address), ...].
    등록번호가 여러 사무소에 매핑되면(구형번호 재사용 등) 후보 리스트로 남겨 매칭 단계에서 '유일'만 인정."""
    idx = {}
    for sr, sgg, ra, bn, rep, addr in db.execute(
            "SELECT sys_regno, sgg_cd, ra_regno, business_name, representative, address "
            "FROM vworld_brokers WHERE ra_regno IS NOT NULL"):
        k = _digits(ra)
        if len(k) >= 12:   # 최소 자리(구형 12 + 표준 14)
            idx.setdefault(k, []).append((sr, sgg, bn, rep, ra, addr))
    return idx


def load_targets(db):
    """realtor_region_counts에 있고 realtor_match(sys_regno) 없는 realtor_id → (이름, 자체등록번호, 대표)."""
    return db.execute("""
        SELECT DISTINCT rc.realtor_id,
               COALESCE(rn.realtor_name, nr.realtor_name, rc.realtor_id) nm,
               nr.establish_registration_no own_reg,
               nr.representative_name own_rep
        FROM realtor_region_counts rc
        LEFT JOIN realtor_match m ON m.realtor_id=rc.realtor_id AND m.sys_regno IS NOT NULL
        LEFT JOIN naver_realtors nr ON nr.realtor_id=rc.realtor_id
        LEFT JOIN realtor_names rn ON rn.realtor_id=rc.realtor_id
        WHERE m.realtor_id IS NULL
    """).fetchall()


def gather_articles(want, k):
    """대상 realtor_id별 매물 article_no 최대 k건 수집(비단지 DB 현재 스냅샷 1패스 스캔)."""
    from collections import defaultdict
    arts = defaultdict(list)
    for cat in CATS:
        p = os.path.join(DATA, f"listings_{cat}.sqlite")
        if not os.path.exists(p):
            continue
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            snap = c.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
            if not snap:
                continue
            for rid, art in c.execute(
                    "SELECT realtor_id, article_no FROM listings "
                    "WHERE realtor_id IS NOT NULL AND realtor_id<>'' AND snapshot_date=?", (snap,)):
                if rid in want and len(arts[rid]) < k and art is not None:
                    arts[rid].append(art)
        finally:
            c.close()
    return arts


def fetch_regno(art, creds):
    """매물 상세 → (digits(등록번호), 대표명). 실패·미제공은 (None, None)."""
    try:
        st, d = get_json(ART_URL.format(art), creds=creds)
        ar = (d or {}).get("articleRealtor") or {}
        reg = ar.get("establishRegistrationNo")
        return (_digits(reg) if reg else None, ar.get("representativeName"))
    except Exception:
        return (None, None)


def resolve_regno(own_reg, arts, creds):
    """이 사무소의 '자기 등록번호'를 안전하게 결정.
      ① 자체번호(own_reg) 있으면 그것(권위) — 매물 조회는 대표 확보용 1건만.
      ② 없으면 매물 상세 등록번호가 전원 동일(≥MIN_CONSIST)일 때만 그 번호. 혼재=오염=포기.
    반환: (use_digits|None, rep|None, reason)"""
    reps = []
    regs = []
    for art in arts:
        reg, rep = fetch_regno(art, creds)
        if rep:
            reps.append(rep)
        if reg:
            regs.append(reg)
        # 자체번호가 있으면 대표 하나만 확보되면 충분
        if own_reg and reps:
            break
    rep = reps[0] if reps else None
    if own_reg and _digits(own_reg):
        return (_digits(own_reg), rep, "own")
    if not regs:
        return (None, rep, "noregno")
    c = Counter(regs)
    top, topn = c.most_common(1)[0]
    if len(c) == 1 and topn >= MIN_CONSIST:
        return (top, rep, "consist")
    if len(c) > 1:
        return (None, rep, "mixed")          # 공동중개 오염 — 매칭 포기
    return (None, rep, f"weak({topn})")       # 표본 부족(<MIN_CONSIST)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="이번 실행 처리 사무소 수 제한(매물 많은 순)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--samples", type=int, default=5, help="사무소당 상세조회 매물 최대 수(일관성 판정용)")
    ap.add_argument("--refresh", action="store_true", help="checked 무시 재조회")
    a = ap.parse_args()

    db = sqlite3.connect(settings.local_db_path, timeout=60)
    db.execute("PRAGMA busy_timeout=60000")
    _init(db)

    vw = load_vworld(db)
    print(f"[*] vworld 등록번호 인덱스: {len(vw):,}", flush=True)

    targets = load_targets(db)
    print(f"[*] 미매칭 지역중개사: {len(targets):,}", flush=True)

    # 최근 확인분(등록번호 미제공·혼재 등) 스킵
    cutoff = (datetime.date.today() - datetime.timedelta(days=STALE_DAYS)).isoformat()
    checked = {}
    if not a.refresh:
        checked = {r[0]: r[1] for r in db.execute("SELECT realtor_id, checked_at FROM region_regno_check")}
    todo = [t for t in targets
            if a.refresh or not (checked.get(t[0]) and checked[t[0]] >= cutoff)]

    # 매물수 많은 순 정렬(랭킹 상위부터 이득)
    tot_of = {r[0]: r[1] for r in db.execute(
        "SELECT realtor_id, (villa_n+house_n+sangga_n+office_n+land_n+factory_n+building_n"
        "+knowledge_n+redev_n+COALESCE(oneroom_n,0)) FROM realtor_region_counts")}
    todo.sort(key=lambda x: -tot_of.get(x[0], 0))
    if a.limit:
        todo = todo[:a.limit]
    print(f"[*] 이번 대상: {len(todo):,} (samples={a.samples}, workers={a.workers}, 일관성≥{MIN_CONSIST})", flush=True)

    want = {t[0] for t in todo}
    print("[*] 매물 article 수집...", flush=True)
    arts = gather_articles(want, a.samples)
    print(f"    매물 확보 사무소: {sum(1 for r in want if arts.get(r)):,}", flush=True)

    creds = ensure_creds()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    meta = {t[0]: (t[1], t[2], t[3]) for t in todo}   # rid -> (name, own_reg, own_rep)

    def work(rid):
        nm, own_reg, own_rep = meta[rid]
        use, rep, reason = resolve_regno(own_reg, arts.get(rid, []), creds)
        rep = rep or own_rep
        return (rid, use, rep, reason)

    linked = regno_rep = noregno = mixed = nomatch = rejected = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, rid): rid for rid, *_ in todo}
        for fut in as_completed(futs):
            rid, use, rep, reason = fut.result()
            nm, own_reg, own_rep = meta[rid]
            sys_regno = ra = None
            confirm = reason
            if not use:
                if reason == "mixed":
                    mixed += 1
                else:
                    noregno += 1
            else:
                cands = vw.get(use, [])
                if len(cands) != 1:
                    nomatch += 1
                    confirm = "nomatch" if not cands else "ambiguous"
                else:
                    sr, sgg, bn, brep, ra_regno, baddr = cands[0]
                    rep_ok = bool(rep) and normalize_name(rep) == normalize_name(brep)
                    name_ok = normalize_name(nm) == normalize_name(bn)
                    std14 = len(use) == 14
                    if not rep_ok:
                        rejected += 1
                        confirm = "rep_mismatch"
                    elif not (std14 or name_ok):
                        rejected += 1
                        confirm = "nonstd_name_diff"
                    else:
                        sys_regno, ra = sr, ra_regno
                        confirm = "regno_rep"
                        # ① 지속성: 정규 등록번호 기록 → match_clean이 매일 자동 재매칭
                        db.execute("UPDATE naver_realtors SET establish_registration_no=? WHERE realtor_id=?",
                                   (ra_regno, rid))
                        # ② 즉시효과: realtor_match upsert(기존 정식매칭 미덮음)
                        db.execute(
                            "INSERT INTO realtor_match(realtor_id, sys_regno, vworld_name, vworld_rep, match_type, matched_at) "
                            "VALUES(?,?,?,?,'regno_region',?) "
                            "ON CONFLICT(realtor_id) DO UPDATE SET sys_regno=excluded.sys_regno, "
                            "vworld_name=excluded.vworld_name, vworld_rep=excluded.vworld_rep, "
                            "match_type=excluded.match_type, matched_at=excluded.matched_at "
                            "WHERE realtor_match.sys_regno IS NULL",
                            (rid, sr, bn, brep, now))
                        linked += 1
                        regno_rep += 1
            db.execute(
                "INSERT INTO region_regno_check(realtor_id, ra_regno, sys_regno, confirm, checked_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(realtor_id) DO UPDATE SET "
                "ra_regno=excluded.ra_regno, sys_regno=excluded.sys_regno, confirm=excluded.confirm, checked_at=excluded.checked_at",
                (rid, ra, sys_regno, confirm, now))
            done = linked + noregno + mixed + nomatch + rejected
            if done % 200 == 0:
                db.commit()
                print(f"    진행 {done}/{len(todo)}  연결 {linked} · 등록번호無 {noregno} · 혼재(오염) {mixed} "
                      f"· vworld無/모호 {nomatch} · 검증탈락 {rejected}", flush=True)
    db.commit()
    print(f"[*] 완료: 연결 {linked:,}(등록번호+대표 {regno_rep:,}) · 등록번호 미제공 {noregno:,} · "
          f"혼재(공동중개 오염) {mixed:,} · vworld無/모호 {nomatch:,} · 검증탈락(대표·비표준) {rejected:,} / 대상 {len(todo):,}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
