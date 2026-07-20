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

TITLE = "선도지구 선정되면 거래 먼저 멈춘다 — 분당·부산, 직후 1~3개월 거래 최대 62% 급감"
SUBTITLE = "콕집, 선정 시점 맞춰 비교 — 가격은 곧바로 9~18% 올라 유지 · 대전은 지금 그 초입"

LEAD = (
    "노후계획도시 정비 선도지구로 선정된 지역은 발표 직후 거래가 먼저 멈추고, 가격은 곧바로 올라 "
    "유지되는 흐름을 보인 것으로 나타났다. 부동산 데이터 플랫폼 콕집(koczip.com)이 앞서 선정된 "
    "분당(2024년 11월, 12개 단지 10,738세대)과 부산(2025년 12월, 5개 단지 7,318세대)을 **선정 시점에 "
    "맞춰** 비교한 결과다. 선정 후 1개월 시점 매매 거래량은 분당이 선정 전 대비 45.6%, 부산이 10.4% "
    "줄었고, 분당은 2개월 시점에 61.6%까지 감소했다. 반면 평균 실거래가는 두 지역 모두 선정 직후부터 "
    "올라 분당 14~18%, 부산 9~12% 높은 수준을 유지했다. 7월 15일 선정된 대전은 발표 엿새째로, 앞선 "
    "두 지역이 지난 구간의 초입에 있다."
)

BODY = [
    ("왜 ‘같은 시점’으로 맞춰야 하나",
     "세 지역은 선정 시점이 각각 2024년 11월(분당), 2025년 12월(부산), 2026년 7월(대전)로 다르다. "
     "경과 기간이 다른 상태를 그대로 나란히 놓으면 비교가 성립하지 않는다. 실제로 분당의 20개월 전체 "
     "평균과 부산의 6개월 평균을 단순 비교하면 분당은 거래가 늘고 부산은 줄어든 것처럼 보이지만, "
     "이는 분당의 후반 회복분이 섞인 결과다. 이번 분석은 각 지역의 ‘선정 전 12개월’을 자기 기준선으로 "
     "삼고, 선정 후 1개월·2개월·3개월·6개월 시점을 같은 자리끼리 맞춰 비교했다."),
    ("① 거래 — 선정 직후 멈췄다가 시차를 두고 돌아온다",
     "선정 후 거래량은 두 지역 모두 감소로 출발했다. 분당은 1개월 시점 -45.6%, 2개월 시점 -61.6%로 "
     "선정 전의 3분의 1 수준까지 떨어졌다가 3개월 -45.6%, 4개월 -26.4%, 5개월 -17.4%를 거쳐 6개월 "
     "시점에는 -8.8%로 거의 회복했다. 부산은 낙폭이 더 완만한 대신 회복도 더뎠다. 1개월 -10.4%로 "
     "시작해 3개월 시점 -26.9%로 저점을 찍은 뒤 6개월 시점에도 -22.4%에 머물렀다. 두 지역 모두 "
     "선정 직후 거래가 위축되는 국면은 공통이었지만, 6개월 시점의 회복 정도는 갈렸다."),
    ("② 가격 — 거래가 멈춰도 곧바로 올라 유지된다",
     "거래가 줄어드는 동안에도 평균 실거래가는 두 지역 모두 선정 직후부터 상승했다. 분당은 1개월 "
     "시점 이미 선정 전보다 15.9% 높았고, 3개월 시점 18.2%까지 오른 뒤 6개월 시점 14.8%를 유지했다. "
     "부산은 1개월 시점 11.4%로 시작해 6개월 시점 9.0%로 다소 낮아졌지만 선정 전 수준을 계속 웃돌았다. "
     "거래 건수가 줄어든 상태에서 나온 평균가라는 점은 감안해야 하지만, 두 지역에서 같은 방향이 "
     "확인됐다는 점은 공통적이다."),
    ("③ 대전 — 지금은 매물이 잠긴 초입",
     "대전 선도지구 6개 단지는 발표 전날인 7월 14일 227건이던 매매 광고매물이 7월 20일 176건으로 "
     "22.5% 줄었다. 실매물 기준으로도 144건에서 117건으로 18.8% 감소했다. 같은 동네의 선정되지 않은 "
     "단지들은 거의 움직이지 않았다. 둔산동 비선정 69개 단지는 2.1% 늘었고 법동 8개 단지는 1.5% "
     "증가했으며 탄방동 33개 단지는 2.8% 줄어드는 데 그쳤다. 매물이 줄어든 경로도 통념과 달랐다. "
     "발표 후 엿새간 신규 등록이 61건에서 39건으로 36% 급감한 반면 회수는 69건에서 82건으로 19% "
     "느는 데 그쳐, 이미 나온 물건을 거둬들인 것보다 새 물건이 나오지 않은 영향이 더 컸다. 대전은 "
     "아직 발표 후 실거래 신고가 접수되지 않아(신고 기한 30일) 거래량·가격은 다음 달부터 확인된다."),
    ("해석 시 유의점",
     "이번 비교는 앞선 두 지역이 지나온 경로를 보여주는 것이며, 대전의 향후 거래량이나 가격을 "
     "예측하지 않는다. 분당은 수도권 1기 신도시, 부산·대전은 지방권으로 시장 규모와 성격이 다르고, "
     "세 지역의 관찰 기간에 적용된 금융·세제 환경도 동일하지 않다. 실제로 분당과 부산도 6개월 시점 "
     "거래 회복 정도가 -8.8%와 -22.4%로 크게 갈렸다. 거래 건수가 적은 구간은 평균가 변동 폭이 커질 "
     "수 있다는 점, 매물 데이터는 콕집 수집이 2026년 5월 시작돼 분당·부산의 선정 직후 매물은 비교할 "
     "수 없다는 점도 함께 고려해야 한다."),
    ("일자별 매물·호가, 누구나 단지 단위로 확인 가능",
     "콕집은 전국 아파트·오피스텔 6만 4천여 단지의 매물과 실거래를 매일 수집해 교차 분석하는 "
     "플랫폼으로, 이번 분석에 쓰인 일자별 매물수·실매물수·평균 호가 추이는 콕집 단지 상세의 "
     "‘매물분석’ 메뉴에서 누구나 무료로 확인할 수 있다. 지역 비교, 부동산 타임머신(정책 연대기), "
     "급매 탐지, 단지별 신고가 등 분석 기능도 함께 제공한다."),
]

QUOTE = ("조용호 콕집 공동창업자는 “선정 시점이 다른 지역을 그냥 나란히 놓으면 엉뚱한 결론이 나온다”며 "
         "“각 지역의 선정 시점을 0으로 맞춰 같은 자리끼리 비교했더니, 거래는 먼저 멈추고 가격은 곧바로 "
         "오르는 공통된 초기 국면이 확인됐다. 다만 6개월 뒤 회복 정도는 지역마다 달랐던 만큼 예측이 "
         "아니라 참고 자료로 봐야 한다”고 말했다.")

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

# ── 실측 데이터(2026-07-20 DB) ──
# 선정 시점을 맞춘 비교: (선정 후 K개월, 거래량 변화율%, 평균가 변화율%)
# 각 도시의 '선정 전 12개월'을 자기 기준선으로 삼고, 선정 후 1~K개월 누적 월평균과 비교.
# 관찰 기간이 다르면(분당 20개월 vs 부산 6개월) 비교가 성립하지 않는다 — 같은 K에서만 비교.
BUNDANG_ALIGNED = [   # 선정 2024-11 · 기준 월평균 31.2건 / 13억 3,828만
    (1, -45.6, 15.9), (2, -61.6, 14.6), (3, -45.6, 18.2),
    (4, -26.4, 14.7), (5, -17.4, 16.3), (6, -8.8, 14.8),
]
BUSAN_ALIGNED = [     # 선정 2025-12 · 기준 월평균 22.3건 / 4억 3,417만
    (1, -10.4, 11.4), (2, -26.1, 10.5), (3, -26.9, 10.3),
    (4, -25.0, 12.0), (5, -22.1, 9.6), (6, -22.4, 9.0),
]

TABLE = [   # 선정 후 같은 경과 시점끼리 비교
    ("선정일", "2024-11-27", "2025-12-12", "2026-07-15"),
    ("규모", "12단지 10,738세대", "5단지 7,318세대", "6단지 7,797세대"),
    ("선정 전 12개월 (기준)", "월 31.2건 · 13억 3,828만", "월 22.3건 · 4억 3,417만", "월 32.5건 · 7억 6,790만"),
    ("+1개월 거래량", "-45.6%", "-10.4%", "신고 전"),
    ("+2개월 거래량", "-61.6%", "-26.1%", "신고 전"),
    ("+3개월 거래량", "-45.6%", "-26.9%", "신고 전"),
    ("+6개월 거래량", "-8.8%", "-22.4%", "신고 전"),
    ("+1개월 가격", "+15.9%", "+11.4%", "신고 전"),
    ("+3개월 가격", "+18.2%", "+10.3%", "신고 전"),
    ("+6개월 가격", "+14.8%", "+9.0%", "신고 전"),
    ("현재 매물 상황", "비교 불가 (수집 전)", "비교 불가 (수집 전)", "발표 엿새 -22.5%"),
]


def make_chart():
    """선정 시점을 0으로 맞춰 **같은 경과 개월끼리** 비교한다.
    경과 시간이 다른 상태(분당 20개월 vs 부산 6개월)를 나란히 놓으면 비교 기준이 없다.
    대전은 아직 +6일이라 실거래가 없으므로 '현재 위치'만 표시하고 수치는 넣지 않는다.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf"):
        font_manager.fontManager.addfont(str(FONTS / f))
    plt.rcParams["font.family"] = "Pretendard"
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.4, 3.9), dpi=200)
    bx = [r[0] for r in BUNDANG_ALIGNED]
    sx = [r[0] for r in BUSAN_ALIGNED]

    for ax, idx, title, ylab, ylim in (
        (ax1, 1, "① 거래량 — 선정 직후 급감했다가 회복", "선정 전 대비 (%)", (-72, 18)),
        (ax2, 2, "② 가격 — 선정 직후 바로 올라 유지", "선정 전 대비 (%)", (-4, 26)),
    ):
        ax.axhline(0, color="#333", lw=1)
        ax.plot(bx, [r[idx] for r in BUNDANG_ALIGNED], "o-", color="#1268d3", lw=2.4,
                ms=5, label="분당 (2024.11 선정)")
        ax.plot(sx, [r[idx] for r in BUSAN_ALIGNED], "s-", color="#e08a1e", lw=2.2,
                ms=5, label="부산 (2025.12 선정)")
        for rows, col, dy in ((BUNDANG_ALIGNED, "#1268d3", 8), (BUSAN_ALIGNED, "#e08a1e", -14)):
            v = rows[-1][idx]
            ax.annotate(f"{v:+.1f}%", (6, v), textcoords="offset points", xytext=(-6, dy),
                        fontsize=9.5, fontweight="bold", color=col, ha="right")
        # 대전 현재 위치
        ax.axvspan(0.0, 0.25, color="#2b8a3e", alpha=.14)
        ax.text(0.30, ylim[0] + (ylim[1]-ylim[0])*0.06, "대전\n현재", fontsize=8.5,
                fontweight="bold", color="#2b8a3e", va="bottom")
        ax.set_xlim(0, 6.6)
        ax.set_xticks([1, 2, 3, 4, 5, 6])
        ax.set_xticklabels(["+1", "+2", "+3", "+4", "+5", "+6"], fontsize=9)
        ax.set_xlabel("선정 후 경과 개월", fontsize=9)
        ax.set_ylabel(ylab, fontsize=9)
        ax.set_ylim(*ylim)
        ax.tick_params(axis="y", labelsize=8.5)
        ax.grid(axis="y", color="#eef2f6", lw=.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.set_title(title, fontsize=10.5, fontweight="bold", pad=8, loc="left")
        ax.legend(fontsize=8.5, frameon=False, loc="lower right")

    fig.suptitle("선도지구 선정 후 같은 시점끼리 비교 — 대전이 앞으로 지날 구간 (콕집 DB)",
                 fontsize=11.5, fontweight="bold", y=0.99)
    fig.text(0.5, 0.005, "각 도시의 '선정 전 12개월'을 자기 기준(0%)으로 삼아 선정 후 누적 월평균과 비교. "
             "대전은 발표 엿새째로 실거래 신고(기한 30일)가 아직 없다.",
             ha="center", fontsize=8, color="#64748b")
    fig.tight_layout(rect=[0, 0.035, 1, 0.955])
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
