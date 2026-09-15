# -*- coding: utf-8 -*-
"""상업용(상가·사무실) 개업입지 Phase 0 — 계획서 design/academy_commercial/.

주거판(academy.py) 프레임 재사용: region_metrics 키를 맞춰 national_basis/abs_score
(절대등급 S~D)를 그대로 쓴다. 차이는 원천 — 실거래 대신 광고 흐름 실측:
  - comm_flow_daily(date×cortar×type×{new,gone,re}): nfind 아카이브 diff 배치 적재.
    소멸(실거래+회수의 상한 추정) = gone − re(7일 내 재등록).
  - dong_daily: 스톡·호가 시계열(수집기 적재, 55일+).
  - listings 현 스냅샷: 건별 보수(환산보증금×0.9%)·경쟁 중개사·무권리 문구.
가격 단위 주의: listings_sangga/office는 **만원** (listings_current의 원과 다름).
"""
from __future__ import annotations

import math
import re as _re

try:
    from scripts.academy import DEALS_PER_AGENT_MAX
except ModuleNotFoundError:                     # 단독 실행(자가검증)용
    from academy import DEALS_PER_AGENT_MAX

# ── 보정계수(상업 전용 — 주거 COEF와 분리 튜닝) ─────────────────────
COEF_C = {
    # 광고 소멸 중 실제 '거래 성사'로 보는 비율. 상업 광고는 30일 만료 자동소멸이
    # 지배적(만료 후 '새 광고번호' 재등록은 re 차감에 안 잡힘) → 소멸의 대부분이
    # 만료 사이클이라 강하게 보수적으로. 실측(2026-09-04): 0.5면 역삼동 월성사
    # 2,700건(스톡 월 1회전 전부 성사)이라는 비현실 → 0.12로 시작, Phase 3 캘리브레이션.
    "close_rate": 0.12,
    # 상업 중개보수 상한 0.9% 중 실수취(협의 관행). 상한 표기와 함께 화면 명시.
    "realize": 0.70,
    "both_side": 1.1,        # 양타(상업은 전속·단독 의뢰 비중이 낮아 주거보다 소폭 낮게)
    # 매매(실거래) 중 중개 경유 비율 — 주거판 success_sale과 동일 근거(직거래 ~10%).
    "success_sale": 0.90,
}
FEE_RATE = 0.009             # 주택 외(상가·사무실·토지) 일률 0.9% 이내 협의
SCENARIOS_C = {"보수": 0.6, "기본": 1.0, "공격": 1.6}
WINDOW = 28                  # 흐름·시세 관측 윈도(일)

# 권리금 문구(상가): premium_price 미기재 관행 → feature_desc에서 추출
_RE_NO_PREMIUM = _re.compile(r"무\s*권리")
_RE_PREMIUM_AMT = _re.compile(r"권리금?\s*([0-9,.]+)\s*(억|천만?|만)?")


def premium_from_desc(desc: str) -> tuple[bool, int]:
    """(무권리 여부, 언급 권리금 만원). 못 찾으면 (False, 0)."""
    if not desc:
        return False, 0
    if _RE_NO_PREMIUM.search(desc):
        return True, 0
    m = _RE_PREMIUM_AMT.search(desc)
    if not m:
        return False, 0
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return False, 0
    unit = m.group(2) or ""
    if unit == "억":
        v *= 10000
    elif unit.startswith("천"):
        v *= 1000
    return False, int(v)


def lease_conv_sql(alias: str = "") -> str:
    """환산보증금(원) — 만원 단위 컬럼 ×1e4. 보증금+월세×100."""
    p = (alias + ".") if alias else ""
    return f"(COALESCE({p}deal_or_warrant_price,0)+COALESCE({p}rent_price,0)*100)*10000.0"


def region_metrics_c(*, kind: str, cortar: str,
                     flow_new: int, flow_gone: int, flow_re: int, flow_days: int,
                     stock_lease: int, stock_sale: int,
                     lease_conv_avg: float, lease_fee_avg: float,
                     sale_n12: int, sale_avg: float, sale_fee_avg: float,
                     agents: int, no_premium_rate: float = 0.0,
                     rent_trend: float = 0.0) -> dict:
    """동/구 원자료 → 상업 입지 원지표. 키는 주거판 basis 호환(per_agent_tx, m_total,
    sale_avg, lease_avg)을 유지한다.
    Phase 1(2026-09-04): 매매는 국토부 상업업무용 **실거래**(nrg_transactions, 12개월) —
    flow_*(광고 소멸)는 임대(B2) 전용이 됐다."""
    agents = max(int(agents or 0), 1)
    days = max(flow_days, 1)
    closed = max((flow_gone or 0) - (flow_re or 0), 0)     # 재등록 차감한 순소멸(임대)
    m_lease = closed / days * 30.0 * COEF_C["close_rate"]  # 월환산 임대 성사 추정
    m_sale = (sale_n12 or 0) / 12.0 * COEF_C["success_sale"]   # 월환산 매매(실거래×중개경유)
    m_new = (flow_new or 0) / days * 30.0
    m_total = m_lease + m_sale
    agents_eff = max(agents, math.ceil(m_total / DEALS_PER_AGENT_MAX)) if m_total else agents
    stock = (stock_lease or 0) + (stock_sale or 0)
    gone_daily = closed / days
    return {
        "kind": kind, "cortar": cortar,
        "agents": agents, "agents_eff": agents_eff,
        "m_total": round(m_total, 2), "m_new": round(m_new, 2),
        "m_lease": round(m_lease, 2), "m_sale": round(m_sale, 2),
        "sale_n12": int(sale_n12 or 0),
        "per_agent_tx": round(m_total / agents_eff, 3),
        "stock": stock, "stock_lease": int(stock_lease or 0), "stock_sale": int(stock_sale or 0),
        "turn_days": round(stock_lease / gone_daily, 1) if gone_daily > 0 else None,  # 임대 재고 회전일수
        "lease_avg": int(lease_conv_avg or 0),      # 환산보증금(원) — basis price축
        "sale_avg": int(sale_avg or 0),             # 매매 실거래 평균(원)
        "lease_fee_avg": int(lease_fee_avg or 0),   # 건별 0.9% 평균(원, 상한 기준)
        "sale_fee_avg": int(sale_fee_avg or 0),
        "no_premium_rate": round(no_premium_rate, 3),
        "rent_trend": round(rent_trend, 4),         # 4주 임대료 방향(비율, +상승)
    }


def revenue_sim_c(m: dict, *, occupancy: float = 1.0, costs: dict | None = None) -> dict:
    """상업 수익시뮬. 매출 = 월성사 × 건별보수(상한×실수취) ÷ 경쟁 × 점유 × 양타.
    임대=광고 소멸 추정, 매매=실거래(Phase 1) — region_metrics_c에서 분리 산출됨."""
    agents = m["agents_eff"]
    m_lease = m.get("m_lease", 0)
    m_sale = m.get("m_sale", 0)
    fee_l = (m["lease_fee_avg"] or 0) * COEF_C["realize"]
    fee_s = (m["sale_fee_avg"] or 0) * COEF_C["realize"]
    rev = (m_lease * fee_l + m_sale * fee_s) / agents * occupancy * COEF_C["both_side"]
    c = costs or {}
    cost = sum(int(c.get(k, 0) or 0) for k in ("rent", "staff", "ad", "assoc"))
    return {
        "occupancy": round(occupancy, 2),
        "est_lease_deals": round(m_lease / agents * occupancy, 2),
        "est_sale_deals": round(m_sale / agents * occupancy, 2),
        "revenue": int(rev), "cost": int(cost), "profit": int(rev - cost),
        "costs": {k: int(c.get(k, 0) or 0) for k in ("rent", "staff", "ad", "assoc")},
        "fee_note": (f"상한 0.9%×실수취 {COEF_C['realize']:.0%} · 임대 성사율 {COEF_C['close_rate']:.0%}(광고 소멸 기반) · "
                     f"매매 = 실거래×중개경유 {COEF_C['success_sale']:.0%}"),
    }


def scenarios_c(m: dict, costs: dict | None = None) -> dict:
    return {name: revenue_sim_c(m, occupancy=occ, costs=costs)
            for name, occ in SCENARIOS_C.items()}


if __name__ == "__main__":
    ok = 0

    def chk(name, got, want):
        global ok
        good = got == want
        ok += good
        print(("  ✓ " if good else "  ✗ ") + f"{name}: {got!r}" + ("" if good else f" (기대 {want!r})"))

    chk("무권리", premium_from_desc("무권리 1층 코너"), (True, 0))
    chk("권리금 5천", premium_from_desc("권리금 5,000만원 협의"), (False, 5000))
    chk("권리 1억", premium_from_desc("권리 1억 시설최상"), (False, 10000))
    chk("언급 없음", premium_from_desc("역세권 코너 상가"), (False, 0))
    m = region_metrics_c(kind="sangga", cortar="1168010300",
                         flow_new=280, flow_gone=250, flow_re=50, flow_days=28,
                         stock_lease=900, stock_sale=100,
                         lease_conv_avg=3e8, lease_fee_avg=int(3e8 * FEE_RATE),
                         sale_n12=48, sale_avg=12e8, sale_fee_avg=int(12e8 * FEE_RATE),
                         agents=20)
    # 임대: 순소멸 200/28일 → 월 214.29 × 0.12 = 25.71 / 매매: 48/12 × 0.9 = 3.6
    chk("월성사(임대+매매)", m["m_total"], 29.31)
    chk("임대 회전일수", m["turn_days"], 126.0)
    s = revenue_sim_c(m, costs={"rent": 2_000_000, "ad": 300_000})
    chk("매출>0", s["revenue"] > 0, True)
    print(f"  (참고) 기본 시나리오 월매출 {s['revenue']/1e4:,.0f}만·순익 {s['profit']/1e4:,.0f}만")
    print(f"통과 {ok}/7")
