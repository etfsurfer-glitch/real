# -*- coding: utf-8 -*-
"""노후계획도시 선도지구 3개 도시(분당·부산·대전) 궤적 비교 보도자료.
수치는 2026-07-20 transactions·complex_daily_agg 실측.
Run: python3 design/press/make_seondo_3city.py
 → design/press/선도지구_3도시비교.docx / .pdf + data/seondo_3city_chart.png
발송 없음 — 파일 생성만.

※ 단지 특정 근거: 분당은 이름·세대수 역추적(시범 우성+현대=3,569세대, 양지 6단지=4,392세대가
   선정 발표 수치와 일치). 부산은 5단지 합 7,318세대가 발표 수치와 정확히 일치.
   **보도 전 국토부 선정 발표문과 최종 대조 권장**(단지 오기는 신뢰도 직결).
※ '대전도 분당처럼 오른다'는 식의 예측은 쓰지 않는다 — 실제로 부산은 거래가 40% 줄어
   분당과 반대로 갔다. 같은 제도라도 결과가 갈렸다는 것이 데이터가 말하는 바다.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "fonts"
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)
CHART = DATA / "seondo_3city_chart.png"
BLUE = (0x12 / 255, 0x68 / 255, 0xD3 / 255)

TITLE = "대전 선도지구 매물 잠김… 분당은 20개월 뒤 23% 올랐고, 부산은 거래가 40% 줄었다"
SUBTITLE = "콕집, 노후계획도시 선도지구 3개 도시 궤적 비교 — 같은 제도, 갈린 결과"

LEAD = (
    "7월 15일 대전 노후계획도시 정비 선도지구 발표로 대상 단지 매물이 엿새 만에 22.5% 줄어든 가운데, "
    "같은 제도로 앞서 선정된 지역들은 서로 다른 길을 걸은 것으로 나타났다. 부동산 데이터 플랫폼 "
    "콕집(koczip.com)이 2024년 11월 선정된 분당 3개 구역(12개 단지, 10,738세대), 2025년 12월 선정된 "
    "부산 2개 구역(5개 단지, 7,318세대), 이번에 선정된 대전 3개 구역(6개 단지, 7,797세대)의 실거래와 "
    "매물을 선정 시점 기준으로 정렬해 비교한 결과다. 선정 20개월이 지난 분당은 아파트 평균 실거래가가 "
    "23.2% 오르고 거래량도 40% 늘었지만, 7개월이 지난 부산은 가격이 5.8% 오르는 사이 거래량은 40% "
    "줄었다. 발표 엿새째인 대전은 매물이 잠긴 초기 국면에 있다."
)

BODY = [
    ("① 대전 — 발표 엿새, 선정된 단지만 잠겼다",
     "대전 선도지구 6개 단지의 매매 광고매물은 발표 전날인 7월 14일 227건에서 7월 20일 176건으로 "
     "22.5% 줄었다. 중복 광고를 합친 실매물 기준으로도 144건에서 117건으로 18.8% 감소했다. "
     "주목할 점은 같은 동네의 선정되지 않은 단지들은 거의 움직이지 않았다는 것이다. 같은 기간 둔산동 "
     "비선정 69개 단지는 1,116건에서 1,139건으로 2.1% 늘었고, 법동 8개 단지도 1.5% 증가했다. "
     "탄방동 33개 단지는 2.8% 줄어드는 데 그쳤다. 지역 전체가 아니라 선정 여부가 갈랐다는 뜻이다. "
     "매물이 줄어든 경로도 통념과 달랐다. 발표 후 엿새간 신규 등록은 61건에서 39건으로 36% 급감했고, "
     "회수는 69건에서 82건으로 19% 늘었다. 이미 나온 물건을 거둬들인 것보다, 새 물건이 나오지 않은 "
     "영향이 더 컸다. 같은 기간 대전 전체(선도지구 제외)는 회수가 오히려 16% 줄어 방향이 반대였다."),
    ("② 부산 — 7개월, 거래는 40% 줄고 가격은 5.8% 올랐다",
     "2025년 12월 12일 지방권 최초로 선정된 부산 화명·금곡(코오롱하늘채 1·2차)과 해운대(두산1차·LG·"
     "대림1차)는 선정 이후 거래가 눈에 띄게 줄었다. 선정 전 4개월간 월평균 33.0건이던 매매 신고 건수는 "
     "선정 후 6개월간 월평균 19.8건으로 40% 감소했다. 반면 평균 실거래가는 4억 4,197만 원에서 "
     "4억 6,744만 원으로 5.8% 올랐다. 단지별로는 두산1차가 17.5%, 코오롱하늘채2차가 12.1%, LG가 9.0% "
     "상승했다. 신고가는 시차를 두고 나왔다. 두산1차는 선정 4개월 뒤인 2026년 4월 16일 8억 5,000만 "
     "원에 거래되며 역대 최고가를 새로 썼다. 매물은 다시 쌓였다. 부산 5개 단지의 현재 매매 매물은 "
     "581건으로 세대수 대비 7.94% 수준이며, 최근 두 달간 614건에서 581건 사이에서 안정적으로 "
     "유지되고 있다."),
    ("③ 분당 — 20개월, 12개 단지가 모두 올랐다",
     "2024년 11월 27일 1기 신도시 선도지구로 선정된 분당 샛별마을·양지마을·시범단지 12개 단지는 "
     "가장 뚜렷한 상승 궤적을 그렸다. 선정 전 12개월간 13억 5,440만 원이던 평균 실거래가는 선정 후 "
     "20개월간 16억 6,802만 원으로 23.2% 올랐다. 거래량도 월평균 31.8건에서 44.6건으로 40% 늘어 "
     "부산과 정반대였다. 분기별로 보면 상승이 계단식으로 이어졌다. 선정 직전 13억 원대이던 평균가는 "
     "2025년 1분기 15억 3,199만 원, 3분기 17억 405만 원, 2026년 2분기 17억 9,762만 원으로 올라섰다. "
     "12개 단지 전부가 상승했다는 점도 특징이다. 샛별동성이 49.9%로 가장 크게 올랐고 양지6단지한양 "
     "43.8%, 샛별우방 40.0%, 시범단지우성 33.4% 순이었다. 상승률이 가장 낮은 샛별삼부도 17.2%였다."),
    ("세 도시를 겹쳐 보면 — 잠김은 초기 현상, 가격 확인엔 시차",
     "선정 시점을 기준으로 세 지역을 정렬하면 공통점과 차이가 함께 드러난다. 공통적으로 선정 직후에는 "
     "매물이 잠기고 거래가 위축되는 국면이 나타난다. 가격이 지표로 확인되기까지는 시차가 있다. 부산은 "
     "선정 4개월 뒤에야 신고가가 나왔고, 분당도 선정 직후 두 개 분기는 거래 건수가 크게 줄었다가 "
     "이후 회복됐다. 반면 결과는 갈렸다. 20개월이 지난 분당은 거래와 가격이 함께 올랐지만, 7개월이 "
     "지난 부산은 가격은 올랐어도 거래는 줄어든 상태가 이어지고 있다. 매물이 세대수에서 차지하는 "
     "비중도 대전 2.26%, 분당 4.29%, 부산 7.94%로 갈린다. 같은 제도가 적용됐다고 해서 같은 경로를 "
     "밟는 것은 아니라는 점을 데이터가 보여준다."),
    ("해석 시 유의점",
     "대전 수치는 발표 후 엿새간의 초기 반응이어서 부산·분당과 관찰 기간이 다르다. 매물 감소에는 "
     "호가를 다시 부르기 위한 회수와 실제 계약 성사가 섞여 있을 수 있고, 발표 이후 계약분의 실거래 "
     "신고는 기한이 30일이어서 아직 집계에 반영되지 않았다. 분당은 수도권 1기 신도시, 부산·대전은 "
     "지방권으로 시장 규모와 성격이 다르며, 세 지역의 관찰 기간에 적용된 금융·세제 환경도 동일하지 "
     "않다. 이번 비교는 앞선 사례의 경로를 보여주는 것이며 특정 지역의 향후 가격을 예측하지 않는다. "
     "월별 실거래 건수가 적은 구간은 평균가 변동 폭이 커질 수 있다는 점도 함께 고려해야 한다."),
    ("일자별 매물·호가, 누구나 단지 단위로 확인 가능",
     "콕집은 전국 아파트·오피스텔 6만 4천여 단지의 매물과 실거래를 매일 수집해 교차 분석하는 "
     "플랫폼으로, 이번 분석에 쓰인 일자별 매물수·실매물수·평균 호가 추이는 콕집 단지 상세의 "
     "‘매물분석’ 메뉴에서 누구나 무료로 확인할 수 있다. 지역 비교, 부동산 타임머신(정책 연대기), "
     "급매 탐지, 단지별 신고가 등 분석 기능도 함께 제공한다."),
]

QUOTE = ("조용호 콕집 공동창업자는 “선도지구 발표가 나면 곧바로 가격이 뛴다는 인식이 있지만, 앞서 "
         "선정된 지역을 시점 기준으로 정렬해 보면 초기에는 오히려 거래가 멈추고 가격은 몇 달 뒤에 "
         "확인됐다”며 “분당과 부산의 궤적이 서로 달랐다는 점도 함께 봐야 한다. 데이터를 시점에 맞춰 "
         "비교해 소비자가 스스로 판단할 근거를 계속 공개하겠다”고 말했다.")

COMPANY = [
    ("서비스", "콕집 — 부동산 매물·실거래·중개사 분석 플랫폼 (koczip.com)"),
    ("운영사", "런투온라인 (대표 황인찬)"),
    ("문의", "조용호 공동창업자 · albooooza@gmail.com · 010-4692-4946"),
]

METHOD = (
    "분석 방법 | 대상: ①분당 3개 구역 12개 단지(샛별마을 동성·라이프·삼부·우방, 양지마을 금호1·청구2·한양5·"
    "금호한양3,5·금호청구6·한양6, 시범단지 우성·현대) 10,738세대, 2024-11-27 선정 ②부산 2개 구역 5개 단지"
    "(코오롱하늘채1·2차, 두산1차, LG, 대림1차) 7,318세대, 2025-12-12 선정 ③대전 3개 구역 6개 단지"
    "(한가람·공작한양·목련·크로바·보람·삼익소월) 7,797세대, 2026-07-15 선정. "
    "실거래 건수·평균가는 국토교통부 실거래 신고 자료(해제거래 제외) 기준이며 신고 기한 30일로 최근 2개월은 미완성. "
    "매물은 콕집 일별 수집 기준(광고매물=포털 노출 광고 건수, 실매물=동일 주택의 중복 광고를 합친 수). "
    "전 수치는 콕집 자체 구축 DB 실측(2026-07-20)."
)

# ── 실측 데이터(2026-07-20 DB) ── (선정 후 개월, 건수, 평균가 만원)
BUNDANG = [
    (-12, 15, 120967), (-11, 18, 117139), (-10, 21, 127469), (-9, 16, 143375),
    (-8, 19, 141347), (-7, 35, 117417), (-6, 49, 130741), (-5, 82, 138154),
    (-4, 39, 132556), (-3, 44, 142095), (-2, 17, 150794), (-1, 20, 138805),
    (0, 21, 153883), (1, 17, 155112), (2, 7, 149107), (3, 27, 162593),
    (4, 41, 147712), (5, 37, 160630), (6, 42, 147845), (7, 114, 148830),
    (8, 19, 160063), (9, 24, 145450), (10, 75, 181011), (11, 67, 178040),
    (12, 5, 177300), (13, 29, 162069), (14, 50, 167740), (15, 40, 173972),
    (16, 45, 170280), (17, 94, 179329), (18, 55, 178858), (19, 60, 181268),
]
BUSAN = [
    (-12, 11, 44945), (-11, 12, 42650), (-10, 11, 43086), (-9, 15, 37260),
    (-8, 18, 41658), (-7, 22, 43523), (-6, 24, 46329), (-5, 23, 41017),
    (-4, 24, 46279), (-3, 38, 41612), (-2, 35, 42654), (-1, 35, 47120),
    (0, 32, 44441), (1, 20, 48350), (2, 13, 47408), (3, 16, 47738),
    (4, 18, 50606), (5, 20, 44120), (6, 17, 46076),
]

TABLE = [
    ("선정일", "2024-11-27", "2025-12-12", "2026-07-15"),
    ("경과", "20개월", "7개월", "6일"),
    ("규모", "12단지 10,738세대", "5단지 7,318세대", "6단지 7,797세대"),
    ("월평균 거래 (선정 전→후)", "31.8 → 44.6건 (+40%)", "33.0 → 19.8건 (-40%)", "관찰 기간 미도래"),
    ("평균 실거래가 (선정 전→후)", "13억 5,440만 → 16억 6,802만 (+23.2%)",
     "4억 4,197만 → 4억 6,744만 (+5.8%)", "관찰 기간 미도래"),
    ("신고가 경신", "다수 단지 상승 지속", "두산1차 8억 5,000만 (선정 4개월 뒤)", "발표 전 4개 단지 2026년 경신"),
    ("현재 매물 (7/20)", "461건 (세대대비 4.29%)", "581건 (7.94%)", "176건 (2.26%)"),
    ("매물 증감", "—", "최근 2개월 안정", "발표 엿새 -22.5%"),
]


def make_chart():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf"):
        font_manager.fontManager.addfont(str(FONTS / f))
    plt.rcParams["font.family"] = "Pretendard"
    plt.rcParams["axes.unicode_minus"] = False

    def smooth(rows):
        """월별 거래가 적어 평균가가 튄다 → 3개월 이동평균으로 추세만 본다."""
        xs = [r[0] for r in rows]
        vs = [r[2] for r in rows]
        out = []
        for i in range(len(vs)):
            w = vs[max(0, i - 1):i + 2]
            out.append(sum(w) / len(w))
        return xs, out

    def index(xs, vs):
        """선정 직전 12개월 평균 = 100."""
        base = [v for x, v in zip(xs, vs) if -12 <= x <= -1]
        b = sum(base) / len(base)
        return [v / b * 100 for v in vs]

    bx, bv = smooth(BUNDANG); bi = index(bx, bv)
    sx, sv = smooth(BUSAN); si = index(sx, sv)

    fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=200)
    ax.axvline(0, color="#e2574c", lw=1.3, ls="--", alpha=.9)
    ax.text(0.35, 138, "선정 시점", color="#e2574c", fontsize=9, fontweight="bold", va="top")
    ax.axhline(100, color="#c9d3de", lw=.9, ls=":")
    ax.plot(bx, bi, color="#1268d3", lw=2.4, label="분당 12단지 (2024.11 선정)")
    ax.plot(sx, si, color="#e08a1e", lw=2.2, label="부산 5단지 (2025.12 선정)")
    ax.scatter([0], [100], color="#2b8a3e", s=70, zorder=5, marker="D",
               label="대전 6단지 (2026.7 선정 · 여기서 출발)")
    ax.annotate(f"{bi[-1]:.0f}", (bx[-1], bi[-1]), textcoords="offset points", xytext=(6, -2),
                fontsize=9.5, fontweight="bold", color="#1268d3")
    ax.annotate(f"{si[-1]:.0f}", (sx[-1], si[-1]), textcoords="offset points", xytext=(6, -2),
                fontsize=9.5, fontweight="bold", color="#e08a1e")
    ax.set_xlim(-13, 22)      # 오른쪽 끝 라벨(분당 지수)이 잘리지 않게 여유
    ax.set_xticks([-12, -9, -6, -3, 0, 3, 6, 9, 12, 15, 19])
    ax.set_xticklabels(["-12", "-9", "-6", "-3", "선정", "+3", "+6", "+9", "+12", "+15", "+19"], fontsize=8.5)
    ax.set_xlabel("선정 후 경과 개월", fontsize=9)
    ax.set_ylabel("선정 직전 12개월 = 100", fontsize=9)
    ax.tick_params(axis="y", labelsize=8.5)
    ax.set_ylim(82, 142)   # 분당 상단이 잘리지 않게
    ax.grid(axis="y", color="#e8edf3", lw=.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.set_title("노후계획도시 선도지구 3개 도시 — 아파트 평균 실거래가 지수 (콕집 DB)",
                 fontsize=10.5, fontweight="bold", pad=8)
    fig.tight_layout()
    fig.savefig(CHART, facecolor="white")
    print("chart:", CHART)


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

    p = d.add_paragraph(); r = p.add_run("보도자료")
    r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = RGBColor(0x12, 0x68, 0xD3)
    p2 = d.add_paragraph()
    r = p2.add_run("배포일: 2026년 7월 · 즉시 보도 가능    문의: 조용호 공동창업자 · albooooza@gmail.com · 010-4692-4946")
    r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    t = d.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run(TITLE); r.font.size = Pt(15); r.font.bold = True
    s = d.add_paragraph(); r = s.add_run(SUBTITLE)
    r.font.size = Pt(11.5); r.font.color.rgb = RGBColor(0x12, 0x68, 0xD3); r.font.bold = True

    d.add_paragraph(LEAD)

    ch = d.add_paragraph(); ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ch.add_run().add_picture(str(CHART), width=Cm(16.2))

    h = d.add_paragraph(); r = h.add_run("■ 3개 도시 한눈에 비교 (콕집 DB)")
    r.font.bold = True; r.font.size = Pt(11.5)
    tbl = d.add_table(rows=1, cols=4)
    tbl.style = "Light Grid Accent 1"
    for c, txt in zip(tbl.rows[0].cells, ["항목", "분당 (1기 신도시)", "부산", "대전"]):
        c.paragraphs[0].add_run(txt).bold = True
    for row in TABLE:
        for c, txt in zip(tbl.add_row().cells, row):
            c.paragraphs[0].add_run(txt)
    for rowx in tbl.rows:
        for c in rowx.cells:
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(2)
                for rr in pp.runs:
                    rr.font.size = Pt(8.5)

    for head, body in BODY:
        h = d.add_paragraph(); r = h.add_run("■ " + head); r.font.bold = True; r.font.size = Pt(11.5)
        h.paragraph_format.space_before = Pt(8); h.paragraph_format.space_after = Pt(4)
        d.add_paragraph(body)
    q = d.add_paragraph(); r = q.add_run(QUOTE); r.font.italic = True

    m = d.add_paragraph(); r = m.add_run(METHOD)
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    h = d.add_paragraph(); r = h.add_run("■ 서비스 개요"); r.font.bold = True; r.font.size = Pt(11.5)
    for k, v in COMPANY:
        d.add_paragraph(f"· {k}: {v}")
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

    pdfmetrics.registerFont(TTFont("P", str(FONTS / "Pretendard-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("PB", str(FONTS / "Pretendard-Bold.ttf")))
    blue = colors.Color(*BLUE)
    gray = colors.Color(0.39, 0.45, 0.55)

    ss = {
        "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=blue, spaceAfter=2),
        "meta": ParagraphStyle("meta", fontName="P", fontSize=8, textColor=gray, spaceAfter=10),
        "title": ParagraphStyle("title", fontName="PB", fontSize=14.5, leading=20, spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName="PB", fontSize=10.8, textColor=blue, leading=15, spaceAfter=11),
        "body": ParagraphStyle("body", fontName="P", fontSize=9.8, leading=15.5, spaceAfter=8),
        "head": ParagraphStyle("head", fontName="PB", fontSize=11, leading=15, spaceBefore=6, spaceAfter=4),
        "quote": ParagraphStyle("quote", fontName="P", fontSize=9.8, leading=15.5,
                                leftIndent=8, textColor=colors.Color(0.2, 0.25, 0.33), spaceAfter=10),
        "method": ParagraphStyle("method", fontName="P", fontSize=7.6, leading=11, textColor=gray, spaceAfter=8),
        "cell": ParagraphStyle("cell", fontName="P", fontSize=8, leading=11),
        "cellb": ParagraphStyle("cellb", fontName="PB", fontSize=8, leading=11),
    }

    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=17 * mm, rightMargin=17 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    from PIL import Image as PImage
    w, h = PImage.open(CHART).size
    chart_w = 176 * mm
    chart = RLImage(str(CHART), width=chart_w, height=chart_w * h / w)

    def cell(txt, bold=False):
        return Paragraph(txt, ss["cellb"] if bold else ss["cell"])

    tdata = [[cell(x, True) for x in ["항목", "분당 (1기 신도시)", "부산", "대전"]]]
    for row in TABLE:
        tdata.append([cell(row[0], True), cell(row[1]), cell(row[2]), cell(row[3])])
    tbl = Table(tdata, colWidths=[36 * mm, 50 * mm, 46 * mm, 44 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.91, 0.945, 0.988)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.88, 0.92)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    story = [
        Paragraph("보도자료", ss["tag"]),
        Paragraph("배포일: 2026년 7월 · 즉시 보도 가능 &nbsp;&nbsp; 문의: 조용호 공동창업자 · albooooza@gmail.com · 010-4692-4946", ss["meta"]),
        Paragraph(TITLE, ss["title"]),
        Paragraph(SUBTITLE, ss["sub"]),
        Paragraph(LEAD, ss["body"]),
        chart,
        Spacer(1, 4 * mm),
        Paragraph("■ 3개 도시 한눈에 비교 (콕집 DB)", ss["head"]),
        tbl,
        Spacer(1, 2 * mm),
    ]
    for head, body in BODY:
        story.append(Paragraph("■ " + head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph(QUOTE, ss["quote"]))
    story.append(Paragraph(METHOD, ss["method"]))
    story.append(Paragraph("■ 서비스 개요", ss["head"]))
    for k, v in COMPANY:
        story.append(Paragraph(f"· <b>{k}</b>: {v}", ss["body"]))
    doc.build(story)
    print("pdf:", out)


if __name__ == "__main__":
    make_chart()
    make_docx(HERE / "선도지구_3도시비교.docx")
    make_pdf(HERE / "선도지구_3도시비교.pdf")
