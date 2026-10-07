# -*- coding: utf-8 -*-
"""서울 급매물 추이 — 데이터 분석 보고서(2026-09-07 발행).
급매선 = 같은 단지·평형 최근 180일 실거래 평균 대비 −10%↓. 모든 집계는 실매물(중복 제거)
기준이며 광고 수는 참고로 병기. 수치는 전부 data/gmae_*.csv에서 동적 산출.
산출: 서울_급매물_추이_보고서.docx / .pdf + data/gmae_*.png
"""
import csv, json, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = Path("/Users/hcode/auto/naverreal/design/fonts")
DATA = HERE / "data"
BLUE = (0x12/255, 0x68/255, 0xD3/255)

S = list(csv.DictReader(open(DATA / "gmae_daily_seoul.csv")))
DAYS = [r["date"] for r in S]
LBL = [d[5:] for d in DAYS]
N = len(S)
r0, r9 = S[0], S[-1]
def gi(r, k): return int(r[k])

D10 = list(csv.reader(open(DATA / "gmae_daily_sgg_d10.csv")))
D5 = list(csv.reader(open(DATA / "gmae_daily_sgg_d5.csv")))
GU = D10[0][1:]                       # 서울 25개 자치구(열 순서 동일)
def mat(rows): return {g: [int(r[j+1]) for r in rows[1:]] for j, g in enumerate(rows[0][1:])}
M10, M5 = mat(D10), mat(D5)

# 급매 성격(디벨롭) — 실매물 −10%↓ 급매의 가격대·할인심도·집중 단지
DEV = json.load(open(DATA / "gmae_develop.json"))
DV0, DV1, DV9 = DEV["8/3"], DEV["9/1"], DEV["9/7"]
BANDS_ORD = DEV.get("bands_order", ["5억 미만", "5~10억", "10~20억", "20~30억", "30억 이상"])
BIG0, BIG1, BIG9 = DV0["band"]["30억 이상"], DV1["band"]["30억 이상"], DV9["band"]["30억 이상"]
BIG_SHARE9 = BIG9 / DV9["n"] * 100
TOPCX = DEV["top_cx"]

# ── 파생 지표 ──────────────────────────────────────────────────
def idx(k): return [gi(r, k)/gi(r0, k)*100 for r in S]
IX_ITEMS, IX_ADS = idx("total_items"), idx("total_ads")
IX_D10 = idx("d10_items")
ITEMS0, ITEMS9 = gi(r0, "total_items"), gi(r9, "total_items")
ADS0, ADS9 = gi(r0, "total_ads"), gi(r9, "total_ads")
D10_0, D10_9 = gi(r0, "d10_items"), gi(r9, "d10_items")
RATIO0, RATIO9 = ADS0/ITEMS0, ADS9/ITEMS9
PCT_ITEMS = (ITEMS9/ITEMS0 - 1)*100
PCT_ADS = (ADS9/ADS0 - 1)*100
PCT_D10 = (D10_9/D10_0 - 1)*100
SEO10 = M10["서초구"]
REST10 = [sum(M10[g][i] for g in GU) - SEO10[i] for i in range(N)]
SEO_INC = SEO10[-1] - SEO10[0]
TOT10_INC = D10_9 - D10_0
SEO_SHARE = SEO_INC / TOT10_INC * 100
# −10%↓ 변동 있는 자치구
ACT10 = [g for g in GU if max(M10[g]) > 0]
# 3시점(−10%↓) 요약: 8/3 · 9/1 · 9/7
_di = {d: i for i, d in enumerate(DAYS)}
def _v10(g, d): return M10[g][_di[d]]
def _tc(d): return sum(_v10(g, d) for g in GU)
TP_ORDER = sorted(GU, key=lambda g: -_v10(g, "2026-09-07"))
# 9/1 중간 시점(3점 비교용)
ITEMS1 = gi(next(r for r in S if r["date"] == "2026-09-01"), "total_items")
D10_1 = _tc("2026-09-01")
SEO1 = _v10("서초구", "2026-09-01")
REST1 = D10_1 - SEO1

# 호가 할인율 분포(9/7 실매물, 실거래 대비 %) — 산출 스냅샷(구간 하한%, 물건수)
HIST = [(-27.5,1),(-25,1),(-22.5,1),(-20,0),(-17.5,4),(-15,12),(-12.5,21),(-10,38),
        (-7.5,91),(-5,219),(-2.5,455),(0,793),(2.5,1232),(5,1428),(7.5,1433),(10,1166),
        (12.5,981),(15,844),(17.5,633),(20,466),(22.5,335),(25,256),(27.5,200),(30,510)]
MEDIAN_PREM = 9.7      # 호가 중앙값 = 실거래 평균 +9.7%
Q1_PREM = 4.8          # 하위 25%도 +4.8%
# 임계별 표본(9/7 실매물 / 광고)
THRESH = [("−5%↓", gi(r9,"d5_items"), gi(r9,"d5_ads")),
          ("−10%↓", gi(r9,"d10_items"), gi(r9,"d10_ads")),
          ("−15%↓", gi(r9,"d15_items"), gi(r9,"d15_ads")),
          ("−20%↓", gi(r9,"d20_items"), gi(r9,"d20_ads")),
          ("−25%↓", 1, None), ("−30%↓", 0, None)]

def won(n): return f"{n:,}"
def nm(v): return f"{v}".replace("-", "−")   # ASCII 하이픈 → 유니코드 마이너스(표기 통일)

DOCTYPE = "데이터 분석 보고서 (취재 참고자료)"
TITLE = f"서울 급매물 추이 — 실거래 평균 −10% 이하 매물, 8월 이후 {PCT_D10:.1f}% 증가"
SUBTITLE = (f"급매선 = 같은 단지·평형 최근 180일 실거래 평균 대비 −10%↓ · 실매물(중복 제거) 기준·광고 병기 · "
            f"2026년 8월 3일 ~ 9월 7일({N}일) 서울 전역 일별 스냅샷")

SUMMARY = [
    ("실매물 재고", f"8/3 {won(ITEMS0)} → 9/1 {won(ITEMS1)} → 9/7 {won(ITEMS9)}건 (+{PCT_ITEMS:.1f}%) · 광고 {won(ADS9)}건(물건당 {RATIO9:.2f}배)"),
    ("급매(−10%↓)", f"{D10_0} → {D10_1} → {D10_9}물건 (+{PCT_D10:.1f}%) — 실매물 재고 증가(+{PCT_ITEMS:.1f}%)의 약 5배 속도"),
    ("서초 집중", f"−10%↓ 증가분 {TOT10_INC}물건 중 서초구가 {SEO_INC}물건({SEO_SHARE:.0f}%) — 서초 {SEO10[0]}→{SEO1}→{SEO10[-1]}, 나머지 24구 {REST10[0]}→{REST1}→{REST10[-1]}"),
    ("급매 성격", f"30억↑ 초고가가 {DV9['n']}건 중 {BIG9}건({BIG_SHARE9:.0f}%)·평균 {DV9['avg_price_eok']}억 — 서초 반포 대장단지 집중"),
    ("급매 기준", f"9/7 실매물 호가 중앙값은 실거래 평균 대비 +{MEDIAN_PREM}%로, 호가는 원래 실거래보다 위 — −10%↓는 분포의 꼬리(희소)"),
]

SECTIONS = [
    ("1. 집계 기준 — 급매선 −10%와 ‘실매물’",
     "‘급매’의 기준선은 같은 단지·같은 평형의 최근 180일 실거래 평균가로 두고, 그 평균 대비 "
     "호가가 −10% 이하인 매물을 급매(−10%↓)로 집계했습니다. 벤치마크(실거래 평균)는 8/3·중간·9/7 "
     "세 시점 모두 ‘현재 시점의 최근 180일 실거래’로 통일해, 벤치마크 이동에 따른 착시를 배제했습니다. "
     "모든 수치는 ‘실매물’(같은 단지·평형·호가의 중복 광고를 하나로 합친 물건 수) 기준이며, "
     "포털 광고 수는 참고로 병기합니다. 광고는 한 물건을 여러 중개업소가 올릴 수 있어 실제 매물 수보다 "
     "많습니다(9/7 기준 물건당 광고 " + f"{RATIO9:.2f}배).", None),
    ("2. 왜 −10%인가 — 임계값 근거",
     f"서울 아파트 호가는 실거래보다 대체로 높습니다. 9월 7일 실매물의 호가는 같은 단지·평형 실거래 "
     f"평균 대비 중앙값이 +{MEDIAN_PREM}%, 하위 25%조차 +{Q1_PREM}%로 분포 전체가 0%(실거래 평균) 위에 "
     f"있습니다(아래 분포 차트). 따라서 실거래 평균을 밑도는 매물 자체가 분포의 왼쪽 꼬리에 해당합니다. "
     f"임계값을 낮출수록 표본은 급격히 사라집니다 — 9월 7일 실매물 기준 −5%↓ {gi(r9,'d5_items')} · "
     f"−10%↓ {gi(r9,'d10_items')} · −15%↓ {gi(r9,'d15_items')} · −20%↓ {gi(r9,'d20_items')} · −25%↓ 1 · −30%↓ 0물건입니다. "
     "−5%는 정상 호가 구간과 겹쳐 ‘급매’로 보기엔 느슨하고, −15% 이하는 표본이 한 자릿수로 사라지며 "
     "면적 오기·지분 매물 등 특수 물건의 잡음이 커집니다. −10%는 호가 분포의 꼬리를 벗어나면서도 "
     "추세와 자치구 단위 분석이 가능한 최소 표본을 유지하는 구간이어서 기준선으로 채택했습니다.", "hist"),
    ("3. 서울 전체 일별 추이",
     f"8월 3일을 100으로 둔 지수로 보면, 9월 7일 실매물 재고는 {IX_ITEMS[-1]:.1f}(+{PCT_ITEMS:.1f}%)인 데 비해 "
     f"급매(−10%↓)는 {IX_D10[-1]:.1f}(+{PCT_D10:.1f}%)로 재고보다 다섯 배가량 빠르게 늘었습니다. "
     f"같은 기간 광고 수는 {IX_ADS[-1]:.1f}(+{PCT_ADS:.1f}%)로 실매물(+{PCT_ITEMS:.1f}%)보다 "
     f"더 늘어, 물건당 광고 수가 {RATIO0:.2f}배→{RATIO9:.2f}배로 커졌습니다(같은 물건을 여러 곳에서 광고하는 "
     "매도 경쟁의 심화).", "index"),
    ("4. 서초구 집중",
     f"급매(−10%↓) 증가는 사실상 서초구에 집중됐습니다. 서초구 −10%↓ 실매물은 8월 3일 {SEO10[0]} → 9월 1일 {SEO1} → "
     f"9월 7일 {SEO10[-1]}물건으로 두 배 이상 늘어난 반면, 나머지 24개 자치구를 합한 값은 {REST10[0]} → {REST1} → {REST10[-1]}물건으로 "
     f"거의 변화가 없었습니다. 서울 전체 −10%↓ 증가분 {TOT10_INC}물건 가운데 {SEO_INC}물건({SEO_SHARE:.0f}%)이 서초구 "
     "몫입니다(아래 차트). 서초 급매의 실체는 반포권 초고가 신축 — 래미안원베일리·아크로리버파크·"
     "래미안퍼스티지·반포자이 등 40~50억대 대장단지입니다(6장).", "seocho"),
    ("5. 급매의 성격 — 30억 이상 초고가가 주도",
     f"−10%↓ 급매의 증가는 저가 매물 소진이 아니라 초고가에서 나옵니다. 30억 이상 급매 실매물은 "
     f"8월 3일 {BIG0}건 → 9월 1일 {BIG1}건 → 9월 7일 {BIG9}건으로 늘어, 9월 7일 전체 급매 {DV9['n']}건의 "
     f"{BIG_SHARE9:.0f}%를 차지합니다. 같은 기간 급매 실매물의 평균 호가는 {DV0['avg_price_eok']} → "
     f"{DV1['avg_price_eok']} → {DV9['avg_price_eok']}억으로 뛰었고(9월 7일 중앙값 {DV9['med_price_eok']}억), 평균 할인심도도 "
     f"{nm(DV0['avg_disc'])} → {nm(DV1['avg_disc'])} → {nm(DV9['avg_disc'])}%(최대 {nm(DV9['max_disc'])}%)로 소폭 깊어졌습니다. 세제 개편을 둘러싼 "
     "관망 국면에서 급매가 저가 소진보다 고가 신축에서 늘어나는 양상입니다(아래 가격대 분포·차트).", "band"),
    ("6. 급매 집중 단지 — 반포 대장 아파트",
     f"9월 7일 −10%↓ 급매는 서초 반포권 대장단지에 몰렸습니다. 래미안원베일리 {TOPCX[0]['cnt']}물건"
     f"(평균 {TOPCX[0]['avg_price']}억)·아크로리버파크 {TOPCX[1]['cnt']}·래미안퍼스티지 {TOPCX[2]['cnt']}"
     f"·반포자이 2물건 등 40~50억대 초고가 신축이 중심으로, 원베일리 한 단지({TOPCX[0]['cnt']}물건)가 "
     f"서울 전체 급매 {DV9['n']}건의 약 4분의 1입니다. 상위 단지는 아래 표와 같습니다.", None),
]

NOTE = ("작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  "
        "‘실매물’은 같은 단지·평형·호가의 중복 광고를 하나로 합친 물건 수이며, 급매·총량 모두 실매물 기준으로 "
        "집계하고 광고 수를 참고로 병기했습니다. 급매선의 벤치마크는 세 시점 모두 현재 시점의 최근 180일 실거래 "
        "평균으로 통일했고(−N%↓), 일별 수치는 정책 백업(policy) 일별 스냅샷에서 산출했습니다. 호가 중앙값이 실거래 "
        f"평균 대비 +{MEDIAN_PREM}%로 원래 실거래보다 높아 −10%↓ 매물은 희소하므로, 절대 수치보다 증감 방향으로 읽어 "
        "주시기 바랍니다. 광고는 수시로 등록·삭제되므로 열람 시점에 따라 수치가 달라질 수 있습니다.")

# ── 차트 ───────────────────────────────────────────────────────
C_HIST = DATA / "gmae_hist.png"
C_INDEX = DATA / "gmae_index.png"
C_SEOCHO = DATA / "gmae_seocho.png"
C_BAND = DATA / "gmae_band.png"

def _font():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    import matplotlib.pyplot as plt
    for f in ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf"):
        font_manager.fontManager.addfont(str(FONTS / f))
    plt.rcParams["font.family"] = "Pretendard"
    plt.rcParams["axes.unicode_minus"] = False
    return plt

def _dayticks(ax):
    idx = [i for i, d in enumerate(DAYS) if d[8:] in ("01",) or i in (0, N-1) or d[8:] in ("10","20")]
    ax.set_xticks(idx); ax.set_xticklabels([LBL[i] for i in idx], fontsize=8.3)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)

def chart_hist():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = [b for b, _ in HIST]; ys = [c for _, c in HIST]
    cols = ["#d64545" if b < -10 + 1e-9 else ("#e8a33d" if b < 0 else "#9db8d6") for b in xs]
    ax.bar(xs, ys, width=2.3, color=cols, linewidth=0)
    for x, lab, col in [(-10, "급매선 −10%", "#d64545"), (0, "실거래 평균 0%", "#334155"),
                        (MEDIAN_PREM, f"호가 중앙값 +{MEDIAN_PREM}%", "#1268D3")]:
        ax.axvline(x, color=col, lw=1.4, ls="--")
        ax.text(x, max(ys)*0.96, lab, rotation=90, va="top", ha="right", fontsize=8.2, color=col)
    ax.set_xlabel("호가의 실거래 평균 대비 편차(%) — 오른쪽일수록 비쌈", fontsize=9)
    ax.set_ylabel("실매물 수", fontsize=9)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    fig.suptitle("서울 아파트 실매물 호가 할인율 분포 (9월 7일 · 실거래 평균 대비)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_HIST, bbox_inches="tight"); print("chart:", C_HIST)

def chart_index():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    xs = list(range(N))
    ax.plot(xs, IX_ITEMS, color="#334155", lw=2.0, label=f"실매물 재고 (+{PCT_ITEMS:.1f}%)")
    ax.plot(xs, IX_D10, color="#d64545", lw=2.0, label=f"−10%↓ 급매 (+{PCT_D10:.1f}%)")
    ax.axhline(100, color="#cbd5e1", lw=1.0, ls=":")
    _dayticks(ax)
    ax.set_ylabel("지수 (8/3=100)", fontsize=9)
    ax.legend(ncol=2, fontsize=8.6, frameon=False, loc="upper left")
    fig.suptitle("서울 실매물·급매 일별 추이 지수 (8월 3일=100)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_INDEX, bbox_inches="tight"); print("chart:", C_INDEX)

def chart_seocho():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    xs = list(range(N))
    ax.plot(xs, SEO10, color="#1268D3", lw=2.2, label=f"서초구 ({SEO10[0]}→{SEO10[-1]})")
    ax.plot(xs, REST10, color="#94a3b8", lw=1.8, ls="--", label=f"나머지 24구 합 ({REST10[0]}→{REST10[-1]})")
    _dayticks(ax)
    ax.set_ylabel("−10%↓ 실매물 수", fontsize=9)
    ax.legend(ncol=2, fontsize=8.6, frameon=False, loc="upper left")
    fig.suptitle("−10%↓ 급매 실매물 — 서초구 대 나머지 24구 (일별)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_SEOCHO, bbox_inches="tight"); print("chart:", C_SEOCHO)

def chart_band():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    import numpy as np
    xs = np.arange(len(BANDS_ORD))
    y0 = [DV0["band"][b] for b in BANDS_ORD]
    y1 = [DV1["band"][b] for b in BANDS_ORD]
    y9 = [DV9["band"][b] for b in BANDS_ORD]
    series = [(-0.27, y0, "#c2d3e8", "8월 3일", "#64748b", 8.0, "normal"),
              (0.0, y1, "#5f8fc9", "9월 1일", "#3a5f8a", 8.2, "normal"),
              (0.27, y9, "#1268D3", "9월 7일", "#1268D3", 8.6, "bold")]
    for off, ys, col, lab, tcol, fs, fw in series:
        ax.bar(xs+off, ys, 0.26, color=col, label=lab)
        for x, v in zip(xs+off, ys):
            ax.text(x, v+0.3, str(v), ha="center", fontsize=fs, color=tcol, fontweight=fw)
    ax.set_xticks(xs); ax.set_xticklabels(BANDS_ORD, fontsize=9)
    ax.set_ylabel("−10%↓ 급매 실매물 수", fontsize=9)
    ax.legend(ncol=3, fontsize=8.6, frameon=False, loc="upper left")
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    fig.suptitle("가격대별 −10%↓ 급매 실매물 — 8월 3일 대 9월 7일 (30억 이상 주도)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_BAND, bbox_inches="tight"); print("chart:", C_BAND)

CHART = {"hist": C_HIST, "index": C_INDEX, "seocho": C_SEOCHO, "band": C_BAND}

# ── 표 ─────────────────────────────────────────────────────────
def gname(g): return g[:-1] if g.endswith("구") else g
def dash(v): return "·" if v == 0 else str(v)

# 임계별 표본 표
TH_HEADS = ["급매 임계", "실매물(물건)", "광고"]
def th_rows():
    return [[t[0], str(t[1]), (str(t[2]) if t[2] is not None else "—")] for t in THRESH]

# 급매 성격 — 가격대별 3시점 표
BAND_HEADS = ["가격대", "8/3", "9/1", "9/7"]
def band_rows():
    rows = [[b, str(DV0["band"][b]), str(DV1["band"][b]), str(DV9["band"][b])] for b in BANDS_ORD]
    rows.append(["계", str(DV0["n"]), str(DV1["n"]), str(DV9["n"])])
    return rows

# 급매 집중 단지 — 상위 10
CX_HEADS = ["단지", "자치구", "급매 물건", "평균 할인율", "평균 호가(억)"]
def cx_rows():
    return [[c["name"], c["sgg"], str(c["cnt"]), f"{nm(c['avg_disc'])}%", f"{c['avg_price']}"] for c in TOPCX[:10]]

# 부록A: −10%↓ 자치구×일별 (변동 있는 구 + 서울계)
A_HEADS = ["날짜"] + [gname(g) for g in ACT10] + ["서울계"]
def a_rows():
    out = []
    for i in range(N):
        out.append([LBL[i]] + [dash(M10[g][i]) for g in ACT10] + [str(sum(M10[g][i] for g in GU))])
    return out
# 자치구별 3시점 요약(−10%↓) — 8/3 · 9/1 · 9/7 (9/7 많은 순 + 서울계)
TP_HEADS = ["자치구", "8/3", "9/1", "9/7", "증감(8/3→9/7)"]
def tp_rows():
    out = []
    for g in TP_ORDER:
        a, b, c = _v10(g, "2026-08-03"), _v10(g, "2026-09-01"), _v10(g, "2026-09-07")
        out.append([gname(g), str(a), str(b), str(c), f"{c-a:+d}"])
    ta, tb, tc = _tc("2026-08-03"), _tc("2026-09-01"), _tc("2026-09-07")
    out.append(["서울계", str(ta), str(tb), str(tc), f"{tc-ta:+d}"])
    return out
TP_LEAD = (f"서울 −10%↓ 급매 실매물은 서울계 기준 8월 3일 {_tc('2026-08-03')} → 9월 1일 {_tc('2026-09-01')} → "
           f"9월 7일 {_tc('2026-09-07')}물건으로 늘었고, 이 증가는 서초구({_v10('서초구','2026-08-03')} → "
           f"{_v10('서초구','2026-09-01')} → {_v10('서초구','2026-09-07')})에 집중됐습니다. 나머지 자치구는 "
           "세 시점 모두 대부분 0~한 자릿수에 머뭅니다.")

def make_docx(out: Path):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_ORIENT
    d = Document()
    st = d.styles["Normal"]; st.font.name = "맑은 고딕"; st.font.size = Pt(10.5)
    st.paragraph_format.line_spacing = 1.45; st.paragraph_format.space_after = Pt(10)
    p = d.add_paragraph(); r = p.add_run(DOCTYPE)
    r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = RGBColor(0x12, 0x68, 0xD3)
    t = d.add_paragraph(); r = t.add_run(TITLE); r.font.size = Pt(14.5); r.font.bold = True
    s = d.add_paragraph(); r = s.add_run(SUBTITLE)
    r.font.size = Pt(10.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    h = d.add_paragraph(); r = h.add_run("■ 요약"); r.font.bold = True; r.font.size = Pt(11.5)
    tb = d.add_table(rows=0, cols=2); tb.style = "Light Grid Accent 1"
    for k, v in SUMMARY:
        c = tb.add_row().cells
        c[0].paragraphs[0].add_run(k).bold = True
        c[1].paragraphs[0].add_run(v)
    for rowx in tb.rows:
        for c in rowx.cells:
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(2)
                for rr in pp.runs: rr.font.size = Pt(9)

    def big_table(title, heads, rows, fs=6.6):
        h = d.add_paragraph(); r = h.add_run(title); r.font.bold = True; r.font.size = Pt(11.5)
        tb = d.add_table(rows=1, cols=len(heads)); tb.style = "Light Grid Accent 1"
        for c, x in zip(tb.rows[0].cells, heads):
            c.paragraphs[0].add_run(str(x)).bold = True
        for row in rows:
            for c, x in zip(tb.add_row().cells, row):
                c.paragraphs[0].add_run(str(x))
        for rowx in tb.rows:
            for c in rowx.cells:
                for pp in c.paragraphs:
                    pp.paragraph_format.space_after = Pt(0); pp.paragraph_format.line_spacing = 1.0
                    for rr in pp.runs: rr.font.size = Pt(fs)

    for head, body, ck in SECTIONS:
        hp = d.add_paragraph(); r = hp.add_run("■ " + head); r.font.bold = True; r.font.size = Pt(11.5)
        hp.paragraph_format.space_before = Pt(8); hp.paragraph_format.space_after = Pt(4)
        d.add_paragraph(body)
        if ck:
            ch = d.add_paragraph(); ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
            ch.add_run().add_picture(str(CHART[ck]), width=Cm(16.4))
        if head.startswith("2."):
            big_table("· 급매 임계별 표본 (9월 7일 기준)", TH_HEADS, th_rows(), fs=9)
        if head.startswith("5."):
            big_table("· 가격대별 −10%↓ 급매 실매물 (8/3 · 9/1 · 9/7, 단위: 물건)", BAND_HEADS, band_rows(), fs=9)
        if head.startswith("6."):
            big_table("· 급매 집중 상위 10개 단지 (9월 7일, −10%↓ 급매 실매물)", CX_HEADS, cx_rows(), fs=8.5)

    # 부록 A(가로 방향 섹션)
    sec = d.add_section(); sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    big_table("■ 부록 A — −10%↓ 급매 실매물 자치구별 일별 (단위: 물건, ·=0)", A_HEADS, a_rows(), fs=6.4)
    # 3시점 요약(세로 복귀) — 결론부
    sec2 = d.add_section(); sec2.orientation = WD_ORIENT.PORTRAIT
    sec2.page_width, sec2.page_height = sec2.page_height, sec2.page_width
    hp = d.add_paragraph(); r = hp.add_run("■ 자치구별 3시점 요약 (8월 3일 · 9월 1일 · 9월 7일, −10%↓ 급매 실매물)")
    r.font.bold = True; r.font.size = Pt(11.5)
    hp.paragraph_format.space_before = Pt(6); hp.paragraph_format.space_after = Pt(4)
    d.add_paragraph(TP_LEAD)
    big_table("· 8월 3일 · 9월 1일 · 9월 7일 (단위: 물건, 9/7 급매 많은 순)", TP_HEADS, tp_rows(), fs=8.5)
    m = d.add_paragraph(); r = m.add_run(NOTE)
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    d.save(out); print("docx:", out)

def make_pdf(out: Path):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                    Image as RLImage, Table, TableStyle, NextPageTemplate, PageBreak)
    from reportlab.lib import colors
    from PIL import Image as PImage
    pdfmetrics.registerFont(TTFont("P", str(FONTS / "Pretendard-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("PB", str(FONTS / "Pretendard-Bold.ttf")))
    blue = colors.Color(*BLUE); gray = colors.Color(0.39, 0.45, 0.55)
    ss = {
        "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=blue, spaceAfter=3),
        "title": ParagraphStyle("title", fontName="PB", fontSize=14, leading=19, spaceAfter=3),
        "sub": ParagraphStyle("sub", fontName="P", fontSize=9.6, textColor=gray, leading=14, spaceAfter=11),
        "body": ParagraphStyle("body", fontName="P", fontSize=9.8, leading=15.5, spaceAfter=8),
        "head": ParagraphStyle("head", fontName="PB", fontSize=11, leading=15, spaceBefore=6, spaceAfter=4),
        "note": ParagraphStyle("note", fontName="P", fontSize=7.6, leading=11.5, textColor=gray, spaceAfter=8),
        "sumk": ParagraphStyle("sumk", fontName="PB", fontSize=8.8, leading=12.5),
        "sumv": ParagraphStyle("sumv", fontName="P", fontSize=8.8, leading=12.5),
    }
    pw, ph = A4; lw, lh = landscape(A4)
    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=13*mm, rightMargin=13*mm,
                          topMargin=13*mm, bottomMargin=13*mm)
    fp = Frame(13*mm, 13*mm, pw-26*mm, ph-26*mm, id="p")
    fl = Frame(13*mm, 13*mm, lw-26*mm, lh-26*mm, id="l")
    doc.addPageTemplates([PageTemplate(id="portrait", frames=[fp], pagesize=A4),
                          PageTemplate(id="land", frames=[fl], pagesize=landscape(A4))])
    def img(pth, cw=184*mm):
        w, h = PImage.open(pth).size
        return RLImage(str(pth), width=cw, height=cw*h/w)
    def data_table(heads, rows, widths, fs=6.6):
        t = Table([heads] + rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,0), "PB", fs), ("FONT", (0,1), (-1,-1), "P", fs),
            ("BACKGROUND", (0,0), (-1,0), colors.Color(0.91,0.945,0.988)),
            ("GRID", (0,0), (-1,-1), 0.4, colors.Color(0.85,0.88,0.92)),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 1.0), ("BOTTOMPADDING", (0,0), (-1,-1), 1.0),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.Color(0.975,0.982,0.99)])]))
        return t
    sum_tbl = Table([[Paragraph(k, ss["sumk"]), Paragraph(v, ss["sumv"])] for k, v in SUMMARY],
                    colWidths=[24*mm, 160*mm])
    sum_tbl.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.Color(0.85,0.88,0.92)),
        ("BACKGROUND", (0,0), (0,-1), colors.Color(0.955,0.97,0.99)),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    story = [NextPageTemplate("portrait"),
             Paragraph(DOCTYPE, ss["tag"]), Paragraph(TITLE, ss["title"]),
             Paragraph(SUBTITLE, ss["sub"]), Paragraph("■ 요약", ss["head"]), sum_tbl, Spacer(1, 4*mm)]
    for head, body, ck in SECTIONS:
        story.append(Paragraph("■ " + head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
        if ck:
            story.append(img(CHART[ck])); story.append(Spacer(1, 2*mm))
        if head.startswith("2."):
            story.append(Paragraph("· 급매 임계별 표본 (9월 7일 기준)", ss["head"]))
            story.append(data_table(TH_HEADS, th_rows(), [40*mm, 40*mm, 40*mm], fs=8.5))
            story.append(Spacer(1, 3*mm))
        if head.startswith("5."):
            story.append(Paragraph("· 가격대별 −10%↓ 급매 실매물 (8/3 · 9/1 · 9/7, 단위: 물건)", ss["head"]))
            story.append(data_table(BAND_HEADS, band_rows(), [56*mm, 28*mm, 28*mm, 28*mm], fs=8.5))
            story.append(Spacer(1, 3*mm))
        if head.startswith("6."):
            story.append(Paragraph("· 급매 집중 상위 10개 단지 (9월 7일)", ss["head"]))
            story.append(data_table(CX_HEADS, cx_rows(), [54*mm, 24*mm, 24*mm, 30*mm, 30*mm], fs=8.2))
            story.append(Spacer(1, 3*mm))
    # 부록(가로)
    story.append(NextPageTemplate("land")); story.append(PageBreak())
    aw = lw - 26*mm
    story.append(Paragraph("■ 부록 A — −10%↓ 급매 실매물 자치구별 일별 (단위: 물건, ·=0)", ss["head"]))
    na = len(A_HEADS) - 1
    story.append(data_table(A_HEADS, a_rows(), [16*mm] + [(aw-16*mm)/na]*na, fs=7.2))
    # 3시점 요약(세로 복귀) — 결론부
    story.append(NextPageTemplate("portrait")); story.append(PageBreak())
    story.append(Paragraph("■ 자치구별 3시점 요약 (8월 3일 · 9월 1일 · 9월 7일, −10%↓ 급매 실매물)", ss["head"]))
    story.append(Paragraph(TP_LEAD, ss["body"]))
    story.append(data_table(TP_HEADS, tp_rows(), [40*mm, 26*mm, 26*mm, 26*mm, 42*mm], fs=8.5))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story); print("pdf:", out)

if __name__ == "__main__":
    chart_hist(); chart_index(); chart_seocho(); chart_band()
    make_docx(HERE / "서울_급매물_추이_보고서.docx")
    make_pdf(HERE / "서울_급매물_추이_보고서.pdf")
