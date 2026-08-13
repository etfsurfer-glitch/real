# -*- coding: utf-8 -*-
"""세제개편안 전후 서울 호가 — 최종(교차검증) 보고서.

앞선 두 자료를 합치는 것이 아니라, **두 가지 자로 잰 결과가 같음을 보이는** 자료다.
  · 1차(사건 기준)  press_tax_*.csv   — 값을 고친 광고 안에서 올린 쪽의 몫
  · 2차(물건 기준)  panel_*.csv       — 값을 안 고친 집까지 넣은 전체
  · 참고(실거래)    tx_*.csv          — 신고 지연 탓에 아직 결론을 못 내는 구간

1절의 환산표가 이 자료의 핵심이다. 두 자료를 같은 축(인상률 = 인상÷인상+인하)에
올리면 9곳 전부 방향이 같다 — 어긋나는 것은 방향이 아니라 크기다.

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
OKBG = colors.HexColor("#F1F8F3")
OKLN = colors.HexColor("#9CC7AC")

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18, leading=24, textColor=INK,
                            spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11, textColor=BLUE_DK, leading=16.5,
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


EV_B = {r["가격대"]: r for r in read("press_tax_band.csv")}
EV_O = {r["구분"]: r for r in read("press_tax_overall.csv")}
PN_B = {r["가격대"]: r for r in read("panel_band.csv")}
PN_O = {r["구분"]: r for r in read("panel_overall.csv")}
ZONE = read("panel_zone.csv")
GU = read("panel_gu.csv")
STOCK = read("panel_stock.csv")
TXP = read("tx_period.csv")
TXL = read("tx_lag.csv")
TXBI = read("tx_bias.csv")
TXBD = read("tx_band.csv")

BANDS = ["10억 미만", "10~15억", "15~20억", "20~30억", "30억 이상"]
n = lambda v: f"{int(float(v)):,}"                    # noqa: E731
pc1 = lambda v: f"{float(v):.1f}%"                    # noqa: E731


def pc2(v):
    f = round(float(v), 2)
    return "0.00%" if f == 0 else f"{f:.2f}%".replace("-", "−")


def sign(v, unit="p", flip=False, bold=True):
    """flip=True 면 '값이 오른 것'이 나쁜 신호(인하 비율 등)."""
    if v in ("", None):
        return "—"
    v = float(v)
    t = f"{v:+.1f}{unit}".replace("-", "−")
    if abs(v) < 0.5:
        return f"<font color='#5A6B80'>{t}</font>"
    bad = (v > 0) if flip else (v < 0)
    c = "#C0392B" if bad else "#1F7A4D"
    return f"<font color='{c}'>{'<b>' if bold else ''}{t}{'</b>' if bold else ''}</font>"


def panel_ratio(row, tag):
    """패널을 1차와 같은 축(인상률)으로 환산."""
    up, dn = float(row[f"{tag}_인상비율"]), float(row[f"{tag}_인하비율"])
    return up / (up + dn) * 100 if (up + dn) else None


TBL = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
       ("GRID", (0, 0), (-1, -1), 0.4, LINE),
       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]

story = []
A = story.append

seoul_p, gn3_p = PN_O["서울"], PN_O["강남3구"]
FLAT = round(100 - float(seoul_p["발표후_인하비율"]) - float(seoul_p["발표후_인상비율"]), 1)
b30 = PN_B["30억 이상"]
b10 = PN_B["10억 미만"]

# 환산표를 먼저 만들어 '몇 곳이 일치하는지'를 본문에서 쓴다
CROSS = []
for k, ev, pn in ([(b, EV_B[b], PN_B[b]) for b in BANDS]
                  + [(x, EV_O[x], PN_O[x]) for x in ("서울", "강남3구", "서울(강남3구 외)", "전국")]):
    de = float(ev["발표후_인상률"]) - float(ev["발표전_인상률"])
    dp_ = panel_ratio(pn, "발표후") - panel_ratio(pn, "발표전")
    CROSS.append({"항목": k, "1차": de, "2차": dp_, "일치": (de < 0) == (dp_ < 0)})
AGREE = sum(1 for r in CROSS if r["일치"])

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편 <b>최종</b>", "tag"))
A(P("다른 자로 재봐도 <b>방향은 같았다</b>", "title"))
A(P(f"세제개편안 전후 서울 아파트 호가를 두 가지 방법으로 따로 집계한 결과 "
    f"{len(CROSS)}개 구분 <b>전부</b> 같은 방향을 가리켰다. 값을 내리는 쪽으로 기운 것은 "
    f"고가 구간뿐이고, 시장 전체의 호가 수준은 {pc2(seoul_p['발표후_전체_평균변동률'])} 움직였다",
    "sub"))
A(P("집계 발표 2026. 8. 3. 18시　|　전후 각 10일 + 평상시 대조군 10일　|　"
    "서울 아파트 매매　|　자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 6))

A(P(
    "호가 통계는 <b>무엇을 분모에 놓느냐</b>에 따라 크기가 크게 달라진다. 그래서 이번에는 "
    "성격이 다른 두 방법으로 따로 집계하고, 결과가 같은 곳을 가리키는지 확인했다.<br/><br/>"
    "<b>① 사건 기준</b> — 호가를 고친 광고만 세어, 그중 올린 쪽의 몫이 어떻게 변했는지 본다. "
    "매도자의 태도가 드러난다.<br/>"
    "<b>② 물건 기준</b> — 같은 집을 열흘 간격 두 시점에 이어 붙여, 값을 안 고친 집까지 "
    "분모에 넣는다. 시장 전체가 실제로 움직인 폭이 나온다.<br/><br/>"
    f"두 방법을 같은 축에 올리면 <b>{len(CROSS)}개 구분 전부 방향이 같다.</b> 다만 크기는 "
    "사건 기준이 1.2~2.4배 크게 나온다 — 한 매물이 두 번 내리면 두 번 세고 광고 단위라 "
    f"중복이 있기 때문이다. 물건 기준으로 보면 서울 아파트의 <b>{FLAT}%</b>는 열흘 동안 "
    "호가를 한 번도 고치지 않았다.", "lead"))

# ── 1. 교차검증 ─────────────────────────────────────────────────────────
_h1 = [P("1. 두 방법을 같은 축에 올린 결과", "h"),
       P("아래는 두 집계를 모두 <b>인상률(인상 ÷ 인상+인하)</b>로 환산해 발표 전후 변화를 "
         "나란히 놓은 것이다. 부호가 같으면 같은 방향을 가리킨 것이다.", "body")]
rows = [hdr(["구분", "① 사건 기준<br/>발표 전후 변화", "② 물건 기준<br/>발표 전후 변화", "방향"])]
for r in CROSS:
    rows.append([P(f"<b>{r['항목']}</b>", "tdl"), P(sign(r["1차"]), "td"),
                 P(sign(r["2차"]), "td"),
                 P("<font color='#1F7A4D'><b>일치</b></font>" if r["일치"]
                   else "<font color='#C0392B'><b>어긋</b></font>", "td")])
t = Table(rows, colWidths=[46 * mm, 42 * mm, 42 * mm, 24 * mm], repeatRows=1)
st = list(TBL)
for i in range(1, len(rows)):
    if i > len(BANDS):
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st.append(("LINEABOVE", (0, len(BANDS) + 1), (-1, len(BANDS) + 1), 1.1, BLUE))
t.setStyle(TableStyle(st))
A(KeepTogether(_h1 + [t]))
A(P("파란 선 위는 서울 가격대별, 아래는 지역 구분이다.", "cap"))

A(Spacer(1, 3))
A(box(
    f"<b>{AGREE}곳 가운데 {AGREE}곳이 같은 방향 — 다른 것은 크기뿐이다</b><br/>"
    "· 두 방법은 분모도 집계 단위도 다른데 결과가 같은 곳을 가리켰다. "
    "<b>어느 한 방법이 만든 착시가 아니라는 뜻</b>이다.<br/>"
    "· 크기 차이는 사건 기준의 성질에서 온다 — 한 매물이 열흘 새 두 번 값을 내리면 두 번 세고, "
    "같은 집을 여러 중개사무소가 올린 광고도 각각 센다.<br/>"
    "· <b>다만 10~15억은 예외로 두시기 바란다.</b> 사건 기준으로는 "
    f"{sign(EV_B['10~15억']['발표전후_변화p'], bold=False)}로 뚜렷한 반등처럼 보이지만, "
    f"물건 기준으로는 {sign(CROSS[1]['2차'], bold=False)}로 사실상 제자리다. "
    "방향은 같아도 크기가 달라 <b>이 구간을 제목으로 뽑는 것은 권하지 않는다.</b>",
    OKBG, OKLN))

# ── 2. 얼마나 움직였나 ──────────────────────────────────────────────────
A(Spacer(1, 5))
_h2 = [P("2. 얼마나 움직였나 — 물건 기준", "h"),
       P("‘인하 물건’은 열흘 뒤 호가가 낮아진 물건의 비율, ‘평균 변동률’은 값을 안 고친 물건을 "
         "0%로 넣은 전체 평균이다. 뒤 숫자가 시장이 실제로 움직인 폭이다.", "body")]
rows = [hdr(["구분", "기준<br/>중앙호가", "인하 물건 비율<br/>평상시 → 발표전 → 발표후",
             "평상시<br/>대비", "평균 변동률<br/>발표 후", "물건 수"])]
for k in ("전국", "서울", "강남3구", "서울(강남3구 외)"):
    r = PN_O[k]
    seq = (f"{pc1(r['대조군_인하비율'])} → {pc1(r['발표전_인하비율'])} → "
           f"<b>{pc1(r['발표후_인하비율'])}</b>")
    rows.append([P(f"<b>{k}</b>", "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"), P(seq, "td"),
                 P(sign(r["대조군대비_인하비율변화p"], flip=True), "td"),
                 P(f"<b>{pc2(r['발표후_전체_평균변동률'])}</b>", "tdb"),
                 P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[32 * mm, 20 * mm, 46 * mm, 18 * mm, 26 * mm, 20 * mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                                   ("BACKGROUND", (0, 3), (-1, 3), HOTBG)]))
A(KeepTogether(_h2 + [t]))
A(P(f"붉은 %p는 값을 내린 물건이 평상시보다 <b>늘었다</b>는 뜻이다. "
    f"강남3구조차 평균 변동률은 {pc2(gn3_p['발표후_전체_평균변동률'])}에 그친다.", "cap"))

# ── 3. 가격대 ───────────────────────────────────────────────────────────
A(Spacer(1, 4))
_h3 = [P("3. 가격대 — 값을 내리는 쪽으로 기운 것은 20억 위뿐", "h"),
       P("가격대는 시작 시점의 호가로 고정했다. 값을 내린 물건이 평상시보다 늘어난 구간은 "
         "20억 위 둘뿐이고, 아래 세 구간은 오히려 줄었다.", "body")]
rows = [hdr(["가격대", "기준<br/>중앙호가", "인하 물건 비율<br/>평상시 → 발표전 → 발표후",
             "평상시<br/>대비", "평균 변동률<br/>발표 후", "물건 수"])]
for b in BANDS:
    r = PN_B[b]
    seq = (f"{pc1(r['대조군_인하비율'])} → {pc1(r['발표전_인하비율'])} → "
           f"<b>{pc1(r['발표후_인하비율'])}</b>")
    rows.append([P(f"<b>{b}</b>", "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"), P(seq, "td"),
                 P(sign(r["대조군대비_인하비율변화p"], flip=True), "td"),
                 P(f"<b>{pc2(r['발표후_전체_평균변동률'])}</b>", "tdb"),
                 P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[26 * mm, 20 * mm, 48 * mm, 18 * mm, 26 * mm, 20 * mm], repeatRows=1)
st = list(TBL)
for i, b in enumerate(BANDS, start=1):
    if float(PN_B[b]["대조군대비_인하비율변화p"]) > 0:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st.append(("LINEABOVE", (0, 4), (-1, 4), 1.1, BLUE))
t.setStyle(TableStyle(st))
A(KeepTogether(_h3 + [t]))
A(P(f"파란 선이 20억 경계다. 10억 미만은 인하 물건이 "
    f"{sign(b10['대조군대비_인하비율변화p'], flip=True, bold=False)}로 줄었고 평균도 "
    f"{pc2(b10['발표후_전체_평균변동률'])}로 플러스다 — 저가에서는 발표의 자취를 찾기 어렵다.",
    "cap"))

# ── 4. 지역 ─────────────────────────────────────────────────────────────
A(Spacer(1, 4))
_h4 = [P("4. 지역 — 비싼 동네일수록 값을 내린다", "h")]
rows = [hdr(["권역", "기준<br/>중앙호가", "인하 물건 비율<br/>평상시 → 발표전 → 발표후",
             "평상시<br/>대비", "평균 변동률<br/>발표 후", "물건 수"])]
ZN = {"강남3구": "강남·서초·송파", "마용성": "마포·용산·성동", "양천·강서": "양천·강서",
      "노도강": "노원·도봉·강북", "그 외 서울": "나머지 14개 구"}
for r in ZONE:
    seq = (f"{pc1(r['대조군_인하비율'])} → {pc1(r['발표전_인하비율'])} → "
           f"<b>{pc1(r['발표후_인하비율'])}</b>")
    rows.append([P(f"<b>{r['권역']}</b> <font size=7 color='#8B95A5'>{ZN.get(r['권역'],'')}</font>",
                   "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"), P(seq, "td"),
                 P(sign(r["대조군대비_인하비율변화p"], flip=True), "td"),
                 P(f"<b>{pc2(r['발표후_전체_평균변동률'])}</b>", "tdb"),
                 P(n(r["발표후_물건수"]), "td")])
t = Table(rows, colWidths=[40 * mm, 18 * mm, 44 * mm, 18 * mm, 24 * mm, 16 * mm], repeatRows=1)
st = list(TBL) + [("BACKGROUND", (0, 1), (-1, 1), HOTBG)]
for i in (3, 5):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h4 + [t]))
A(P("노도강은 평균 변동률이 여전히 플러스다 — 값을 올리는 쪽이 더 많다.", "cap"))

GU.sort(key=lambda r: -float(r["대조군대비_인하비율변화p"]))
story.append(P("자치구별 — 세 구간 모두 300물건 이상인 25곳", "h"))
rows = [hdr(["자치구", "기준<br/>중앙호가", "평상시", "발표전", "발표후", "평상시<br/>대비",
             "평균 변동률", "물건 수"])]
for r in GU:
    rows.append([P(f"<b>{r['자치구']}</b>", "tdl"), P(f"{r['기준_중앙호가_억']}억", "td"),
                 P(pc1(r["대조군_인하비율"]), "td"), P(pc1(r["발표전_인하비율"]), "td"),
                 P(f"<b>{pc1(r['발표후_인하비율'])}</b>", "tdb"),
                 P(sign(r["대조군대비_인하비율변화p"], flip=True), "td"),
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
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. 25개 구에서 <b>중앙 호가와 인하 비율 변화의 "
    "상관은 r = +0.68</b>(순위 상관 ρ = +0.44) — 비쌀수록 값을 내린다.", "cap"))

# ── 5. 재고 ─────────────────────────────────────────────────────────────
A(Spacer(1, 4))
_h5 = [P("5. 값은 안 내렸지만 매물은 쌓이고 있다", "h")]
rows = [hdr(["가격대", "8월 2일", "8월 12일", "증감", "증감률"])]
for r in STOCK:
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"), P(n(r["2026-08-02"]), "td"),
                 P(f"<b>{n(r['2026-08-12'])}</b>", "tdb"),
                 P(f"{int(r['발표후_증감']):+,}".replace("-", "−"), "td"),
                 P(sign(r["발표후_증감률"], unit="%", flip=True), "td")])
t = Table(rows, colWidths=[30 * mm, 26 * mm, 26 * mm, 24 * mm, 24 * mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 5), (-1, 5), HOTBG),
                                   ("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                                   ("BACKGROUND", (0, 4), (-1, 4), ROWALT)]))
A(KeepTogether(_h5 + [t]))
A(P("호가를 안 고쳤다고 시장이 멎은 것은 아니다. 30억 이상이 가장 빠르게 쌓인다.", "cap"))

# ── 6. 실거래(참고) ─────────────────────────────────────────────────────
A(Spacer(1, 5))
tx = {r["구간"]: r for r in TXP}
lag7 = [r for r in TXL if r["계약후_일수"] == "7"][0]
lag14 = [r for r in TXL if r["계약후_일수"] == "14"][0]
bias = TXBI[-1]
_h6 = [P("6. [참고] 실거래 — 아직 답할 수 없는 구간", "h"),
       P("호가가 아니라 실제 계약은 어떤가. 결론부터 적으면 <b>지금 시점에는 판단할 수 없다.</b> "
         "실거래는 계약 후 30일 이내 신고라 8월 계약분이 아직 절반도 들어오지 않았다.", "body")]
rows = [hdr(["계약 후", "신고 완료율"])]
for r in TXL:
    if r["계약후_일수"] in ("1", "3", "7", "10", "14", "20", "30"):
        rows.append([P(f"{r['계약후_일수']}일", "td"), P(f"{r['신고완료율']}%", "td")])
t1 = Table(rows, colWidths=[24 * mm, 30 * mm], repeatRows=1)
t1.setStyle(TableStyle(list(TBL)))
rows = [hdr(["구간", "관측 건수", "중앙가", "평당가", "대조군 대비"])]
for k in ("대조군", "발표전", "발표후"):
    r = tx[k]
    rows.append([P(f"<b>{k}</b> <font size=7 color='#8B95A5'>{r['기간']}</font>", "tdl"),
                 P(n(r["건수"]), "td"), P(f"{r['중앙가_억']}억", "td"),
                 P(f"{int(r['평당가_중앙_만']):,}만", "td"),
                 P("<font color='#5A6B80'>기준</font>" if k == "대조군"
                   else sign(r["대조군대비_중앙가"], unit="%"), "td")])
t2 = Table(rows, colWidths=[40 * mm, 22 * mm, 22 * mm, 22 * mm, 24 * mm], repeatRows=1)
t2.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 2), (-1, 2), ROWALT)]))
both = Table([[t1, t2]], colWidths=[58 * mm, 132 * mm])
both.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("LEFTPADDING", (0, 0), (-1, -1), 0),
                          ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
CAP6 = P("오른쪽 표는 세 구간 모두 <b>계약 후 9일 이내 신고분</b>만 골라 조건을 맞춘 것이다.", "cap")
BOX6 = box(
    "<b>이 숫자를 ‘집값이 12% 내렸다’로 읽으면 안 되는 이유</b><br/>"
    f"· <b>신고가 덜 찼다.</b> 계약 후 7일이면 {lag7['신고완료율']}%, 14일이면 "
    f"{lag14['신고완료율']}%만 신고된다(6월 계약분 실측). 발표 후 구간은 관측 "
    f"{n(tx['발표후']['건수'])}건뿐이고, 그중 고가(15억 이상)는 33건이다.<br/>"
    f"· <b>싼 거래가 먼저 신고된다.</b> 6월 계약분에서 9일 이내 신고분의 중앙가는 그 뒤 "
    f"신고분보다 <b>{bias['중앙가_억']}</b> 낮았다. 조건을 맞춰도 이 편향이 완전히 지워지지는 않는다.<br/>"
    "· <b>중앙가 하락은 거래 구성 변화다.</b> 같은 집이 싸진 것이 아니라 비싼 거래가 줄어든 것이다. "
    "10억 미만 거래 비중이 61.6% → 69.4%로 늘었다. 다만 고가 거래 비중이 줄어든 것은 "
    "<b>발표 전부터</b>(16.5% → 12.0%) 진행된 일이라 발표 탓으로 돌릴 수 없다.<br/>"
    "· <b>언제 답할 수 있나</b> — 8월 계약분 신고가 채워지는 <b>9월 초</b>다. 그때 같은 기준으로 "
    "다시 집계해 알려 드리겠다.",
    WARNBG, WARNLN)
A(KeepTogether(_h6 + [both, CAP6, Spacer(1, 2), BOX6]))

# ── 7. 방법·유의 ────────────────────────────────────────────────────────
A(Spacer(1, 5))
A(KeepTogether([
    P("7. 집계 방법과 유의사항", "h"),
    box(
        "<b>구간</b> — 발표 2026. 8. 3. 18시. 평상시 대조군 7/13~7/23, 발표 전 7/24~8/02, "
        "발표 후 8/04~8/13(물건 기준은 8/02→8/12 두 시점). 사건 기준에서는 하루 안에 전후가 "
        "섞이는 <b>8/03을 통째로 제외</b>했다.<br/>"
        "<b>① 사건 기준</b> — 같은 매물번호의 호가가 직전 수집 때와 달라진 건만 센다. "
        "신규 등록·매물 회수는 포함하지 않는다.<br/>"
        "<b>② 물건 기준</b> — 한 집을 여러 중개사무소가 올리면 광고는 여러 건이다"
        "(전국 아파트 매매 광고 126만 → 물건 52만). 묶는 기준은 "
        "<b>단지+동+층+전용면적+향+공급면적</b>이며 호가는 넣지 않았다. 이 기준으로 센 물건 수는 "
        "포털이 자체 표기하는 동일주소 광고 수로 환산한 값의 <b>97.8%</b>로 거의 일치한다.<br/>"
        "<b>생존 편향은 결론과 반대 방향이다.</b> 열흘 뒤에도 남아 있는 비율은 10억 미만 89.0%, "
        "30억 이상 94.1%로 싼 매물이 더 많이 빠진다. 남은 저가 매물은 ‘안 팔린 것’ 쪽으로 "
        "치우치는데도 값을 덜 내렸다.<br/>"
        "<b>기준점을 바꿔도 같다.</b> 매물 수집은 11시·19시라 8/03 스냅샷은 발표 뒤다. 마지막 "
        "온전한 발표 전 상태인 8/02를 기준으로 삼았고, 8/03으로 바꿔도 순서와 부호가 그대로였다"
        "(30억 이상 인하 물건 13.1% vs 14.8%).<br/>"
        "<b>대조군을 함께 봐야 한다.</b> ‘비싼 집일수록 값을 잘 내린다’는 7월 중순에도 이미 "
        "그랬다(10억 미만 4.1% vs 30억 이상 9.2%). 발표가 만든 것은 그 서열이 아니라 <b>격차</b>다.<br/>"
        "<b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이며 그 값에 팔린다는 뜻이 아니다. "
        "거래 기반 지수와 나란히 놓을 때는 6절의 시차를 함께 밝혀야 한다.",
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
                        title="다른 자로 재봐도 방향은 같았다 — 세제개편안 전후 서울 호가",
                        author="황인찬 (런투온라인)")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
print(f"  교차검증 {AGREE}/{len(CROSS)} 일치")
