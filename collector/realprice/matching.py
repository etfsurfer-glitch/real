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
# 두 표기가 같은 단지를 가리키는데 normalization 만으로는 안 합쳐지는 케이스.
# variant 생성에서 양방향으로 치환된 alternative 추가.
EN_KO_PAIRS = [
    # 약자 (단지명 전체)
    ("sk", "에스케이"),
    ("lg", "엘지"),
    ("lh", "엘에이치"),
    ("kcc", "케이씨씨"),
    ("gs", "지에스"),
    ("e편한세상", "이편한세상"),
    # 브랜드/접미어 합성어. Naver 마스터가 동일 단지를 "중흥S-클래스" /
    # "중흥에스-클래스" 로 일관성 없이 등록해 두는 패턴 해결.
    # 1글자 영문↔한글(예: 's'↔'에스')은 '단지' 의 '지' 가 'g' 로 치환되는 등
    # 부작용 큼. 합성어 단위로만 명시.
    ("sclass",  "에스클래스"),
    ("s클래스",  "에스클래스"),
    ("class",   "클래스"),
    ("city",    "시티"),
    ("park",    "파크"),
    ("tower",   "타워"),
    ("view",    "뷰"),
    ("hill",    "힐"),
    ("hills",   "힐스"),
    ("plus",    "플러스"),
    ("the",     "더"),
    ("center",  "센터"),
    ("centre",  "센터"),
    ("ipark",   "아이파크"),
    ("xi",      "자이"),
]
# 길이 긴 토큰부터 치환해 합성어 매칭을 먼저 잡는다.
EN_KO_PAIRS.sort(key=lambda kv: -max(len(kv[0]), len(kv[1])))

# Common trailing tokens used to generate "core name" variants.
_GENERIC_SUFFIXES = ("아파트", "빌라트", "타운", "하우스", "맨션")

# 흔한 브랜드 prefix. complex name 이 이 prefix 로 시작하면 prefix 를 떼어낸
# variant 를 추가로 생성. 거래 데이터의 단지명("옥수파크힐스117동~125동") 이
# 브랜드를 포함하지 않을 때도 substring 매칭에 도달 가능하게 함.
# (base_normalize 결과는 lowercase·whitespace 제거 상태 → 여기도 동일 포맷.)
_BRAND_PREFIXES_RAW = [
    # 흔한 시공사 브랜드. 단지명 앞에 붙는 경우가 잦음.
    "e편한세상", "이편한세상",
    "래미안", "푸르지오", "자이", "더샵", "롯데캐슬",
    "힐스테이트", "아이파크", "센트레빌", "위브", "두산위브",
    "데시앙", "베르디움", "꿈에그린", "한화꿈에그린",
    "코오롱하늘채", "하늘채", "에스케이뷰", "sk뷰",
    "호반베르디움", "호반써밋", "한신더휴", "한신휴플러스",
    "트리지움", "어울림",
    "벽산블루밍", "동부센트레빌", "현대홈타운",
    "한라비발디캐슬", "한라비발디",
    "우미린", "우방아이유쉘",
    "더플래티넘", "포레나", "디에이치",
]
_BRAND_PREFIXES = [_NORM_TRIM.sub("", b.lower()) for b in _BRAND_PREFIXES_RAW]

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
    # 브랜드 prefix 떼기: "e편한세상옥수파크힐스" → "옥수파크힐스" variant 추가.
    # 거래 데이터가 brand 없이 local 이름만 가지고 들어오는 경우(예: "옥수파크힐스
    # 117동~125동")도 substring 매칭 가능하게.
    for v in list(variants):
        for bp in _BRAND_PREFIXES:
            if v.startswith(bp) and len(v) > len(bp) + 2:  # local 이름 최소 3자
                variants.add(v[len(bp):])
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
    """'0055-0012' → '55-12'. data.go.kr jibun('1968') 과 Naver detail_address('신대리 1968').
    detail_address 는 동/리명이 앞에 붙는 경우가 많아('신대리 1968','역삼동 718-3') 끝의 지번만
    뽑아 둘을 일치시킨다. (이게 안 되면 '리명 지번' 단지가 지번매칭에서 통째로 빠져 오매칭됨)"""
    if not s:
        return ""
    s = s.strip()
    m = re.search(r"(\d+(?:-\d+)?)\s*$", s)   # 끝의 지번(본번 또는 본번-부번) 추출
    if m:
        s = m.group(1)
    parts = s.split("-")
    if all(p.isdigit() for p in parts):
        return "-".join(_LEADING_ZEROS_RE.sub("", p) or "0" for p in parts)
    return s


def bonbun_of(jibun: str) -> str:
    """'55-12' → '55'. 부지번(-12) 떼고 본번만. 같은 단지의 부속 지번 거래를
    본 지번 매칭으로 끌어들이는 fallback 용도."""
    if not jibun:
        return ""
    return jibun.split("-", 1)[0]


_ROAD_TRAIL_RE = re.compile(r"\d+\s*(번지|호)?\s*$")


def normalize_road(s: str) -> str:
    """'매봉길 50' → '매봉길', '독서당로 100번길 5' → '독서당로100번길'.

    한국 도로명 주소는 "○○로/길/대로 N" 형태로 끝에 번지가 붙음.
    공백 제거 + 끝 숫자 토큰(+ '번지'/'호' 접미사) 제거로 도로명 부분만 남김.
    거래측 road_nm 은 보통 번지 없이 도로명만(예: "매봉길"), 마스터의
    road_address 는 "매봉길 50" 처럼 번지 포함. 양쪽 normalize 후 일치 비교.
    """
    if not s:
        return ""
    s = re.sub(r"\s+", "", s.strip())
    # 끝 번지 제거 — 한 번만 (예: "독서당로100번길5" → "독서당로100번길")
    s = _ROAD_TRAIL_RE.sub("", s)
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
        "       c.road_address, r.cortar_name "
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
            "road_address_norm": normalize_road(r[4] or ""),
            "dong_name": r[5] or "",
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


def build_bonbun_index(complexes: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """(sgg5, bonbun_only) → 단지 목록. 부지번 fallback 용. 본번이 같은 단지가
    여럿 있으면 안전을 위해 매칭에서 제외(호출 측에서 len(list)==1 체크)."""
    idx: dict[tuple[str, str], list[dict]] = {}
    for c in complexes:
        sgg5 = (c.get("cortar_no") or "")[:5]
        addr = normalize_jibun(c.get("detail_address") or "")
        bb = bonbun_of(addr)
        if sgg5 and bb:
            idx.setdefault((sgg5, bb), []).append(c)
    return idx


def build_road_index(complexes: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """(sgg5, normalized_road_name) → 단지 목록. 도로명 매칭용. 같은 도로에
    여러 단지가 있을 수 있으므로 호출 측에서 단지명 verification 또는
    uniqueness check 필요."""
    idx: dict[tuple[str, str], list[dict]] = {}
    for c in complexes:
        sgg5 = (c.get("cortar_no") or "")[:5]
        road = c.get("road_address_norm") or ""
        if sgg5 and road:
            idx.setdefault((sgg5, road), []).append(c)
    return idx


class ComplexIndex:
    """Bundle name + address indexes + complex list for repeated lookups."""

    def __init__(self, complexes: list[dict]):
        self.complexes = complexes
        self.name_idx = build_name_index(complexes)
        self.addr_idx = build_address_index(complexes)
        self.bonbun_idx = build_bonbun_index(complexes)
        self.road_idx = build_road_index(complexes)


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
          "tx": {aptNm, umdNm, sggCd, jibun, roadNm, excluUseAr},
          "tx_variants": [...],
          "candidates": [{complex_no, complex_name, method, score, reason}, ...],
          "chosen": {complex_no, method, score} or null,
        }
    """
    apt = tx.get("aptName") or tx.get("aptNm") or tx.get("offiNm") or ""
    umd = tx.get("umdNm") or tx.get("legalDong") or ""
    sgg = (tx.get("sggCd") or "").strip()
    jibun = normalize_jibun(tx.get("jibun") or "")
    road = normalize_road(tx.get("roadNm") or tx.get("roadName") or "")
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

    # ---- 0b. 본번 fallback ----
    # jibun 528-1 매칭 실패 시, 본번 528 만으로 시도. 단, **단지명도 substring
    # 으로 일치할 때만** 채택. 그렇지 않으면 false-match 위험 큼.
    #
    # 예: 다산동 683번지에는 경남아너스빌(683), 진주(683-30), 청구(683-XX) 등
    # 여러 단지가 같은 본번 안에 모여있는 빌리지 형태. 본번만 보고 매칭하면
    # 진주 거래가 경남아너스빌로 빨려들어감. 단지명 검증으로 막는다.
    #
    # 옥수파크힐스(528-1) → 528 본단지 110938: name="e편한세상옥수파크힐스" 이
    # tx="옥수파크힐스117동~125동" 의 substring 이므로 통과 → 0.95.
    if not candidates and sgg and jibun:
        bb = bonbun_of(jibun)
        if bb and bb != jibun:
            bb_hits = index.bonbun_idx.get((sgg, bb), [])
            if len(bb_hits) == 1:
                c = bb_hits[0]
                # 단지명도 substring 으로 일치해야 채택. (양방향: 거래 라벨이
                # 단지명에 포함되거나, 단지명이 거래 라벨에 포함되거나)
                name_ok = any(
                    cn and any((cn in tn or tn in cn) for tn in tx_variants)
                    for cn in c["variants"]
                )
                if not name_ok:
                    pass  # name 검증 실패 → 본번만으로는 안전하지 않음, 다음 단계로
                else:
                    method = ("bonbun+dong+name"
                              if (umd and umd in c["dong_name"])
                              else "bonbun+name")
                    score = 0.95 if method == "bonbun+dong+name" else 0.90
                    candidates.append(
                        _candidate_summary(c, method, score,
                                           f"bonbun-fallback(jibun={jibun}→{bb})")
                    )

    # ---- 0c. 도로명 매칭 ----
    # jibun/본번 fallback 둘 다 실패한 경우, 도로명 + 단지명 substring 또는
    # 도로명+sgg 유일성으로 매칭. complexes.road_address(99.1% 채워짐) 와
    # data.go.kr 의 road_nm(99%+ 채워짐) 양쪽 normalize 해서 일치 확인.
    #
    # 패턴: 옥수파크힐스 117~125동(jibun=528-1) 도로명 "매봉길" ↔ 마스터
    # 110938 road_address "매봉길 50". 같은 sgg 안 동일 도로명 단지를 찾고,
    # 단지명 substring 검증으로 안전성 확보.
    if not candidates and sgg and road:
        road_hits = index.road_idx.get((sgg, road), [])
        if road_hits:
            # 단지명 substring 검증 통과한 후보들만 채택. 같은 도로 여러 단지
            # 있어도 단지명으로 분별 가능.
            name_matched = []
            for c in road_hits:
                ok = any(
                    cn and any((cn in tn or tn in cn) for tn in tx_variants)
                    for cn in c["variants"]
                )
                if ok:
                    name_matched.append(c)
            if name_matched:
                for c in name_matched:
                    method = ("road+dong+name"
                              if (umd and umd in c["dong_name"])
                              else "road+name")
                    score = 0.95 if method == "road+dong+name" else 0.90
                    candidates.append(
                        _candidate_summary(c, method, score,
                                           f"road={road!r}, sgg={sgg}")
                    )
            elif len(road_hits) == 1:
                # 도로명+sgg 가 단지를 유일하게 가리키지만 단지명 verification
                # 실패. dong 일치 시에만 채택 (이름이 아예 달라도 도로+동 유일
                # 이면 합리적 매칭).
                c = road_hits[0]
                if umd and umd in c["dong_name"]:
                    candidates.append(
                        _candidate_summary(c, "road+dong", 0.85,
                                           f"road={road!r} unique, sgg={sgg}")
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

    # ---- 2. substring (길이비율 점수, 짧은 매칭 거부) ----
    # "옥수" 같은 2자 단지명이 "옥수파크힐스117동125동" 에 끌려들어 false-match
    # 되는 것을 방지. min_match_len=3 으로 차단하고, 매칭된 토큰 길이가 길수록
    # 점수 가산 (긴 일치는 거의 exact 수준 신뢰).
    if not candidates:
        min_match_len = 3
        for c in index.complexes:
            # 법정동 검증 — 거래 법정동(umd)과 단지 동(dong_name)이 둘 다 있는데 서로
            # 포함관계가 아니면 cross-동 오매칭(예: 방학동 거래→쌍문동 '신동아', 정관읍→일광읍)
            # 으로 보고 substr 매칭 거부. 도시(방학동==방학동)·시골(정관읍⊂"정관읍 모전리") 양방향.
            if umd and c["dong_name"] and not (c["dong_name"] in umd or umd in c["dong_name"]):
                continue
            best_match_len = 0
            best_cn = ""
            best_tn = ""
            for cn in c["variants"]:
                if not cn or len(cn) < min_match_len:
                    continue
                for tn in tx_variants:
                    if not tn or len(tn) < min_match_len:
                        continue
                    if cn in tn or tn in cn:
                        m = min(len(cn), len(tn))
                        if m > best_match_len:
                            best_match_len = m
                            best_cn, best_tn = cn, tn
            if best_match_len < min_match_len:
                continue
            tn_max_len = max((len(t) for t in tx_variants), default=1)
            ratio = best_match_len / tn_max_len
            method = "substr+dong" if (umd and umd in c["dong_name"]) else "substr"
            base = 0.70 if method == "substr+dong" else 0.50
            # 길이비율 보너스 (0 ~ 0.15). 전체 이름급 매칭 → 0.85 / dong 일치
            # 시 최대 0.85 까지. exact 와 같은 라인.
            score = base + 0.15 * min(ratio, 1.0)
            candidates.append(
                _candidate_summary(c, method, round(score, 3),
                                   f"substr(cn={best_cn!r}, tn={best_tn!r}, "
                                   f"matchlen={best_match_len}, ratio={ratio:.2f})")
            )

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
