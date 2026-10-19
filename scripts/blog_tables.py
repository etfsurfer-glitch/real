# -*- coding: utf-8 -*-
"""블로그 글의 표(table)를 상업용 빌딩 데이터로 구조화한다. 네트워크를 타지 않는다.

왜 표인가
  중개사 블로그는 임대조건을 **표로** 적는다(글 28건 중 20건, 평균 4.4개). 그 표에
  '층 | 임대면적 | 전용면적 | 입주시기' 와 '층 | 보증금 | 임대료 | 관리비' 가 들어 있다.
  평문에서 정규식으로 긁으면 빌딩당 스칼라 한 줄이 남지만, 표를 읽으면 **층별 공실
  재고**가 날짜와 함께 남는다. 같은 측정으로 원자 127개 → 485개(3.8배)였다.

이 모듈을 수집기에서 떼어 놓은 이유
  파서는 계속 고쳐진다. 본문(표+평문)을 DB에 넣어 두고 이 모듈만 다시 돌리면
  재수집 없이 재파싱된다(scripts/blog_reparse.py).
"""
from __future__ import annotations

import html
import re

PY_M2 = 3.3058


# ── 표를 2차원 리스트로 ────────────────────────────────────────────────
def tables(src: str) -> list[list[list[str]]]:
    out = []
    for tb in re.findall(r"<table.*?</table>", src, flags=re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tb, flags=re.S):
            cs = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                  for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            if any(cs):
                rows.append(cs)
        if rows:
            out.append(rows)
    return out


# ── 값 정규화 ─────────────────────────────────────────────────────────
def money(s) -> float | None:
    """'1,164,555,900원' → 1164555900 · '1,626만 원' → 16260000"""
    if not s:
        return None
    s = re.sub(r"(?<=\d)[\s,](?=\d)", "", s.strip())      # '630,0 00' → '6300 00' 방지
    s = s.replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    v = float(m.group(1))
    if "만" in s and v < 100000:
        v *= 10000
    return v


def area(s) -> tuple[float | None, float | None]:
    """'464.94평(1,537.00㎡)' / '302.74py (1,000.79㎡)' / '2,538.57㎡767.92평' → (평, ㎡).

    한쪽만 적힌 표가 많아 없는 쪽은 3.3058 로 환산해 채운다(환산값임을 구분하지
    않는다 — 두 값이 같이 적힌 글에서 오차가 0.1% 미만이었다).
    """
    if not s:
        return None, None
    s = s.replace(" ", "").replace("@", "")
    m2 = re.search(r"([\d,]+\.?\d*)(?:㎡|m2|m²)", s)
    pyo = re.search(r"([\d,]+\.?\d*)(?:평|py)", s)
    a2 = float(m2.group(1).replace(",", "")) if m2 else None
    ap = float(pyo.group(1).replace(",", "")) if pyo else None
    if a2 and not ap:
        ap = round(a2 / PY_M2, 2)
    if ap and not a2:
        a2 = round(ap * PY_M2, 2)
    return ap, a2


def area_max(s) -> float | None:
    """한 칸에 면적이 여러 개 적힌 경우 가장 큰 값(평). 평당 역산의 분모로 쓴다.

    '전용면적 / 공급면적 | 692.08평(2287.88㎡) / 1088.37평(3597.93㎡)' 처럼 한 칸에
    전용과 임대가 같이 온다. 앞에서부터 집으면 전용으로 나눠 평당 임대료가 1.6배로
    튄다(실측: 168,269원 vs 실제 107,000원). 임대·공급면적은 늘 전용보다 크다.
    """
    if not s:
        return None
    got = []
    for chunk in re.split(r"[/|]", s):
        ap, _ = area(chunk)
        if ap:
            got.append(ap)
    return max(got) if got else None


def floor_label(s) -> tuple[str, bool] | None:
    """'6층' → ('6F', False) · '15~17' → ('15~17F', True) · '5F(일부)' → ('5F', False).

    '합계' 행은 버린다(층별 값을 더한 것이라 중복이다).
    """
    if not s:
        return None
    t = s.replace(" ", "").replace("지하", "B")
    if re.match(r"^(합계|소계|계|-|총)", t):
        return None
    m = re.match(r"^(B?\d{1,2})(?:[F층])?(?:[~\-](\d{1,2})[F층]?)?", t)
    if not m:
        return None
    lab = m.group(1) + (f"~{m.group(2)}" if m.group(2) else "") + "F"
    return lab, bool(m.group(2))


def norm_posted(raw: str, fetched: str) -> str | None:
    """'2026.06.05.' → '2026-06-05' · '1일 전' → 수집일-1 · '3시간 전' → 수집일.

    FsasReview.date 는 최근 글에 상대시간을 돌려준다(가장 값진 최신 글에서 하필
    날짜가 깨진다). 임대료는 시점 데이터라 날짜가 값의 일부다.
    """
    import datetime as _dt

    if not raw:
        return None
    t = raw.strip()
    m = re.match(r"^(\d+)\s*일\s*전", t)
    if m:
        return (_dt.date.fromisoformat(fetched) - _dt.timedelta(days=int(m.group(1)))).isoformat()
    if re.match(r"^(방금|\d+\s*(분|시간)\s*전)", t):
        return fetched
    t = t.rstrip(".").replace(".", "-").replace("/", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
    if m:
        return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups())
    return None


# ── 제원(key|value) 표 ────────────────────────────────────────────────
#  키 표기가 블로거마다 다르다. 정규화한 키를 '포함' 으로 맞춘다.
SPEC = [
    ("typ_rent", ("기준층임대면적", "기준층면적")),
    ("rent_area", ("임대면적", "공급면적")),
    ("typ_excl", ("기준층전용면적", "기준층전용")),
    ("pk_free", ("기본주차", "기본제공주차")),
    ("pk_extra", ("추가주차",)),
    ("pk_note", ("주차정보",)),
    ("pk_unit", ("주차대수여건",)),            # ★ 호실 배정분. 건물 총대수가 아니다
    ("pk_total", ("주차대수", "주차장현황", "총주차대수", "주차현황", "총주차", "주차")),
    ("gfa", ("연면적",)),
    ("eff", ("전용률", "전용율")),
    ("approved", ("사용승인", "준공")),
    ("purpose", ("주용도", "건축물용도", "용도")),
    ("elev", ("엘리베이터", "승강기", "E/V", "EV")),
    ("toilet", ("화장실", "방욕실수")),
    ("hvac", ("냉난방",)),
    ("facing", ("방향",)),
    ("movein", ("입주",)),
    ("scale", ("건물규모", "빌딩규모", "총층수", "층수", "규모")),
    ("structure", ("구조",)),
    ("deal", ("거래형태",)),
    ("noc", ("NOC",)),
    ("addr", ("소재지", "소재", "주소")),
]
_SPEC_SKIP = re.compile(r"보증금|임대료|관리비|평당|디포짓|월세")


def spec_key(k: str) -> str | None:
    k = re.sub(r"[\s()\[\]/,·]", "", k)
    k = re.sub(r"(기준|일자|시기|연월|연도|현황|가능|시점|여부)$", "", k)
    if not k or _SPEC_SKIP.search(k):
        return None
    for name, pats in SPEC:
        if any(p in k for p in pats):
            return name
    return None


# 금액 칸의 키. 접두(임대·공급·전용)와 평당 표기가 앞뒤 어디든 붙는다 —
# '평당 보증금' · '임대평당 보증금' · '임대료 / 평당' 이 다 같은 뜻이다.
# 반대로 '전용 평당 비용 [(임대료+관리비)÷전용면적]' 은 파생지표이므로 받지 않는다
# (키를 fullmatch 로 묶어 긴 수식 키를 걸러낸다).
MONEY_KEY = re.compile(r"^(?:임대|공급|전용)?(?:평당|면적당|3\.3㎡당|py당)?"
                       r"(보증금|디포짓|임대료|월세|관리비)(?:평당|면적당)?$")
UNIT_MARK = re.compile(r"평당|면적당|3\.3\s*㎡\s*당|py당")
FIELD = {"보증금": "deposit", "디포짓": "deposit", "임대료": "rent",
         "월세": "rent", "관리비": "cam"}


def _hdr_row(rows):
    """'단위 : 원' 같은 설명행이 맨 위에 오는 표가 있어 헤더는 앞 2행에서 찾는다."""
    for j, r in enumerate(rows[:2]):
        if any(re.fullmatch(r"해당\s*층|층", c.strip()) for c in r):
            return j
    return None


def parse(src: str) -> dict:
    """표 묶음 → {spec, unit, floor_area, floor_price, extra}."""
    spec: dict[str, str] = {}
    unit: dict[str, tuple[float, float | None]] = {}
    absolute: dict[str, float] = {}
    fa: list[dict] = []
    fp: list[dict] = []
    extra: dict[str, str] = {}

    for rows in tables(src):
        flat = " ".join(" ".join(r) for r in rows)
        m = re.search(r"물건\s*확인일\s*[:·]?\s*(\d{2})[.\-](\d{1,2})", flat)
        if m:
            extra["verified_on"] = "20%s-%02d" % (m.group(1), int(m.group(2)))
        m = re.search(r"기준\s*NOC\s*[|:]?\s*([\d.,]+\s*만?\s*원?)", flat)
        if m:
            extra["noc"] = m.group(1).strip()

        hi = _hdr_row(rows)
        if hi is not None:
            hdr = " ".join(rows[hi])
            body = rows[hi + 1:]
            if "보증금" in hdr:
                for r in body:
                    fo = floor_label(r[0]) if len(r) >= 2 else None
                    if fo:
                        fp.append({"idx": len(fp), "floor": fo[0], "span": int(fo[1]),
                                   "deposit": money(r[1]),
                                   "rent": money(r[2]) if len(r) > 2 else None,
                                   "cam": money(r[3]) if len(r) > 3 else None})
                continue
            if re.search(r"면적|임대|전용", hdr):
                # 컬럼 순서를 가정하면 안 된다. '층|전용 면적|임대 면적' 으로 적는
                # 글이 있어 고정 순서로 읽으면 전용 57평/임대 120평이 뒤집힌다.
                cols = rows[hi]
                swap = False
                for ci, c in enumerate(cols[1:3], 1):
                    if "전용" in c:
                        swap = (ci == 1)
                        break
                    if re.search(r"임대|공급", c):
                        swap = (ci == 2)
                        break
                for r in body:
                    fo = floor_label(r[0]) if len(r) >= 2 else None
                    if fo:
                        c1, c2 = r[1], (r[2] if len(r) > 2 else "")
                        if swap:
                            c1, c2 = c2, c1
                        rp, rm = area(c1)
                        ep, em = area(c2)
                        fa.append({"idx": len(fa), "floor": fo[0], "span": int(fo[1]),
                                   "rent_py": rp, "rent_m2": rm,
                                   "excl_py": ep, "excl_m2": em,
                                   "movein": (r[3].strip() or None) if len(r) > 3 else None})
                continue

        # 가로형 평당표: 헤더행이 '평당 보증금|평당 임대료|평당 관리비', 다음 행이 값
        if sum("평당" in c for c in rows[0]) >= 2 and len(rows) > 1:
            for k, v in zip(rows[0], rows[1]):
                mm = MONEY_KEY.match(re.sub(r"[\s/·]", "", k))
                if mm and money(v):
                    unit.setdefault("u_" + FIELD[mm.group(1)], (money(v), None))

        # 이 표가 평당 기준인가. 캡션('단위 : 임대면적 3.3㎡당', '임대 면적당 임대료
        # 조건')이나 키 하나라도 평당 표기를 달고 있으면 그 표는 평당이다. 아무
        # 칸에나 '평당'이 있으면 평당으로 보던 예전 판정은 '전용 평당 비용' 행
        # 하나 때문에 월세 26,555,741원을 평당 임대료로 적었다.
        keys2 = [re.sub(r"[\s/·]", "", r[0]) for r in rows if len(r) == 2]
        tbl_unit = any(UNIT_MARK.search(c) for r in rows if len(r) == 1 for c in r) or \
            any(MONEY_KEY.match(k) and UNIT_MARK.search(k) for k in keys2)
        for r in rows:
            if len(r) != 2:
                continue
            k, v = r
            kk = re.sub(r"[\s/·]", "", k)
            m = MONEY_KEY.match(kk)
            if m:
                fld = FIELD[m.group(1)]
                if UNIT_MARK.search(kk) or tbl_unit:
                    # '1,070,000 ~ 1,180,000원' — 층마다 단가가 다르면 범위로 적는다.
                    # 범위를 끊기 전에 숫자 사이 공백을 먼저 없앤다 — '630,0 00' 을
                    # 그대로 끊으면 '630,0' 이 떨어져 나와 6,300원이 된다.
                    vv = re.sub(r"(?<=\d)[\s](?=\d)", "", v)
                    got = [g for g in (money(x) for x in re.findall(r"[\d,]{5,}", vv)) if g]
                    if got:
                        unit.setdefault("u_" + fld,
                                        (got[0], got[-1] if len(got) > 1 else None))
                elif money(v) and money(v) >= 1_000_000:
                    absolute.setdefault("a_" + fld, money(v))
                continue
            sk = spec_key(kk)
            if sk and sk not in spec:
                spec[sk] = v.strip()[:80]

    # 평당값이 없고 절대금액만 있는 글 → 기준층 임대면적으로 역산
    if "u_rent" not in unit and absolute.get("a_rent"):
        base = area_max(spec.get("typ_rent") or spec.get("rent_area") or "")
        if not base and fa:
            base = fa[0].get("rent_py")
        cand = round(absolute["a_rent"] / base) if base else None
        if cand and 20_000 <= cand <= 400_000:          # 평당 임대료의 현실 범위
            for a_k, u_k in (("a_deposit", "u_deposit"), ("a_rent", "u_rent"),
                             ("a_cam", "u_cam")):
                if absolute.get(a_k):
                    unit[u_k] = (round(absolute[a_k] / base), None)
            extra["unit_derived"] = "1"
        elif cand:
            extra["unit_derive_failed"] = str(cand)

    return {"spec": spec, "unit": unit, "floor_area": fa, "floor_price": fp,
            "abs": absolute, "extra": extra}


def kind(src: str, parsed: dict) -> str:
    """임대매물 글인가. 글 28건 중 10건(36%)이 병원 후기·식당 오픈·층간소음이었다.

    무관 글에 Gemini 를 부르면 돈만 쓰고 홍보문이 들어온다. 다만 버리지는 않는다 —
    '브라운돈까스 씨티스퀘어점 오픈' 은 입점 테넌트 신호다(본문을 저장해 두므로
    분류를 나중에 더 쪼갤 수 있다).
    """
    if parsed["unit"] or parsed["abs"] or parsed["floor_price"] or parsed["floor_area"]:
        return "lease"
    if re.search(r"평당\s*(보증금|임대료|관리비)", src):
        return "lease"
    if re.search(r"(신규\s*매장|오픈|입점|지점|점\s*오픈)", src):
        return "tenant"
    return "other"


def name_variants(name: str) -> list[str]:
    """빌딩명으로 검색이 빈손일 때 써 볼 변형들. 앞에 있는 것부터 가능성이 높다.

    실측(316곳 중 159곳 실패)에서 실패 원인은 대부분 우리 쪽 표기였다.
      · PDF 의 'NEW' 배지가 이름에 붙었다 — 시그니처타워NEW, LG트윈텔2차NEW
      · 괄호 별칭 — KB라이프타워(푸르덴셜타워), 위워크타워(PCA타워)
      · 동 접미 — 배재정동빌딩B동, 트윈트리타워A동
    괄호 안이 옛 이름인 경우가 많아 **괄호 안도 하나의 후보**로 쓴다.
    """
    out, seen = [], set()

    def add(s):
        s = re.sub(r"\s{2,}", " ", (s or "").strip(" ·‧,")).strip()
        if len(s) >= 2 and s not in seen:
            seen.add(s)
            out.append(s)

    base = re.sub(r"\s*NEW\s*$", "", name.strip(), flags=re.I)
    add(base)

    inner = re.findall(r"[(（]([^)）]+)[)）]", base)
    outer = re.sub(r"\s*[(（][^)）]*[)）]", "", base).strip()
    add(outer)
    for v in inner:
        if not re.search(r"\d+\s*[-‧·]\s*\d+|지구|BL|블[록럭]", v):   # 재개발 블록코드는 이름이 아니다
            add(v)

    for v in (outer, base):
        add(re.sub(r"\s*[A-Z]동$", "", v))                    # B동 · A동
        add(re.sub(r"\s*\d+차$", "", v))                      # 2차
    return out
