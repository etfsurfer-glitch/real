"""Naver new.land 단지명 검색을 이용한 reverse lookup.

local matching이 실패한 거래에 대해 Naver search/complex API로
역조회해서 매칭. 토큰 순서 변형 (삼주용산타운 ↔ 용산삼주타운),
차수 위치 (정관1차동원로얄듀크 ↔ 정관동원로얄듀크1차),
괄호 (경성큰마을(2단지) ↔ 큰마을경성2단지) 케이스 처리.
"""
from __future__ import annotations

import re

from ..http import get_json

SEARCH_URL = "https://new.land.naver.com/api/search/complex"


def _query_variants(name: str) -> list[str]:
    """Progressively relaxed query forms. Order matters — try more specific first."""
    out: list[str] = []
    seen = set()

    def add(s: str) -> None:
        s = (s or "").strip()
        if s and len(s) > 1 and s not in seen:
            seen.add(s)
            out.append(s)

    add(name)
    s1 = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name).strip()
    add(s1)
    s_base = s1 or name
    # strip "1차" → leave "1"
    add(re.sub(r"(\d+)\s*차", r"\1", s_base))
    # strip "1차" entirely
    add(re.sub(r"\d+\s*차", "", s_base).strip())
    # strip "1단지" entirely (case "경성큰마을(2단지)" already covered by paren strip)
    add(re.sub(r"\d+\s*단지", "", s_base).strip())
    # Prefix-strip variants — Naver search is order-sensitive; "큰마을경성"
    # ranks differently from "경성큰마을". Try dropping leading 2-3 chars so a
    # brand-only query like "큰마을" or "메트로자이" can still surface candidates
    # that get narrowed by sgg + digit filter downstream.
    digits_stripped = re.sub(r"\d+\s*(?:차|단지)?", "", s_base).strip()
    for source in (digits_stripped, s_base):
        if len(source) >= 4:
            for cut in (2, 3):
                add(source[cut:].strip())
    return out


def search_complex(query: str, creds: dict) -> list[dict]:
    """Single Naver search/complex call. Returns list of complex dicts."""
    status, data = get_json(SEARCH_URL, creds, params={"query": query})
    if status != 200 or not isinstance(data, dict):
        return []
    return data.get("list") or data.get("complexes") or []


_ALNUM_RE = re.compile(r"[^가-힣A-Za-z0-9]")


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _names_compatible(tx_name: str, candidate_name: str,
                      bigram_min: float = 0.30, char_min: float = 0.55) -> bool:
    """Reject obviously unrelated names. Catches "대안IPARK" vs "현대" type
    false positives while still allowing "GS메트로자이" vs "광려천메트로자이"
    (shared brand)."""
    a = _ALNUM_RE.sub("", tx_name).lower()
    b = _ALNUM_RE.sub("", candidate_name).lower()
    if not a or not b:
        return False
    bg_a, bg_b = _bigrams(a), _bigrams(b)
    if bg_a and bg_b:
        bg_overlap = len(bg_a & bg_b) / max(len(bg_a), len(bg_b))
    else:
        bg_overlap = 0.0
    chars_a, chars_b = set(a), set(b)
    char_overlap = len(chars_a & chars_b) / max(len(chars_a), len(chars_b))
    return bg_overlap >= bigram_min or char_overlap >= char_min


def lookup_match(
    apt_nm: str,
    sgg_cd: str,
    creds: dict,
    known_complex_nos: set[str] | None = None,
) -> tuple[str | None, str, float, dict]:
    """Try variants until we find a sgg-matching Naver complex.

    Returns (complex_no, method, score, debug_dict) where debug_dict captures
    the variants tried + first hit details for transactions.match_details.
    """
    debug: dict = {"variants_tried": [], "hits": []}
    digits = re.findall(r"\d+", apt_nm)

    for v in _query_variants(apt_nm):
        results = search_complex(v, creds)
        debug["variants_tried"].append({"query": v, "n_results": len(results)})
        if not results:
            continue
        sgg_filtered = [
            r for r in results
            if (r.get("cortarNo") or "")[:5] == sgg_cd
        ]
        if not sgg_filtered:
            continue
        if known_complex_nos:
            in_db = [r for r in sgg_filtered
                     if str(r.get("complexNo") or "") in known_complex_nos]
            candidates = in_db or sgg_filtered
        else:
            candidates = sgg_filtered
        debug["hits"] = [
            {"complex_no": c.get("complexNo"),
             "complex_name": c.get("complexName"),
             "base_address": c.get("baseAddress")}
            for c in candidates[:5]
        ]
        # Strict digit-hint: tx has digit → candidate must contain that digit.
        # If no candidate matches, fall through to next variant rather than
        # accepting a wrong digit (e.g. "에코르3단지" ↛ "에코르2단지").
        if digits:
            for d in digits:
                digit_match = [c for c in candidates
                               if d in (c.get("complexName") or "")]
                if digit_match:
                    chosen = digit_match[0]
                    if _names_compatible(apt_nm, chosen.get("complexName") or ""):
                        return (
                            str(chosen["complexNo"]),
                            "naver_search+digit",
                            0.85,
                            debug,
                        )
            continue  # digit constraint unmet for this variant — try next

        # No digit constraint — require name compatibility to filter out
        # accidental hits like "대안IPARK" ↛ "현대".
        compat = [
            c for c in candidates
            if _names_compatible(apt_nm, c.get("complexName") or "")
        ]
        if compat:
            chosen = compat[0]
            chosen_name = chosen.get("complexName") or ""
            # Boost to 0.90 if it's a pure token-order swap (same chars).
            # E.g., 삼주용산타운 ↔ 용산삼주타운 / 거성수락산 ↔ 수락산거성.
            tx_chars = sorted(_ALNUM_RE.sub("", apt_nm).lower())
            cn_chars = sorted(_ALNUM_RE.sub("", chosen_name).lower())
            if tx_chars == cn_chars and tx_chars:
                return (
                    str(chosen["complexNo"]),
                    "naver_search+swap",
                    0.90,
                    debug,
                )
            return (
                str(chosen["complexNo"]),
                f"naver_search via {v!r}",
                0.75,
                debug,
            )
        # else fall through

    return None, "naver_search_unmatched", 0.0, debug
