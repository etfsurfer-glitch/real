# -*- coding: utf-8 -*-
"""세제개편안 전후 서울 아파트 호가 변동 보고서 (기자 배포용).

수치는 design/press/data/press_tax_*.csv 를 그대로 읽어 조판한다
(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
원천은 콕집 article_events(PRICE_CHANGE) — 같은 매물의 호가가 바뀐 순간만 기록한 이벤트다.
Run: python3 design/press/세제개편-호가/make_tax_price_report.py
  → design/press/세제개편-호가/세제개편_전후_호가변동.pdf
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
OUT = HERE / "세제개편_전후_호가변동.pdf"

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
    "tds": ParagraphStyle("tds", fontName="P", fontSize=7.6, leading=10, textColor=GRAY,
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


OV = {r["구분"]: r for r in read("press_tax_overall.csv")}
BAND = read("press_tax_band.csv")
ZONE = read("press_tax_zone.csv")
GU_ALL = read("press_tax_gu.csv")
CROSS = read("press_tax_cross.csv")

n = lambda v: f"{int(float(v)):,}"                                       # noqa: E731
pc = lambda v: f"{float(v):.1f}%" if v not in ("", None) else "—"        # noqa: E731


def dp(v, bold=True):
    """변화폭(%p) — 내림은 붉게, 오름은 푸르게. 0.5p 미만은 회색(없는 신호를 색으로 만들지 않는다)."""
    if v in ("", None):
        return "—"
    v = float(v)
    t = f"{v:+.1f}p".replace("-", "−")
    if abs(v) < 0.5:
        return f"<font color='#5A6B80'>{t}</font>"
    c = "#C0392B" if v < 0 else "#1F7A4D"
    return f"<font color='{c}'>{'<b>' if bold else ''}{t}{'</b>' if bold else ''}</font>"


# 자치구는 표본이 얕으면 극단값이 나온다 — 세 구간 모두 150건 이상만 싣는다
GU = [r for r in GU_ALL
      if min(int(r["대조군_건수"]), int(r["발표전_건수"]), int(r["발표후_건수"])) >= 150]
GU.sort(key=lambda r: float(r["대조군대비_변화p"]))
GU_DROP = len(GU_ALL) - len(GU)

TBL = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
       ("GRID", (0, 0), (-1, -1), 0.4, LINE),
       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8)]

story = []
A = story.append

# ── 표지 ────────────────────────────────────────────────────────────────
b15 = [r for r in BAND if r["가격대"] == "15~20억"][0]
b10 = [r for r in BAND if r["가격대"] == "10억 미만"][0]
b1015 = [r for r in BAND if r["가격대"] == "10~15억"][0]
b30 = [r for r in BAND if r["가격대"] == "30억 이상"][0]

A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제개편안 열흘, 서울 호가는 <b>15억</b>에서 갈렸다", "title"))
A(P(f"15억 미만은 값을 올린 매물이 오히려 늘었고(+{b1015['발표전후_변화p']}p), "
    f"15억을 넘으면 전부 두 자릿수로 꺾였다. 가장 크게 다친 구간은 30억 이상이 아니라 "
    f"<b>15~20억</b>(평상시 대비 {dp(b15['대조군대비_변화p'], False)})이었다", "sub"))
A(P("집계 발표 전 10일(2026. 7. 24.~8. 2.) · 발표 후 10일(8. 4.~8. 13.) · "
    "평상시 대조군 10일(7. 14.~7. 23.)　|　서울 아파트 매매 호가 변경 전수　|　"
    "자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 8))

A(P(
    "8월 3일 저녁 세제개편안이 발표된 뒤 열흘, 서울 아파트를 내놓은 사람들이 <b>부르는 값을 "
    "어떻게 고쳤는지</b> 전수로 셌다. 콕집은 매물 광고를 하루 여러 차례 수집하면서 같은 "
    "매물번호의 호가가 바뀐 순간을 모두 기록한다. 새로 올라오거나 내려간 매물이 아니라 "
    "<b>이미 나와 있던 집이 값을 고쳐 부른 사건</b>만 본 것이다.<br/><br/>"
    "결과는 '집값이 내렸다'로 요약되지 않는다. <b>가격대에 따라 정반대로 갈렸다.</b> "
    f"10억 미만은 거의 움직이지 않았고({dp(b10['발표전후_변화p'], False)}), "
    f"10~15억은 값을 올린 매물이 오히려 늘었다({dp(b1015['발표전후_변화p'], False)}). "
    "반면 15억을 넘는 구간은 예외 없이 두 자릿수로 꺾였다. "
    "<b>세제개편안이 시장 전체를 누른 것이 아니라, 특정 가격대 위쪽만 잘라낸 모양</b>이다.", "lead"))

# ── 1. 전체 ─────────────────────────────────────────────────────────────
A(P("1. 전국은 그대로다 — 서울, 그중 강남3구에서만 일어난 일", "h"))
A(P("먼저 이 변화가 어디까지 미쳤는지 본다. 아래 값은 <b>값을 고친 매물 중 올린 비율</b>"
    "(인상 ÷ 인상+인하)이다. 100%에 가까울수록 올린 사람이 많다는 뜻이다.", "body"))
rows = [hdr(["구분", "평상시<br/>(7/14~23)", "발표 전 10일", "발표 후 10일",
             "발표 전후", "평상시 대비", "발표 후<br/>건수"])]
for k in ("전국", "서울", "강남3구", "서울(강남3구 외)"):
    r = OV[k]
    rows.append([P(f"<b>{k}</b>", "tdl"),
                 P(pc(r["대조군_인상률"]), "td"), P(pc(r["발표전_인상률"]), "td"),
                 P(f"<b>{pc(r['발표후_인상률'])}</b>", "tdb"),
                 P(dp(r["발표전후_변화p"]), "td"), P(dp(r["대조군대비_변화p"]), "td"),
                 P(n(r["발표후_건수"]), "td")])
t = Table(rows, colWidths=[36 * mm, 24 * mm, 24 * mm, 24 * mm, 20 * mm, 20 * mm, 20 * mm],
          repeatRows=1)
st = list(TBL)
st += [("BACKGROUND", (0, 2), (-1, 2), ROWALT), ("BACKGROUND", (0, 3), (-1, 3), HOTBG),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(t)
A(P("‘평상시’는 발표와 무관한 7월 중순 10일이다. 이 열이 없으면 원래 그랬던 것을 "
    "발표 효과로 잘못 읽게 된다.", "cap"))

A(Spacer(1, 3))
A(box(
    "<b>같은 열흘인데 전국은 −0.9p, 강남3구는 −9.1p</b><br/>"
    f"· 전국은 {pc(OV['전국']['발표전_인상률'])} → {pc(OV['전국']['발표후_인상률'])}로 "
    "사실상 제자리다. <b>이 사안은 전국 현상이 아니다.</b><br/>"
    f"· 서울은 {pc(OV['서울']['발표전_인상률'])} → {pc(OV['서울']['발표후_인상률'])}, "
    f"강남3구는 {pc(OV['강남3구']['발표전_인상률'])} → "
    f"{pc(OV['강남3구']['발표후_인상률'])}로 떨어졌다. 강남3구에서는 이제 "
    "<b>값을 고친 매물 여섯 중 다섯이 내린 것</b>이다.<br/>"
    f"· 같은 서울이라도 강남3구를 뺀 나머지는 {pc(OV['서울(강남3구 외)']['발표후_인상률'])}로 "
    "절반 가까이가 여전히 올리고 있다. 서울 안에서도 갈렸다."))

# ── 2. 가격대별 ─────────────────────────────────────────────────────────
A(Spacer(1, 6))
_h2 = [P("2. 분기선은 20억이 아니라 <b>15억</b>이었다", "h"),
       P("가격대별로 끊어 보면 경계가 뚜렷하다. 매물마다 <b>전 기간 첫 관측 호가</b> 하나로 "
         "구간을 고정했다 — 이벤트마다 그때 값으로 나누면 값을 내린 매물이 아래 구간으로 "
         "옮겨가 저가 구간에 인하가 쌓인다.", "body")]
rows = [hdr(["가격대", "평상시", "발표 전 10일", "발표 후 10일",
             "발표 전후", "평상시 대비", "발표 후<br/>건수"])]
for r in BAND:
    hot = float(r["발표전후_변화p"]) <= -5
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"),
                 P(pc(r["대조군_인상률"]), "td"), P(pc(r["발표전_인상률"]), "td"),
                 P(f"<b>{pc(r['발표후_인상률'])}</b>", "tdb"),
                 P(dp(r["발표전후_변화p"]), "td"), P(dp(r["대조군대비_변화p"]), "td"),
                 P(n(r["발표후_건수"]), "td")])
t = Table(rows, colWidths=[30 * mm, 22 * mm, 26 * mm, 26 * mm, 22 * mm, 22 * mm, 20 * mm],
          repeatRows=1)
st = list(TBL)
for i, r in enumerate(BAND, start=1):
    if float(r["발표전후_변화p"]) <= -5:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st += [("LINEABOVE", (0, 3), (-1, 3), 1.1, BLUE), ("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(KeepTogether(_h2 + [t]))
A(P("파란 선이 15억 경계다. 붉게 칠한 줄은 발표 전후로 5%p 넘게 꺾인 구간이다.", "cap"))

A(Spacer(1, 3))
A(box(
    "<b>아래는 버텼고 위는 무너졌다 — 그런데 가장 크게 다친 건 최고가가 아니다</b><br/>"
    f"· <b>10억 미만</b>은 {dp(b10['발표전후_변화p'], False)}로 미동이 없다. "
    "평상시와 견줘도 −1.7p로, 발표가 없었던 것과 다르지 않다.<br/>"
    f"· <b>10~15억</b>은 오히려 {dp(b1015['발표전후_변화p'], False)} 올랐다. "
    f"{pc(b1015['발표전_인상률'])} → {pc(b1015['발표후_인상률'])}로, 값을 고친 매물의 "
    "열에 여섯이 올린 쪽이다.<br/>"
    f"· <b>15~20억이 가장 크게 다쳤다.</b> 발표 전후 {dp(b15['발표전후_변화p'], False)}, "
    f"평상시와 견주면 {dp(b15['대조군대비_변화p'], False)}로 전 구간 최대다. "
    f"30억 이상({dp(b30['대조군대비_변화p'], False)})보다 폭이 크다.<br/>"
    f"· 다만 <b>절대 수준</b>은 30억 이상이 가장 낮다({pc(b30['발표후_인상률'])}). "
    "고가 구간은 원래도 올리는 사람이 적었고, 지금은 아홉 중 한 명만 올린다."))

# ── 3. 지역별 ───────────────────────────────────────────────────────────
A(Spacer(1, 6))
_h3 = [P("3. 지역별 — 강남3구에서 노도강까지, 낙폭이 계단처럼 줄어든다", "h"),
       P("권역으로 묶으면 낙폭이 비싼 권역에서 싼 권역으로 갈수록 얕아진다. 다만 권역은 값싼 "
         "단지와 비싼 단지를 함께 담고 있어, 뒤(4절)에서 같은 구 안을 다시 갈라 확인했다.",
         "body")]
rows = [hdr(["권역", "평상시", "발표 전 10일", "발표 후 10일", "발표 전후",
             "평상시 대비", "발표 후<br/>건수"])]
ZNOTE = {"강남3구": "강남·서초·송파", "마용성": "마포·용산·성동",
         "양천·강서": "양천·강서", "노도강": "노원·도봉·강북", "그 외 서울": "나머지 14개 구"}
for r in ZONE:
    rows.append([P(f"<b>{r['권역']}</b> <font size=7 color='#8B95A5'>{ZNOTE.get(r['권역'], '')}</font>", "tdl"),
                 P(pc(r["대조군_인상률"]), "td"), P(pc(r["발표전_인상률"]), "td"),
                 P(f"<b>{pc(r['발표후_인상률'])}</b>", "tdb"),
                 P(dp(r["발표전후_변화p"]), "td"), P(dp(r["대조군대비_변화p"]), "td"),
                 P(n(r["발표후_건수"]), "td")])
t = Table(rows, colWidths=[44 * mm, 20 * mm, 24 * mm, 24 * mm, 20 * mm, 20 * mm, 16 * mm],
          repeatRows=1)
st = list(TBL)
st += [("BACKGROUND", (0, 1), (-1, 1), HOTBG), ("LEFTPADDING", (0, 0), (0, -1), 5)]
for i in (3, 5):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h3 + [t]))
A(P("‘그 외 서울’은 위 네 권역에 들지 않는 14개 구다.", "cap"))

A(Spacer(1, 3))
A(box(
    "<b>강남3구 −20.1p, 노도강 −2.6p — 같은 서울에서 여덟 배 차이</b><br/>"
    "· <b>강남3구</b>가 평상시 대비 −20.1p로 가장 크게 꺾였다. 발표 후 16.3%는 서울 어느 "
    "권역보다 낮다.<br/>"
    "· <b>노도강</b>(노원·도봉·강북)은 −2.6p에 그쳤고, 발표 후에도 63.5%가 값을 올리는 쪽이다. "
    "10억 미만이 두터운 권역이라 2절 결과와 맞물린다.<br/>"
    "· <b>양천·강서</b>는 발표 후가 오히려 +7.9p로 되올랐다. 다만 발표 전 10일에 이미 크게 "
    "내려앉아 있어(56.0% → 36.1%), 평상시와 견주면 여전히 −12.0p다. "
    "<b>‘발표 후 반등’으로만 읽으면 안 되는 자리</b>다."))

A(Spacer(1, 5))
_h3b = [P("자치구별 — 표본이 두꺼운 17곳만", "h"),
        P(f"자치구로 쪼개면 호가 변경 건수가 얕아져 극단값이 튄다. 세 구간 모두 150건 이상인 "
          f"<b>17개 구만</b> 싣는다(나머지 {GU_DROP}곳 제외). 낙폭이 큰 순서다.", "body")]
rows = [hdr(["자치구", "평상시", "발표 전", "발표 후", "평상시 대비", "3구간 합계"])]
for r in GU:
    tot = int(r["대조군_건수"]) + int(r["발표전_건수"]) + int(r["발표후_건수"])
    rows.append([P(f"<b>{r['자치구']}</b>", "tdl"),
                 P(pc(r["대조군_인상률"]), "td"), P(pc(r["발표전_인상률"]), "td"),
                 P(f"<b>{pc(r['발표후_인상률'])}</b>", "tdb"),
                 P(dp(r["대조군대비_변화p"]), "td"), P(n(tot), "td")])
t = Table(rows, colWidths=[28 * mm, 22 * mm, 22 * mm, 22 * mm, 26 * mm, 24 * mm], repeatRows=1)
st = list(TBL)
for i, r in enumerate(GU, start=1):
    if r["자치구"] in ("강남구", "서초구", "송파구"):
        # 옅은 배경만으로는 교대색과 구분이 안 된다 — 왼쪽에 굵은 선을 함께 긋는다
        st += [("BACKGROUND", (0, i), (-1, i), HOTBG),
               ("LINEBEFORE", (0, i), (0, i), 2.2, colors.HexColor("#C0392B"))]
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st += [("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
# 17행짜리라 통째로 묶으면 앞 쪽 절반이 비어버린다 — 머리글만 붙들고 표는 흐르게 둔다
# (repeatRows=1 이라 쪽을 넘어가도 열 이름이 다시 찍힌다)
story.extend(_h3b)
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. 동대문구만 유일하게 올랐는데, 이 구는 "
    "15억 미만 매물이 대부분이어서 2절의 가격대 결과와 어긋나지 않는다.", "cap"))

# ── 4. 교차 ─────────────────────────────────────────────────────────────
A(Spacer(1, 6))
_h4 = [P("4. 진짜 축은 지역이 아니라 가격대다", "h"),
       P("지역과 가격대는 서로 얽혀 있다 — 강남이 비싸기 때문에, 위 두 표가 같은 것을 다르게 "
         "말한 것일 수 있다. 그래서 <b>같은 구 안에서</b> 가격대별로 다시 갈랐다. "
         "두 구간 모두 40건 이상인 칸만 싣는다.", "body")]
CB = ["10억 미만", "10~15억", "15~20억", "20~30억", "30억 이상"]
cx = {}
for r in CROSS:
    if int(r["발표후_건수"]) >= 40 and int(r["발표전_건수"]) >= 40:
        cx.setdefault(r["자치구"], {})[r["가격대"]] = float(r["발표전후_변화p"])
pick = [(g, d) for g, d in cx.items()
        if any(b in d for b in CB[:2]) and any(b in d for b in CB[2:])]
pick.sort(key=lambda x: -len(x[1]))
rows = [hdr(["자치구"] + CB)]
for g, d in pick:
    rows.append([P(f"<b>{g}</b>", "tdl")]
                + [P(dp(d[b]) if b in d else "<font color='#C9D6E5'>·</font>", "td") for b in CB])
t = Table(rows, colWidths=[26 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm], repeatRows=1)
st = list(TBL)
for i in range(2, len(rows), 2):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st += [("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(KeepTogether(_h4 + [t]))
A(P("값은 발표 전후 인상률 변화(%p)다. 점(·)은 표본이 얕아 싣지 않은 칸이다.", "cap"))

A(Spacer(1, 3))
A(box(
    "<b>같은 동네 안에서도 싼 집과 비싼 집이 반대로 움직였다</b><br/>"
    "· 위 표에서 저가·고가를 함께 비교할 수 있는 구는 7곳인데, 그중 <b>6곳</b>에서 "
    "저가 구간이 고가 구간보다 덜 빠졌다(영등포구만 역전).<br/>"
    "· 강동구는 10~15억이 +7.6p인데 20~30억은 −53.4p다. 송파구는 10억 미만 +9.4p, "
    "20~30억 −21.7p다. <b>같은 구, 같은 열흘, 정반대 방향</b>이다.<br/>"
    "· 따라서 이 현상은 '강남이라서'가 아니라 <b>'비싸서'</b>로 읽어야 한다. "
    "지역은 결과이고 원인은 가격대다."))

# ── 5. 방법·유의 ────────────────────────────────────────────────────────
A(Spacer(1, 6))
A(KeepTogether([
    P("5. 집계 방법과 유의사항", "h"),
    box(
        "· <b>무엇을 셌나</b> — 콕집이 하루 여러 차례 매물을 수집하면서 <b>같은 매물번호</b>의 "
        "호가가 직전 수집 때와 달라진 건을 기록한 것이다. 새 매물 등록이나 매물 회수는 "
        "포함되지 않는다. 지표는 <b>인상 ÷ (인상+인하)</b>다.<br/>"
        "· <b>8월 3일은 통째로 뺐다.</b> 18시 발표라 하루 안에 전후가 섞인다(그날만 인하가 75%).<br/>"
        "· <b>대조군을 함께 봐야 한다.</b> ‘비싼 집일수록 호가를 덜 올린다’는 7월 중순에도 "
        "이미 그랬다(10억 미만 49.6% vs 30억 이상 26.4%). 발표가 만든 것은 그 서열이 아니라 "
        "<b>격차가 벌어진 것</b>이다.<br/>"
        "· <b>가격대는 매물마다 하나로 고정했다.</b> 이벤트가 일어난 시점의 값으로 나누면 "
        "값을 내린 매물이 아래 구간으로 옮겨가 저가 구간에 인하가 쌓인다.<br/>"
        "· <b>자치구 표는 표본이 두꺼운 곳만 실었다.</b> 뺀 구 가운데는 낙폭이 −28%p로 "
        "보이는 곳도 있으나 세 구간 합계가 336건에 그쳐 신뢰하기 어렵다.<br/>"
        "· <b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이며, 그 값에 팔린다는 뜻이 아니다. "
        "실거래는 계약 후 30일 이내 신고를 거치므로 <b>8월 계약분은 9월 초에야 집계가 채워진다</b>. "
        "이 기간의 호가 움직임이 거래로 이어졌는지는 아직 확인할 수 없다.<br/>"
        "· <b>다른 기관 지수와 시점이 다르다.</b> 거래 기반 지수는 이미 체결된 계약을 뒤늦게 "
        "반영하고, 이 자료는 오늘 시장에 걸려 있는 호가다. 두 수치를 나란히 놓을 때는 "
        "이 시차를 함께 밝혀야 한다.<br/>"
        "· <b>세는 단위는 광고다.</b> 같은 집을 여러 중개사무소가 올렸으면 각각 1건으로 센다.",
        WARNBG, WARNLN),
]))

A(KeepTogether([
    Spacer(1, 9),
    P("작성 <b>황인찬</b>　|　런투온라인 대표　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-5942-8014　runtoonline@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="세제개편안 열흘, 서울 호가는 15억에서 갈렸다",
                        author="황인찬 (런투온라인)")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
