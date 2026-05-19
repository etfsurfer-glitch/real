"""의심 매칭(match_suggestions) 후보를 보수적 휴리스틱으로 자동 분류.

ACCEPT:
  - 영문↔한글 음차 (e편한세상↔이편한세상, IC↔아이시 등) 적용 후 normalize한
    두 이름이 같음
  - 한쪽이 다른 쪽의 substring이고 차이가 generic 접두/접미만 (대림/신도시 등
    잘 알려진 prefix; 또는 length diff < 40%)
REJECT:
  - tx 가 candidate에 없는 의미있는 토큰을 가짐 (예: 마을, 이수, 덕하)
  - SequenceMatcher ratio < 0.55
PENDING 유지:
  - 위 어느 쪽도 명확치 않은 경우

  python scripts/auto_review_suggestions.py            # dry-run: 분류만
  python scripts/auto_review_suggestions.py --apply    # API 호출해 accept/reject 적용
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.request
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402

ADMIN_BASE = "http://localhost:8001"

# Bidirectional Latin↔Korean transliteration pairs commonly seen in 아파트 brand naming.
# Order matters: longer first so multi-char tokens are replaced before single chars.
TRANSLIT_PAIRS = [
    ("e-편한세상", "이편한세상"),
    ("e편한세상", "이편한세상"),
    ("ipark", "아이파크"),
    ("kcc", "케이씨씨"),
    ("sk", "에스케이"),
    ("lg", "엘지"),
    ("gs", "지에스"),
    ("sr", "에스알"),
    ("ic", "아이시"),
    ("the", "더"),
]

# Tokens we consider "dropping is OK" — Naver sometimes omits these.
GENERIC_OPTIONAL = {"아파트", "타운", "마을", "단지"}

_NORM = re.compile(r"[\s\-_·・,\.\(\)\[\]]+")


def normalize(s: str) -> str:
    if not s:
        return ""
    # remove paren content
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", s)
    # "1차" → "1차" (no-op, but normalize 단지/N단지 to N)
    s = s.lower()
    s = _NORM.sub("", s)
    return s


def translit_variants(s: str) -> set[str]:
    out = {s}
    for la, ko in TRANSLIT_PAIRS:
        new = set()
        for v in out:
            if la in v:
                new.add(v.replace(la, ko))
            if ko in v:
                new.add(v.replace(ko, la))
        out |= new
    return out


def decide(tx_name: str, cn_name: str) -> tuple[str, str, float]:
    """Return (decision, reason, similarity)."""
    a = normalize(tx_name)
    b = normalize(cn_name)
    if not a or not b:
        return "pending", "empty name", 0.0

    a_set = translit_variants(a)
    b_set = translit_variants(b)

    # 1. translit-normalized exact match
    if a_set & b_set:
        return "accept", "translit_equal", 1.0

    # 2. substring containment (with translit) — check all variant pairs
    best_ratio = 0.0
    for av in a_set:
        for bv in b_set:
            r = SequenceMatcher(None, av, bv).ratio()
            if r > best_ratio:
                best_ratio = r
            if av and bv:
                if av in bv:
                    diff = bv.replace(av, "", 1)
                    # Naver added prefix/suffix — accept if not too much added
                    if len(diff) / max(len(bv), 1) < 0.50:
                        return "accept", f"tx_in_cn diff={diff!r}", r
                if bv in av:
                    diff = av.replace(bv, "", 1)
                    # tx has extra. Accept only if extra is a generic optional token.
                    if diff in GENERIC_OPTIONAL:
                        return "accept", f"cn_in_tx generic_drop={diff!r}", r
                    if not diff:
                        return "accept", "equal_after_norm", r
                    return "reject", f"tx_has_extra={diff!r}", r

    # 3. similarity threshold
    if best_ratio >= 0.85:
        return "accept", f"high_similarity={best_ratio:.2f}", best_ratio
    if best_ratio < 0.55:
        return "reject", f"low_similarity={best_ratio:.2f}", best_ratio
    return "pending", f"ambiguous_similarity={best_ratio:.2f}", best_ratio


def post(path: str) -> dict:
    req = urllib.request.Request(ADMIN_BASE + path, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true",
                   help="실제로 admin API 호출해 accept/reject 반영")
    args = p.parse_args()

    conn = sqlite3.connect(str(settings.local_db_path))
    rows = conn.execute(
        """
        SELECT s.suggestion_id, s.apt_nm, s.sgg_cd, s.tx_count,
               s.suggested_method, s.suggested_score,
               x.complex_name AS cn_name
        FROM match_suggestions s
        LEFT JOIN complexes x ON x.complex_no = s.suggested_complex_no
        WHERE s.status = 'pending'
        ORDER BY s.tx_count DESC
        """
    ).fetchall()
    print(f"[*] pending suggestions: {len(rows)}\n")

    decisions: dict[str, list[tuple]] = {"accept": [], "reject": [], "pending": []}
    counts = Counter()
    for sid, apt, sgg, n, method, score, cn in rows:
        dec, reason, sim = decide(apt, cn or "")
        decisions[dec].append((sid, apt, cn, n, dec, reason, sim))
        counts[dec] += 1

    for dec in ("accept", "reject", "pending"):
        items = decisions[dec]
        tx_sum = sum(x[3] for x in items)
        print(f"\n--- {dec.upper()} ({len(items)} groups, {tx_sum} tx) ---")
        for sid, apt, cn, n, _, reason, sim in items[:20]:
            print(f"  [{sid:>4}]  {apt:<26} → {cn:<26}  n={n:>4}  ({reason})")
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more")

    if not args.apply:
        print("\n--apply 추가하면 admin API로 반영")
        return 0

    print(f"\n[apply] calling admin API ...")
    n_accept = 0
    n_reject = 0
    for sid, apt, cn, n, _, _, _ in decisions["accept"]:
        try:
            r = post(f"/api/suggestions/{sid}/accept")
            n_accept += r.get("updated_tx", 0)
        except Exception as e:  # noqa: BLE001
            print(f"  ERR accept {sid}: {e}")
    for sid, *_ in decisions["reject"]:
        try:
            post(f"/api/suggestions/{sid}/reject")
            n_reject += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ERR reject {sid}: {e}")
    print(f"  accepted: {len(decisions['accept'])} groups → {n_accept} tx updated")
    print(f"  rejected: {n_reject} groups")
    print(f"  pending:  {len(decisions['pending'])} groups (manual review)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
