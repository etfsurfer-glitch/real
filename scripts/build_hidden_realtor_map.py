"""숨김 ID 중개사 전수 발굴 + 등록번호 검증 매핑 (2026-07-07, 정확도 최우선).

배경: 네이버에 realtor_id를 숨긴 사무소의 매물이 전 DB에 42만 건(상호·시군구 그룹
3.5만 개). 브라운홈즈(동대문, vworld 2026-04 등록)처럼 네이버 프로필이 아예 없으면
홈페이지 검색·사무소 페이지에서 실종된다.

원칙(사용자 확정): 정확성 우선 — 상호 유일일치만으로 귀속하지 않는다.
  ① 후보: 숨김 매물 그룹(상호, 시군구) × vworld 영업 사무소 상호 정확일치가
     시군구 내 유일하거나 전국 유일인 경우만.
  ② 검증: 그룹 매물 최대 2건의 상세 API 개설등록번호 == vworld ra_regno(숫자 정규화).
     1건 이상 일치 & 불일치 0건일 때만 hidden_realtor_map 등록.
     불일치 발견 → 보류 목록에 기록(동명 혼재 의심).
  ③ 귀속 ID: realtor_match에 네이버 ID가 있으면 그 ID, 없으면 vw{sys_regno} 합성 ID
     (+naver_realtors 프로비저닝 — 검색·상세페이지 노출용).

적용은 apply_hidden_realtor_map.py 가 수행(전 매물 DB). 재실행 시 기매핑 그룹 스킵(멱등).

Run(박스):  .venv/bin/python scripts/build_hidden_realtor_map.py [--limit N] [--workers 4]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
DB = DATA / "naverreal.sqlite"

_digits = lambda s: re.sub(r"\D", "", s or "")


def collect_groups() -> dict:
    """(상호, sgg5) → {"n": 매물수, "arts": [(article_no, complex_no|None), ...]}"""
    groups: dict[tuple, dict] = {}

    def add(nm, sgg, art, cx, n=1):
        g = groups.setdefault((nm, sgg), {"n": 0, "arts": []})
        g["n"] += n
        if art and len(g["arts"]) < 6:
            g["arts"].append((art, cx))

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for nm, sgg, art, cx in con.execute(
            "SELECT l.realtor_name, substr(cx.cortar_no,1,5), l.article_no, l.complex_no "
            "FROM listings_current l JOIN complexes cx ON cx.complex_no=l.complex_no "
            "WHERE (l.realtor_id IS NULL OR l.realtor_id='') "
            "AND l.realtor_name IS NOT NULL AND l.realtor_name!=''"):
        add(nm, sgg, art, cx)
    con.close()
    for f in sorted(glob.glob(str(DATA / "listings_*.sqlite"))):
        d = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        try:
            for nm, sgg, art in d.execute(
                    "SELECT realtor_name, substr(cortar_no,1,5), article_no FROM listings "
                    "WHERE (realtor_id IS NULL OR realtor_id='') "
                    "AND realtor_name IS NOT NULL AND realtor_name!='' "
                    "AND snapshot_date=(SELECT MAX(snapshot_date) FROM listings)"):
                add(nm, sgg, art, None)
        except sqlite3.Error:
            pass
        d.close()
    return groups


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="검증할 그룹 수 상한(0=전체)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    from collector.article_detail import fetch_article_detail
    from collector.creds import ensure_creds
    creds = ensure_creds()

    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS hidden_realtor_map (
        realtor_name TEXT NOT NULL, cortar_prefix TEXT NOT NULL,
        realtor_id TEXT NOT NULL, note TEXT,
        PRIMARY KEY (realtor_name, cortar_prefix))""")
    mapped = {(r[0], r[1]) for r in con.execute(
        "SELECT realtor_name, cortar_prefix FROM hidden_realtor_map")}

    # vworld 인덱스(영업만) + 네이버 매칭
    vw_by_name_sgg: dict[tuple, list] = {}
    vw_by_name: dict[str, list] = {}
    for bn, sgg, sregno, ra in con.execute(
            "SELECT business_name, sgg_cd, sys_regno, ra_regno FROM vworld_brokers "
            "WHERE status='영업' AND business_name IS NOT NULL"):
        vw_by_name_sgg.setdefault((bn, sgg), []).append((sregno, ra))
        vw_by_name.setdefault(bn, []).append((sregno, ra, sgg))
    naver_of = dict(con.execute(
        "SELECT sys_regno, realtor_id FROM realtor_match WHERE realtor_id IS NOT NULL"))

    groups = collect_groups()
    # 후보 산출: 시군구 유일 → 그 사무소 / 아니면 전국 유일 → 그 사무소
    cands = []
    for (nm, sgg), g in groups.items():
        if (nm, sgg) in mapped or not g["arts"]:
            continue
        local = vw_by_name_sgg.get((nm, sgg), [])
        if len(local) == 1:
            cands.append((nm, sgg, local[0][0], local[0][1], g))
        elif not local:
            nat = vw_by_name.get(nm, [])
            if len(nat) == 1:
                cands.append((nm, sgg, nat[0][0], nat[0][1], g))
    cands.sort(key=lambda x: -x[4]["n"])   # 매물 많은 그룹 우선
    if args.limit:
        cands = cands[: args.limit]
    print(f"그룹 {len(groups):,} · 검증 대상 후보 {len(cands):,} "
          f"(매물 {sum(c[4]['n'] for c in cands):,}건)")

    lock = threading.Lock()
    stats = {"ok": 0, "mismatch": 0, "noresp": 0, "listings": 0}
    rows_ok, rows_bad = [], []

    def verify(c):
        nm, sgg, sregno, ra_regno, g = c
        want = _digits(ra_regno)
        if not want:
            return None
        confirmed = mismatched = 0
        for art, cx in g["arts"][:2]:
            try:
                st, d = fetch_article_detail(str(art), cx, creds)
            except Exception:
                continue
            if st != 200 or not d:
                continue
            reg = _digits(((d.get("articleRealtor") or {}).get("establishRegistrationNo") or ""))
            if not reg:
                continue
            if reg == want:
                confirmed += 1
            else:
                mismatched += 1
                break
            time.sleep(0.15)
        if mismatched:
            return ("bad", nm, sgg, sregno, g["n"])
        if confirmed:
            return ("ok", nm, sgg, sregno, g["n"])
        return ("noresp", nm, sgg, sregno, g["n"])

    with ThreadPoolExecutor(max_workers=args.workers) as exe:
        futs = {exe.submit(verify, c): c for c in cands}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if done % 200 == 0:
                print(f"  진행 {done:,}/{len(cands):,} — 확정 {stats['ok']:,} "
                      f"불일치 {stats['mismatch']:,} 무응답 {stats['noresp']:,}")
            if not r:
                continue
            kind, nm, sgg, sregno, n = r
            with lock:
                if kind == "ok":
                    stats["ok"] += 1
                    stats["listings"] += n
                    rid = naver_of.get(sregno) or f"vw{sregno}"
                    rows_ok.append((nm, sgg, rid, sregno, n))
                elif kind == "bad":
                    stats["mismatch"] += 1
                    rows_bad.append((nm, sgg, sregno, n))
                else:
                    stats["noresp"] += 1

    # 확정분 기록 + vw 프로비저닝
    now_note = "등록번호 검증 자동귀속(2026 batch)"
    for nm, sgg, rid, sregno, n in rows_ok:
        con.execute("INSERT OR IGNORE INTO hidden_realtor_map VALUES(?,?,?,?)",
                    (nm, sgg, rid, f"{now_note} — 매물 {n}건, sys_regno {sregno}"))
        if rid.startswith("vw"):
            v = con.execute("SELECT business_name, representative, address, phone, ra_regno, sgg_cd "
                            "FROM vworld_brokers WHERE sys_regno=?", (sregno,)).fetchone()
            if v and not con.execute("SELECT 1 FROM naver_realtors WHERE realtor_id=?", (rid,)).fetchone():
                con.execute(
                    "INSERT OR IGNORE INTO naver_realtors(realtor_id, realtor_name, representative_name, "
                    "address, establish_registration_no, representative_tel_no, cortar_no, raw_json, fetched_at) "
                    "VALUES(?,?,?,?,?,?,?,?,datetime('now'))",
                    (rid, v[0], v[1], v[2], v[4], (v[3] or "").split()[0] if v[3] else None,
                     (v[5] + "00000") if v[5] else None,
                     json.dumps({"source": "vworld_auto", "sys_regno": sregno}, ensure_ascii=False)))
    con.commit()
    (DATA / "hidden_map_mismatch.json").write_text(
        json.dumps(rows_bad, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n확정 매핑 {stats['ok']:,}그룹({stats['listings']:,}건) · "
          f"등록번호 불일치 보류 {stats['mismatch']:,} · 무응답 {stats['noresp']:,}")
    print("불일치 목록: data/hidden_map_mismatch.json")


if __name__ == "__main__":
    main()
