# -*- coding: utf-8 -*-
"""세제개편안 전후 — 동일 물건 호가 '수준' 보고서 (2차 자료, 기자 배포용).

1차 자료(세제개편_전후_호가변동.pdf)는 '값을 고친 사건'을 셌다. 이 자료는 값을 안 고친
집까지 분모에 넣어 '시장 전체가 얼마나 움직였나'를 본다. 두 자료의 숫자는 분모가 달라
섞어 쓰면 안 되고, 그 경고를 자료 안에 박아 둔다.

수치는 design/press/data/panel_*.csv 를 그대로 읽어 조판한다(박스 실측 산출물).
Run: python3 design/press/세제개편-호가/make_panel_report.py
  → design/press/세제개편-호가/세제개편_전후_호가수준.pdf
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
OUT = HERE / "세제개편_전후_호가수준.pdf"

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


OV = {r["구분"]: r for r in read("panel_overall.csv")}
BAND = read("panel_band.csv")
ZONE = read("panel_zone.csv")
GU = read("panel_gu.csv")
STOCK = read("panel_stock.csv")
SENS = "민감도(8/03→8/13)"

n = lambda v: f"{int(float(v)):,}"                    # noqa: E731
pc1 = lambda v: f"{float(v):.1f}%"                    # noqa: E731


def pc2(v):
    """평균 변동률 — 0.00% 는 '거의 안 움직였다'는 뜻이지 결측이 아니다.
    반올림해서 0 이 된 음수를 '−0.00%' 로 적으면 없는 방향성을 있는 것처럼 보이게 한다."""
    f = round(float(v), 2)
    if f == 0:
        return "0.00%"
    return f"{f:.2f}%".replace("-", "−")


def dp(v, bold=True, unit="p"):
    if v in ("", None):
        return "—"
    v = float(v)
    t = f"{v:+.1f}{unit}".replace("-", "−")
    if abs(v) < 0.5:
        return f"<font color='#5A6B80'>{t}</font>"
    # 인하 비율이 '오른' 것이 나쁜 신호다 — 색을 값 부호가 아니라 의미에 맞춘다
    c = "#C0392B" if v > 0 else "#1F7A4D"
    return f"<font color='{c}'>{'<b>' if bold else ''}{t}{'</b>' if bold else ''}</font>"


TBL = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
       ("GRID", (0, 0), (-1, -1), 0.4, LINE),
       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]

story = []
A = story.append

b10 = [r for r in BAND if r["가격대"] == "10억 미만"][0]
b30 = [r for r in BAND if r["가격대"] == "30억 이상"][0]
b2030 = [r for r in BAND if r["가격대"] == "20~30억"][0]
b1520 = [r for r in BAND if r["가격대"] == "15~20억"][0]
seoul = OV["서울"]
gn3 = OV["강남3구"]
# 값을 한 번도 안 고친 물건 비율
FLAT = round(100 - float(seoul["발표후_인하비율"]) - float(seoul["발표후_인상비율"]), 1)

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편 <b>2차</b>", "tag"))
A(P("열흘간 서울 아파트 열에 아홉은 <b>호가를 그대로 뒀다</b>", "title"))
A(P(f"값을 내린 물건이 늘어난 곳은 20억 위뿐이다(30억 이상 "
    f"{pc1(b30['대조군_인하비율'])} → {pc1(b30['발표후_인하비율'])}). "
    f"서울 전체 호가 수준의 변화는 {pc2(seoul['발표후_전체_평균변동률'])}에 그쳤다", "sub"))
A(P("집계 발표 전 10일(2026. 8. 2. 기준) · 발표 후 10일(8. 12. 기준) · "
    "평상시 대조군 10일(7. 13.→7. 23.)　|　서울 아파트 매매, 같은 물건을 두 시점에 이어 붙임　|　"
    "자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 8))

A(P(
    "앞서 배포한 1차 자료는 <b>호가를 고친 사건</b>을 셌다. 값을 고친 사람들 안에서 "
    "올린 쪽이 얼마나 줄었는지를 본 것이다. 이 2차 자료는 <b>값을 안 고친 집까지 분모에 "
    "넣는다.</b> 같은 집을 열흘 간격 두 시점에 이어 붙여, 시장 전체의 호가 수준이 실제로 "
    "얼마나 움직였는지를 잰다.<br/><br/>"
    f"답부터 적으면 <b>거의 움직이지 않았다.</b> 서울 아파트 물건의 <b>{FLAT}%</b>는 열흘 동안 "
    f"호가를 한 번도 고치지 않았고, 전체 평균 호가 변동은 "
    f"{pc2(seoul['발표후_전체_평균변동률'])}다. 가장 크게 움직인 30억 이상도 "
    f"{pc2(b30['발표후_전체_평균변동률'])}에 그친다.<br/><br/>"
    "달라진 것은 <b>값을 내리는 물건의 비율</b>이고, 그것도 위쪽에만 몰려 있다. "
    "1차 자료의 큰 낙폭과 이 자료의 작은 낙폭은 서로 어긋나는 것이 아니다 — "
    "<b>분모가 다르다.</b>", "lead"))

# ── 1. 두 자료의 관계 ───────────────────────────────────────────────────
A(KeepTogether([
    P("1. 1차 자료와 무엇이 다른가 — 숫자를 섞지 마시라", "h"),
    box(
        "<b>같은 시장을 두 가지 자로 잰 것이다.</b><br/>"
        "· <b>1차(사건 기준)</b> — 분모는 ‘값을 고친 광고’다. 강남3구 인상률 36.4% → 16.3%. "
        "고친 사람들 안에서 올린 쪽의 몫이 줄었다는 뜻이다.<br/>"
        "· <b>2차(물건 기준, 이 자료)</b> — 분모는 ‘살아 있는 모든 물건’이다. 강남3구에서 값을 "
        f"내린 물건은 {pc1(gn3['대조군_인하비율'])} → {pc1(gn3['발표후_인하비율'])}. "
        "나머지 대다수는 값을 그대로 뒀다.<br/>"
        "· 한 자료의 분자를 다른 자료의 분모에 얹으면 틀린 수가 나온다. "
        "<b>기사에서는 둘 중 하나를 골라 쓰시고, 출처 표기를 나눠 주시기 바란다.</b>",
        WARNBG, WARNLN),
]))

# ── 2. 전체 ─────────────────────────────────────────────────────────────
A(P("2. 호가 수준은 서울에서도 거의 안 움직였다", "h"))
A(P("‘인하 물건’은 열흘 뒤 호가가 낮아진 물건의 비율, ‘평균 변동률’은 값을 안 고친 물건을 "
    "0%로 넣은 전체 평균이다. 뒤 숫자가 시장이 실제로 움직인 폭이다.", "body"))
rows = [hdr(["구분", "기준<br/>중앙호가", "인하 물건 비율<br/>평상시 → 발표전 → 발표후",
             "평상시<br/>대비", "평균 변동률<br/>발표 후 10일", "물건 수"])]
for k in ("전국", "서울", "강남3구", "서울(강남3구 외)"):
    r = OV[k]
    seq = (f"{pc1(r['대조군_인하비율'])} → {pc1(r['발표전_인하비율'])} → "
           f"<b>{pc1(r['발표후_인하비율'])}</b>")
    rows.append([P(f"<b>{k}</b>", "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"), P(seq, "td"),
                 P(dp(r["대조군대비_인하비율변화p"]), "td"),
                 P(f"<b>{pc2(r['발표후_전체_평균변동률'])}</b>", "tdb"),
                 P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[32 * mm, 20 * mm, 46 * mm, 18 * mm, 26 * mm, 20 * mm], repeatRows=1)
st = list(TBL) + [("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                  ("BACKGROUND", (0, 3), (-1, 3), HOTBG)]
t.setStyle(TableStyle(st))
A(t)
A(P("붉은 %p는 값을 내린 물건이 평상시보다 <b>늘었다</b>는 뜻이다(나쁜 신호). "
    "‘물건 수’는 두 시점에 모두 살아 있어 이어 붙은 물건이다.", "cap"))

A(Spacer(1, 3))
A(box(
    f"<b>강남3구만 눈에 띄고, 그 강남3구도 {pc2(gn3['발표후_전체_평균변동률'])}다</b><br/>"
    f"· <b>전국</b>은 인하 물건이 {pc1(OV['전국']['대조군_인하비율'])} → "
    f"{pc1(OV['전국']['발표후_인하비율'])}로 오히려 줄었다. 이 사안은 전국 현상이 아니다.<br/>"
    f"· <b>강남3구</b>만 {pc1(gn3['대조군_인하비율'])} → {pc1(gn3['발표후_인하비율'])}로 늘었다"
    f"({dp(gn3['대조군대비_인하비율변화p'], False)}). 그래도 열에 아홉은 값을 그대로 뒀다.<br/>"
    f"· <b>강남3구를 뺀 서울</b>은 {pc1(OV['서울(강남3구 외)']['발표후_인하비율'])}로 평상시보다 "
    "낮다. 서울을 한 덩어리로 말하면 강남3구의 움직임이 전 지역으로 번진 것처럼 보인다."))

# ── 3. 가격대 ───────────────────────────────────────────────────────────
A(Spacer(1, 6))
_h3 = [P("3. 경계는 <b>20억</b>이다 — 1차 자료의 15억과 다른 이유", "h"),
       P("가격대는 시작 시점의 호가로 고정했다. 값을 내린 물건이 평상시보다 늘어난 구간은 "
         "20억 위 둘뿐이고, 아래 세 구간은 오히려 줄었다.", "body")]
rows = [hdr(["가격대", "기준<br/>중앙호가", "인하 물건 비율<br/>평상시 → 발표전 → 발표후",
             "평상시<br/>대비", "평균 변동률<br/>발표 후", "물건 수"])]
for r in BAND:
    up = float(r["대조군대비_인하비율변화p"]) > 0
    seq = (f"{pc1(r['대조군_인하비율'])} → {pc1(r['발표전_인하비율'])} → "
           f"<b>{pc1(r['발표후_인하비율'])}</b>")
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"),
                 P(seq, "td"), P(dp(r["대조군대비_인하비율변화p"]), "td"),
                 P(f"<b>{pc2(r['발표후_전체_평균변동률'])}</b>", "tdb"),
                 P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[26 * mm, 20 * mm, 48 * mm, 18 * mm, 26 * mm, 20 * mm], repeatRows=1)
st = list(TBL)
for i, r in enumerate(BAND, start=1):
    if float(r["대조군대비_인하비율변화p"]) > 0:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st.append(("LINEABOVE", (0, 4), (-1, 4), 1.1, BLUE))
t.setStyle(TableStyle(st))
A(KeepTogether(_h3 + [t]))
A(P("파란 선이 20억 경계다. 붉게 칠한 두 줄만 값을 내린 물건이 평상시보다 늘었다.", "cap"))

A(Spacer(1, 3))
A(box(
    "<b>지표가 다르면 경계도 다르다 — 둘 다 사실이다</b><br/>"
    f"· <b>인하 물건 비율</b>로 보면 경계는 <b>20억</b>이다. 20~30억 "
    f"{dp(b2030['대조군대비_인하비율변화p'], False)}, 30억 이상 "
    f"{dp(b30['대조군대비_인하비율변화p'], False)}만 늘었고, 15~20억은 "
    f"{dp(b1520['대조군대비_인하비율변화p'], False)}로 오히려 줄었다.<br/>"
    f"· <b>평균 변동률이 0 에 닿는 자리</b>는 <b>15~20억</b>"
    f"({pc2(b1520['대조군_전체_평균변동률'])} → {pc2(b1520['발표후_전체_평균변동률'])})이다. "
    "1차 자료가 15억을 경계로 본 것과 같은 자리인데, 여기서는 값이 0 에 붙었을 뿐 "
    "아래로 내려가지는 않았다.<br/>"
    f"· <b>10억 미만</b>은 인하 물건이 {dp(b10['대조군대비_인하비율변화p'], False)}로 줄었고 "
    f"평균도 {pc2(b10['발표후_전체_평균변동률'])}로 여전히 플러스다. "
    "저가 구간에서는 발표의 자취를 찾기 어렵다."))

# ── 4. 지역 ─────────────────────────────────────────────────────────────
A(Spacer(1, 6))
_h4 = [P("4. 지역 — 비싼 동네일수록 값을 내린다", "h"),
       P("권역별로도 가격대 순서와 겹친다. 자치구를 중앙 호가와 나란히 놓으면 관계가 더 뚜렷하다.",
         "body")]
rows = [hdr(["권역", "기준<br/>중앙호가", "인하 물건 비율<br/>평상시 → 발표전 → 발표후",
             "평상시<br/>대비", "평균 변동률<br/>발표 후", "물건 수"])]
ZN = {"강남3구": "강남·서초·송파", "마용성": "마포·용산·성동", "양천·강서": "양천·강서",
      "노도강": "노원·도봉·강북", "그 외 서울": "나머지 14개 구"}
for r in ZONE:
    seq = (f"{pc1(r['대조군_인하비율'])} → {pc1(r['발표전_인하비율'])} → "
           f"<b>{pc1(r['발표후_인하비율'])}</b>")
    rows.append([P(f"<b>{r['권역']}</b> <font size=7 color='#8B95A5'>{ZN.get(r['권역'], '')}</font>",
                   "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"), P(seq, "td"),
                 P(dp(r["대조군대비_인하비율변화p"]), "td"),
                 P(f"<b>{pc2(r['발표후_전체_평균변동률'])}</b>", "tdb"),
                 P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[40 * mm, 18 * mm, 44 * mm, 18 * mm, 24 * mm, 16 * mm], repeatRows=1)
st = list(TBL) + [("BACKGROUND", (0, 1), (-1, 1), HOTBG)]
for i in (3, 5):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h4 + [t]))
A(P("노도강은 평균 변동률이 여전히 플러스다 — 값을 올리는 쪽이 더 많다.", "cap"))

A(Spacer(1, 5))
GU.sort(key=lambda r: -float(r["대조군대비_인하비율변화p"]))
_h4b = [P("자치구별 — 중앙 호가 순으로 갈린다", "h"),
        P("세 구간 모두 300물건 이상인 25개 구다. 평상시 대비 인하 물건이 늘어난 순서로 "
          "놓았는데, 위쪽에는 비싼 구가 아래쪽에는 싼 구가 모인다.", "body")]
rows = [hdr(["자치구", "기준<br/>중앙호가", "평상시", "발표전", "발표후", "평상시<br/>대비",
             "평균 변동률", "물건 수"])]
for r in GU:
    rows.append([P(f"<b>{r['자치구']}</b>", "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"),
                 P(pc1(r["대조군_인하비율"]), "td"), P(pc1(r["발표전_인하비율"]), "td"),
                 P(f"<b>{pc1(r['발표후_인하비율'])}</b>", "tdb"),
                 P(dp(r["대조군대비_인하비율변화p"]), "td"),
                 P(pc2(r["발표후_전체_평균변동률"]), "td"), P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[24 * mm, 20 * mm, 19 * mm, 19 * mm, 19 * mm, 20 * mm,
                           24 * mm, 20 * mm], repeatRows=1)
st = list(TBL)
for i, r in enumerate(GU, start=1):
    if r["자치구"] in ("강남구", "서초구", "송파구"):
        st += [("BACKGROUND", (0, i), (-1, i), HOTBG),
               ("LINEBEFORE", (0, i), (0, i), 2.2, colors.HexColor("#C0392B"))]
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
story.extend(_h4b)
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. 25개 구에서 <b>중앙 호가와 인하 비율 변화의 "
    "상관은 r = +0.68</b>(순위 상관 ρ = +0.44) — 비쌀수록 값을 내린다.", "cap"))

# ── 5. 재고 ─────────────────────────────────────────────────────────────
A(Spacer(1, 6))
_h5 = [P("5. 값은 안 내렸지만 <b>매물은 쌓이고 있다</b>", "h"),
       P("호가를 안 고쳤다고 시장이 멎은 것은 아니다. 같은 열흘 동안 서울 물건 수는 전 구간에서 "
         "늘었고, 고가일수록 빠르게 늘었다.", "body")]
rows = [hdr(["가격대", "8월 2일", "8월 12일", "증감", "증감률"])]
for r in STOCK:
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"), P(n(r["2026-08-02"]), "td"),
                 P(f"<b>{n(r['2026-08-12'])}</b>", "tdb"),
                 P(f"{int(r['발표후_증감']):+,}".replace("-", "−"), "td"),
                 P(dp(r["발표후_증감률"], unit="%"), "td")])
t = Table(rows, colWidths=[30 * mm, 26 * mm, 26 * mm, 24 * mm, 24 * mm], repeatRows=1)
st = list(TBL) + [("BACKGROUND", (0, 5), (-1, 5), HOTBG)]
for i in (2, 4):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h5 + [t]))
A(P("증감률의 붉은색은 매물이 늘었다는 뜻이다. 30억 이상이 가장 빠르게 쌓인다.", "cap"))

# ── 6. 방법·유의 ────────────────────────────────────────────────────────
A(Spacer(1, 6))
A(KeepTogether([
    P("6. 집계 방법과 유의사항", "h"),
    box(
        "· <b>광고가 아니라 물건을 셌다.</b> 한 집을 여러 중개사무소가 올리면 광고는 여러 건이다"
        "(전국 아파트 매매 광고 126만 → 물건 52만). 같은 집으로 묶는 기준은 "
        "<b>단지+동+층+전용면적+향+공급면적</b>이며, 호가는 기준에 넣지 않았다"
        "(넣으면 값이 바뀐 순간 다른 물건이 돼 추적이 끊긴다).<br/>"
        "· <b>묶음 기준을 검증했다.</b> 이 기준으로 센 물건 수가 포털이 자체 표기하는 "
        "동일주소 광고 수로 환산한 값의 <b>97.8%</b>로 거의 일치한다.<br/>"
        "· <b>두 시점에 모두 살아 있는 물건만</b> 이었다. 열흘 사이 팔리거나 거둬들인 매물은 빠진다.<br/>"
        "· <b>생존 편향은 이 자료의 결론과 반대 방향이다.</b> 열흘 뒤에도 남아 있는 비율은 "
        "10억 미만 89.0%, 30억 이상 94.1%로 <b>싼 매물이 더 많이 빠진다</b>. 남은 저가 매물은 "
        "‘안 팔린 것’ 쪽으로 치우치는데도 값을 덜 내렸다 — 편향이 결론을 만들어낸 것이 아니다.<br/>"
        "· <b>기준점을 바꿔도 같다.</b> 매물 수집은 11시·19시라 8월 3일 스냅샷은 발표(18시) 뒤다. "
        "그래서 마지막 온전한 발표 전 상태인 <b>8월 2일</b>을 기준으로 삼았고, 8월 3일로 바꿔 "
        "다시 계산해도 순서와 부호가 그대로였다(30억 이상 인하 물건 13.1% vs 14.8%).<br/>"
        "· <b>대조군을 함께 봐야 한다.</b> ‘비싼 집일수록 값을 잘 내린다’는 7월 중순에도 이미 "
        "그랬다(10억 미만 4.1% vs 30억 이상 9.2%). 발표가 만든 것은 그 서열이 아니라 <b>격차</b>다.<br/>"
        "· <b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이며 그 값에 팔린다는 뜻이 아니다. "
        "실거래는 계약 후 30일 이내 신고라 <b>8월 계약분은 9월 초에야 집계가 채워진다</b>. "
        "거래 기반 지수와 나란히 놓을 때는 이 시차를 함께 밝혀야 한다.",
        WARNBG, WARNLN),
]))

A(KeepTogether([
    Spacer(1, 9),
    P("작성 <b>황인찬</b>　|　런투온라인 대표　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-5942-8014　runtoonline@gmail.com", "small"),
    P("※ 1차 자료 「세제개편안 열흘, 서울 호가는 15억에서 갈렸다」와 분모가 다릅니다. "
      "두 자료의 수치를 한 문장에 섞지 말아 주십시오.", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="열흘간 서울 아파트 열에 아홉은 호가를 그대로 뒀다",
                        author="황인찬 (런투온라인)")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
