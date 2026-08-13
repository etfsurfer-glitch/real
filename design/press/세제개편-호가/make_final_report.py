# -*- coding: utf-8 -*-
"""세제개편안 전후 서울 호가 — 최종보고서.

흐름: 기준 ①(사건)로 보면 이렇고 → 기준 ②(물건)로 보면 이렇다 → 그래서 시장은 이렇다.

의도적으로 뺀 것 둘
  · 대조군('평상시') — 10일짜리 한 구간을 평상시라고 부르기엔 기간이 너무 짧다.
    이 자료는 발표 전 10일과 발표 후 10일만 견준다.
  · 실거래 — 8월 계약분은 신고가 절반도 안 찼고(계약 후 14일에 50.2%),
    싼 거래가 먼저 신고되는 편향(-26.6%)까지 겹쳐 지금 시점에 쓸 수 없다.

원자료: design/press/data/press_tax_*.csv(사건) · panel_*.csv(물건)
Run: python3 design/press/세제개편-호가/make_final_report.py
  → design/press/세제개편-호가/세제개편_전후_호가_최종보고서.pdf
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
OUT = HERE / "세제개편_전후_호가_최종보고서.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="PB", italic="P", boldItalic="PB")

BLUE = colors.HexColor("#1268D3")
BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC")
INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80")
LINE = colors.HexColor("#C9D6E5")
BOXBG = colors.HexColor("#F4F8FD")
HOTBG = colors.HexColor("#FDF3F2")
WARNBG = colors.HexColor("#FFF8EC")
WARNLN = colors.HexColor("#E0A85E")

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18, leading=24, textColor=INK,
                            spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11, textColor=BLUE_DK, leading=16.5,
                          spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12,
                        spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="PB", fontSize=10.5, textColor=BLUE_DK, spaceBefore=8,
                         spaceAfter=4),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.6, leading=15.5, textColor=INK,
                           spaceAfter=6),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.2, leading=17, textColor=INK,
                           spaceAfter=7),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY,
                            spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY,
                          spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.2, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white,
                         alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK,
                         alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=10.4, textColor=INK,
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


EV_B = {r["가격대"]: r for r in read("press_tax_band.csv")}
EV_O = {r["구분"]: r for r in read("press_tax_overall.csv")}
PN_B = {r["가격대"]: r for r in read("panel_band.csv")}
PN_O = {r["구분"]: r for r in read("panel_overall.csv")}
ZONE = read("panel_zone.csv")
GU = read("panel_gu.csv")
STOCK = read("panel_stock.csv")

BANDS = ["10억 미만", "10~15억", "15~20억", "20~30억", "30억 이상"]
AREAS = ["전국", "서울", "강남3구", "서울(강남3구 외)"]
n = lambda v: f"{int(float(v)):,}"                    # noqa: E731
pc1 = lambda v: f"{float(v):.1f}%"                    # noqa: E731


def pc2(v):
    f = round(float(v), 2)
    return "0.00%" if f == 0 else f"{f:.2f}%".replace("-", "−")


def pair(a, b, pct=None):
    """발표 전 → 발표 후 건수. 두 구간은 모집단 자체가 다르므로 비율을 함께 적는다."""
    t = f"{int(float(a)):,} → <b>{int(float(b)):,}</b>"
    if pct is not None:
        t += f" <font size=7 color='#8B95A5'>({float(pct):.1f}%)</font>"
    return t


def ratio(v):
    """내린 집 : 올린 집. 1.0 이 분기점 — 넘으면 내리는 쪽이 많다."""
    if v in ("", None):
        return "—"
    f = float(v)
    c = "#C0392B" if f >= 1.3 else ("#1F7A4D" if f < 1.0 else "#18233A")
    b = "<b>" if f >= 1.3 or f < 1.0 else ""
    return f"<font color='{c}'>{b}{f:.2f}배{'</b>' if b else ''}</font>"


def cut(man, pct):
    """내릴 때 깎는 폭 — 금액이 먼저, 비율은 괄호로."""
    if man in ("", None):
        return "—"
    m = int(float(man))
    txt = f"{m/10000:.1f}억" if m >= 10000 else f"{m:,}만"
    return f"{txt} <font size=7 color='#8B95A5'>({float(pct):.1f}%)</font>"


def sign(v, unit="p", flip=False, bold=True):
    """flip=True 면 '값이 오른 것'이 나쁜 신호(인하 물건 비율·재고 등)."""
    if v in ("", None):
        return "—"
    v = float(v)
    t = f"{v:+.1f}{unit}".replace("-", "−")
    if abs(v) < 0.5:
        return f"<font color='#5A6B80'>{t}</font>"
    bad = (v > 0) if flip else (v < 0)
    c = "#C0392B" if bad else "#1F7A4D"
    return f"<font color='{c}'>{'<b>' if bold else ''}{t}{'</b>' if bold else ''}</font>"


TBL = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
       ("GRID", (0, 0), (-1, -1), 0.4, LINE),
       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]

story = []
A = story.append

seoul_p, gn3_p = PN_O["서울"], PN_O["강남3구"]
FLAT = round(100 - float(seoul_p["발표후_인하비율"]) - float(seoul_p["발표후_인상비율"]), 1)
b30, b10 = PN_B["30억 이상"], PN_B["10억 미만"]
st30 = [r for r in STOCK if r["가격대"] == "30억 이상"][0]
st10 = [r for r in STOCK if r["가격대"] == "10억 미만"][0]

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제개편안 열흘, <b>고가는 내리고 저가는 버텼다</b>", "title"))
A(P(f"같은 서울인데 가격대에 따라 반대로 움직였다. 30억 이상은 값을 내린 집이 올린 집의 "
    f"<b>{b30['발표후_인하대인상_배']}배</b>인 반면, 10억 미만은 "
    f"{b10['발표후_인하대인상_배']}배로 오히려 올리는 쪽이 많다. "
    f"<b>갈라지는 선은 15억</b>이고, 그사이 매물은 전 구간에서 쌓였다", "sub"))
A(P("집계 발표 2026. 8. 3. 18시　|　발표 전 10일(7/24~8/02) vs 발표 후 10일(8/04~8/13)　|　"
    "서울 아파트 매매　|　자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 6))

A(P(
    "호가 통계는 <b>무엇을 분모에 놓느냐</b>에 따라 크기가 크게 달라진다. 그래서 성격이 다른 "
    "두 방법으로 따로 집계했다.<br/><br/>"
    "<b>① 사건 기준</b> — 호가를 고친 광고만 세어, 그중 <b>올린 쪽의 몫</b>이 어떻게 변했는지 "
    "본다. 값을 고칠 만큼 움직인 매도자들이 어느 쪽으로 기울었는지가 드러난다.<br/>"
    "<b>② 물건 기준</b> — 같은 집을 열흘 간격 두 시점에 이어 붙여, 값을 안 고친 집까지 분모에 "
    "넣는다. <b>시장 전체가 실제로 움직인 폭</b>이 나온다.<br/><br/>"
    "아래는 두 기준으로 각각 본 결과이고, 마지막에 둘을 겹쳐 어느 가격대가 내리고 어느 "
    "가격대가 버티는지를 정리했다.", "lead"))

# ── 1. 사건 기준 ────────────────────────────────────────────────────────
_h1 = [P("1. 기준 ① 사건 — 값을 고친 사람들은 어느 쪽으로 기울었나", "h"),
       P("지표는 <b>인상률 = 인상 ÷ (인상+인하)</b>다. 100%에 가까울수록 값을 고친 사람 중 "
         "올린 쪽이 많다는 뜻이다.", "body")]
rows = [hdr(["구분", "호가 고친 건수<br/>발표 전 → 후", "올린 건수<br/>발표 전 → 후",
             "내린 건수<br/>발표 전 → 후", "인상률<br/>발표 전 → 후", "변화"])]
for k in AREAS:
    r = EV_O[k]
    rows.append([P(f"<b>{k}</b>", "tdl"), P(pair(r["발표전_건수"], r["발표후_건수"]), "td"),
                 P(pair(r["발표전_인상"], r["발표후_인상"]), "td"),
                 P(pair(r["발표전_인하"], r["발표후_인하"]), "td"),
                 P(f"{pc1(r['발표전_인상률'])} → <b>{pc1(r['발표후_인상률'])}</b>", "td"),
                 P(sign(r["발표전후_변화p"]), "td")])
t = Table(rows, colWidths=[28 * mm, 30 * mm, 28 * mm, 28 * mm, 30 * mm, 18 * mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                                   ("BACKGROUND", (0, 3), (-1, 3), HOTBG)]))
A(KeepTogether(_h1 + [t]))

rows = [hdr(["서울 가격대", "호가 고친 건수<br/>발표 전 → 후", "올린 건수<br/>발표 전 → 후",
             "내린 건수<br/>발표 전 → 후", "인상률<br/>발표 전 → 후", "변화"])]
for b in BANDS:
    r = EV_B[b]
    rows.append([P(f"<b>{b}</b>", "tdl"), P(pair(r["발표전_건수"], r["발표후_건수"]), "td"),
                 P(pair(r["발표전_인상"], r["발표후_인상"]), "td"),
                 P(pair(r["발표전_인하"], r["발표후_인하"]), "td"),
                 P(f"{pc1(r['발표전_인상률'])} → <b>{pc1(r['발표후_인상률'])}</b>", "td"),
                 P(sign(r["발표전후_변화p"]), "td")])
t = Table(rows, colWidths=[28 * mm, 30 * mm, 28 * mm, 28 * mm, 30 * mm, 18 * mm], repeatRows=1)
st = list(TBL)
for i, b in enumerate(BANDS, start=1):
    if float(EV_B[b]["발표전후_변화p"]) <= -5:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(t)
A(P("건수는 광고 단위다 — 한 매물이 두 번 고치면 두 건, 같은 집을 여러 사무소가 올렸으면 각각 센다. 붉게 칠한 줄은 발표 전후로 5%p 넘게 꺾인 구간이다.", "cap"))

A(box(
    "<b>움직인 사람들 안에서는 15억을 경계로 갈렸다</b><br/>"
    f"· 서울은 {pc1(EV_O['서울']['발표전_인상률'])} → {pc1(EV_O['서울']['발표후_인상률'])}, "
    f"강남3구는 {pc1(EV_O['강남3구']['발표전_인상률'])} → "
    f"{pc1(EV_O['강남3구']['발표후_인상률'])}로 떨어졌다. 강남3구에서 값을 고친 매물은 "
    "이제 여섯 중 다섯이 내린 것이다.<br/>"
    f"· 15억 위 세 구간이 모두 두 자리로 꺾였다(15~20억 "
    f"{sign(EV_B['15~20억']['발표전후_변화p'], bold=False)}, 20~30억 "
    f"{sign(EV_B['20~30억']['발표전후_변화p'], bold=False)}, 30억 이상 "
    f"{sign(EV_B['30억 이상']['발표전후_변화p'], bold=False)}).<br/>"
    f"· <b>전국은 {sign(EV_O['전국']['발표전후_변화p'], bold=False)}로 제자리다.</b> "
    "이 사안은 전국 현상이 아니다."))

# ── 2. 물건 기준 ────────────────────────────────────────────────────────
A(Spacer(1, 5))
_h2 = [P("2. 기준 ② 물건 — 어느 가격대에서 값을 내리고 있나", "h"),
       P("여기서 ‘물건’은 광고가 아니라 집이다 — 여러 사무소가 올린 같은 집은 한 채로 접었다. "
         "괄호 안은 물건 수 대비 비율이고, ‘내린 집 : 올린 집’이 <b>1.00배를 넘으면 내리는 쪽이 "
         "더 많다</b>는 뜻이다. 두 구간은 살아 있던 물건이 달라 모집단 자체가 다르므로, "
         "건수보다 비율과 배수를 견주는 것이 맞다.", "body")]
rows = [hdr(["구분", "물건 수<br/>발표 전 → 후", "내린 집<br/>발표 전 → 후 (비율)",
             "올린 집<br/>발표 전 → 후 (비율)", "내린 집 : 올린 집<br/>발표 전 → 후",
             "내릴 때<br/>깎는 폭"])]
for k in AREAS:
    r = PN_O[k]
    rows.append([P(f"<b>{k}</b>", "tdl"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"),
                 P(pair(r["발표전_인하물건"], r["발표후_인하물건"], r["발표후_인하비율"]), "td"),
                 P(pair(r["발표전_인상물건"], r["발표후_인상물건"], r["발표후_인상비율"]), "td"),
                 P(f"{float(r['발표전_인하대인상_배']):.2f} → "
                   f"{ratio(r['발표후_인하대인상_배'])}", "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=[26 * mm, 26 * mm, 34 * mm, 34 * mm, 26 * mm, 22 * mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                                   ("BACKGROUND", (0, 3), (-1, 3), HOTBG)]))
A(KeepTogether(_h2 + [t]))

rows = [hdr(["서울 가격대", "물건 수<br/>발표 전 → 후", "내린 집<br/>발표 전 → 후 (비율)",
             "올린 집<br/>발표 전 → 후 (비율)", "내린 집 : 올린 집<br/>발표 전 → 후",
             "내릴 때<br/>깎는 폭"])]
for b in BANDS:
    r = PN_B[b]
    rows.append([P(f"<b>{b}</b>", "tdl"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"),
                 P(pair(r["발표전_인하물건"], r["발표후_인하물건"], r["발표후_인하비율"]), "td"),
                 P(pair(r["발표전_인상물건"], r["발표후_인상물건"], r["발표후_인상비율"]), "td"),
                 P(f"{float(r['발표전_인하대인상_배']):.2f} → "
                   f"{ratio(r['발표후_인하대인상_배'])}", "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=[26 * mm, 26 * mm, 34 * mm, 34 * mm, 26 * mm, 22 * mm], repeatRows=1)
st = list(TBL)
for i, b in enumerate(BANDS, start=1):
    if float(PN_B[b]["발표전후_인하비율변화p"]) > 0:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st.append(("LINEABOVE", (0, 3), (-1, 3), 1.1, BLUE))
t.setStyle(TableStyle(st))
A(t)
A(P("파란 선 위는 올린 집이 더 많고(1.00배 미만), 아래는 내린 집이 더 많다. 붉게 칠한 두 줄은 내린 집 비율까지 늘어난 구간이다.", "cap"))

A(box(
    f"<b>내린 집이 올린 집보다 많아지는 선은 15억이다</b><br/>"
    f"· 10억 미만 {float(b10['발표후_인하대인상_배']):.2f}배, 10~15억 "
    f"{float(PN_B['10~15억']['발표후_인하대인상_배']):.2f}배로 <b>올리는 집이 더 많다</b>. "
    f"15~20억 {float(PN_B['15~20억']['발표후_인하대인상_배']):.2f}배부터 뒤집혀 30억 이상은 "
    f"{float(b30['발표후_인하대인상_배']):.2f}배까지 벌어진다.<br/>"
    f"· 값을 내린 집의 비율도 30억 이상만 "
    f"{sign(b30['발표전후_인하비율변화p'], flip=True, bold=False)}로 뚜렷이 늘었다. "
    f"10억 미만은 {sign(b10['발표전후_인하비율변화p'], flip=True, bold=False)}로 줄었다.<br/>"
    f"· <b>깎는 비율은 어느 구간이나 2% 안팎으로 비슷하다</b> — 달라지는 것은 얼마나 많은 집이 "
    f"내리느냐다.<br/>"
    f"· 사건 기준(1절)이 15억을 경계로 본 것과 <b>같은 자리</b>다."))

# ── 3. 지역 ─────────────────────────────────────────────────────────────
A(Spacer(1, 5))
_h3 = [P("3. 지역 — 흔들리는 곳은 비싼 동네다", "h"),
       P("물건 기준으로 본 권역별 흐름이다.", "body")]
rows = [hdr(["권역", "중앙<br/>호가", "물건 수<br/>발표 전 → 후",
             "내린 집<br/>발표 전 → 후 (비율)", "올린 집<br/>발표 전 → 후 (비율)",
             "내린 집 :<br/>올린 집", "깎는 폭"])]
ZN = {"강남3구": "강남·서초·송파", "마용성": "마포·용산·성동", "양천·강서": "양천·강서",
      "노도강": "노원·도봉·강북", "그 외 서울": "나머지 14개 구"}
for r in ZONE:
    rows.append([P(f"<b>{r['권역']}</b> <font size=7 color='#8B95A5'>{ZN.get(r['권역'],'')}</font>",
                   "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"),
                 P(pair(r["발표전_인하물건"], r["발표후_인하물건"], r["발표후_인하비율"]), "td"),
                 P(pair(r["발표전_인상물건"], r["발표후_인상물건"], r["발표후_인상비율"]), "td"),
                 P(ratio(r["발표후_인하대인상_배"]), "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=[32 * mm, 14 * mm, 24 * mm, 32 * mm, 32 * mm, 16 * mm, 18 * mm], repeatRows=1)
st = list(TBL) + [("BACKGROUND", (0, 1), (-1, 1), HOTBG)]
for i in (3, 5):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h3 + [t]))
A(P("노도강·양천·강서는 1.00배를 밑돈다 — 값을 올리는 집이 더 많다.", "cap"))

GU.sort(key=lambda r: -float(r["발표후_인하대인상_배"] or 0))
story.append(P("자치구별 — 300물건 이상인 25곳, 내린 집이 올린 집보다 많은 순서", "h2"))
rows = [hdr(["자치구", "중앙<br/>호가", "물건 수<br/>발표 전 → 후",
             "내린 집<br/>발표 전 → 후 (비율)", "올린 집<br/>발표 전 → 후 (비율)",
             "내린 집 :<br/>올린 집", "깎는 폭"])]
for r in GU:
    thin = int(r["발표후_인하물건"]) + int(r["발표후_인상물건"]) < 50
    rows.append([P(f"<b>{r['자치구']}</b>" + (" <font color='#C9A227'>★</font>" if thin else ""),
                   "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"),
                 P(pair(r["발표전_인하물건"], r["발표후_인하물건"], r["발표후_인하비율"]), "td"),
                 P(pair(r["발표전_인상물건"], r["발표후_인상물건"], r["발표후_인상비율"]), "td"),
                 P(ratio(r["발표후_인하대인상_배"]), "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=[22 * mm, 16 * mm, 26 * mm, 32 * mm, 32 * mm, 18 * mm, 22 * mm],
          repeatRows=1)
st = list(TBL)
for i, r in enumerate(GU, start=1):
    if r["자치구"] in ("강남구", "서초구", "송파구"):
        st += [("BACKGROUND", (0, i), (-1, i), HOTBG),
               ("LINEBEFORE", (0, i), (0, i), 2.2, colors.HexColor("#C0392B"))]
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. 두 구간은 살아 있던 물건이 달라 모집단이 "
    "다르므로 건수는 괄호 안 비율과 함께 읽어야 한다. <b>★</b>는 발표 후 값을 고친 물건이 "
    "50건에 못 미쳐 배수가 쉽게 흔들리는 구다.", "cap"))

# ── 4. 재고 ─────────────────────────────────────────────────────────────
A(Spacer(1, 5))
_h4 = [P("4. 값은 안 내렸지만 매물은 쌓이고 있다", "h"),
       P("호가를 안 고쳤다고 시장이 멎은 것은 아니다. 같은 열흘 동안 서울 물건 수는 "
         "전 구간에서 늘었고, 비쌀수록 빠르게 늘었다.", "body")]
rows = [hdr(["서울 가격대", "8월 2일", "8월 12일", "증감", "증감률"])]
for r in STOCK:
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"), P(n(r["2026-08-02"]), "td"),
                 P(f"<b>{n(r['2026-08-12'])}</b>", "tdb"),
                 P(f"{int(r['발표후_증감']):+,}".replace("-", "−"), "td"),
                 P(sign(r["발표후_증감률"], unit="%", flip=True), "td")])
t = Table(rows, colWidths=[32 * mm, 28 * mm, 28 * mm, 24 * mm, 26 * mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 5), (-1, 5), HOTBG),
                                   ("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                                   ("BACKGROUND", (0, 4), (-1, 4), ROWALT)]))
A(KeepTogether(_h4 + [t]))
A(P("증감률의 붉은색은 매물이 늘었다는 뜻이다.", "cap"))

# ── 5. 결론 ─────────────────────────────────────────────────────────────
A(Spacer(1, 4))
A(KeepTogether([
    P("5. 두 기준을 겹쳐 보면 — 고가는 내리고, 저가는 받쳐준다", "h"),
    box(
        f"<b>① 15억을 기준으로 시장이 둘로 갈렸다.</b> 15억 아래에서는 값을 올린 집이 더 많고"
        f"(10억 미만 {float(b10['발표후_인하대인상_배']):.2f}배, 10~15억 "
        f"{float(PN_B['10~15억']['발표후_인하대인상_배']):.2f}배), 15억을 넘으면 뒤집혀 30억 "
        f"이상은 내린 집이 올린 집보다 <b>{float(b30['발표후_인하대인상_배']):.2f}배</b> 많다. "
        "사건 기준(1절)에서 15억 위 세 구간이 두 자리로 꺾인 것과 같은 자리다. "
        "<b>서로 다른 분모를 쓴 두 방법이 같은 선을 가리켰다.</b><br/><br/>"
        f"<b>② 고가는 값이 내려가고 있다.</b> 30억 이상은 100채 중 "
        f"{b30['발표후_인하비율']}채가 열흘 새 호가를 내렸고, 그 비율은 발표 전보다 "
        f"{sign(b30['발표전후_인하비율변화p'], flip=True, bold=False)} 늘었다. "
        f"내릴 때 깎는 금액은 중앙값 "
        f"{int(float(b30['발표후_인하폭_중앙_만원']))//10000}억이다. "
        "강남3구·마용성이 이 흐름을 이끈다.<br/><br/>"
        f"<b>③ 저가는 흔들리지 않았다 — 다만 올린 것도 아니다.</b> 10억 미만은 값을 내린 집이 "
        f"{sign(b10['발표전후_인하비율변화p'], flip=True, bold=False)} 줄었고 올린 집이 내린 "
        f"집보다 많다({float(b10['발표후_인하대인상_배']):.2f}배). 다만 <b>올린 집도 "
        f"{float(b10['발표전_인상비율']) - float(b10['발표후_인상비율']):.1f}채 줄어</b> "
        f"비율은 발표 전({float(b10['발표전_인하대인상_배']):.2f}배)과 사실상 같다. "
        "<b>저가가 값을 올린 것이 아니라, 내리는 쪽으로 기울지 않은 것</b>이다. 노도강은 "
        f"{float([r for r in ZONE if r['권역']=='노도강'][0]['발표후_인하대인상_배']):.2f}배로 "
        "서울에서 값을 올리는 쪽이 가장 두텁다.<br/><br/>"
        f"<b>④ 깎는 폭이 아니라 깎는 집의 수가 달라졌다.</b> 내릴 때 깎는 비율은 10억 미만 "
        f"{b10['발표후_인하폭_중앙_률']}%, 30억 이상 {b30['발표후_인하폭_중앙_률']}%로 차이가 "
        "없다. 고가에서 벌어진 일은 한 집이 크게 깎은 것이 아니라 <b>내리는 집이 늘어난 것</b>이다."
        "<br/><br/>"
        f"<b>⑤ 값을 올리려는 힘은 서울 전역에서 약해졌다.</b> 올린 집은 <b>다섯 구간 모두</b> "
        f"줄었다(10억 미만 −{float(b10['발표전_인상비율'])-float(b10['발표후_인상비율']):.1f}채, "
        f"30억 이상 −{float(b30['발표전_인상비율'])-float(b30['발표후_인상비율']):.1f}채). "
        "고가에서 배수가 벌어진 것은 내리는 집이 늘어난 동시에 <b>올리는 집이 줄었기</b> "
        "때문이다. 저가에서 배수가 그대로인 것도 양쪽이 함께 줄어서다.<br/><br/>"
        "<b>⑥ 매물은 전 구간에서 쌓이고 있다 — 이것이 앞으로의 압력이다.</b> 열흘 만에 서울 "
        f"물건은 10억 미만 {sign(st10['발표후_증감률'], unit='%', flip=True, bold=False)}, "
        f"30억 이상 {sign(st30['발표후_증감률'], unit='%', flip=True, bold=False)} 늘었다. "
        "<b>부르는 값과 사려는 값의 거리가 벌어지고 있다</b>는 뜻이고, 이 상태가 이어지면 "
        "다음에 움직이는 것은 호가다.")]))

# ── 6. 방법 ─────────────────────────────────────────────────────────────
A(Spacer(1, 4))
A(KeepTogether([
    P("6. 집계 방법과 유의사항", "h"),
    box(
        "<b>구간</b> — 발표 2026. 8. 3. 18시. 발표 전 10일 7/24~8/02, 발표 후 10일 8/04~8/13"
        "(물건 기준은 8/02→8/12 두 시점을 잇는다). 사건 기준에서는 하루 안에 전후가 섞이는 "
        "<b>8/03을 통째로 제외</b>했다.<br/>"
        "<b>① 사건 기준</b> — 같은 매물번호의 호가가 직전 수집 때와 달라진 건만 센다. 신규 "
        "등록·매물 회수는 포함하지 않는다. 한 매물이 두 번 내리면 두 번 세고, 같은 집을 여러 "
        "중개사무소가 올린 광고도 각각 센다 — 그래서 물건 기준보다 크게 나온다.<br/>"
        "<b>② 물건 기준</b> — 한 집을 여러 중개사무소가 올리면 광고는 여러 건이다(전국 아파트 "
        "매매 광고 126만 → 물건 52만). 묶는 기준은 <b>단지+동+층+전용면적+향+공급면적</b>이며 "
        "호가는 넣지 않았다(넣으면 값이 바뀐 순간 다른 물건이 돼 추적이 끊긴다). 이 기준으로 센 "
        "물건 수는 포털이 자체 표기하는 동일주소 광고 수로 환산한 값의 <b>97.8%</b>로 거의 "
        "일치한다.<br/>"
        "<b>가격대는 매물마다 하나로 고정</b>했다. 그때그때 값으로 나누면 값을 내린 매물이 아래 "
        "구간으로 옮겨가 저가 구간에 인하가 쌓인다.<br/>"
        "<b>생존 편향은 결론과 반대 방향이다.</b> 열흘 뒤에도 남아 있는 비율은 10억 미만 89.0%, "
        "30억 이상 94.1%로 싼 매물이 더 많이 빠진다. 남은 저가 매물은 ‘안 팔린 것’ 쪽으로 "
        "치우치는데도 값을 덜 내렸다.<br/>"
        "<b>기준점을 바꿔도 같다.</b> 매물 수집은 11시·19시라 8/03 스냅샷은 발표 뒤다. 마지막 "
        "온전한 발표 전 상태인 8/02를 기준으로 삼았고, 8/03으로 바꿔도 순서와 부호가 그대로였다"
        "(30억 이상 인하 물건 13.1% vs 14.8%).<br/>"
        "<b>자치구 표는 표본이 두꺼운 곳만</b> 실었다(300물건 이상 25곳).<br/>"
        "<b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이며 그 값에 팔린다는 뜻이 아니다. "
        "실거래는 계약 후 30일 이내 신고라 8월 계약분은 신고가 절반도 차지 않았고, 싼 거래가 "
        "먼저 신고되는 편향까지 겹쳐 <b>지금 시점에는 견줄 수 없다.</b> 신고가 채워지는 9월 초에 "
        "같은 기준으로 다시 집계할 예정이다.",
        WARNBG, WARNLN),
]))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>황인찬</b>　|　런투온라인 대표　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-5942-8014　runtoonline@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="세제개편안 열흘, 서울 아파트 시장은 어디로 가고 있나",
                        author="황인찬 (런투온라인)")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
