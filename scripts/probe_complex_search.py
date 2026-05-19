"""Naver new.land 단지명 검색 API 동작 확인.

   GET https://new.land.naver.com/api/search/complex?query=...

NAVER_API_PORTING.md §2.2: '1차: 인증 불필요 (Referer만)' — Bearer 없이 동작.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.creds import ensure_creds  # noqa: E402
from collector.http import get_json  # noqa: E402

# 사용자가 알려준 4개 케이스
CASES = [
    ("삼주용산타운", "용산삼주타운"),
    ("정관1차동원로얄듀크", "정관동원로얄듀크1차"),
    ("경성큰마을(2단지)", "큰마을경성2단지"),
    ("거성수락산", "수락산거성"),
]


def search(query: str, creds: dict) -> list[dict]:
    url = "https://new.land.naver.com/api/search/complex"
    status, data = get_json(url, creds, params={"query": query})
    if status != 200 or not isinstance(data, dict):
        print(f"  search({query!r}) -> {status}: {str(data)[:160]}")
        return []
    return data.get("list") or data.get("complexes") or []


import re


def query_variants(name: str) -> list[str]:
    """Generate progressively-relaxed search queries for Naver search/complex."""
    seen: list[str] = [name]
    # 1. strip 괄호
    s1 = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name).strip()
    if s1 and s1 != name:
        seen.append(s1)
    # 2. strip 차수 (1차/2차 등) — but keep the leading number too
    s2 = re.sub(r"(\d+)\s*차", r"\1", s1 or name)
    if s2 and s2 not in seen:
        seen.append(s2)
    # 3. strip trailing numbers entirely
    s3 = re.sub(r"\d+\s*차?$", "", s1 or name).strip()
    if s3 and s3 not in seen and len(s3) > 1:
        seen.append(s3)
    return seen


def main() -> int:
    creds = ensure_creds()
    print(f"[*] creds bearer={creds['bearer'][:20]}...\n")
    for tx_name, expected in CASES:
        print(f"=== 실거래 단지명: {tx_name!r}  (예상: {expected!r}) ===")
        variants = query_variants(tx_name)
        print(f"  variants: {variants}")
        for v in variants:
            results = search(v, creds)
            if results:
                print(f"  [hit via {v!r}] {len(results)} results")
                for i, r in enumerate(results[:3]):
                    print(f"    [{i}] {r.get('complexName')!r} (cortar {r.get('cortarNo')}, "
                          f"{r.get('baseAddress')})")
                break
        else:
            print("  ❌ 모든 variant에서 못 찾음")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
