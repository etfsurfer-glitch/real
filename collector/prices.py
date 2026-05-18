"""Korean Won price text -> integer Won.

Examples:
    "5억 8,000"  -> 580_000_000   (5억 + 8000만)
    "10억"        -> 1_000_000_000
    "9,500"      -> 95_000_000    (만원 단위)
    "120"        -> 1_200_000     (월세 120만원)
    "1,000/120"  -> (10_000_000, 1_200_000)   via parse_rent
    ""/None      -> None
"""
from __future__ import annotations

import re

_EOK = re.compile(r"^(\d+(?:\.\d+)?)\s*억(.*)$")


def parse_price_text(text: str | None) -> int | None:
    if not text:
        return None
    s = str(text).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    total = 0
    m = _EOK.match(s)
    if m:
        eok = float(m.group(1))
        total += int(eok * 100_000_000)
        rest = m.group(2)
        if rest:
            try:
                total += int(rest) * 10_000
            except ValueError:
                pass
        return total
    try:
        return int(s) * 10_000  # bare number is 만원
    except ValueError:
        return None


def parse_rent_pair(text: str | None) -> tuple[int | None, int | None]:
    """Some rent fields appear as 'deposit/monthly' (e.g. '1,000/120')."""
    if not text or "/" not in str(text):
        return parse_price_text(text), None
    left, right = str(text).split("/", 1)
    return parse_price_text(left), parse_price_text(right)
