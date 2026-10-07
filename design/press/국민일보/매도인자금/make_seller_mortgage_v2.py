# -*- coding: utf-8 -*-
"""매도인 자금 제공(이른바 '주인대출') 매물 — 데이터 분석 보고서 v2 (2026-09-07 발행, 최신일 9-07).

v1(7월 21일, 전수 육안 6건)의 업그레이드판. 일별 parquet 아카이브 78일치(6/16~9/2)와
당일 listings_current를 같은 기준으로 자동 추출·분류해 일별 추세·가격대·지역·표기 유형을 집계했다.
Run: python3 design/press/매도인자금/make_seller_mortgage_v2.py
 → 매도인자금제공_분석보고서_v2.docx / .pdf + data/sf2_*.png

원칙(v1과 동일): 의견·평가 없이 집계 사실만. 원문 표 공개로 기자가 직접 검증 가능하게.
수치 산출 근거: nfind /opt/koczip-archive parquet 78일 + 박스 listings_current(최신 9/7),
추출식 = 주체어(매도인·매도자·집주인·주인·소유자·소유주) × 자금어(대출·융자·근저당·담보·대여) 인접,
부정(무융자 등)·승계·우연결합 제외. 스크립트: scratchpad/extract_seller_fin.py (세션 기록).
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = Path("/Users/hcode/auto/naverreal/design/fonts")
DATA = HERE.parent / "data"
DATA.mkdir(exist_ok=True)
C_TREND = DATA / "sf2_trend.png"
C_PRICE = DATA / "sf2_price.png"
C_REGION = DATA / "sf2_region.png"
BLUE = (0x12 / 255, 0x68 / 255, 0xD3 / 255)

DOCTYPE = "데이터 분석 보고서 (취재 참고자료)"
TITLE = "‘집주인 대출 가능’ 매물 광고, 7월 4건에서 9월 261건으로"
SUBTITLE = ("전국 아파트·오피스텔 매매 광고 설명 문구 일별 전수 분석 · 2026년 6월 16일~9월 7일 · "
            "9월 7일 기준 매매 광고 1,523,304건")

SUMMARY = [
    ("분석 대상", "전국 아파트·오피스텔 매매 광고 설명 문구 — 9월 7일 1,473,495건 및 6월 16일 이후 83개 일별 스냅샷"),
    ("집계 결과", "매도인이 매수인에게 자금을 대준다고 밝힌 광고 9월 7일 261건 — 7월 22일까지는 하루 2~6건"),
    ("증가 시점", "7월 23일(16건)부터 늘기 시작해 8월 1일 148건, 8월 19일 이후 250건 안팎 유지"),
    ("가격대", "261건 중 20억원 이상이 152건(58.2%) — 전체 매매 광고에서 20억원 이상 비중은 7.1%"),
    ("지역", "서울 188건(72.0%)·경기 62건(23.8%) — 서초·강남·송파·성동 순"),
    ("유의 사항", "광고 문구 집계이며 등기부상 실제 근저당 설정 건수가 아닙니다. 광고 건수는 물건 수와 다릅니다"),
]

BODY = [
    ("1. 분석 배경",
     "최근 부동산 매매에서 매도인이 매수인 앞으로 근저당권을 설정하고 매매대금의 일부를 "
     "사실상 빌려주는 방식 — 광고에서는 ‘집주인 대출 가능’, ‘매도인 근저당 가능’ 등으로 "
     "표기됩니다 — 이 언급되고 있으나, 그 규모에 대한 공개 통계는 확인되지 않습니다. 이에 "
     "전국 아파트·오피스텔 매매 광고에서 중개사가 이 조건을 명시해 광고한 사례가 시점별로 "
     "얼마나 되는지를 집계했습니다. 본 보고서는 그 집계 결과만을 정리한 것으로, 이러한 거래 "
     "방식의 적법성·통상성에 대한 평가는 담고 있지 않습니다."),
    ("2. 분석 대상과 방법",
     "전국 아파트·오피스텔 매매 광고의 설명 문구(중개사가 직접 작성하는 소개란)를 대상으로 "
     "했습니다. 9월 7일 기준 매매 광고는 1,523,304건, 이 가운데 설명 문구가 있는 광고는 "
     "1,473,495건입니다. 설명 문구에서 주체어(매도인·매도자·집주인·주인·소유자·소유주)와 "
     "자금어(대출·융자·근저당·담보·대여)가 인접해 나타나는 광고를 자동 추출한 뒤, "
     "①‘무융자·근저당없음·집주인대출없음’처럼 담보가 없다는 반대 표기, ②‘대출승계’처럼 "
     "매수인이 매도인의 기존 금융기관 대출을 넘겨받는 표기, ③‘주인거주’ 등 주체어가 자금과 "
     "무관하게 붙은 경우를 규칙으로 제외했습니다. 참고로 7월 21일 시점을 후보 전수 육안 확인 "
     "방식으로 별도 집계했을 때 6건이었는데, 이번 자동 기준을 같은 날 스냅샷에 적용해도 4건으로 "
     "비슷하게 나와 두 방법의 결과가 부합합니다. 즉 7월 이후의 증가는 집계 방법의 차이 때문이 "
     "아닙니다."),
    ("3. 결과 (1) — 일별 추세: 7월 22일까지 하루 4건 안팎, 9월 7일 261건",
     "6월 16일부터 7월 22일까지 37일 동안 해당 광고는 하루 2~6건(평균 3.5건)에 머물렀습니다. "
     "7월 23일 16건으로 늘어난 뒤 7월 25일 46건, 7월 30일 109건, 8월 1일 148건, 8월 7일 "
     "200건을 넘었고, 8월 19일부터는 250건 안팎에서 유지되고 있습니다(최대 8월 23일 270건, "
     "9월 7일 261건). 같은 기간 전체 매매 광고 수는 150만~157만 건으로 큰 변화가 없어, 해당 "
     "광고의 비중은 광고 10만 건당 0.2건에서 17.1건으로 늘었습니다. 참고로 반대로 담보가 없다는 점을 "
     "내세운 매매 광고(무융자·근저당없음 등)는 9월 7일 542건입니다."),
    ("4. 결과 (2) — 가격대: 절반 이상이 20억원 이상",
     "9월 7일 해당 광고 261건의 호가 분포는 30억원 이상 98건(37.5%), 20~30억원 54건(20.7%), "
     "10~20억원 88건(33.7%), 5~10억원 14건(5.4%), 5억원 미만 7건(2.7%)입니다. 20억원 이상이 "
     "58.2%로, 전체 매매 광고에서 20억원 이상이 차지하는 비중(7.1%)의 8.2배입니다. 다만 7월의 "
     "6건이 전부 20억원 이상이었던 것과 달리, 이번에는 10~20억원대가 88건으로 늘었고 5억원 "
     "미만(평택·고양 등)도 7건 확인됐습니다."),
    ("5. 결과 (3) — 지역: 서울 72%, 자치구별로는 서초·송파·강남·성동 순",
     "9월 7일 261건 중 서울이 188건(72.0%), 경기가 62건(23.8%)이며 그 외 지역은 부산·대구 각 3건, "
     "인천 2건, 충북 1건 등 11건입니다. 자치구별로는 서초구 33건, 강남구 31건, 송파구 31건, "
     "성동구 23건, 성남 분당구 17건, 마포구 13건, 영등포구 10건, 동대문구·남양주시 각 9건, 과천시 "
     "8건 순입니다. 그 지역 매매 광고 수 대비 비율로는 과천시(광고 2,698건 중 8건, 0.30%)와 "
     "성동구(10,567건 중 23건, 0.22%)가 가장 높고, 서초구는 0.16%, 남양주시는 0.04%입니다."),
    ("6. 결과 (4) — 표기와 금액",
     "전체 관측 기간의 표기(광고-일 기준)는 ‘집주인/주인+대출’ 계열 2,931건, ‘매도인/매도자+대출’ "
     "계열 2,573건, ‘매도인/매도자+근저당’ 계열 2,424건, ‘집주인/주인+근저당’ 계열 1,507건 "
     "순으로, 근저당·담보를 직접 언급한 표기가 전체의 42%입니다(관측 기간 합계 9,435건 중 3,931건). 9월 7일 광고 중 대여 금액을 명시한 "
     "경우는 52건으로, 금액은 수천만원대부터 수십억원대까지 폭넓게 분포합니다. ‘협의’, ‘조건 협의’, ‘설정금액 조정 가능’처럼 금액을 정하지 않고 협의로 "
     "표시한 광고도 다수 확인됩니다."),
    ("7. 저희 데이터로 말할 수 없는 것",
     "① 등기 — 실제로 매수인 앞 근저당 설정 등기가 몇 건 이뤄졌는지는 등기 자료의 영역이어서 "
     "저희 데이터로는 확인되지 않습니다. ② 계약 반영 — 광고 문구가 실제 계약 조건으로 이어진 "
     "비율은 확인할 수 없습니다. ③ 세무 — 매도인이 자금을 대여할 경우의 이자소득·증여 관련 "
     "판단은 저희가 할 수 있는 영역이 아닙니다. ④ 증가의 원인 — 특정 정책이나 사건과의 인과는 "
     "본 집계만으로 단정할 수 없어 시점 사실만 기재했습니다. 아울러 광고는 같은 물건이 복수로 "
     "등록될 수 있어 건수가 물건 수보다 많습니다(9월 7일 261건을 단지·면적형·호가 기준으로 "
     "중복 제거하면 151건). 광고는 수시로 등록·삭제되므로 열람 시점에 따라 수치가 달라질 수 있습니다."),
]

NOTE = (
    "작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  ※ 본 집계는 2026년 9월 7일 최신 수집 데이터를 기준으로 재산정한 값입니다. 관측 기간 중간의 수집 스냅샷이 보강되면서, 앞서 배포된 잠정치와는 게재 광고·물건 수 등 일부 수치가 소폭 조정되었습니다. "
    "모든 수치는 저희가 자체 구축한 DB에서 집계했습니다(일별 수치는 각 일자 수집 스냅샷, 9월 7일 "
    "수치는 당일 기준). 부록의 광고 원문은 중개사가 작성한 문구를 그대로 옮긴 것이며 확인일자는 "
    "중개사가 매물을 최종 확인한 날짜입니다. 분석 방법이나 원자료에 대해 더 확인이 필요하시면, "
    "또는 추가 집계·다른 조건의 교차 분석이 필요하시면 언제든 연락 주시기 바랍니다."
)

# ── 실측 데이터 ──────────────────────────────────────────────────
DAILY = [
    ("06-16", 5), ("06-17", 5), ("06-18", 4), ("06-19", 4), ("06-20", 4), ("06-21", 4),
    ("06-22", 4), ("06-23", 4), ("06-24", 4), ("06-25", 4), ("06-26", 4), ("06-27", 4),
    ("06-29", 4), ("06-30", 4), ("07-01", 4), ("07-02", 4), ("07-03", 4), ("07-04", 4),
    ("07-05", 4), ("07-06", 3), ("07-07", 3), ("07-08", 3), ("07-09", 3), ("07-10", 3),
    ("07-11", 2), ("07-12", 2), ("07-13", 2), ("07-14", 3), ("07-15", 3), ("07-16", 3),
    ("07-17", 3), ("07-18", 3), ("07-19", 3), ("07-20", 3), ("07-21", 4), ("07-22", 6),
    ("07-23", 16), ("07-24", 19), ("07-25", 46), ("07-26", 47), ("07-27", 48), ("07-28", 69),
    ("07-29", 82), ("07-30", 109), ("07-31", 131), ("08-01", 148), ("08-02", 154), ("08-03", 153),
    ("08-04", 156), ("08-05", 168), ("08-06", 181), ("08-07", 200), ("08-08", 195), ("08-09", 194),
    ("08-10", 192), ("08-11", 216), ("08-12", 225), ("08-13", 230), ("08-14", 237), ("08-15", 240),
    ("08-16", 236), ("08-17", 236), ("08-18", 233), ("08-19", 251), ("08-20", 252), ("08-21", 256),
    ("08-22", 263), ("08-23", 270), ("08-24", 269), ("08-25", 268), ("08-26", 257), ("08-27", 253),
    ("08-28", 257), ("08-29", 253), ("08-30", 248), ("08-31", 243), ("09-01", 248), ("09-02", 250),
    ("09-03", 252), ("09-04", 254), ("09-05", 253), ("09-06", 261), ("09-07", 261),
]

# 가격대 구성 — (라벨, 주인대출 261건, 전체 매매 1,523,304건)
BANDS = ["5억 미만", "5~10억", "10~20억", "20~30억", "30억 이상"]
PRICE_SELF = [7, 14, 88, 54, 98]
PRICE_ALL = [744231, 494327, 176515, 55469, 52762]
BAND_COLORS = ["#dbe4ee", "#a9bed6", "#7aa3cf", "#5b86bd", "#d64545"]

# 지역 상위 — (이름, 건수, 그 지역 매매 광고 수)
REGION = [
    ("서울 서초구", 33, 20436), ("서울 강남구", 31, 27567), ("서울 송파구", 31, 21508),
    ("서울 성동구", 23, 10567), ("경기 성남 분당구", 17, 11867), ("서울 마포구", 13, 10465),
    ("서울 영등포구", 10, 11590), ("경기 남양주시", 9, 24188), ("서울 동대문구", 9, 8831),
    ("경기 과천시", 8, 2698),
]

# 부록 — 대표 원문(최신 스냅샷 기준, 가격대·지역·표기 다양화 17건)
RAW = [
    ("잠실르엘", "서울 송파구", "93.0억", "177㎡", "53 복층펜트하우스 희소성의가치 풀옵션 매도인근저당컨설팅o 협의", "09-02"),
    ("래미안퍼스티지", "서울 서초구", "90.0억", "238T1", "72  로얄층 트인조망 매도자대출가능", "08-31"),
    ("트리마제", "서울 성동구", "85.0억", "126A", "38A매도인대출 30억가능. 한층에 한세대만 있는 프라이버시 보장매물", "08-05"),
    ("아크로삼성", "서울 강남구", "73.5억", "132B", "40 열린 네고, 집주인대출25억 가능, 한강뷰 정원뷰 양창", "09-01"),
    ("신반포2차", "서울 서초구", "71.5억", "164㎡", "50 찐매물 . 매도자 근저당 가능", "08-28"),
    ("신현대(현대9,11,12차)", "서울 강남구", "60.0억", "119D", "35 실매물, 비거주1주택자,매도인 근저당권설정금액조정가능", "08-28"),
    ("도곡렉슬", "서울 강남구", "57.0억", "167㎡", "앞이 트여있는 로얄동 매도자대출가능 세안고 매매", "09-02"),
    ("청담자이", "서울 강남구", "55.0억", "120C", "매도인 근저당 가능, 청담대교, 롯데타워가 일품 뷰맛집", "09-03"),
    ("포제스한강", "서울 광진구", "54.0억", "168㎡", "마2억 매도인근저당가능 방음벽너머 한강뷰 개방감최고", "08-14"),
    ("메이플자이", "서울 서초구", "49.0억", "111B4", "33.급매 커뮤니티 인근동 주인근저당 주가능 대단지 신축아파트 잠원역세권", "09-01"),
    ("봇들9단지금호어울림", "경기 성남 분당구", "47.0억", "188C", "57 복층 펜트 특전망 넓은 테라스 매도인근저당 협의", "09-03"),
    ("판교푸르지오그랑블", "경기 성남 분당구", "46.0억", "171㎡", "51 매도인근저당 조건협의 트인조망 인테리어 판교역초역세권", "08-31"),
    ("반포자이", "서울 서초구", "45.8억", "116B", "35 마지막급매 입주매물 매도인근저당10억내에서 협의가능", "08-31"),
    ("송파파밀리에더퍼스트", "서울 송파구", "19.5억", "84형", "집주인대출가능,공동환영,27년 6월만기,전세안고 매매, 최근 올수리", "09-03"),
    ("브레인시티로제비앙엘가더퍼스트", "경기 평택시", "3.8억", "82B", "무피 l 매도자 대출가능O l 귀한소형평수 l 시스템에어컨4대 l", "08-18"),
    ("중산5단지동부,건영", "경기 고양시", "2.3억", "72B", "최근전체올수리,공실,매도인대출가능,아주조용,고봉산밑접함,한번보시지요", "08-18"),
    ("동영센트럴타워", "경기 평택시", "1.6억", "66㎡", "송탄역 초역세권 탁트인 전망 투룸, 집주인대출 3,500만원 가능", "08-22"),
]


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


def chart_trend():
    plt = _font()
    xs = list(range(len(DAILY)))
    ys = [v for _, v in DAILY]
    fig, ax = plt.subplots(figsize=(10.4, 3.4), dpi=200)
    ax.plot(xs, ys, color="#1268D3", lw=2.2, zorder=3)
    ax.fill_between(xs, ys, color="#1268D3", alpha=.10, zorder=2)
    ax.scatter([xs[-1]], [ys[-1]], s=26, color="#d64545", zorder=4)
    ax.annotate(f"9월 7일 {ys[-1]}건", (xs[-1], ys[-1]), xytext=(-84, 6),
                textcoords="offset points", fontsize=10, fontweight="bold", color="#d64545")
    i0 = next(i for i, (d, _) in enumerate(DAILY) if d == "07-23")
    ax.axvline(i0, color="#94a3b8", lw=.9, ls="--")
    ax.annotate("7월 23일부터 증가 시작\n(직전까지 하루 2~6건)", (i0, 150), xytext=(8, 0),
                textcoords="offset points", fontsize=8.8, color="#475569")
    ticks = [i for i, (d, _) in enumerate(DAILY) if d in ("06-16", "07-01", "07-15", "08-01", "08-15", "09-01")]
    ax.set_xticks(ticks)
    ax.set_xticklabels([DAILY[i][0] for i in ticks], fontsize=8.5)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_ylabel("광고 수(건)", fontsize=9)
    fig.suptitle("매도인이 자금을 대준다고 밝힌 매매 광고 — 일별 건수 (2026.6.16 ~ 9.3)",
                 fontsize=11.5, fontweight="bold", y=1.0)
    fig.text(0.995, -0.04, "전국 아파트·오피스텔 매매 광고 설명 문구 자동 추출·분류, 각 일자 수집 스냅샷 기준 | 콕집",
             ha="right", fontsize=7.6, color="#94a3b8")
    fig.tight_layout()
    fig.savefig(C_TREND, bbox_inches="tight")
    print("chart:", C_TREND)


def chart_price():
    plt = _font()
    rowsx = [("전체 매매 광고 (대조군)", PRICE_ALL, 1567528),
             ("매도인이 자금 제공 (9/7)", PRICE_SELF, 261)]
    fig, ax = plt.subplots(figsize=(10.4, 2.5), dpi=200)
    ys = [1, 0]
    for yi, (label, counts, n) in zip(ys, rowsx):
        left = 0.0
        for ci, (cnt, col) in enumerate(zip(counts, BAND_COLORS)):
            pct = 100.0 * cnt / n
            if pct <= 0:
                continue
            ax.barh(yi, pct, 0.56, left=left, color=col,
                    label=BANDS[ci] if yi == 1 else None, edgecolor="white", linewidth=.8)
            if pct >= 5:
                ax.annotate(f"{pct:.0f}%", (left + pct / 2, yi), ha="center", va="center",
                            fontsize=8.6, fontweight="bold",
                            color="white" if ci >= 2 else "#334155")
            left += pct
        ax.annotate(f"{n:,}건", (101, yi), va="center", ha="left", fontsize=8.8,
                    fontweight="bold", color="#334155")
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rowsx], fontsize=9.4)
    ax.set_xlim(0, 116)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"], fontsize=8.5)
    ax.grid(axis="x", color="#eef2f6", lw=.8)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.legend(ncol=5, fontsize=8.4, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.04))
    fig.suptitle("호가 구간별 구성비 — 해당 광고는 20억 이상이 57%, 전체 시장은 7%",
                 fontsize=11.5, fontweight="bold", y=1.14)
    fig.tight_layout()
    fig.savefig(C_PRICE, bbox_inches="tight")
    print("chart:", C_PRICE)


def chart_region():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    names = [r[0] for r in REGION][::-1]
    cnts = [r[1] for r in REGION][::-1]
    ax.barh(range(len(REGION)), cnts, 0.62, color="#1268D3")
    for i, (n, c, tot) in enumerate(REGION[::-1]):
        ax.annotate(f"{c}건  (그 지역 매매 광고의 {100 * c / tot:.2f}%)", (c + 0.4, i),
                    va="center", fontsize=8.6, color="#334155")
    ax.set_yticks(range(len(REGION)))
    ax.set_yticklabels(names, fontsize=9.2)
    ax.set_xlim(0, 44)
    ax.grid(axis="x", color="#eef2f6", lw=.8)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.set_xlabel("광고 수(건)", fontsize=9)
    fig.suptitle("지역별 분포 상위 10 (9월 7일 261건 중) — 괄호는 그 지역 매매 광고 대비 비율",
                 fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(C_REGION, bbox_inches="tight")
    print("chart:", C_REGION)


def make_docx(out: Path):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    d = Document()
    st = d.styles["Normal"]
    st.font.name = "맑은 고딕"
    st.font.size = Pt(10.5)
    st.paragraph_format.line_spacing = 1.45
    st.paragraph_format.space_after = Pt(10)

    p = d.add_paragraph(); r = p.add_run(DOCTYPE)
    r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = RGBColor(0x12, 0x68, 0xD3)
    t = d.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run(TITLE); r.font.size = Pt(14.5); r.font.bold = True
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
                for rr in pp.runs:
                    rr.font.size = Pt(9)

    for img in (C_TREND, C_PRICE, C_REGION):
        ch = d.add_paragraph(); ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ch.add_run().add_picture(str(img), width=Cm(16.4))

    for head, body in BODY:
        h = d.add_paragraph(); r = h.add_run("■ " + head); r.font.bold = True; r.font.size = Pt(11.5)
        h.paragraph_format.space_before = Pt(8); h.paragraph_format.space_after = Pt(4)
        d.add_paragraph(body)

    h = d.add_paragraph(); r = h.add_run("■ 부록 — 대표 광고 원문 17건 (최신 게재분, 가격 내림차순)")
    r.font.bold = True; r.font.size = Pt(11.5)
    HEADS = ["단지", "소재지", "호가", "면적", "광고 원문", "확인일"]
    tb2 = d.add_table(rows=1, cols=len(HEADS)); tb2.style = "Light Grid Accent 1"
    for c, x in zip(tb2.rows[0].cells, HEADS):
        c.paragraphs[0].add_run(x).bold = True
    for row in RAW:
        for c, x in zip(tb2.add_row().cells, row):
            c.paragraphs[0].add_run(x)
    for rowx in tb2.rows:
        for c in rowx.cells:
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(2)
                for rr in pp.runs:
                    rr.font.size = Pt(8)

    m = d.add_paragraph(); r = m.add_run(NOTE)
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    d.save(out)
    print("docx:", out)


def make_pdf(out: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
                                    Table, TableStyle)
    from reportlab.lib import colors
    from PIL import Image as PImage

    pdfmetrics.registerFont(TTFont("P", str(FONTS / "Pretendard-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("PB", str(FONTS / "Pretendard-Bold.ttf")))
    blue = colors.Color(*BLUE)
    gray = colors.Color(0.39, 0.45, 0.55)
    ss = {
        "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=blue, spaceAfter=3),
        "title": ParagraphStyle("title", fontName="PB", fontSize=14, leading=19, spaceAfter=3),
        "sub": ParagraphStyle("sub", fontName="P", fontSize=9.6, textColor=gray, leading=14, spaceAfter=11),
        "body": ParagraphStyle("body", fontName="P", fontSize=9.8, leading=15.5, spaceAfter=8),
        "head": ParagraphStyle("head", fontName="PB", fontSize=11, leading=15, spaceBefore=6, spaceAfter=4),
        "note": ParagraphStyle("note", fontName="P", fontSize=7.6, leading=11.5, textColor=gray, spaceAfter=8),
        "cell": ParagraphStyle("cell", fontName="P", fontSize=7.4, leading=10.2),
        "cellb": ParagraphStyle("cellb", fontName="PB", fontSize=7.4, leading=10.2),
        "sumk": ParagraphStyle("sumk", fontName="PB", fontSize=8.8, leading=12.5),
        "sumv": ParagraphStyle("sumv", fontName="P", fontSize=8.8, leading=12.5),
    }
    GRID = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.91, 0.945, 0.988)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.88, 0.92)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)

    def img(pth):
        w, h = PImage.open(pth).size
        cw = 178 * mm
        return RLImage(str(pth), width=cw, height=cw * h / w)

    sum_tbl = Table([[Paragraph(k, ss["sumk"]), Paragraph(v, ss["sumv"])] for k, v in SUMMARY],
                    colWidths=[26 * mm, 152 * mm])
    sum_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.88, 0.92)),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.955, 0.97, 0.99)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    HEADS = ["단지", "소재지", "호가", "면적", "광고 원문", "확인일"]
    raw_tbl = Table(
        [[Paragraph(x, ss["cellb"]) for x in HEADS]] +
        [[Paragraph(x, ss["cell"]) for x in row] for row in RAW],
        colWidths=[32 * mm, 26 * mm, 13 * mm, 13 * mm, 81 * mm, 13 * mm])
    raw_tbl.setStyle(GRID)

    story = [
        Paragraph(DOCTYPE, ss["tag"]),
        Paragraph(TITLE, ss["title"]),
        Paragraph(SUBTITLE, ss["sub"]),
        Paragraph("■ 요약", ss["head"]), sum_tbl, Spacer(1, 4 * mm),
        img(C_TREND), Spacer(1, 2 * mm),
        img(C_PRICE), Spacer(1, 2 * mm),
        img(C_REGION), Spacer(1, 3 * mm),
    ]
    for head, body in BODY:
        story.append(Paragraph("■ " + head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph("■ 부록 — 대표 광고 원문 17건 (최신 게재분, 가격 내림차순)", ss["head"]))
    story.append(raw_tbl)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story)
    print("pdf:", out)


if __name__ == "__main__":
    chart_trend()
    chart_price()
    chart_region()
    make_docx(HERE / "매도인자금제공_분석보고서_v2.docx")
    make_pdf(HERE / "매도인자금제공_분석보고서_v2.pdf")
