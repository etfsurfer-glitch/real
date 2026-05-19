"""실거래가 매칭률을 여러 시군구로 검증."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sqlite3
from collections import Counter

# Re-use probe utilities
from scripts.probe_realprice import (  # noqa: E402
    base_normalize,
    build_address_index,
    build_index,
    fetch,
    match_one,
    name_variants,
    parse_items,
)
from collector.config import settings  # noqa: E402


def load_complexes_under(conn, sgg_cortar5: str) -> list[dict]:
    cur = conn.execute(
        """
        SELECT c.complex_no, c.complex_name, c.cortar_no, c.detail_address, r.cortar_name as dong_name
        FROM complexes c
        LEFT JOIN regions r ON r.cortar_no = c.cortar_no
        WHERE c.cortar_no LIKE ?
        """,
        (sgg_cortar5 + "%",),
    )
    out = []
    for r in cur.fetchall():
        out.append({
            "complex_no": r[0],
            "complex_name": r[1] or "",
            "cortar_no": r[2],
            "detail_address": (r[3] or "").strip(),
            "dong_name": r[4] or "",
            "variants": name_variants(r[1] or ""),
        })
    return out


def test_area(conn, lawd_cd: str, deal_ymd: str, label: str) -> dict:
    body = fetch(lawd_cd, deal_ymd)
    items, meta = parse_items(body)
    complexes = load_complexes_under(conn, lawd_cd)
    idx = build_index(complexes)
    addr_idx = build_address_index(complexes)
    counts = Counter()
    for tx in items:
        _, method = match_one(tx, complexes, idx, addr_idx)
        counts[method] += 1
    total = len(items)
    matched = total - counts["unmatched"] - counts["no-name"]
    print(f"\n=== {label} ({lawd_cd}, {deal_ymd}) ===")
    print(f"  complexes in DB: {len(complexes)}")
    print(f"  transactions:    {total}")
    # show every method with a count, fuzzy variants included
    preferred = ["jibun+dong", "jibun", "exact+dong", "exact",
                 "substr+dong", "substr"]
    fuzzy_methods = sorted(m for m in counts if m.startswith("fuzzy"))
    tail = ["unmatched", "no-name"]
    for m in preferred + fuzzy_methods + tail:
        if counts.get(m):
            print(f"    {m:<22} {counts[m]:>5}  ({counts[m]*100/total:.1f}%)")
    rate = matched / total * 100 if total else 0
    print(f"  match rate: {rate:.1f}%")
    return {"label": label, "total": total, "matched": matched, "rate": rate}


def main() -> int:
    conn = sqlite3.connect(str(settings.local_db_path))
    results = []
    for lawd_cd, label in [
        ("11650", "서울 서초구"),
        ("11680", "서울 강남구"),
        ("11710", "서울 송파구"),
        ("26350", "부산 해운대구"),
        ("44131", "충남 천안시 서북구"),
    ]:
        try:
            results.append(test_area(conn, lawd_cd, "202604", label))
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {label}: {e}")

    print("\n=== 요약 ===")
    for r in results:
        print(f"  {r['label']:<20} {r['matched']:>4}/{r['total']:<4} = {r['rate']:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
