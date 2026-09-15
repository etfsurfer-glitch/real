# -*- coding: utf-8 -*-
"""개업 입지 + 수익 시뮬레이터 계산 (공인중개사 학원 제휴 특별기능).

순수 함수 모듈 — DB 접근 없음. local_api.py 의 /admin/academy/* 엔드포인트가
동/단지별 원자료(거래건수·평균가·활성중개사수·세대수)를 넘겨주면 여기서
① 입지 점수(정규화는 호출부에서 세트 단위로) ② 수익 시뮬레이션을 계산한다.

중개보수 요율은 frontend/src/lib/buycalc.ts 와 동일(상한요율·permille 정수연산).
보정계수(COEF)는 튜닝 대상 — Phase 3 실측 캘리브레이션 전까지 보수적 디폴트.
"""
from __future__ import annotations

# ── 중개보수 상한요율 (buycalc.ts 포팅). (미만 경계, permille, 한도) ──
_SALE = [(5e7, 6, 25e4), (2e8, 5, 80e4), (9e8, 4, None),
         (12e8, 5, None), (15e8, 6, None), (float("inf"), 7, None)]
_LEASE = [(5e7, 5, 20e4), (1e8, 4, 30e4), (6e8, 3, None),
          (12e8, 4, None), (15e8, 5, None), (float("inf"), 6, None)]


def _fee(price: float, tiers) -> int:
    if not price or price <= 0:
        return 0
    for cap, pm, lim in tiers:
        if price < cap:
            f = int(price * pm // 1000)      # 정수연산: 상한 초과·부동소수점 오차 없음
            return min(f, lim) if lim else f
    return 0


def sale_fee(price: float) -> int:
    """매매 1건 중개보수(원). 매도·매수 각각이므로 일방 기준."""
    return _fee(price, _SALE)


def lease_fee(price: float) -> int:
    """임대차 1건 중개보수(원). 보증금 환산가 기준(월세는 호출부에서 환산)."""
    return _fee(price, _LEASE)


def _fee_sql(expr: str, tiers) -> str:
    """요율표를 SQL CASE식으로 — 지역 평균가 1점이 아니라 **거래 건별** 요율 적용
    (구간·한도가 비선형이라 평균가 방식은 분포에 따라 오차. 2026-09-04 정밀화).
    티어 테이블(_SALE/_LEASE) 단일 소스에서 생성해 파이썬 계산과 이원화 방지."""
    parts = []
    for cap, pm, lim in tiers:
        base = f"CAST(({expr})*{pm}/1000 AS INTEGER)"
        val = f"MIN({base}, {int(lim)})" if lim else base
        if cap == float("inf"):
            parts.append(f"ELSE {val}")
        else:
            parts.append(f"WHEN ({expr}) < {int(cap)} THEN {val}")
    return "CASE " + " ".join(parts) + " END"


def sale_fee_sql(expr: str = "deal_amount") -> str:
    return _fee_sql(expr, _SALE)


def lease_fee_sql(expr: str) -> str:
    return _fee_sql(expr, _LEASE)


# ── 보정계수 (튜닝 대상) ──────────────────────────────────────────────
COEF = {
    "occupancy": 1.00,       # 기본=안착 중개사(동 평균 1인당 거래를 잡음). 신규 램프는 시나리오로.
    # 경유율 현실화(2026-09-01, 사용자 보정 지시): 부동산업 특성상 직거래·타지역 빈도는 낮다.
    # 매매 직거래(친족·증여성 포함)는 신고 기준 ~10% 미만 → 0.90.
    # 임대는 **갱신계약을 집계에서 제외**(전체의 35%, 중개보수 미발생)한 신규 기준이라
    # 직거래가 드묾 → 0.95. (이전 0.55/0.65는 갱신 혼입을 어림하던 값)
    "success_sale": 0.90,
    "success_lease": 0.95,
    "both_side": 1.2,        # 양타 계수(1.0=일방만, 일부 양타 성사 반영 1.2)
}
# 시나리오별 occupancy — 보수(신규 초기)/기본(안착)/공격(상위 중개사)
SCENARIOS = {"conservative": 0.60, "base": 1.00, "aggressive": 1.50}

# 입지 점수 축 가중치 (합=1)
WEIGHTS = {"competition": 0.40, "demand": 0.35, "price": 0.25}


def cost_defaults(avg_deal_amount: float = 0) -> dict:
    """월 고정비 제안값(원) — 수동입력 프리필용. 임대료는 지역 평균 거래가로 러프 프록시
    (상가 임대 실거래 확보 전까지 '추정 제안값'). 사용자가 화면에서 덮어쓴다."""
    a = avg_deal_amount or 0
    if a >= 15e8:
        rent = 4_000_000
    elif a >= 7e8:
        rent = 2_500_000
    elif a >= 3e8:
        rent = 1_500_000
    else:
        rent = 1_000_000
    return {"rent": rent, "staff": 0, "ad": 300_000, "assoc": 50_000}


import math

# 중개사 1인이 월에 소화 가능한 현실적 상한(매매+임대). 중개사수 과소집계(realtor_dong 커버 공백)
# 로 분모가 작아져 수익이 폭주하는 것을 막는다 → 유효중개사수 하한 = 거래량÷이 값.
DEALS_PER_AGENT_MAX = 5.0


def region_metrics(*, sale_n: int, lease_n: int, sale_avg: float, lease_avg: float,
                   agents: int, months: int = 12, households: int = 0,
                   sale_fee_avg: float = 0, lease_fee_avg: float = 0) -> dict:
    """동/단지 원자료 → 입지 원지표(정규화 전).
    sale_fee_avg/lease_fee_avg: 거래 **건별** 상한요율 적용 후 평균 보수(원) — SQL
    _fee_sql 집계값. 0이면 revenue_sim이 평균가 방식으로 폴백(데모·구버전 호환)."""
    agents = max(int(agents or 0), 1)
    m_sale = (sale_n or 0) / months
    m_lease = (lease_n or 0) / months
    m_total = m_sale + m_lease
    # 유효 중개사수: 실집계와 '거래량이 함의하는 최소치' 중 큰 값 → 1인당 거래 ≤ 상한
    agents_eff = max(agents, math.ceil(m_total / DEALS_PER_AGENT_MAX)) if m_total else agents
    return {
        "agents": agents, "agents_eff": agents_eff,
        "sale_n": int(sale_n or 0), "lease_n": int(lease_n or 0),
        "sale_avg": int(sale_avg or 0), "lease_avg": int(lease_avg or 0),
        "sale_fee_avg": int(sale_fee_avg or 0), "lease_fee_avg": int(lease_fee_avg or 0),
        "m_sale": round(m_sale, 2), "m_lease": round(m_lease, 2),
        "m_total": round(m_total, 2),
        "per_agent_tx": round(m_total / agents_eff, 3),      # 1인당 월거래(경쟁 역지표)
        "turnover": round((sale_n / households) * 100, 2) if households else None,  # 세대대비 연거래율%
    }


def revenue_sim(m: dict, *, occupancy: float | None = None, costs: dict | None = None,
                initial_cost: float = 0) -> dict:
    """입지 원지표 + 점유율 + 비용 → 예상 월매출·순이익·손익분기."""
    occ = COEF["occupancy"] if occupancy is None else float(occupancy)
    agents = m.get("agents_eff") or m["agents"]
    # 지역중개 경유분을 활성중개사가 나누고, 신규는 그 몫의 occ 배
    est_sale = (m["m_sale"] * COEF["success_sale"]) / agents * occ
    est_lease = (m["m_lease"] * COEF["success_lease"]) / agents * occ
    # 건당 보수: 지역 거래 분포에 건별 요율을 적용한 평균(정확) — 없으면 평균가 1점 방식 폴백
    fee_s = m.get("sale_fee_avg") or sale_fee(m["sale_avg"])
    fee_l = m.get("lease_fee_avg") or lease_fee(m["lease_avg"])
    rev_sale = est_sale * fee_s * COEF["both_side"]
    rev_lease = est_lease * fee_l * COEF["both_side"]
    revenue = rev_sale + rev_lease
    c = costs or cost_defaults(m["sale_avg"])
    cost = sum(int(c.get(k, 0) or 0) for k in ("rent", "staff", "ad", "assoc"))
    profit = revenue - cost
    out = {
        "occupancy": round(occ, 2),
        "est_sale_deals": round(est_sale, 2), "est_lease_deals": round(est_lease, 2),
        "revenue_sale": int(rev_sale), "revenue_lease": int(rev_lease),
        "revenue": int(revenue), "cost": int(cost), "profit": int(profit),
        "costs": {k: int(c.get(k, 0) or 0) for k in ("rent", "staff", "ad", "assoc")},
    }
    if initial_cost and profit > 0:
        out["breakeven_months"] = round(initial_cost / profit, 1)
    return out


def scenarios(m: dict, costs: dict | None = None) -> dict:
    """보수/기본/공격 3종 시나리오 예상 순이익."""
    return {name: revenue_sim(m, occupancy=occ, costs=costs)
            for name, occ in SCENARIOS.items()}


# ── 입지 점수(절대): 전국 분포 백분위 기반 ─────────────────────────────
# 뷰포트 상대평가(score_set)는 지도를 옮길 때마다 등급이 요동해 신뢰를 깎는다 →
# 레벨별(구끼리/동끼리/단지끼리) 전국 분포에 대한 백분위로 절대화(2026-09-01, 사용자 결정).
# 등급 컷 고정: S=상위5% / A=15% / B=40% / C=70% / D=나머지.
import bisect

GRADE_CUTS = ((95.0, "S"), (85.0, "A"), (60.0, "B"), (30.0, "C"))


def _pct(sorted_vals: list, v: float) -> float:
    """정렬된 전국 분포에서 v의 백분위(0~100)."""
    if not sorted_vals:
        return 50.0
    return bisect.bisect_right(sorted_vals, v) / len(sorted_vals) * 100.0


def _axes_of(m: dict) -> tuple[float, float, float]:
    return (m["per_agent_tx"], m["m_total"], float(max(m["sale_avg"], m["lease_avg"])))


def national_basis(metrics_list: list[dict]) -> dict:
    """전국 지역 metrics → 축별 정렬분포 + 종합점수 분포(절대등급 기준표).
    일 1회 사전계산해 캐시한다(호출부)."""
    pa = sorted(x["per_agent_tx"] for x in metrics_list)
    mt = sorted(x["m_total"] for x in metrics_list)
    pr = sorted(float(max(x["sale_avg"], x["lease_avg"])) for x in metrics_list)
    b = {"pa": pa, "mt": mt, "pr": pr, "n": len(metrics_list)}
    comps = []
    for x in metrics_list:
        a, t, p = _axes_of(x)
        comps.append(_pct(pa, a) * WEIGHTS["competition"]
                     + _pct(mt, t) * WEIGHTS["demand"]
                     + _pct(pr, p) * WEIGHTS["price"])
    b["comp"] = sorted(comps)
    return b


def abs_score(m: dict, basis: dict) -> None:
    """전국 basis 대비 절대 점수·등급을 m에 in-place 기록. 뷰포트와 무관하게 안정."""
    a, t, p = _axes_of(m)
    comp = (_pct(basis["pa"], a) * WEIGHTS["competition"]
            + _pct(basis["mt"], t) * WEIGHTS["demand"]
            + _pct(basis["pr"], p) * WEIGHTS["price"])
    s = _pct(basis["comp"], comp)          # 전국 백분위(=상위 100-s %)
    m["score"] = round(s, 1)
    m["grade"] = next((g for cut, g in GRADE_CUTS if s >= cut), "D")


# ── (구) 상대 정규화 — 절대화로 대체됨. 화면 내 순위 등 보조용으로만 유지 ──
def score_set(metrics_list: list[dict]) -> None:
    """metrics dict 리스트를 받아 각 항목에 score(0~100)·grade 를 in-place 추가.
    경쟁(1인당거래 높을수록↑좋음)·수요(월거래총량↑)·시세(평균가↑, 수수료규모) 3축을
    세트 내 min-max 정규화 후 가중합. 세트가 1개면 중앙값 처리."""
    if not metrics_list:
        return

    def norm(vals):
        lo, hi = min(vals), max(vals)
        if hi <= lo:
            return [50.0] * len(vals)
        return [(v - lo) / (hi - lo) * 100 for v in vals]

    comp = norm([x["per_agent_tx"] for x in metrics_list])          # ↑ = 경쟁 여유
    dem = norm([x["m_total"] for x in metrics_list])                # ↑ = 수요
    pri = norm([max(x["sale_avg"], x["lease_avg"]) for x in metrics_list])  # ↑ = 수수료 규모
    for x, cscore, dscore, pscore in zip(metrics_list, comp, dem, pri):
        s = (cscore * WEIGHTS["competition"] + dscore * WEIGHTS["demand"]
             + pscore * WEIGHTS["price"])
        x["score"] = round(s, 1)
        x["grade"] = ("S" if s >= 80 else "A" if s >= 65 else "B" if s >= 45
                      else "C" if s >= 25 else "D")


if __name__ == "__main__":  # 간이 자가검증
    demo = [
        dict(name="개포동", **region_metrics(sale_n=413, lease_n=2670, sale_avg=int(28.5e8),
             lease_avg=int(6e8), agents=213)),
        dict(name="역삼동", **region_metrics(sale_n=316, lease_n=2201, sale_avg=int(18.1e8),
             lease_avg=int(5e8), agents=457)),
        dict(name="중계동", **region_metrics(sale_n=1461, lease_n=3340, sale_avg=int(7.2e8),
             lease_avg=int(3e8), agents=86)),
    ]
    score_set(demo)
    for d in demo:
        r = revenue_sim(d)
        print(f"{d['name']}: 점수 {d['score']}({d['grade']}) | 1인당월거래 {d['per_agent_tx']} "
              f"| 예상매출 {r['revenue']//10000}만 순이익 {r['profit']//10000}만")
