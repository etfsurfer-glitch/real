# -*- coding: utf-8 -*-
"""계약서 작성 도메인 모듈 (P0) — 한방(KREN) 역공학 명세의 콕집 이식.

근거: hanbang/docs/00_MASTER_참고서.md (+구현스펙·요율표). 등급 [확정/도메인]만 채택,
[추론]은 주석에 표기. 레거시 구조(380컬럼 평탄화·문자열 날짜)는 버리고 규칙만 가져온다.

구성:
  · 한글/한자 금액 표기      amount_korean()          — §7.1
  · 중개보수 완전판           commission()             — §7.2 (2021-10-19 분기·오피스텔 특례·월세환산)
  · 거래금액 산정             deal_amount()            — §7.2 표
  · 서식 버전 선택            select_form_version()    — §5.2 (계약일 기준 최신 유효버전)
  · 필수 검증                 validate_contract()      — §7.3 (한방 원문 메시지 재사용)
  · 주민/사업자번호 형식      valid_jumin_or_bizno()
순수 함수 모듈 — DB 접근 없음.
"""
from __future__ import annotations

import re

# ══════════════════════════════════════════════════════════════════
# 1. 금액 한글/한자 표기 — 레거시 CostC(숫자/한글/한자/한글+숫자/한자+숫자)·Unit(만원/천원/원)
# ══════════════════════════════════════════════════════════════════
_KO_DIG = "영일이삼사오육칠팔구"
_HJ_DIG = "零壹貳參肆伍陸柒捌玖"          # 갖은자(계약서 관례)
_KO_SMALL = ["", "십", "백", "천"]
_HJ_SMALL = ["", "拾", "佰", "仟"]
_KO_BIG = ["", "만", "억", "조"]
_HJ_BIG = ["", "萬", "億", "兆"]


def _four(n: int, dig: str, small: list[str]) -> str:
    """0~9999 → 한글/한자. 관례상 '일십'→'십', '일백'→'백', '일천'→'천'."""
    out = []
    for i in range(3, -1, -1):
        d = (n // (10 ** i)) % 10
        if d == 0:
            continue
        if d == 1 and i > 0:
            out.append(small[i])
        else:
            out.append(dig[d] + small[i])
    return "".join(out)


def _read_number(n: int, hanja: bool = False) -> str:
    if n == 0:
        return _HJ_DIG[0] if hanja else _KO_DIG[0]
    dig, small, big = (_HJ_DIG, _HJ_SMALL, _HJ_BIG) if hanja else (_KO_DIG, _KO_SMALL, _KO_BIG)
    parts = []
    unit = 0
    while n > 0:
        chunk = n % 10000
        if chunk:
            parts.append(_four(chunk, dig, small) + big[unit])
        n //= 10000
        unit += 1
    return "".join(reversed(parts))


def amount_korean(won: int, style: str = "한글", unit: str = "원") -> str:
    """금액(원) → 계약서 표기 문자열.

    style: 숫자 / 한글 / 한자 / 한글+숫자 / 한자+숫자   (레거시 CostC)
    unit : 원 / 천원 / 만원                              (레거시 Unit — 표기 단위 절사)
    예: amount_korean(150_000_000) → '일금 일억오천만원정'
        amount_korean(150_000_000, '한글+숫자') → '일금 일억오천만원정 (₩150,000,000)'
    """
    won = int(won or 0)
    if unit == "만원":
        disp_n, suffix = won // 10000, "만원" if won % 10000 == 0 else "원"
        if won % 10000:                      # 절사 안 되는 금액은 원 단위 유지
            disp_n, suffix = won, "원"
    elif unit == "천원":
        disp_n, suffix = (won // 1000, "천원") if won % 1000 == 0 else (won, "원")
    else:
        disp_n, suffix = won, "원"

    num_str = f"₩{won:,}"
    if style == "숫자":
        return num_str
    hanja = style.startswith("한자")
    body = _read_number(disp_n, hanja=hanja)
    if unit == "만원" and suffix == "만원":
        body += "萬" if hanja else "만"
    elif unit == "천원" and suffix == "천원":
        body += "仟" if hanja else "천"
    head = "一金" if hanja else "일금"
    tail = "원整" if hanja else "원정"
    text = f"{head} {body}{tail}"
    if style.endswith("+숫자"):
        text += f" ({num_str})"
    return text


# ══════════════════════════════════════════════════════════════════
# 2. 중개보수 완전판 — [도메인] 시행규칙 표준(시·도 조례 우선), [확정] 2021-10-19 경계
#    property_gb: HOUSE / OFFICETEL_Q / ETC     trade_gb: SALE / RENT
#    구간 [하한, 상한) · (상한액, 요율, 한도액|None)
# ══════════════════════════════════════════════════════════════════
_INF = float("inf")
_RATES = {
    ("HOUSE", "SALE", "OLD"): [(5e7, .006, 25e4), (2e8, .005, 80e4), (6e8, .004, None),
                               (9e8, .005, None), (_INF, .009, None)],       # 9억↑ 협의(상한 제안)
    ("HOUSE", "SALE", "NEW"): [(5e7, .006, 25e4), (2e8, .005, 80e4), (9e8, .004, None),
                               (12e8, .005, None), (15e8, .006, None), (_INF, .007, None)],
    ("HOUSE", "RENT", "OLD"): [(5e7, .005, 20e4), (1e8, .004, 30e4), (3e8, .003, None),
                               (6e8, .004, None), (_INF, .008, None)],       # 6억↑ 협의
    ("HOUSE", "RENT", "NEW"): [(5e7, .005, 20e4), (1e8, .004, 30e4), (6e8, .003, None),
                               (12e8, .004, None), (15e8, .005, None), (_INF, .006, None)],
}
_RATE_CUTOVER = "2021-10-19"   # [확정] "계약일자가 2021년10월19일 이후로 변경되어 개정된 요율…"
_NEGOTIABLE = {("HOUSE", "SALE", "OLD"): 9e8, ("HOUSE", "RENT", "OLD"): 6e8}


def deal_amount(mtype1: str, cost: int, fine_cost: int = 0,
                paid_in: int = 0, premium: int = 0) -> int:
    """중개보수 거래금액 산정 [도메인].
    매매/전세=총액(보증금) · 월세=보증금+월차임×100(5천만 미만이면 ×70) ·
    연세=월차임 환산(연세÷12) 후 월세식 · 분양권=기납입금(융자포함)+프리미엄."""
    cost = int(cost or 0)
    fine = int(fine_cost or 0)
    if mtype1 == "분양권":
        return int(paid_in or 0) + int(premium or 0)
    if mtype1 in ("매매", "전세"):
        return cost
    if mtype1 == "연세":
        fine = fine // 12
    if mtype1 in ("월세", "연세"):
        v = cost + fine * 100
        return cost + fine * 70 if v < 5e7 else v
    return cost


def commission(property_gb: str, trade_gb: str, amount: int,
               contract_date: str = "") -> dict:
    """중개보수 상한 계산. contract_date='YYYY-MM-DD'(빈값=현행 요율).
    반환: {fee(원), rate, limit, negotiable(협의구간 여부), period(NEW/OLD)}"""
    amount = int(amount or 0)
    period = "OLD" if (contract_date and contract_date < _RATE_CUTOVER) else "NEW"
    if property_gb == "OFFICETEL_Q":          # [확정: 특례 메시지] 구간·한도·시기 없음
        rate = .005 if trade_gb == "SALE" else .004
        return {"fee": int(amount * rate), "rate": rate, "limit": None,
                "negotiable": False, "period": "ALL"}
    if property_gb == "ETC":                  # 주택외 — 0.9% 이내 협의(상한 제안)
        rate = .009
        return {"fee": int(amount * rate), "rate": rate, "limit": None,
                "negotiable": True, "period": "ALL"}
    tiers = _RATES[("HOUSE", trade_gb, period)]
    for cap, rate, lim in tiers:
        if amount < cap:
            fee = int(amount * rate)
            if lim is not None:
                fee = min(fee, int(lim))
            neg = _NEGOTIABLE.get(("HOUSE", trade_gb, period), _INF) <= amount
            return {"fee": fee, "rate": rate, "limit": int(lim) if lim else None,
                    "negotiable": neg, "period": period}
    return {"fee": 0, "rate": 0, "limit": None, "negotiable": False, "period": period}


def officetel_q(exclusive_m2: float, kitchen: bool, toilet_bath: bool) -> bool:
    """오피스텔 특례 요건 [확정: 메시지] — 전용85㎡↓ + 전용입식부엌(상하수도) + 전용수세식화장실·목욕시설."""
    return bool(exclusive_m2 and exclusive_m2 <= 85 and kitchen and toilet_bath)


# ══════════════════════════════════════════════════════════════════
# 3. 잔금 자동계산 · 분양권 합산 — §7.1
# ══════════════════════════════════════════════════════════════════
def auto_balance(total: int, down: int = 0, mid1: int = 0, mid2: int = 0) -> int:
    """잔금 = 총액 − 계약금 − 중도금1 − 중도금2 (chk_auto)."""
    return max(int(total or 0) - int(down or 0) - int(mid1 or 0) - int(mid2 or 0), 0)


def bunyang_total(base: int, premium: int = 0, option: int = 0, tax: int = 0) -> int:
    """분양권/권리금/입주권 자동계산 = 분양가(취득가) + 프리미엄 + 옵션 + 제세공과."""
    return int(base or 0) + int(premium or 0) + int(option or 0) + int(tax or 0)


# ══════════════════════════════════════════════════════════════════
# 4. 서식 버전 선택 — §5.2 [확정: 경계(±1일 주의 → 구현스펙 표의 '적용 계약일 범위' 채택)]
#    버전키=효력개시일('YYYY-MM-DD'). 규칙: max{v: 개시일 ≤ 계약일}
# ══════════════════════════════════════════════════════════════════
FORM_VERSIONS: dict[int, list[str]] = {
    1: ["2000-01-01"],
    2: ["2000-01-01"], 3: ["2000-01-01"],
    5: ["2015-05-27"],                      # 국토부 권리금 표준계약서 제정일
    7: ["2000-01-01"], 8: ["2000-01-01"],
    4: ["2017-09-19", "2018-03-29", "2018-07-17", "2019-02-27", "2019-10-29",
        "2020-05-27", "2020-12-10", "2022-01-14", "2022-12-30", "2023-08-03",
        "2025-06-04", "2025-10-31"],
    6: ["2000-01-01", "2026-05-12"],
    9: ["2000-01-01"],
}
CATEGORY_NAMES = {1: "부동산 매매/임대차(일반)", 2: "분양권 매매", 3: "권리(시설)양수·양도",
                  4: "표준임대차(민특법)", 5: "상가건물 임대차 권리금", 6: "상가건물 임대차 표준",
                  7: "조합원입주권 매매", 8: "전대차", 9: "주택임대차표준"}


def select_form_version(category: int, contract_date: str) -> str | None:
    """계약일로 유효한 최신 서식버전. 최초 버전 이전 날짜면 None(차단 —
    '이 양식은 <날짜> 보다 과거의 일자로는 계약일자를 입력할 수 없습니다')."""
    vers = FORM_VERSIONS.get(int(category)) or ["2000-01-01"]
    ok = [v for v in vers if v <= contract_date]
    return max(ok) if ok else None


# ══════════════════════════════════════════════════════════════════
# 4.5 기본 계약조항(서식 1) — 협회 표준 서식 관용문. DFM Caption 추출문 + 표준문 보완.
#     슬롯: {인도일} {만기일} {연체기수} — 화면·인쇄에서 입력값 치환.
# ══════════════════════════════════════════════════════════════════
ARTICLES_SALE = [
    ("제1조", "", "위 부동산의 매매에 대하여 매도인과 매수인은 합의에 의하여 매매대금을 아래와 같이 지급하기로 한다."),
    ("제2조", "소유권이전 등", "매도인은 매매대금의 잔금 수령과 동시에 매수인에게 소유권이전등기에 필요한 모든 서류를 교부하고 등기절차에 협력하며, 위 부동산의 인도일은 {인도일}로 한다."),
    ("제3조", "제한물권 등의 소멸", "매도인은 위 부동산에 설정된 저당권, 지상권, 임차권 등 소유권의 행사를 제한하는 사유가 있거나 제세공과금과 기타 부담금의 미납 등이 있을 때에는 잔금 수수일까지 그 권리의 하자 및 부담 등을 제거하여 완전한 소유권을 매수인에게 이전한다. 다만 승계하기로 합의하는 권리 및 금액은 그러하지 아니하다."),
    ("제4조", "지방세 등", "위 부동산에 관하여 발생한 수익의 귀속과 제세공과금 등의 부담은 위 부동산의 인도일을 기준으로 하되, 지방세의 납부의무 및 납부책임은 지방세법의 규정에 의한다."),
    ("제5조", "계약의 해제", "매수인이 매도인에게 중도금(중도금이 없을 때에는 잔금)을 지불하기 전까지 매도인은 계약금의 배액을 상환하고, 매수인은 계약금을 포기하고 본 계약을 해제할 수 있다."),
    ("제6조", "채무불이행과 손해배상", "매도인 또는 매수인이 본 계약상의 내용에 대하여 불이행이 있을 경우 그 상대방은 불이행한 자에 대하여 서면으로 최고하고 계약을 해제할 수 있다. 그리고 계약당사자는 계약해제에 따른 손해배상을 각각 상대방에게 청구할 수 있으며, 손해배상에 대하여 별도의 약정이 없는 한 계약금을 손해배상의 기준으로 본다."),
    ("제7조", "중개보수", "개업공인중개사는 매도인 또는 매수인의 본 계약 불이행에 대하여 책임을 지지 않는다. 또한 중개보수는 본 계약체결과 동시에 계약 당사자 쌍방이 각각 지불하며, 개업공인중개사의 고의나 과실 없이 본 계약이 무효·취소 또는 해제되어도 중개보수는 지급한다."),
    ("제8조", "중개보수 외", "매도인 또는 매수인이 본 계약 이외의 업무를 의뢰한 경우 이에 관한 보수는 중개보수와는 별도로 지급하며 그 금액은 합의에 의한다."),
    ("제9조", "중개대상물확인·설명서 교부 등", "개업공인중개사는 중개대상물 확인·설명서를 작성하고 업무보증관계증서(공제증서 등) 사본을 첨부하여 계약체결과 동시에 거래당사자 쌍방에게 교부한다."),
]
ARTICLES_RENT = [
    ("제1조", "목적", "위 부동산의 임대차에 한하여 임대인과 임차인은 합의에 의하여 임차보증금 및 차임을 아래와 같이 지불하기로 한다."),
    ("제2조", "존속기간", "임대인은 위 부동산을 임대차 목적대로 사용·수익할 수 있는 상태로 {인도일}까지 임차인에게 인도하며, 임대차 기간은 인도일로부터 {만기일}까지로 한다."),
    ("제3조", "용도변경 및 전대 등", "임차인은 임대인의 동의 없이 위 부동산의 용도나 구조를 변경하거나 전대·임차권 양도 또는 담보제공을 하지 못하며 임대차 목적 이외의 용도로 사용할 수 없다."),
    ("제4조", "계약의 해지", "임차인의 차임연체액이 {연체기수}기의 차임액에 달하거나 제3조를 위반하였을 때 임대인은 즉시 본 계약을 해지할 수 있다."),
    ("제5조", "계약의 종료", "임대차계약이 종료된 경우에 임차인은 위 부동산을 원상으로 회복하여 임대인에게 반환한다. 이러한 경우 임대인은 보증금을 임차인에게 반환하고, 연체 임대료 또는 손해배상금이 있을 때는 이들을 제하고 그 잔액을 반환한다."),
    ("제6조", "계약의 해제", "임차인이 임대인에게 중도금(중도금이 없을 때에는 잔금)을 지불하기 전까지 임대인은 계약금의 배액을 상환하고, 임차인은 계약금을 포기하고 이 계약을 해제할 수 있다."),
    ("제7조", "채무불이행과 손해배상", "임대인 또는 임차인이 본 계약상의 내용에 대하여 불이행이 있을 경우 그 상대방은 불이행한 자에 대하여 서면으로 최고하고 계약을 해제할 수 있다. 그리고 계약당사자는 계약해제에 따른 손해배상을 각각 상대방에게 청구할 수 있다."),
    ("제8조", "중개보수", "개업공인중개사는 임대인과 임차인이 본 계약을 불이행함으로 인한 책임을 지지 않는다. 또한 중개보수는 본 계약체결과 동시에 계약 당사자 쌍방이 각각 지불하며, 개업공인중개사의 고의나 과실 없이 본 계약이 무효·취소 또는 해제되어도 중개보수는 지급한다."),
    ("제9조", "중개대상물확인·설명서 교부 등", "개업공인중개사는 중개대상물 확인·설명서를 작성하고 업무보증관계증서(공제증서 등) 사본을 첨부하여 계약체결과 동시에 거래당사자 쌍방에게 교부한다."),
]


def articles_for(mtype1: str) -> list[tuple[str, str, str]]:
    return ARTICLES_SALE if mtype1 == "매매" else ARTICLES_RENT


# ══════════════════════════════════════════════════════════════════
# 5. 필수 검증 — §7.3 (한방 원문 메시지 재사용) + 주민/사업자번호 형식
# ══════════════════════════════════════════════════════════════════
_JUMIN_RE = re.compile(r"^\d{6}-?\d{7}$")
_BIZNO_RE = re.compile(r"^\d{3}-?\d{2}-?\d{5}$")
_CORP_RE = re.compile(r"^\d{6}-?\d{7}$")     # 법인등록번호도 13자리


def valid_jumin_or_bizno(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return True                            # 빈값 허용(필수 여부는 별도 룰)
    return bool(_JUMIN_RE.match(s) or _BIZNO_RE.match(s))


def validate_contract(body: dict, category: int, mtype1: str) -> list[str]:
    """저장 차단 검증. body는 폼 JSON(레거시 컬럼명 키 사용: cost, fine_cost, ...).
    반환: 오류 메시지 목록(비면 통과). 메시지는 한방 원문 [확정]."""
    errs: list[str] = []
    cat = int(category)

    def _n(k):
        try:
            return int(body.get(k) or 0)
        except (TypeError, ValueError):
            return 0

    if cat == 8 and mtype1 == "매매":
        errs.append("전대차계약서는 매매를 선택할 수 없습니다!")
    if not (body.get("contract_date") or "").strip():
        errs.append("계약일자를 입력하세요")          # 서식버전·일정등록의 기준일(2026-09-02 검토 추가)
    if cat == 5:
        # 권리금계약(국토부 표준): 임차인↔신규임차인. 매매/임대차 금액·면적 검증 대신 권리금 필수.
        if _n("kw_total") <= 0:
            errs.append("총 권리금을 입력해 주세요")
        if not (body.get("rent_area") or body.get("exclusive_area") or body.get("build_py")):
            errs.append("임대면적 또는 전용면적을 입력해 주세요")
        for side in ("sell", "buy"):
            for p in body.get(f"{side}_parties") or []:
                if not valid_jumin_or_bizno(p.get("jumin") or ""):
                    errs.append("주민등록번호 또는 사업자번호를 정확히 입력하세요!")
                    break
        cd5 = (body.get("contract_date") or "").strip()
        if cd5 and select_form_version(cat, cd5) is None:
            first5 = (FORM_VERSIONS.get(cat) or ["2000-01-01"])[0]
            errs.append(f"이 양식은 {first5} 보다 과거의 일자로는 계약일자를 입력할 수 없습니다.")
        return errs
    if mtype1 == "매매" and cat != 8:
        if _n("cost") <= 0:
            errs.append("매매금액을 입력해 주세요")
    elif mtype1 in ("전세", "월세", "연세"):
        if _n("cost") <= 0:
            errs.append("보증금을 입력해 주세요")
        if not (body.get("rent_py") or body.get("build_py")):
            errs.append("임대 면적을 입력하여 주십시오")
    if not (body.get("build_py") or body.get("land_py") or body.get("rent_py")):
        errs.append("명시사항 규정에 따라 계약면적을 입력해 주세요")
    if cat == 4 and not body.get("rent_kind"):
        errs.append("민간임대주택유형을 선택하세요")
    for side in ("sell", "buy"):
        for p in body.get(f"{side}_parties") or []:
            if not valid_jumin_or_bizno(p.get("jumin") or ""):
                errs.append("주민등록번호 또는 사업자번호를 정확히 입력하세요!")
                break
    # 중개보수 지급시기 의무기재 [확정]
    if body.get("charge") and not (body.get("charge_sigi") or "").strip():
        errs.append("중개보수 지급시기는 의무기재사항입니다. 지급시기를 기재하세요!")
    # 서식버전 범위
    cd = (body.get("contract_date") or "").strip()
    if cd and select_form_version(cat, cd) is None:
        first = (FORM_VERSIONS.get(cat) or ["2000-01-01"])[0]
        errs.append(f"이 양식은 {first} 보다 과거의 일자로는 계약일자를 입력할 수 없습니다.")
    return errs


# ══════════════════════════════════════════════════════════════════
# 자가검증
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ok = 0

    def chk(name, got, want):
        global ok
        good = got == want
        ok += good
        print(("  ✓ " if good else "  ✗ ") + f"{name}: {got!r}" + ("" if good else f" (기대 {want!r})"))

    print("[한글금액]")
    chk("1.5억", amount_korean(150_000_000), "일금 일억오천만원정")
    chk("3,050만", amount_korean(30_500_000), "일금 삼천오십만원정")
    chk("12.7억+숫자", amount_korean(1_270_000_000, "한글+숫자"),
        "일금 십이억칠천만원정 (₩1,270,000,000)")
    chk("한자 2억", amount_korean(200_000_000, "한자"), "一金 貳億원整")
    chk("숫자", amount_korean(55_000_000, "숫자"), "₩55,000,000")

    print("[중개보수]")
    chk("주택매매 10억(현행 0.5%)", commission("HOUSE", "SALE", 1_000_000_000)["fee"], 5_000_000)
    chk("주택매매 10억(구 0.9%협의)", commission("HOUSE", "SALE", 1_000_000_000, "2021-01-01")["fee"], 9_000_000)
    chk("주택임대 4천만(한도 20만)", commission("HOUSE", "RENT", 40_000_000)["fee"], 200_000)
    chk("오피스텔Q 임대 0.4%", commission("OFFICETEL_Q", "RENT", 300_000_000)["fee"], 1_200_000)
    chk("ETC 협의", commission("ETC", "SALE", 500_000_000)["negotiable"], True)
    print("[거래금액]")
    chk("월세 5천/40만→×100", deal_amount("월세", 50_000_000, 400_000), 90_000_000)
    chk("월세 1천/30만→×70", deal_amount("월세", 10_000_000, 300_000), 31_000_000)
    chk("연세 1천/연360만", deal_amount("연세", 10_000_000, 3_600_000), 31_000_000)
    chk("분양권", deal_amount("분양권", 0, 0, 300_000_000, 50_000_000), 350_000_000)

    print("[서식버전]")
    chk("표준임대차 2024-01-01", select_form_version(4, "2024-01-01"), "2023-08-03")
    chk("표준임대차 2026-01-01", select_form_version(4, "2026-01-01"), "2025-10-31")
    chk("표준임대차 2017-01-01(차단)", select_form_version(4, "2017-01-01"), None)
    chk("상가 2026-06-01", select_form_version(6, "2026-06-01"), "2026-05-12")

    print("[검증]")
    chk("전대차+매매 차단", validate_contract({}, 8, "매매")[0], "전대차계약서는 매매를 선택할 수 없습니다!")
    e = validate_contract({"cost": 0}, 1, "매매")
    chk("매매금액 필수", "매매금액을 입력해 주세요" in e, True)
    e = validate_contract({"cost": 100, "build_py": "59.9", "rent_py": "59.9",
                           "charge": 500000}, 1, "전세")
    chk("지급시기 의무", "중개보수 지급시기는 의무기재사항입니다. 지급시기를 기재하세요!" in e, True)
    chk("주민번호 형식", valid_jumin_or_bizno("800101-1234567"), True)
    chk("사업자번호 형식", valid_jumin_or_bizno("123-45-67890"), True)
    chk("이상 형식", valid_jumin_or_bizno("80-01"), False)

    print(f"\n통과 {ok}/23")
