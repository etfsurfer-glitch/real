"""관리자 '실거래 추가 매칭' 큐 — 단지에 못 붙은 거래를 국토부 단지 번호(aptSeq)로 묶고 후보 단지를 붙여 둔다.

전월세 미매칭 45만 행을 화면에서 매번 묶으면 20초+ 라 미리 만든다(daily step 10c, 재매칭 뒤).
메인 DB 는 읽기만. 결과는 data/tx_unmatched.sqlite:
  groups  — 매번 새로 씀(aptSeq 별 거래 수·이름·지번·동·면적·후보 단지)
  review  — 관리자가 정한 것(matched/none). 다시 만들어도 지우지 않는다.

    python scripts/build_tx_unmatched.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realprice import matching as m  # noqa: E402

OUT = Path(settings.local_db_path).parent / "tx_unmatched.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
  apt_seq   TEXT PRIMARY KEY,
  sgg_cd    TEXT, umd_nm TEXT,
  names     TEXT,            -- JSON [[이름, 건수], ...]
  jibuns    TEXT,            -- JSON [[지번, 건수], ...]
  n_sale    INTEGER, n_rent INTEGER,
  first_ymd TEXT, last_ymd TEXT,
  build_year INTEGER,
  areas     TEXT,            -- JSON 전용면적 목록(소수 1자리, 많은 순 8개)
  cands     TEXT,            -- JSON 후보 단지
  built_at  TEXT
);
CREATE INDEX IF NOT EXISTS groups_sgg ON groups(sgg_cd);
CREATE TABLE IF NOT EXISTS review (
  apt_seq    TEXT PRIMARY KEY,
  status     TEXT NOT NULL,   -- matched | none
  complex_no TEXT,
  note       TEXT,
  n_applied  INTEGER,
  by_user    TEXT,
  at         TEXT
);
"""


def _sim(a: str, b: str) -> float:
    x, y = m.base_normalize(a), m.base_normalize(b)
    bx, by = m._bigrams(x), m._bigrams(y)
    if not bx or not by:
        return 0.0
    return len(bx & by) / max(1, min(len(bx), len(by)))


def candidates(g: dict, idx_cache: dict, conn: sqlite3.Connection) -> list[dict]:
    sgg = g["sgg_cd"]
    if sgg not in idx_cache:
        idx_cache[sgg] = m.load_complexes(conn, cortar_prefix=sgg)
    umd = g["umd_nm"] or ""
    names = [n for n, _ in g["names"]]
    jibuns = {m.normalize_jibun(j) for j, _ in g["jibuns"] if j}
    bonbuns = {m.bonbun_of(j) for j in jibuns if j}
    areas = g["areas"]
    out = []
    for c in idx_cache[sgg]:
        same_dong = m.dong_compatible(umd, c["dong_name"]) and bool(c["dong_name"])
        addr = m.normalize_jibun(c["detail_address"])
        jib = bool(addr) and addr in jibuns
        bon = bool(addr) and m.bonbun_of(addr) in bonbuns
        sim = max((_sim(n, c["complex_name"]) for n in names), default=0.0)
        if not same_dong and not jib:
            continue
        area_ok = bool(areas) and any(abs(a - e) <= 0.6 for a in areas for e in c["areas"])
        score = sim * 0.6 + (0.25 if jib else 0.12 if bon else 0) + (0.1 if area_ok else 0) + (0.05 if same_dong else 0)
        if sim < 0.2 and not (jib or bon):
            continue
        num_bad = not any(m.digits_strict(n, c["complex_name"]) for n in names)   # 부영3차 ↔ 부영1차
        if num_bad:
            score *= 0.5
        reasons = [r for r, ok in (("지번 같음", jib), ("본번 같음", bon and not jib), ("면적 맞음", area_ok),
                                   ("같은 동", same_dong), (f"이름 {round(sim * 100)}%", sim >= 0.2),
                                   ("번호 다름", num_bad)) if ok]
        out.append({"complex_no": c["complex_no"], "complex_name": c["complex_name"], "dong": c["dong_name"],
                    "jibun": c["detail_address"], "score": round(score, 3), "reasons": reasons})
    out.sort(key=lambda x: -x["score"])
    return out[:6]


def main() -> int:
    t0 = time.time()
    src = sqlite3.connect(f"file:{settings.local_db_path}?mode=ro", uri=True, timeout=60)
    rules = {r[0] for r in src.execute("SELECT apt_seq FROM tx_seq_map WHERE source='rule'")}
    G: dict[str, dict] = {}

    def add(seq, sgg, umd, name, jibun, ymd, by, excl, kind):
        if not seq or seq in rules:
            return
        g = G.get(seq)
        if g is None:
            g = G[seq] = {"sgg_cd": sgg, "umd": Counter(), "names": Counter(), "jibuns": Counter(), "n_sale": 0,
                          "n_rent": 0, "ymd": [], "by": Counter(), "areas": Counter()}
        g["umd"][umd or ""] += 1
        g["names"][name or ""] += 1
        g["jibuns"][jibun or ""] += 1
        g["n_" + kind] += 1
        if ymd:
            g["ymd"].append(ymd)
        if by:
            g["by"][by] += 1
        try:
            g["areas"][round(float(excl), 1)] += 1
        except (TypeError, ValueError):
            pass

    for r in src.execute("SELECT apt_seq, sgg_cd, umd_nm, apt_nm, jibun, deal_ymd, build_year, excl_use_ar "
                         "FROM transactions WHERE matched_complex_no IS NULL AND COALESCE(is_cancelled,0)=0"):
        add(*r, "sale")
    for r in src.execute("SELECT json_extract(raw,'$.aptSeq'), sgg_cd, umd_nm, apt_nm, jibun, deal_ymd, build_year, excl_use_ar "
                         "FROM rentals WHERE matched_complex_no IS NULL"):
        add(*r, "rent")
    print(f"[unmatched] aptSeq {len(G):,}개 · {time.time() - t0:.0f}s")

    idx_cache: dict = {}
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for seq, g in G.items():
        d = {"sgg_cd": g["sgg_cd"], "umd_nm": g["umd"].most_common(1)[0][0],
             "names": g["names"].most_common(5), "jibuns": g["jibuns"].most_common(5),
             "areas": [a for a, _ in g["areas"].most_common(8)]}
        cs = candidates(d, idx_cache, src)
        ys = sorted(g["ymd"])
        rows.append((seq, d["sgg_cd"], d["umd_nm"], json.dumps(d["names"], ensure_ascii=False),
                     json.dumps(d["jibuns"], ensure_ascii=False), g["n_sale"], g["n_rent"],
                     ys[0] if ys else None, ys[-1] if ys else None,
                     g["by"].most_common(1)[0][0] if g["by"] else None,
                     json.dumps(d["areas"]), json.dumps(cs, ensure_ascii=False), now))
    src.close()

    out = sqlite3.connect(OUT, timeout=30)
    out.executescript(SCHEMA)
    with out:
        out.execute("DELETE FROM groups")
        out.executemany("INSERT INTO groups VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    n_c = sum(1 for r in rows if r[11] != "[]")
    print(f"[done] groups {len(rows):,} (후보 있음 {n_c:,}) → {OUT} · {time.time() - t0:.0f}s")
    out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
