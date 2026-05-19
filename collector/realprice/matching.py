"""실거래 → Naver complex 매칭 로직.

전략 (강력순):
  1. 지번 매칭: (sggCd 5자리, jibun) == (complex.cortar_no[:5], complex.detail_address)
     단지명 표기 변형 무시. 도시권에서 95%+ 적중.
  2. 단지명 exact: 정규화 + 변종(차수/괄호/영한/접미사) 인덱스 hit
  3. 단지명 substring: 부분 일치 (양방향)
  4. SequenceMatcher fuzzy: ratio ≥ 0.85, 동 필터 필수 (수↔슈 등)

match_one_with_trace는 결정 + 후보 top-N + 사유를 dict로 반환 — 관리자
디버그용. transactions.match_details JSONB로 저장하면 관리자 페이지에서
"왜 이렇게 매칭됐나" 추적 가능.
"""
from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

_PAREN_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_CHA_RE = re.compile(r"(\d+)\s*차")
_NORM_TRIM = re.compile(r"[\s\-_·・,\.·]+")

ROMAN_TO_DIGIT = {
    "Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
    "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10",
    "ⅰ": "1", "ⅱ": "2", "ⅲ": "3", "ⅳ": "4", "ⅴ": "5",
}

# English ↔ Korean brand-name pairs seen inconsistently across sources.
EN_KO_PAIRS = [
    ("sk", "에스케이"),
    ("lg", "엘지"),
    ("lh", "엘에이치"),
    ("kcc", "케이씨씨"),
    ("gs", "지에스"),
    ("e편한세상", "이편한세상"),
]

# Common trailing tokens used to generate "core name" variants.
_GENERIC_SUFFIXES = ("아파트", "빌라트", "타운", "하우스", "맨션")

_LEADING_ZEROS_RE = re.compile(r"^0+")


def base_normalize(s: str) -> str:
    if not s:
        return ""
    s = _PAREN_RE.sub("", s)
    for r, d in ROMAN_TO_DIGIT.items():
        s = s.replace(r, d)
    s = s.lower()
    s = _CHA_RE.sub(r"\1", s)
    return _NORM_TRIM.sub("", s)


def name_variants(name: str) -> set[str]:
    """All reasonable normalized forms of a single name."""
    base = base_normalize(name)
    if not base:
        return set()
    variants = {base}
    for en, ko in EN_KO_PAIRS:
        new_set: set[str] = set()
        for v in variants:
            if en in v:
                new_set.add(v.replace(en, ko))
            if ko in v:
                new_set.add(v.replace(ko, en))
        variants |= new_set
    # Generic suffix strip + trailing-digit strip (lossy variants kept alongside base)
    for v in list(variants):
        for suf in _GENERIC_SUFFIXES:
            if v.endswith(suf) and len(v) > len(suf) + 1:
                variants.add(v[: -len(suf)])
        stripped = re.sub(r"\d+$", "", v)
        if stripped and stripped != v and len(stripped) > 1:
            variants.add(stripped)
    return variants


def normalize_jibun(s: str) -> str:
    """'0055-0012' → '55-12'. Both bonbun-bubun and Naver detail_address."""
    if not s:
        return ""
    s = s.strip()
    parts = s.split("-")
    if all(p.isdigit() for p in parts):
        return "-".join(_LEADING_ZEROS_RE.sub("", p) or "0" for p in parts)
    return s


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def load_complexes(conn: sqlite3.Connection, cortar_prefix: str | None = None
                   ) -> list[dict]:
    """Load complexes (+region dong) into match-ready dicts.

    cortar_prefix: filter to complexes whose cortar_no starts with this (e.g.
    "1165" for 서초구, "11" for 서울). None = all.
    """
    sql = (
        "SELECT c.complex_no, c.complex_name, c.cortar_no, c.detail_address, "
        "       r.cortar_name "
        "FROM complexes c LEFT JOIN regions r ON r.cortar_no = c.cortar_no"
    )
    params: tuple = ()
    if cortar_prefix:
        sql += " WHERE c.cortar_no LIKE ?"
        params = (cortar_prefix + "%",)
    cur = conn.execute(sql, params)
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


def build_name_index(complexes: list[dict]) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for c in complexes:
        for v in c["variants"]:
            idx.setdefault(v, []).append(c)
    return idx


def build_address_index(complexes: list[dict]) -> dict[tuple[str, str], list[dict]]:
    idx: dict[tuple[str, str], list[dict]] = {}
    for c in complexes:
        sgg5 = (c.get("cortar_no") or "")[:5]
        addr = normalize_jibun(c.get("detail_address") or "")
        if sgg5 and addr:
            idx.setdefault((sgg5, addr), []).append(c)
    return idx


class ComplexIndex:
    """Bundle name + address indexes + complex list for repeated lookups."""

    def __init__(self, complexes: list[dict]):
        self.complexes = complexes
        self.name_idx = build_name_index(complexes)
        self.addr_idx = build_address_index(complexes)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD = 0.85


def _candidate_summary(c: dict, method: str, score: float, reason: str) -> dict:
    return {
        "complex_no": c["complex_no"],
        "complex_name": c["complex_name"],
        "cortar_no": c["cortar_no"],
        "detail_address": c.get("detail_address", ""),
        "dong_name": c["dong_name"],
        "method": method,
        "score": round(score, 4),
        "reason": reason,
    }


def match_one_with_trace(tx: dict, index: ComplexIndex,
                         keep_top: int = 5) -> dict:
    """Match a single transaction. Returns a dict suitable for storage as
    transactions.match_details JSONB.

    Schema:
        {
          "tx": {aptNm, umdNm, sggCd, jibun, excluUseAr},
          "tx_variants": [...],
          "candidates": [{complex_no, complex_name, method, score, reason}, ...],
          "chosen": {complex_no, method, score} or null,
        }
    """
    apt = tx.get("aptName") or tx.get("aptNm") or ""
    umd = tx.get("umdNm") or tx.get("legalDong") or ""
    sgg = (tx.get("sggCd") or "").strip()
    jibun = normalize_jibun(tx.get("jibun") or "")
    excl = tx.get("excluUseAr") or ""

    tx_variants = name_variants(apt)
    candidates: list[dict] = []

    # ---- 0. 지번 매칭 ----
    if sgg and jibun and (sgg, jibun) in index.addr_idx:
        for c in index.addr_idx[(sgg, jibun)]:
            method = "jibun+dong" if (umd and umd in c["dong_name"]) else "jibun"
            score = 1.0 if method == "jibun+dong" else 0.95
            candidates.append(
                _candidate_summary(c, method, score, f"sgg+jibun=({sgg},{jibun})")
            )

    # ---- 1. exact variant ----
    if not candidates:
        for v in tx_variants:
            for c in index.name_idx.get(v, []):
                method = "exact+dong" if (umd and umd in c["dong_name"]) else "exact"
                score = 0.95 if method == "exact+dong" else 0.85
                candidates.append(
                    _candidate_summary(c, method, score, f"variant={v!r}")
                )

    # ---- 2. substring ----
    if not candidates:
        for c in index.complexes:
            hit = False
            reason = ""
            for cn in c["variants"]:
                if not cn:
                    continue
                for tn in tx_variants:
                    if cn in tn or tn in cn:
                        hit = True
                        reason = f"substr(c={cn!r}, t={tn!r})"
                        break
                if hit:
                    break
            if hit:
                method = "substr+dong" if (umd and umd in c["dong_name"]) else "substr"
                score = 0.75 if method == "substr+dong" else 0.55
                candidates.append(_candidate_summary(c, method, score, reason))

    # ---- 3. fuzzy (dong-restricted) ----
    if not candidates and umd and tx_variants:
        best: dict | None = None
        best_score = 0.0
        best_reason = ""
        for c in index.complexes:
            if c["dong_name"] and umd not in c["dong_name"]:
                continue
            for cn in c["variants"]:
                if not cn:
                    continue
                for tn in tx_variants:
                    r = SequenceMatcher(None, tn, cn).ratio()
                    if r > best_score:
                        best_score = r
                        best = c
                        best_reason = f"seqmatch({tn!r} vs {cn!r})={r:.3f}"
        if best is not None and best_score >= FUZZY_THRESHOLD:
            candidates.append(
                _candidate_summary(best, "fuzzy+dong", best_score, best_reason)
            )

    # Sort candidates by score desc, then by method preference
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:keep_top]

    chosen = None
    if candidates:
        c0 = candidates[0]
        chosen = {
            "complex_no": c0["complex_no"],
            "method": c0["method"],
            "score": c0["score"],
        }

    return {
        "tx": {
            "aptNm": apt,
            "umdNm": umd,
            "sggCd": sgg,
            "jibun": jibun,
            "excluUseAr": excl,
        },
        "tx_variants": sorted(tx_variants),
        "candidates": candidates,
        "chosen": chosen,
    }


def match_one(tx: dict, index: ComplexIndex) -> tuple[str | None, str, float]:
    """Compact variant: just (complex_no, method, score) — no trace overhead."""
    trace = match_one_with_trace(tx, index, keep_top=1)
    if trace["chosen"]:
        ch = trace["chosen"]
        return ch["complex_no"], ch["method"], ch["score"]
    return None, "unmatched", 0.0
