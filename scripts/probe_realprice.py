"""실거래가 API Phase A — fetch 서초구 1 month, parse XML, measure match rate
against our complexes table.

No DB writes. Read-only probe to decide if Phase B (nationwide backfill) is
worth doing.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402

API = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
LAWD_CD = "11650"  # 서초구 (cortar_no 1165000000의 앞 5자리)
DEAL_YMD = "202604"  # 2026-04


def fetch(lawd_cd: str, deal_ymd: str, page_no: int = 1, num_rows: int = 1000) -> bytes:
    if not settings.data_go_kr_service_key:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY missing in .env")
    qs = urllib.parse.urlencode({
        "serviceKey": settings.data_go_kr_service_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
    })
    url = f"{API}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/xml"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_items(xml_bytes: bytes) -> tuple[list[dict], dict]:
    root = ET.fromstring(xml_bytes)
    # Detect error envelope
    err = root.find(".//errMsg")
    if err is not None:
        auth = root.find(".//returnAuthMsg")
        msg = err.text or ""
        if auth is not None:
            msg += f" ({auth.text})"
        raise RuntimeError(f"API error: {msg}")
    header = root.find(".//header")
    rc = header.findtext("resultCode") if header is not None else ""
    rm = header.findtext("resultMsg") if header is not None else ""
    # 000/00/0 are all "OK" depending on which data.go.kr service
    if rc and rc.lstrip("0") not in ("",):
        raise RuntimeError(f"API error: {rc} {rm}")
    items: list[dict] = []
    for it in root.iter("item"):
        rec = {child.tag: (child.text or "").strip() for child in it}
        items.append(rec)
    body = root.find(".//body")
    meta = {}
    if body is not None:
        for k in ("numOfRows", "pageNo", "totalCount"):
            meta[k] = body.findtext(k)
    return items, meta


_PAREN_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_CHA_RE = re.compile(r"(\d+)\s*차")
_NORM_TRIM = re.compile(r"[\s\-_·・,\.·]+")
# Common trailing tokens to strip when generating "core name" variants.
# Risk: false positives — only used as fallback variants, not primary key.
_GENERIC_SUFFIXES = (
    "아파트", "빌라트", "타운", "하우스", "맨션",
)

# Roman numerals → Arabic digits (only ones realistically seen in apt names)
ROMAN_TO_DIGIT = {
    "Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
    "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10",
    "ⅰ": "1", "ⅱ": "2", "ⅲ": "3", "ⅳ": "4", "ⅴ": "5",
}

# English↔Korean brand-name pairs that appear inconsistently across sources.
EN_KO_PAIRS = [
    ("sk", "에스케이"),
    ("lg", "엘지"),
    ("lh", "엘에이치"),
    ("kcc", "케이씨씨"),
    ("gs", "지에스"),
    ("e편한세상", "이편한세상"),
]


def base_normalize(s: str) -> str:
    """Lossless-ish normalization: strip parens/차/whitespace, romanize, lowercase."""
    if not s:
        return ""
    # Remove (...) and [...] (often contains 동 numbers, building tags)
    s = _PAREN_RE.sub("", s)
    # Roman → digit
    for r, d in ROMAN_TO_DIGIT.items():
        s = s.replace(r, d)
    # Lowercase (helps en brand match)
    s = s.lower()
    # "1차" → "1"  (드물게 표기 다름)
    s = _CHA_RE.sub(r"\1", s)
    # Drop separators
    s = _NORM_TRIM.sub("", s)
    return s


def name_variants(name: str) -> set[str]:
    """Generate all reasonable normalized forms (en/ko brand swaps + suffix strip)."""
    base = base_normalize(name)
    if not base:
        return set()
    variants = {base}
    # English ↔ Korean brand swaps (small fixed list; harmless if no match)
    for en, ko in EN_KO_PAIRS:
        new_set: set[str] = set()
        for v in variants:
            if en in v:
                new_set.add(v.replace(en, ko))
            if ko in v:
                new_set.add(v.replace(ko, en))
        variants |= new_set
    # Generic suffix strip (only as additional variants — base name still in set)
    for v in list(variants):
        for suf in _GENERIC_SUFFIXES:
            if v.endswith(suf) and len(v) > len(suf) + 1:
                variants.add(v[: -len(suf)])
        # Also strip trailing digits as a *separate* variant (so "우성5" → "우성")
        stripped = re.sub(r"\d+$", "", v)
        if stripped and stripped != v and len(stripped) > 1:
            variants.add(stripped)
    return variants


def load_complexes_in_seocho(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        """
        SELECT c.complex_no, c.complex_name, c.cortar_no, c.detail_address, r.cortar_name as dong_name
        FROM complexes c
        LEFT JOIN regions r ON r.cortar_no = c.cortar_no
        WHERE c.cortar_no LIKE '1165%'
        """
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


def build_index(complexes: list[dict]) -> dict[str, list[dict]]:
    """Map every variant form → list of complexes that match it."""
    idx: dict[str, list[dict]] = {}
    for c in complexes:
        for v in c["variants"]:
            idx.setdefault(v, []).append(c)
    return idx


def build_address_index(complexes: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """(시군구 5자리, 지번) → 단지 후보. 지번 표기 정규화 포함."""
    idx: dict[tuple[str, str], list[dict]] = {}
    for c in complexes:
        sgg5 = (c.get("cortar_no") or "")[:5]
        addr = _normalize_jibun(c.get("detail_address", ""))
        if sgg5 and addr:
            idx.setdefault((sgg5, addr), []).append(c)
    return idx


_LEADING_ZEROS_RE = re.compile(r"^0+")


def _normalize_jibun(s: str) -> str:
    """'0055-0012' → '55-12', '1597-6' → '1597-6'. 'bon-bu' 표준화."""
    if not s:
        return ""
    s = s.strip()
    # If looks like "NNN-NNN" or "NNN", strip leading zeros from each segment.
    parts = s.split("-")
    if all(p.isdigit() for p in parts):
        return "-".join(_LEADING_ZEROS_RE.sub("", p) or "0" for p in parts)
    return s


_FUZZY_THRESHOLD = 0.85


def _fuzzy_best(tx_variants: set[str], complexes: list[dict], umd: str
                ) -> tuple[dict, float] | None:
    """Last-resort SequenceMatcher fuzzy match, restricted to same 동 if known.
    Threshold 0.85 catches 수↔슈, 휘↔휴 등 single-char transliteration drift.
    """
    best: dict | None = None
    best_ratio = 0.0
    for c in complexes:
        if umd and c["dong_name"] and umd not in c["dong_name"]:
            continue
        for cn in c["variants"]:
            if not cn:
                continue
            for tn in tx_variants:
                r = SequenceMatcher(None, tn, cn).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best = c
    if best is not None and best_ratio >= _FUZZY_THRESHOLD:
        return best, best_ratio
    return None


def match_one(tx: dict, complexes: list[dict], idx: dict[str, list[dict]],
              addr_idx: dict[tuple[str, str], list[dict]] | None = None
              ) -> tuple[str | None, str]:
    apt = tx.get("aptName") or tx.get("aptNm") or ""
    umd = tx.get("umdNm") or tx.get("legalDong") or ""
    sgg = (tx.get("sggCd") or "").strip()
    jibun = _normalize_jibun(tx.get("jibun") or "")
    tx_variants = name_variants(apt)

    # 0. 지번 매칭 (가장 강력) — 단지명 표기 변형 무시
    if sgg and jibun and addr_idx and (sgg, jibun) in addr_idx:
        candidates = addr_idx[(sgg, jibun)]
        if umd:
            narrow = [c for c in candidates if umd in c["dong_name"]]
            if narrow:
                return narrow[0]["complex_no"], "jibun+dong"
        return candidates[0]["complex_no"], "jibun"

    if not tx_variants:
        return None, "no-name"

    # 1. Exact variant lookup via index (O(1))
    for v in tx_variants:
        if v in idx:
            candidates = idx[v]
            if umd:
                narrow = [c for c in candidates if umd in c["dong_name"]]
                if narrow:
                    return narrow[0]["complex_no"], "exact+dong"
            return candidates[0]["complex_no"], "exact"

    # 2. Substring fallback — bidirectional containment
    for c in complexes:
        for cn in c["variants"]:
            if not cn:
                continue
            for tn in tx_variants:
                if cn in tn or tn in cn:
                    if umd and c["dong_name"] and umd in c["dong_name"]:
                        return c["complex_no"], "substr+dong"
                    return c["complex_no"], "substr"

    # 3. Fuzzy fallback (dong-restricted) — for 수↔슈 etc.
    if umd:
        result = _fuzzy_best(tx_variants, complexes, umd)
        if result:
            c, ratio = result
            return c["complex_no"], f"fuzzy+dong({ratio:.2f})"

    return None, "unmatched"


def main() -> int:
    print(f"[*] LAWD_CD={LAWD_CD} (서초구)  DEAL_YMD={DEAL_YMD}")
    print(f"[*] service key: {settings.data_go_kr_service_key[:20]}...")

    print("\n[1] fetch")
    body = fetch(LAWD_CD, DEAL_YMD)
    items, meta = parse_items(body)
    print(f"    items: {len(items)}  meta: {meta}")
    if items:
        sample = items[0]
        print("    sample fields:")
        for k in sorted(sample.keys())[:30]:
            v = sample[k][:60] if sample[k] else ""
            print(f"      {k:<24} = {v}")

    print("\n[2] load 서초구 complexes from SQLite")
    conn = sqlite3.connect(str(settings.local_db_path))
    complexes = load_complexes_in_seocho(conn)
    print(f"    complexes: {len(complexes)}")
    idx = build_index(complexes)
    addr_idx = build_address_index(complexes)
    print(f"    variant index: {len(idx)}  address index: {len(addr_idx)}")

    print("\n[3] match transactions to complexes")
    counts = Counter()
    matched_names: dict[str, set[str]] = {}
    for tx in items:
        complex_no, method = match_one(tx, complexes, idx, addr_idx)
        counts[method] += 1
        apt = (tx.get("aptName") or tx.get("aptNm") or "").strip()
        umd = (tx.get("umdNm") or "").strip()
        matched_names.setdefault(method, set()).add(f"{apt}  ({umd})")

    total = len(items)
    print(f"\n    total transactions: {total}")
    method_order = ("jibun+dong", "jibun", "exact+dong", "exact",
                    "substr+dong", "substr")
    fuzzy_keys = sorted(m for m in counts if m.startswith("fuzzy"))
    tail = ("unmatched", "no-name")
    for method in list(method_order) + fuzzy_keys + list(tail):
        if counts.get(method):
            pct = counts[method] * 100 / total if total else 0
            print(f"      {method:<22} {counts[method]:>5}  ({pct:.1f}%)")
    matched = total - counts["unmatched"] - counts["no-name"]
    print(f"\n    match rate: {matched}/{total} = {matched/total*100:.1f}%" if total else "n/a")

    if counts["unmatched"]:
        print("\n[4] unmatched 단지명 샘플 (max 20):")
        for nm in list(matched_names["unmatched"])[:20]:
            print(f"      {nm}")

    print("\n[5] 전체 transactions 가격 분포 (sanity)")
    prices = []
    for tx in items:
        p = (tx.get("dealAmount") or "").replace(",", "").strip()
        if p.isdigit():
            prices.append(int(p) * 10_000)  # 만원 → 원
    if prices:
        prices.sort()
        med = prices[len(prices) // 2]
        print(f"    n={len(prices)}  min={prices[0]:,}  median={med:,}  max={prices[-1]:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
