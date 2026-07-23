"""아파트매수마법사 — 구매력 계산 + 추천 엔진 (2026-07-07, 관리자 가오픈).

'내 현금으로 실제 살 수 있는 단지·평형'을 찾아주는 엔진. 단순 계산기가 아니라
대출한도(LTV·DSR·지역별 총액캡) + 부대비용(취득세·중개보수·채권·인지·법무비) 전부를
반영해 구매 가능 상한가를 산출하고, 실거래(12개월)·현재 매물 DB에서 후보를 뽑아
점수화한다.

정책값(LTV/세율/한도 등)은 코드에 박지 않고 data/buywizard_policy.json 에서 로드
(관리자 API로 수정 가능). 정책 변경(규제지역 지정 등) 시 JSON만 고치면 된다.

방·욕실수: 벌크 DB에 없어 전용면적 기반 추정치(rooms_est)로 제공 — 관례상
~45㎡ 방1~2/욕1, 45~59 방2~3/욕1, 59~84 방3/욕2, 84+ 방3~4/욕2.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "data" / "buywizard_policy.json"

# ---------------------------------------------------------------------------
# 기본 정책 (JSON 파일이 없을 때 시드로 기록됨). 출처는 스펙 문서(금융위 2025.6/10월
# 대책, 주금공 디딤돌/보금자리, 법제처 취득세, 서울시 중개보수표) 기준.
# ---------------------------------------------------------------------------
DEFAULT_POLICY = {
    "updated_at": "2026-07-07",
    "note": "정책값은 관리자 설정. 실제 한도·세금은 금융기관·지자체·개인조건에 따라 다름.",
    # 규제지역(조정대상지역 등) cortar prefix — 2026 기준 서울 전역. 지정 변경 시 수정.
    "regulated_prefixes": ["11"],
    # 수도권 시도 prefix (서울/경기/인천)
    "capital_prefixes": ["11", "41", "28"],
    # LTV: buyer_type × region_type. buyer: none(무주택)/first(생애최초)/sell_one(처분조건부)
    #       /keep_one(1주택 유지 추가매수)/multi(다주택)
    "ltv": {
        "none":     {"normal": 0.70, "capital": 0.70, "regulated": 0.50},
        "first":    {"normal": 0.80, "capital": 0.70, "regulated": 0.50},
        "sell_one": {"normal": 0.70, "capital": 0.70, "regulated": 0.50},
        "keep_one": {"normal": 0.60, "capital": 0.0,  "regulated": 0.0},
        "multi":    {"normal": 0.0,  "capital": 0.0,  "regulated": 0.0},
    },
    # 수도권·규제지역 주담대 총액 캡 (금융위 2025-10): [가격상한(원), 대출캡(원)]
    "regional_loan_caps": [
        [1_500_000_000, 600_000_000],
        [2_500_000_000, 400_000_000],
        [999_999_999_999, 200_000_000],
    ],
    "dsr": {
        "limit": 0.40,
        "default_rate": 0.042,          # 예상 주담대 금리
        "stress_rate": 0.015,           # 기본 스트레스 가산
        "stress_rate_capital": 0.030,   # 수도권·규제 스트레스 하한(2025-10)
        "default_years": 30,
    },
    "acq_tax": {
        # 다주택 중과: [주택수, 규제여부] → 세율. 1주택은 구간식(1~3%).
        "two_house_regulated": 0.08,
        "three_house_normal": 0.08,
        "three_house_regulated": 0.12,
        "four_plus": 0.12,
        "first_time_cut_max": 2_000_000,   # 생애최초 감면 최대
        "first_time_price_cap": 1_200_000_000,
    },
    # 중개보수 상한 (서울시 요율표): [가격상한, 요율, 한도액(0=없음)]
    "brokerage": [
        [50_000_000, 0.006, 250_000],
        [200_000_000, 0.005, 800_000],
        [900_000_000, 0.004, 0],
        [1_200_000_000, 0.005, 0],
        [1_500_000_000, 0.006, 0],
        [999_999_999_999, 0.007, 0],
    ],
    "broker_vat": 0.10,
    # 국민주택채권 할인비용 보수 추정: [가격상한, 비용]
    "bond_cost": [
        [300_000_000, 300_000],
        [600_000_000, 700_000],
        [900_000_000, 1_300_000],
        [1_500_000_000, 2_500_000],
        [999_999_999_999, 4_000_000],
    ],
    # 인지세: [가격상한, 세액]
    "stamp_tax": [
        [10_000_000, 0],
        [30_000_000, 20_000],
        [50_000_000, 40_000],
        [100_000_000, 70_000],
        [1_000_000_000, 150_000],
        [999_999_999_999, 350_000],
    ],
    # 법무사/등기 부대비 추정: [가격상한, 비용]
    "legal_cost": [
        [300_000_000, 600_000],
        [600_000_000, 900_000],
        [900_000_000, 1_200_000],
        [999_999_999_999, 1_800_000],
    ],
    "preserve_cash_default": 10_000_000,
    # 추천 점수 가중치
    "score": {
        "afford_85": 35, "afford_95": 25, "afford_100": 10,
        "cheap_3pct": 25, "similar": 15, "expensive_5pct": -10,
        "has_listing": 15, "tx_only": 5,
        "area_fit": 10, "region_exact": 10,
    },
}


def load_policy() -> dict:
    if POLICY_PATH.exists():
        try:
            return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(DEFAULT_POLICY, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    return dict(DEFAULT_POLICY)


def save_policy(policy: dict) -> None:
    POLICY_PATH.write_text(json.dumps(policy, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def _tier(table: list, price: float) -> float:
    for cap, val, *_ in [(row[0], row[1], row[2:]) for row in table]:
        if price <= cap:
            return val
    return table[-1][1]


# ---------------------------------------------------------------------------
# 세금·비용
# ---------------------------------------------------------------------------

def acquisition_tax_rate(price: float) -> float:
    """1주택 유상거래 기본 취득세율: 6억↓ 1%, 6~9억 구간식, 9억↑ 3%."""
    if price <= 600_000_000:
        return 0.01
    if price <= 900_000_000:
        return ((price / 100_000_000) * 2 / 3 - 3) / 100
    return 0.03


def acq_tax_rate_by_house(price: float, house_after: int, regulated: bool,
                          policy: dict) -> float:
    p = policy["acq_tax"]
    if house_after <= 1:
        return acquisition_tax_rate(price)
    if house_after == 2:
        return p["two_house_regulated"] if regulated else acquisition_tax_rate(price)
    if house_after == 3:
        return p["three_house_regulated"] if regulated else p["three_house_normal"]
    return p["four_plus"]


def brokerage_fee(price: float, policy: dict) -> float:
    for cap, rate, limit in policy["brokerage"]:
        if price <= cap:
            fee = price * rate
            return min(fee, limit) if limit else fee
    return price * policy["brokerage"][-1][1]


def calc_costs(price: float, *, area_m2: float, house_after: int, regulated: bool,
               first_time: bool, policy: dict, include_vat: bool = True) -> dict:
    """매매가에 붙는 부대비용 전부 (대출 제외)."""
    rate = acq_tax_rate_by_house(price, house_after, regulated, policy)
    acq = price * rate
    edu = acq * 0.1
    rural = price * 0.002 if (area_m2 or 0) > 85 else 0
    tax_total = acq + edu + rural
    cut = 0
    if first_time and house_after <= 1 and price <= policy["acq_tax"]["first_time_price_cap"]:
        cut = min(policy["acq_tax"]["first_time_cut_max"], tax_total)
        tax_total -= cut
    broker = brokerage_fee(price, policy)
    if include_vat:
        broker *= (1 + policy["broker_vat"])
    bond = _tier(policy["bond_cost"], price)
    stamp = _tier(policy["stamp_tax"], price)
    legal = _tier(policy["legal_cost"], price)
    return {
        "acq_tax": round(acq), "edu_tax": round(edu), "rural_tax": round(rural),
        "first_time_cut": round(cut), "tax_total": round(tax_total),
        "acq_tax_rate": round(rate, 4),
        "broker_fee": round(broker), "bond_cost": bond, "stamp_tax": stamp,
        "legal_cost": legal,
        "costs_total": round(tax_total + broker + bond + stamp + legal),
    }


# ---------------------------------------------------------------------------
# 대출
# ---------------------------------------------------------------------------

def region_flags(codes: list[str], policy: dict) -> tuple[bool, bool]:
    """(규제지역 포함?, 수도권 포함?) — 선택지역 중 하나라도 해당하면 보수적으로 True."""
    reg = any(any(c.startswith(p) for p in policy["regulated_prefixes"]) for c in codes)
    cap = any(any(c.startswith(p) for p in policy["capital_prefixes"]) for c in codes)
    return reg, cap


def ltv_rate(buyer: str, regulated: bool, capital: bool, policy: dict) -> float:
    row = policy["ltv"].get(buyer) or policy["ltv"]["none"]
    if regulated:
        return row["regulated"]
    if capital:
        return row["capital"]
    return row["normal"]


def dsr_loan(annual_income: float, existing_annual_payment: float, *,
             rate: float, stress: float, years: int, limit: float) -> float:
    """DSR 한도 내 원리금균등 대출 가능액 (스트레스 금리 반영)."""
    max_annual = annual_income * limit - existing_annual_payment
    if max_annual <= 0:
        return 0
    monthly = max_annual / 12
    r = (rate + stress) / 12
    n = years * 12
    if r <= 0:
        return monthly * n
    return monthly * (1 - (1 + r) ** -n) / r


def expected_loan(price: float, profile: dict, policy: dict) -> dict:
    regulated, capital = region_flags(profile.get("region_codes") or [], policy)
    buyer = profile.get("buyer_type", "none")
    if profile.get("is_first_time") and buyer in ("none", "sell_one"):
        buyer = "first"
    ltv = ltv_rate(buyer, regulated, capital, policy)
    ltv_amt = price * ltv

    cap_amt = None
    if regulated or capital:
        cap_amt = _tier([(c, v) for c, v in policy["regional_loan_caps"]], price)

    d = policy["dsr"]
    stress = d["stress_rate_capital"] if (regulated or capital) else d["stress_rate"]
    dsr_amt = dsr_loan(
        profile.get("annual_income") or 0,
        profile.get("existing_annual_payment") or 0,
        rate=profile.get("mortgage_rate") or d["default_rate"],
        stress=stress,
        years=int(profile.get("loan_years") or d["default_years"]),
        limit=d["limit"],
    )
    loan = max(0, min(ltv_amt, dsr_amt, cap_amt if cap_amt is not None else ltv_amt))
    return {
        "loan": round(loan), "ltv": ltv, "ltv_amt": round(ltv_amt),
        "dsr_amt": round(dsr_amt), "regional_cap": cap_amt,
        "regulated": regulated, "capital": capital, "stress_rate": stress,
    }


# ---------------------------------------------------------------------------
# 필요현금 · 상한가
# ---------------------------------------------------------------------------

def required_cash(price: float, profile: dict, policy: dict, *,
                  jeonse_deposit: float | None = None,
                  area_m2: float = 84.0) -> dict:
    """실제 필요 현금 = 매매가 - 대출(또는 전세보증금) + 부대비용."""
    gap = profile.get("purpose") == "gap"
    house_after = _house_after(profile)
    regulated, _ = region_flags(profile.get("region_codes") or [], policy)
    costs = calc_costs(price, area_m2=area_m2, house_after=house_after,
                       regulated=regulated,
                       first_time=bool(profile.get("is_first_time")), policy=policy)
    if gap:
        lev = min(jeonse_deposit or 0, price * 0.9)
        loan_info = {"loan": 0, "jeonse_deposit": round(lev)}
        leverage = lev
    else:
        loan_info = expected_loan(price, profile, policy)
        leverage = loan_info["loan"]
    req = price - leverage + costs["costs_total"]
    preserve = profile.get("preserve_cash", policy["preserve_cash_default"])
    return {
        "price": round(price), "leverage": round(leverage),
        "loan_info": loan_info, "costs": costs,
        "required_cash": round(req),
        "required_with_reserve": round(req + preserve),
        "preserve_cash": preserve,
    }


def _house_after(profile: dict) -> int:
    b = profile.get("buyer_type", "none")
    return {"none": 1, "first": 1, "sell_one": 1, "keep_one": 2, "multi": 3}.get(b, 1)


def risk_level(required_with_reserve: float, cash: float) -> str:
    if cash <= 0:
        return "불가"
    r = required_with_reserve / cash
    if r <= 0.85:
        return "안정"
    if r <= 0.95:
        return "보통"
    if r <= 1.0:
        return "빠듯"
    return "불가"


def max_affordable_price(profile: dict, policy: dict, *,
                         jeonse_ratio: float | None = None) -> int:
    """필요현금(예비비 포함) ≤ 보유현금인 최대 매매가 — 이분탐색(필요현금은 가격에 단조증가)."""
    cash = profile.get("cash_on_hand") or 0
    if cash <= 0:
        return 0
    area = (profile.get("area_min") or 59) if profile.get("purpose") == "gap" else \
        (profile.get("area_max") or 84)

    def feasible(price: float) -> bool:
        jd = price * jeonse_ratio if (jeonse_ratio and profile.get("purpose") == "gap") else None
        r = required_cash(price, profile, policy, jeonse_deposit=jd, area_m2=area)
        return r["required_with_reserve"] <= cash

    lo, hi = 0, 5_000_000_000
    if not feasible(50_000_000):
        return 0
    while hi - lo > 5_000_000:
        mid = (lo + hi) // 2
        if feasible(mid):
            lo = mid
        else:
            hi = mid
    return int(lo // 5_000_000 * 5_000_000)


def rooms_estimate(excl: float | None) -> tuple[str, str]:
    """전용면적 기반 방/욕실 추정(관례) — 실데이터 아님, '추정' 표기 필수."""
    if excl is None:
        return "-", "-"
    if excl < 45:
        return "1~2", "1"
    if excl < 59:
        return "2~3", "1"
    if excl < 84:
        return "3", "2"
    if excl < 115:
        return "3~4", "2"
    return "4+", "2+"


# ---------------------------------------------------------------------------
# 추천 엔진
# ---------------------------------------------------------------------------

def recommend(conn, profile: dict, policy: dict, limit: int = 30) -> dict:
    """현재 매물 기반 후보 → 12개월 실거래 대조 → 필요현금·위험도·점수."""
    codes = profile.get("region_codes") or []
    dongs = profile.get("dong_codes") or []
    if not codes and not dongs:
        return {"error": "지역을 선택하세요"}
    prefixes = [d[:10] for d in dongs] if dongs else [c[:5] for c in codes]
    a_min = profile.get("area_min") or 0
    a_max = profile.get("area_max") or 300
    cash = profile.get("cash_on_hand") or 0

    # 갭투자 상한가용 전세가율(지역 최근 6개월) — 대략치
    jeonse_ratio = None
    if profile.get("purpose") == "gap":
        conds = " OR ".join("c.cortar_no LIKE ?" for _ in prefixes)
        row = conn.execute(
            f"""SELECT AVG(r.deposit * 1.0) / AVG(t.deal_amount) FROM complexes c
                JOIN rentals r ON r.matched_complex_no = c.complex_no
                    AND r.monthly_rent = 0 AND r.deal_ymd >= date('now','+9 hours','-6 months')
                JOIN transactions t ON t.matched_complex_no = c.complex_no
                    AND t.is_cancelled = 0 AND t.deal_ymd >= date('now','+9 hours','-6 months')
                WHERE ({conds})""",
            [p + "%" for p in prefixes]).fetchone()
        jeonse_ratio = min(0.9, max(0.3, row[0])) if row and row[0] else 0.6

    max_price = max_affordable_price(profile, policy, jeonse_ratio=jeonse_ratio)
    summary_calc = required_cash(
        max_price, profile, policy,
        jeonse_deposit=(max_price * jeonse_ratio if jeonse_ratio else None),
        area_m2=profile.get("area_max") or 84) if max_price else None

    if not max_price:
        return {"max_price": 0, "summary": None, "items": [],
                "jeonse_ratio": jeonse_ratio}

    # 후보: 현재 매물(최신 스냅샷, 매매) — 단지×면적명 단위 최저호가
    conds = " OR ".join("c.cortar_no LIKE ?" for _ in prefixes)
    rows = conn.execute(
        f"""SELECT l.complex_no, c.complex_name, c.cortar_no, r.cortar_name,
                   l.area_name, l.area2_m2,
                   MIN(l.deal_or_warrant_price), COUNT(*),
                   c.total_household_count, c.use_approve_ymd
            FROM listings_current l
            JOIN complexes c ON c.complex_no = l.complex_no
            LEFT JOIN regions r ON r.cortar_no = c.cortar_no
            WHERE l.trade_type = 'A1'
              AND c.real_estate_type_name IN ('아파트', '재건축')
              AND ({conds})
              AND l.area2_m2 BETWEEN ? AND ?
              AND l.deal_or_warrant_price > 0
              AND l.deal_or_warrant_price <= ?
              AND l.snapshot_date = (SELECT MAX(snapshot_date) FROM listings_current)
            GROUP BY l.complex_no, l.area_name
            ORDER BY MIN(l.deal_or_warrant_price) DESC
            LIMIT 400""",
        [p + "%" for p in prefixes] + [a_min, a_max, max_price * 1.05]).fetchall()

    sc = policy["score"]
    items = []
    for (cno, cname, cortar, region_name, aname, excl, min_ask, n_ask,
         households, approve) in rows:
        # 최근 12개월 실거래 (같은 평형 ±1.5㎡)
        tx = conn.execute(
            """SELECT AVG(deal_amount), COUNT(*), MAX(deal_ymd) FROM transactions
               WHERE matched_complex_no=? AND is_cancelled=0
                 AND deal_ymd >= date('now','+9 hours','-12 months')
                 AND ABS(excl_use_ar - ?) <= 1.5""",
            (cno, excl or 0)).fetchone()
        tx_avg, tx_n, tx_last = (tx[0], tx[1], tx[2]) if tx else (None, 0, None)

        jd = None
        if profile.get("purpose") == "gap":
            jr = conn.execute(
                """SELECT AVG(deposit) FROM rentals
                   WHERE matched_complex_no=? AND monthly_rent=0
                     AND deal_ymd >= date('now','+9 hours','-6 months')
                     AND ABS(excl_use_ar - ?) <= 1.5""",
                (cno, excl or 0)).fetchone()
            jd = jr[0] if jr and jr[0] else (min_ask * (jeonse_ratio or 0.6))

        calc = required_cash(min_ask, profile, policy,
                             jeonse_deposit=jd, area_m2=excl or 84)
        risk = risk_level(calc["required_with_reserve"], cash)
        if risk == "불가":
            continue

        score = 0
        ratio = calc["required_with_reserve"] / cash if cash else 9
        if ratio <= 0.85:
            score += sc["afford_85"]
        elif ratio <= 0.95:
            score += sc["afford_95"]
        else:
            score += sc["afford_100"]
        disc = None
        if tx_avg:
            disc = (tx_avg - min_ask) / tx_avg
            if disc >= 0.03:
                score += sc["cheap_3pct"]
            elif disc >= -0.03:
                score += sc["similar"]
            elif disc <= -0.05:
                score += sc["expensive_5pct"]
        score += sc["has_listing"] if n_ask else sc["tx_only"]
        if a_min <= (excl or 0) <= a_max:
            score += sc["area_fit"]
        if dongs:
            score += sc["region_exact"]

        rooms, baths = rooms_estimate(excl)
        items.append({
            "complex_no": cno, "complex_name": cname,
            "region": region_name, "area_name": aname, "excl": excl,
            "min_ask": min_ask, "n_ask": n_ask,
            "tx_avg": round(tx_avg) if tx_avg else None, "tx_n": tx_n,
            "tx_last": tx_last, "discount": round(disc, 4) if disc is not None else None,
            "households": households, "approve_ymd": approve,
            "rooms_est": rooms, "baths_est": baths,
            "leverage": calc["leverage"], "loan_info": calc["loan_info"],
            "costs": calc["costs"],
            "required_cash": calc["required_cash"],
            "required_with_reserve": calc["required_with_reserve"],
            "risk": risk, "score": score,
        })

    # 동점이면 예산 상한에 가까운(=더 상급) 매물 우선 — 최저가 구축만 상단을 채우는 것 방지
    items.sort(key=lambda x: (-x["score"], -x["min_ask"]))
    return {
        "max_price": max_price,
        "summary": summary_calc,
        "jeonse_ratio": round(jeonse_ratio, 3) if jeonse_ratio else None,
        "candidates_scanned": len(rows),
        "items": items[:limit],
    }
