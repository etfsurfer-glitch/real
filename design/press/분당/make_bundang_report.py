# -*- coding: utf-8 -*-
"""세제개편안 발표 이후 분당구 매물 시장 보고서 (기자 배포용).

종합보고서(세제개편안_발표이틀_종합보고서.pdf)의 최상위 10개 시군구 표에서 분당의 낙폭이
가장 컸다 — 그 한 칸을 지역 단위로 펼친 것이다.
수치는 design/press/data/press_bundang_*.csv 를 그대로 읽어 조판한다
(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
Run: python3 design/press/분당/make_bundang_report.py
  → design/press/분당/세제개편안_분당_매물시장.pdf
"""
import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
OUT = HERE / "세제개편안_분당_매물시장.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="PB", italic="P", boldItalic="PB")
pdfmetrics.registerFontFamily("PM", normal="PM", bold="PB", italic="PM", boldItalic="PB")

BLUE = colors.HexColor("#1268D3")
BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC")
INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80")
LINE = colors.HexColor("#C9D6E5")
RED = colors.HexColor("#C0392B")
GREEN = colors.HexColor("#1F7A4D")
BOXBG = colors.HexColor("#F4F8FD")
HOTBG = colors.HexColor("#FDF3F2")
WARNBG = colors.HexColor("#FFF8EC")
WARNLN = colors.HexColor("#E0A85E")

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18.5, leading=25, textColor=INK,
                            spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11.2, textColor=BLUE_DK, leading=17,
                          spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12,
                        spaceAfter=5),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.6, leading=15.5, textColor=INK,
                           spaceAfter=6),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.2, leading=17, textColor=INK,
                           spaceAfter=7),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY,
                            spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY,
                          spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.8, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white,
                         alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK,
                         alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=1),
    "tdr": ParagraphStyle("tdr", fontName="PB", fontSize=8.5, leading=10.4, textColor=RED,
                          alignment=1),
    "tdg": ParagraphStyle("tdg", fontName="PB", fontSize=8.5, leading=10.4, textColor=GREEN,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=0),
}


def P(t, s="body"):
    return Paragraph(t, ss[s])


def read(fn):
    with open(DATA / fn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hdr(cells):
    return [P(c, "th") for c in cells]


def box(html, bg=BOXBG, ln=LINE):
    t = Table([[P(html, "boxb")]], colWidths=[168 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("BOX", (0, 0), (-1, -1), 0.6, ln),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


FLOW = {(r["일차"], r["거래"], r["지표"]): r for r in read("press_bundang_flow.csv")}
BAND = read("press_bundang_band.csv")
WEEK = read("press_bundang_week.csv")
TOPCUT = read("press_bundang_topcut.csv")
DONG = read("press_bundang_dong.csv")
PEER = read("press_bundang_peer.csv")
TAX = read("press_bundang_tax.csv")
M = {r["항목"]: r["값"] for r in read("press_bundang_meta.csv")}

n = lambda v: f"{int(float(v)):,}"                      # noqa: E731
DD = ("1일차", "2일차", "3일차")

story = []
A = story.append

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 지역편", "tag"))
A(P("분당, 발표 당일 매물이 끊겼다 — 신규 등록 하루 만에 81% 감소", "title"))
A(P("평당가 상위 10개 시군구 중 낙폭이 가장 컸다 · 매매 신규 등록 "
    f"{FLOW[('1일차','매매','신규등록')]['증감율']}% → 사라진 매물 "
    f"{FLOW[('2일차','매매','실질소멸')]['증감율']}% → 사흘째 신규만 회복", "sub"))
A(P("발표 2026. 8. 3.(월) 18:00　|　관측 2026. 8. 4.(화)~8. 6.(목)　|　"
    "대상 경기도 성남시 분당구 아파트 매물 전수　|　자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 10))

A(P(
    f"세제개편안 발표 이틀째 종합보고서에서 평당가 상위 10개 시군구를 훑었을 때, "
    f"<b>분당구의 낙폭이 가장 컸다</b>. 사라진 매물이 평소의 5분의 1로 줄어(2일차 "
    f"{FLOW[('2일차','매매','실질소멸')]['증감율']}%) 강남·서초를 포함한 어느 지역보다 "
    "깊게 멈췄다. 그 한 칸을 지역 단위로 펼쳐 사흘간의 움직임을 따라간 것이 이 보고서다. "
    f"분당구 아파트 매매 광고는 <b>{n(M['매매매물_8월7일'])}건</b>({n(M['단지수'])}개 단지), "
    f"최근 1년 실거래 평당가 중위값은 <b>{n(M['평당가만원'])}만원</b>으로 전국 시군구 중 "
    "7위다.", "lead"))

# ── 1 ───────────────────────────────────────────────────────────────────
A(P("1. 사흘간 무슨 일이 있었나 — 내놓기가 먼저 멈추고, 거래가 뒤따라 멈췄다", "h"))
A(P("각 수치는 <b>직전 3주 같은 요일 평균</b>과 견준 것이다(요일 효과 제거). "
    "<b>실질소멸</b>은 거래·회수로 사라진 매물에서 광고 기간만료를 뺀 건수, "
    "<b>신규 등록</b>은 그날 새로 올라온 매물이다."))
rows = [hdr(["거래", "지표", "1일차 (8/4 화)", "", "2일차 (8/5 수)", "", "3일차 (8/6 목)", ""]),
        hdr(["", "", "건수", "평상시 대비", "건수", "평상시 대비", "건수", "평상시 대비"])]
for tr in ("매매", "전세"):
    for gi, ind in enumerate(("실질소멸", "신규등록")):
        cells = [P(f"<b>{tr}</b>" if gi == 0 else "", "tdb"),
                 P(ind.replace("등록", " 등록"), "tdb")]
        for d in DD:
            r = FLOW[(d, tr, ind)]
            v = float(r["증감율"])
            cells.append(P(f"{n(r['당일'])}<br/>"
                           f'<font size=6.1 color="#6B7684">({n(r["평상시"])})</font>', "td"))
            cells.append(P(f"{v:+.1f}%", "tdr" if v <= -70 else "tdb"))
        rows.append(cells)
t = Table(rows, colWidths=[16 * mm, 22 * mm] + [22 * mm, 21 * mm] * 3, repeatRows=2)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 1), BLUE),
    ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)),
    ("SPAN", (2, 0), (3, 0)), ("SPAN", (4, 0), (5, 0)), ("SPAN", (6, 0), (7, 0)),
    ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("LINEAFTER", (3, 0), (3, -1), 0.7, BLUE_DK),
    ("LINEAFTER", (5, 0), (5, -1), 0.7, BLUE_DK),
    ("LINEABOVE", (0, 4), (-1, 4), 0.7, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(t)
A(P("괄호 안은 비교 기준인 직전 3주 같은 요일 평균이다. 발표는 8월 3일 18시였다.", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>순서가 있었다 — 파는 쪽이 먼저 멈추고, 거래가 하루 늦게 멈췄다</b><br/>"
    f"· <b>1일차(8월 4일)</b> — 새로 올라온 매물이 "
    f"{n(FLOW[('1일차','매매','신규등록')]['당일'])}건으로 평소 "
    f"{n(FLOW[('1일차','매매','신규등록')]['평상시'])}건의 5분의 1도 되지 않았다"
    f"(<b>{FLOW[('1일차','매매','신규등록')]['증감율']}%</b>). 반면 사라진 매물은 "
    f"{FLOW[('1일차','매매','실질소멸')]['증감율']}%로 덜 줄었다. "
    "<b>내놓기를 미룬 것이 먼저였다.</b><br/>"
    f"· <b>2일차(8월 5일)</b> — 사라진 매물까지 "
    f"{n(FLOW[('2일차','매매','실질소멸')]['당일'])}건"
    f"(<b>{FLOW[('2일차','매매','실질소멸')]['증감율']}%</b>)으로 무너졌다. "
    "내놓지도, 팔리지도 않는 이틀째였다.<br/>"
    f"· <b>3일차(8월 6일)</b> — 신규 등록이 "
    f"{n(FLOW[('3일차','매매','신규등록')]['당일'])}건"
    f"({FLOW[('3일차','매매','신규등록')]['증감율']}%)으로 돌아왔지만, 사라지는 매물은 "
    f"여전히 <b>{FLOW[('3일차','매매','실질소멸')]['증감율']}%</b>다. "
    "<b>내놓는 쪽만 돌아오고 거래는 아직이다.</b><br/>"
    f"· <b>전세도 같은 순서다.</b> 1일차 신규 등록 "
    f"{FLOW[('1일차','전세','신규등록')]['증감율']}% → 2일차 실질소멸 "
    f"{FLOW[('2일차','전세','실질소멸')]['증감율']}% → 3일차 신규 등록 "
    f"{FLOW[('3일차','전세','신규등록')]['증감율']}%."))

A(Spacer(1, 6))
A(box(
    "<b>전국 최고가 구간(5분위)과 견주면 분당이 훨씬 깊었다</b><br/>"
    "같은 기간 전국 5분위(최고가 43개 시군구) 전체의 매매 신규 등록은 1일차 -30.0% → "
    "2일차 -21.0% → 3일차 +7.9%였다. 분당은 <b>1일차에만 -81.1%</b>로 그 세 배 가까이 "
    "빠졌고, 3일차에도 -26.8%로 평소를 밑돌았다. <b>같은 5분위 안에서도 분당의 반응이 "
    "유독 컸다.</b>", WARNBG, WARNLN))

# ── 2 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h2 = [P("2. 왜 분당인가 — 실거주 여부로 세금이 갈리는 구간에 매물이 가장 두껍다", "h"),
       P("종합부동산세는 <b>공시가격</b> 기준이다. 개편안은 기본공제를 <b>실거주 여부로 "
         "이원화</b>했다 — 1세대 1주택 거주자 14억원, 비거주 9억원, 다주택자는 "
         "<b>4억원 + 5억원 × (거주주택 공시가격 ÷ 전체 주택 공시가격)</b>으로 거주 비중에 "
         "따라 4억~9억 사이에서 정해진다. 2026년 공동주택 공시가격 현실화율 "
         "<b>69.0%</b>(4년 연속 동결)로 시가 환산하면 문턱이 셋 생긴다.")]
rows = [hdr(["구분", "기본공제(공시가격)", "시가 환산", "비고"])]
for r in TAX:
    now = r["비고"].startswith("개편 전")
    sty = "td" if now else "tdb"
    rows.append([P(r["구분"], "tdl"), P(r["기본공제_공시"], "tdl"),
                 P(r["시가환산"], "tdr" if not now else "td"), P(r["비고"], "td")])
t = Table(rows, colWidths=[38 * mm, 60 * mm, 30 * mm, 40 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, 4), (-1, 5), ROWALT),
    ("LINEABOVE", (0, 4), (-1, 4), 1.0, BLUE_DK),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
]))
A(KeepTogether(_h2 + [t]))
A(P("<b>공시가격 현실화율은 단지·연도마다 달라 위 시가 환산은 근사치이며, 개별 매물의 실제 "
    "과세 여부와는 다를 수 있다.</b> 공정시장가액비율(현행 60% → 2027년 70%, 3주택 이상·"
    "조정대상지역은 2028년 80%)과 세율표 개편(2028년 가액 기준 0.5~5.0%)은 별도다.", "cap"))

A(Spacer(1, 6))
_h2b = [P("분당 매물을 그 문턱으로 자르면", "h")]
rows = [hdr(["매매 호가 구간", "종부세상 의미", "분당 매물", "분당 비중", "전국 비중", "전국 대비"])]
for r in BAND:
    hot = r["가격대"] == "13.0~20.3억"
    sty = "tdb" if hot else "td"
    rows.append([P(r["가격대"], "tdl"), P(r["의미"], "tdl"), P(n(r["분당"]), sty),
                 P(f"{r['분당비중']}%", "tdr" if hot else "tdb"),
                 P(f"{r['전국비중']}%", "td"), P(f"{r['배수']}배", sty)])
t = Table(rows, colWidths=[24 * mm, 62 * mm, 20 * mm, 21 * mm, 20 * mm, 21 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, 3), (-1, 3), HOTBG),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
]))
A(t)
A(P("2026년 8월 7일 기준 분당구 아파트 매매 광고의 호가 분포다. ‘전국 대비’는 분당 비중을 "
    "전국 비중으로 나눈 값이다.", "cap"))

A(Spacer(1, 6))
_h2c = [P("평당가 상위 10개 시군구 비교 — 13.0~20.3억 비중은 분당이 1위", "h")]
rows = [hdr(["시·군·구", "매매 매물", "5.8억 미만", "5.8~13.0억", "13.0~20.3억", "20.3억 이상"])]
for r in PEER:
    bd_ = "분당" in r["시군구"]
    sty = "tdb" if bd_ else "td"
    rows.append([P(r["시군구"], "tdl"), P(n(r["매물수"]), sty), P(f"{r['a_58미만']}%", sty),
                 P(f"{r['b_58_130']}%", sty),
                 P(f"{r['c_130_203']}%", "tdr" if bd_ else "tdb"),
                 P(f"{r['d_203이상']}%", sty)])
t = Table(rows, colWidths=[32 * mm, 26 * mm, 26 * mm, 28 * mm, 28 * mm, 28 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, 1), (-1, 1), HOTBG),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether(_h2c + [t]))

A(Spacer(1, 6))
A(box(
    "<b>분당은 ‘실거주냐 아니냐’로 세금이 갈리는 자리에 매물이 가장 많다</b><br/>"
    "· 개편안의 핵심은 <b>같은 집이라도 본인이 사느냐에 따라 공제를 달리 준다</b>는 것이다. "
    "그 차이가 실제로 발생하는 구간이 <b>시가 13.0~20.3억</b>이다 — 거주 1주택이면 "
    "한 푼도 안 내지만, 비거주거나 다주택이면 과세 대상이 된다.<br/>"
    "· <b>분당은 이 구간에 매물의 35.7%가 있다.</b> 평당가 상위 10개 시군구 중 가장 높다"
    "(성동 34.1%, 강동 33.3%, 광진 33.1%). 전국 비중(6.0%)의 <b>5.9배</b>다.<br/>"
    "· <b>강남(7.8%)·서초(7.7%)·과천(10.9%)·용산(12.7%)은 이 구간이 얇다.</b> 매물의 "
    "6~8할이 이미 20.3억을 넘어 거주 1주택이어도 과세권이다. 실거주 여부로 새로 갈릴 여지가 "
    "그만큼 적다.<br/>"
    "· 즉 분당은 <b>개편안이 새로 그은 선 위에 매물이 가장 두껍게 얹힌 지역</b>이다. "
    "보유·매도 판단이 가장 크게 흔들릴 조건이고, 발표 직후 신규 등록이 하루 만에 81% 빠진 "
    "것과 맞아떨어진다.<br/>"
    "· <b>다만 이는 구조적 정합성이지 인과의 증명은 아니다.</b> 사흘치 관측으로는 "
    "매도 보류인지 매수 위축인지 가릴 수 없다."))

# ── 3 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h3 = [P("3. 호가는 — 6월까지 올리는 쪽이 두 배였는데 뒤집혔다", "h"),
       P("같은 매물의 호가가 바뀐 건을 주(목~수) 단위로 세어 <b>인하÷인상</b> 배율을 냈다. "
         "1을 밑돌면 값을 올린 매물이 더 많았다는 뜻이다.")]
rows = [hdr(["주 시작(목)"] + [r["주시작"] for r in WEEK]),
        [P("<b>인하</b>", "tdb")] + [P(n(r["인하"]), "td") for r in WEEK],
        [P("<b>인상</b>", "tdb")] + [P(n(r["인상"]), "td") for r in WEEK],
        [P("<b>인하÷인상</b>", "tdb")] +
        [P(r["배율"], "tdr" if i == len(WEEK) - 1 else
           ("tdg" if float(r["배율"]) < 1 else "tdb")) for i, r in enumerate(WEEK)]]
t = Table(rows, colWidths=[22 * mm] + [14.6 * mm] * 10, repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (1, 0), (-1, -1), 2), ("RIGHTPADDING", (1, 0), (-1, -1), 2),
    ("TOPPADDING", (0, 0), (-1, -1), 3.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
]))
A(KeepTogether(_h3 + [t]))
A(P(f"녹색은 1 미만(인상이 더 많았던 주)이다. 평상시(최근 2주를 뺀 직전 8주) 범위는 "
    f"{M['평상시배율_최저']}~{M['평상시배율_최고']}배, 평균 {M['평상시배율_평균']}배였다.", "cap"))

A(Spacer(1, 6))
A(box(
    f"· <b>6월까지 분당은 값을 올려 부르는 쪽이 더 많았다.</b> 배율이 "
    f"{M['평상시배율_최저']}~0.78로 1을 크게 밑돌았다. 7월 10일 주에 처음 1을 넘었고"
    f"(1.13), 최근 주는 <b>{M['최근주배율']}배</b>다.<br/>"
    f"· 다만 <b>건수 자체는 많지 않다.</b> 최근 주 인하 {n(WEEK[-1]['인하'])}건·인상 "
    f"{n(WEEK[-1]['인상'])}건으로, 분당 매매 광고 {n(M['매매매물_8월7일'])}건의 1.6%다. "
    "호가를 고치는 일 자체가 줄어든 상태에서 방향만 바뀐 것으로 읽어야 한다.<br/>"
    f"· <b>재고는 거의 그대로다.</b> 7월 31일 {n(M['재고_7월31일'])}건 → 8월 6일 "
    f"{n(M['재고_8월6일'])}건으로 3% 줄었을 뿐이다. <b>매물이 쏟아지지도, 사라지지도 "
    "않았다.</b>"))

A(Spacer(1, 8))
_h3b = [P("4. 최근 1주일 호가를 내린 단지", "h"),
        P("7월 31일~8월 6일 분당구에서 호가를 내린 건이 많았던 단지다. "
          "단지 단위로는 건수가 적어 순위보다 <b>어떤 단지에서 움직임이 있었는지</b>로 "
          "읽는 것이 적절하다.")]
rows = [hdr(["단지", "동", "인하 건수", "평균 인하폭", "평균 호가"])]
for r in TOPCUT:
    rows.append([P(r["단지"], "tdl"), P(r["동"], "td"), P(n(r["인하건수"]), "tdb"),
                 P(f"{r['평균인하율']}%", "tdr" if float(r["평균인하율"]) >= 5 else "td"),
                 P(f"{r['평균호가억']}억", "td")])
t = Table(rows, colWidths=[46 * mm, 22 * mm, 24 * mm, 26 * mm, 26 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether(_h3b + [t]))
A(P("‘평균 호가’는 값을 고치기 전 호가의 평균이다. 인하 건수가 2건 이하인 단지는 뺐다.", "cap"))

# ── 5 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h4 = [P("5. 동별 매물 분포", "h"),
       P("분당구 안에서도 호가 수준이 크게 갈린다. 판교 일대(백현·삼평·운중·판교동)와 "
         "이매·수내·서현이 높고, 야탑·구미·금곡이 낮다.")]
rows = [hdr(["동", "매매 매물", "평균 호가", "최고 호가"])]
for r in DONG:
    hi = float(r["평균호가억"]) >= 19
    rows.append([P(r["동"], "tdl"), P(n(r["매물수"]), "td"),
                 P(f"{r['평균호가억']}억", "tdb" if hi else "td"),
                 P(f"{r['최고호가억']}억", "td")])
t = Table(rows, colWidths=[36 * mm, 36 * mm, 36 * mm, 36 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether(_h4 + [t]))
A(P("2026년 8월 7일 기준. 매물 3건뿐인 궁내동은 뺐다.", "cap"))

# ── 6 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(KeepTogether([
    P("6. 해석 시 유의사항", "h"),
    box(
        "· <b>사흘치 관측이다.</b> 발표 다음 날부터 사흘을 각각 직전 3주 같은 요일과 비교한 "
        "결과로, 추세 확정에는 며칠간의 누적 확인이 필요하다.<br/>"
        "· <b>매도 보류와 매수 위축은 이 지표만으로 구분되지 않는다.</b> 매물이 덜 사라진 것이 "
        "파는 쪽이 멈춰서인지, 사는 쪽이 줄어서인지는 실거래 확정 후 판단이 가능하다.<br/>"
        "· <b>시군구 단위는 표본이 작다.</b> 분당은 하루 수백~1천 건 규모여서 전국 집계보다 "
        "진폭이 크다. 단지 단위는 더 작으므로 개별 값보다 방향으로 읽어야 한다.<br/>"
        "· <b>실거래 통계로는 아직 확인할 수 없다.</b> 부동산 거래는 계약 후 30일 이내 "
        f"신고여서 8월 초 계약분은 9월 초에야 집계가 채워진다. 분당의 최근 실거래는 "
        f"2026년 7월 {n(M['실거래_2026_07'])}건이 마지막으로 채워진 달이다.<br/>"
        "· <b>‘실질소멸’은 광고 기간만료를 뺀 수치다.</b> 네이버 부동산 광고는 확인일자로부터 "
        "31일이 지나면 자동으로 내려간다. 이 물량은 시장 상황과 무관하므로 전부 걷어냈다.<br/>"
        "· <b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이다.<br/>"
        "· <b>개정 ‘안’이다.</b> 국회 논의 과정에서 내용이 바뀔 수 있다.", WARNBG, WARNLN),
]))
A(Spacer(1, 12))
A(P("런투온라인 대표 황인찬　|　부동산 데이터 서비스 ‘콕집’　"
    "<font color='#1268D3'>koczip.com</font>", "small"))
A(P("010-5942-8014　runtoonline@gmail.com", "small"))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="세제개편안 이후 분당 매물 시장", author="런투온라인")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
