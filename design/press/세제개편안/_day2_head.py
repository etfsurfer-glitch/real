# -*- coding: utf-8 -*-
"""2026년 세제개편안 발표 이틀째 아파트 매물 시장 반응 보고서 (기자 배포용).

수치는 design/press/data/press_day2.csv · press_day2_top.csv · press_tiers.csv 를
그대로 읽어 조판한다(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
Run: python3 design/press/세제개편안/make_tax_reform_day2.py
  → design/press/세제개편안/세제개편안_발표이틀째_매물시장반응.pdf
"""
import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
OUT = HERE / "세제개편안_발표이틀째_매물시장반응.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

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
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=9.6, textColor=INK, alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=9.6, textColor=INK,
                          alignment=1),
    "tdr": ParagraphStyle("tdr", fontName="PB", fontSize=8.5, leading=9.6, textColor=RED,
                          alignment=1),
    "tdg": ParagraphStyle("tdg", fontName="PB", fontSize=8.5, leading=9.6, textColor=GREEN,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=9.6, textColor=INK,
                          alignment=0),
    "tier": ParagraphStyle("tier", fontName="P", fontSize=7.6, leading=11.6, textColor=INK,
                           alignment=0),
    "credit": ParagraphStyle("credit", fontName="PM", fontSize=9, leading=14.5, textColor=INK),
}


def P(t, s="body"):
    return Paragraph(t, ss[s])


def read(fn):
    with open(DATA / fn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


D1, D2 = "1일차(8/4 화)", "2일차(8/5 수)"
RAW = read("press_day2.csv")
T = {(r["일차"], r["거래"], r["구분"]): r for r in RAW}
TOP = read("press_day2_top.csv")
TIERS = read("press_tiers.csv")
# CSV 는 급지 표기(1급지=최고가) — 보도자료는 5분위=최고가 관행을 따른다
T2Q = {"1급지": "5분위", "2급지": "4분위", "3급지": "3분위", "4급지": "2분위", "5급지": "1분위"}
QS = ("5분위", "4분위", "3분위", "2분위", "1분위")
TRS = ("매매", "전세", "월세")
n = lambda v: f"{int(float(v)):,}"          # noqa: E731


pc = lambda v: f"{float(v):+.1f}%"          # noqa: E731
sn = lambda v: f"{int(float(v)):+,}"        # 부호 붙은 건수(증감) # noqa: E731

