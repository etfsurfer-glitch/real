"""국토부 단지 일련번호(aptSeq) → 단지 지도(tx_seq_map) 만들기.

- rule      : 사람이 확정한 매칭(manual_override=1 이고 단지가 있는 행). aptSeq 하나가
              한 단지만 가리킬 때만 규칙이 된다. 갈리면 conflicts 로 보고만 한다.
              이미 있는 rule 은 지우지 않는다(사람 결정 보존).
- consensus : 동까지 맞은 매칭(아래 VOTE_METHODS)만 표로 센다. 3건 이상이고 90% 이상이
              한 단지면 합의. rule 이 있는 aptSeq 는 건너뛴다. 밤마다 다시 만든다.

aptSeq 는 아파트 매매(transactions.apt_seq)·전월세(rentals.raw.aptSeq)에만 있다.
오피스텔·분양권 원천에는 없다.

    python scripts/build_tx_seq_map.py            # 보고만(쓰지 않음)
    python scripts/build_tx_seq_map.py --apply    # tx_seq_map 갱신
    python scripts/build_tx_seq_map.py --db PATH  # 다른 DB
"""
from __future__ import annotations

import argparse
import collections
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.realprice import matching as rp_match  # noqa: E402

# 동까지 검증된 매칭만 투표한다. 'jibun'(동 표기 차이·동 불일치 섞임)·substr·fuzzy·
# naver_search(동 검증 없음)·seq(자기 자신) 는 투표하지 않는다.
VOTE_METHODS = ("jibun+dong", "road+dong+name", "bonbun+dong+name", "exact+dong", "token+dong+area")
# 여기에 더해, 거래 단지명과 단지 이름의 번호가 어긋나는 표(상계주공7 → 상계주공2단지)는 버린다.
# 지금 DB 에 남아 있는 옛 오매칭이 합의로 굳지 않게 하려는 것.
MIN_VOTES = 3
MIN_SHARE = 0.9

SOURCES = (("transactions", "apt_seq"), ("rentals", "json_extract(raw,'$.aptSeq')"))


def collect(conn: sqlite3.Connection):
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    manual: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    names = {r[0]: r[1] or "" for r in conn.execute("SELECT complex_no, complex_name FROM complexes")}
    dg_cache: dict[tuple[str, str], bool] = {}
    for tbl, seqexpr in SOURCES:
        q = (f"SELECT {seqexpr}, matched_complex_no, matched_method, manual_override, apt_nm FROM {tbl} "
             f"WHERE matched_complex_no IS NOT NULL")
        for seq, cno, method, man, apt in conn.execute(q):
            if not seq:
                continue
            if man:
                manual[seq][cno] += 1
            elif method in VOTE_METHODS:
                k = (apt or "", cno)
                ok = dg_cache.get(k)
                if ok is None:
                    ok = dg_cache[k] = rp_match.digits_compatible(apt or "", names.get(cno, ""))
                if ok:
                    votes[seq][cno] += 1
    return votes, manual


def compute(conn: sqlite3.Connection) -> dict:
    """{'rules': {seq:(cno,n)}, 'consensus': {seq:(cno,n,share)}, 'conflicts': [...], 'split': [...]}"""
    votes, manual = collect(conn)
    existing_rules = {}
    try:
        existing_rules = {r[0]: r[1] for r in conn.execute("SELECT apt_seq, complex_no FROM tx_seq_map WHERE source='rule'")}
    except sqlite3.Error:
        pass
    rules: dict[str, tuple[str, int]] = {}
    conflicts = []
    for seq, cnt in manual.items():
        if len(cnt) == 1:
            cno, n = next(iter(cnt.items()))
            rules[seq] = (cno, n)
        else:
            conflicts.append((seq, dict(cnt)))
    for seq, cno in existing_rules.items():
        rules.setdefault(seq, (cno, 0))
    consensus: dict[str, tuple[str, int, float]] = {}
    split = []
    for seq, cnt in votes.items():
        if seq in rules:
            continue
        tot = sum(cnt.values())
        cno, n = cnt.most_common(1)[0]
        if n >= MIN_VOTES and n / tot >= MIN_SHARE:
            consensus[seq] = (cno, n, round(n / tot, 3))
        elif tot >= MIN_VOTES:
            split.append((seq, dict(cnt)))
    return {"rules": rules, "consensus": consensus, "conflicts": conflicts, "split": split,
            "existing_rules": existing_rules}


def as_seq_map(res: dict) -> dict[str, tuple[str, str]]:
    out = {s: (c, "consensus") for s, (c, _n, _sh) in res["consensus"].items()}
    out.update({s: (c, "rule") for s, (c, _n) in res["rules"].items()})
    return out


def apply(conn: sqlite3.Connection, res: dict) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.executescript(rp_match.SEQ_SCHEMA)
    conn.execute("DELETE FROM tx_seq_map WHERE source='consensus'")
    conn.executemany(
        "INSERT OR IGNORE INTO tx_seq_map(apt_seq, complex_no, source, votes, share, note, updated_at) "
        "VALUES (?,?,'rule',?,1.0,'manual_override 행에서',?)",
        [(s, c, n, now) for s, (c, n) in res["rules"].items() if s not in res["existing_rules"]])
    conn.executemany(
        "INSERT OR IGNORE INTO tx_seq_map(apt_seq, complex_no, source, votes, share, note, updated_at) "
        "VALUES (?,?,'consensus',?,?,NULL,?)",
        [(s, c, n, sh, now) for s, (c, n, sh) in res["consensus"].items()])
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    if a.db:
        db = a.db
    else:
        from collector.config import settings
        db = str(settings.local_db_path)
    t0 = time.time()
    if a.apply:
        conn = sqlite3.connect(db, timeout=60)
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute("PRAGMA journal_size_limit=1073741824")
    else:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    res = compute(conn)
    print(f"[seq_map] rule {len(res['rules']):,} (기존 {len(res['existing_rules']):,}) · consensus {len(res['consensus']):,} · "
          f"규칙 충돌 {len(res['conflicts']):,} · 합의 갈림 {len(res['split']):,} · {time.time() - t0:.0f}s")
    for seq, cnt in res["conflicts"][:10]:
        print("  conflict", seq, cnt)
    if a.apply:
        apply(conn, res)
        print("[seq_map] 저장 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
