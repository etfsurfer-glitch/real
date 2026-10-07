# -*- coding: utf-8 -*-
"""세제개편안 전후 서울 호가 — 최초보고서(기준① 사건 전용, 8/17 기준·전후 2주).

기준① 사건만 쓴다. 지표 = 인상률 = 인상 ÷ (인상+인하). '값을 고친 매물 중 올린 쪽의 몫'.
대조군(발표와 무관한 앞선 2주)을 함께 두어, 평상시에도 있던 서열과 발표가 만든 격차를 가른다.

원자료: design/press/data/press_tax0817_*.csv  (measure_gijun1_0817.py, 박스에서 산출)
Run: python3 design/press/세제개편-호가/make_report_gijun1_0817.py
  → design/press/세제개편-호가/세제개편_전후_호가_최종보고서_기준1(20260817기준).pdf
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
OUT = HERE / "세제개편_전후_호가_최종보고서_기준1(20260817기준).pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="PB", italic="P", boldItalic="PB")

BLUE = colors.HexColor("#1268D3"); BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC"); INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80"); LINE = colors.HexColor("#C9D6E5")
BOXBG = colors.HexColor("#F4F8FD"); HOTBG = colors.HexColor("#FDF3F2")

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18, leading=24, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11, textColor=BLUE_DK, leading=16.5, spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="PB", fontSize=10.5, textColor=BLUE_DK, spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.6, leading=15.5, textColor=INK, spaceAfter=6),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.2, leading=17, textColor=INK, spaceAfter=7),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY, spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY, spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.2, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.4, textColor=INK, alignment=0),
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
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 0.6, ln),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


EV_O = {r["구분"]: r for r in read("press_tax0817_overall.csv")}
EV_B = {r["가격대"]: r for r in read("press_tax0817_band.csv")}
ZONE = read("press_tax0817_zone.csv")
GU = read("press_tax0817_gu.csv")

BANDS = ["10억 미만", "10~15억", "15~20억", "20~30억", "30억 이상"]
AREAS = ["전국", "서울", "강남3구", "서울(강남3구 외)"]
pc1 = lambda v: f"{float(v):.1f}%"                                        # noqa: E731


def pair(a, b):
    return f"{int(float(a)):,} → <b>{int(float(b)):,}</b>"


def ir(r):
    """'값 올린 집 비율' 셀 — 평상시(대조군)를 옅게 깔고, 발표 전 → 후."""
    return (f"<font size=7 color='#8B95A5'>평상시 {pc1(r['대조군_인상률'])}</font><br/>"
            f"{pc1(r['발표전_인상률'])} → <b>{pc1(r['발표후_인상률'])}</b>")


def sign(v, unit="p", bold=True):
    """인상률 변화 — 내려간 쪽(값 올리는 힘 약화)이 이 사안의 신호라 붉게."""
    if v in ("", None):
        return "—"
    v = float(v)
    t = f"{v:+.1f}{unit}".replace("-", "−")
    if abs(v) < 0.5:
        return f"<font color='#5A6B80'>{t}</font>"
    c = "#C0392B" if v < 0 else "#1F7A4D"
    return f"<font color='{c}'>{'<b>' if bold else ''}{t}{'</b>' if bold else ''}</font>"


def eok(r):
    return f"{r['중앙호가_억']}억" if r.get("중앙호가_억") not in ("", None) else "—"


TBL = [("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 2.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]
COLS = [26 * mm, 14 * mm, 28 * mm, 48 * mm, 16 * mm, 20 * mm]
HEAD = ["중간<br/>호가", "값 고친 집<br/>발표 전 → 후", "값 올린 집 비율<br/>평상시 · 발표 전 → 후",
        "발표 전<br/>대비", "평상시<br/>대비"]

story = []
A = story.append

b30, b10, b1015, b1520 = EV_B["30억 이상"], EV_B["10억 미만"], EV_B["10~15억"], EV_B["15~20억"]
gn3, seoul = EV_O["강남3구"], EV_O["서울"]
nodo = [r for r in ZONE if r["권역"] == "노도강"][0]

# ── 표지 ──────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제개편 2주, <b>15억 넘는 아파트부터 호가를 내렸다</b>", "title"))
A(P(f"이미 나와 있던 서울 아파트가 부르는 값(호가)을 바꿀 때, <b>올리기보다 내리는 쪽이 "
    f"많아졌다.</b> 특히 <b>15억이 갈림길</b>이다 — 30억대 아파트는 값을 고친 집 100채 중 "
    f"<b>{round(100 - float(b30['발표후_인상률']))}채가 값을 내렸고</b>, 반대로 15억 미만은 "
    f"평상시와 거의 다르지 않았다. 전국이 아니라 <b>서울, 그중에서도 비싼 아파트</b>에 몰린 "
    f"현상이다.", "sub"))
A(P("발표 2026. 8. 3. 18시　|　평상시(대조군) 7/6~7/19 · 발표 전 7/20~8/2 · 발표 후 8/4~8/17 (각 2주)"
    "　|　서울 아파트 매매　|　2026. 8. 17. 집계　|　자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 4))

A(P(
    "<b>무엇을 봤나.</b> 이미 시장에 나와 있던 서울 아파트가 <b>부르는 값(호가)을 바꿨을 때, "
    "올렸는지 내렸는지</b>를 셌다. 새로 나온 매물이나 거둬들인 매물은 뺐다 — ‘있던 집이 값을 "
    "고쳐 부른 것’만 본 것이다.<br/><br/>"
    "<b>지표 — ‘값 올린 집 비율’.</b> 값을 고친 집 100채 중 <b>올린 집이 몇 채인지</b>다. 이 비율이 "
    "30%라면, 값 고친 집 10채 중 3채는 올리고 7채는 내렸다는 뜻이다. <b>숫자가 낮아질수록 내리는 "
    "쪽으로 기운 시장</b>이다.<br/><br/>"
    "<b>왜 ‘평상시’와 견주나.</b> 발표 전 2주와 후 2주만 비교하면 함정이 있다. 비싼 아파트는 "
    "세제개편과 상관없이 <b>평소에도 값을 잘 안 올린다.</b> 그래서 발표와 아무 관계 없는 "
    "<b>그 이전 2주(7/6~7/19)를 ‘평상시 기준선’</b>으로 함께 놓았다. 발표 후 숫자가 이 평상시보다 "
    "얼마나 더 떨어졌는지가 <b>‘평상시 대비’</b>이고, 그것이 세제개편이 실제로 만든 변화다.<br/>"
    f"<font color='#5A6B80'>예) 30억 넘는 아파트는 평상시에도 값 올린 집이 100채 중 "
    f"{round(float(b30['대조군_인상률']))}채뿐이었다. 발표 후엔 {round(float(b30['발표후_인상률']))}채로 "
    f"줄었다 — 100채당 {abs(round(float(b30['대조군대비_변화p'])))}채 감소(−"
    f"{abs(round(float(b30['대조군대비_변화p']),1))}%p). 이 몫이 발표가 만든 변화다.</font><br/><br/>"
    "<font color='#5A6B80'>실거래가는 넣지 않았다. 8월에 맺은 계약은 신고(계약 후 30일 이내)가 "
    "아직 절반도 안 찼고, 싼 거래가 먼저 신고되는 쏠림까지 겹쳐 지금은 쓸 수 없다. 호가가 먼저 "
    "움직이고 실제 거래가 뒤따른다.</font>", "lead"))

# ── 1. 전체 ────────────────────────────────────────────────────────────────
_h1 = [P("1. 전체 — 서울에서, 비쌀수록 값 올리는 집이 크게 줄었다", "h")]
rows = [hdr(["구분"] + HEAD)]
for k in AREAS:
    r = EV_O[k]
    rows.append([P(f"<b>{k}</b>", "tdl"), P(eok(r), "td"),
                 P(pair(r["발표전_건수"], r["발표후_건수"]), "td"), P(ir(r), "td"),
                 P(sign(r["발표전후_변화p"]), "td"), P(sign(r["대조군대비_변화p"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND", (0, 2), (-1, 2), ROWALT),
                                   ("BACKGROUND", (0, 3), (-1, 3), HOTBG)]))
A(KeepTogether(_h1 + [t]))
A(P("‘발표 전 대비’는 발표 직전 2주와 견준 변화, ‘평상시 대비’는 세제개편과 무관한 앞선 2주와 "
    "견준 변화다(단위 %p). <b>붉은 숫자는 값 올리는 집이 줄었다</b>는 뜻이며, ‘평상시 대비’가 "
    "세제개편의 순수 효과에 가깝다.", "cap"))

# ── 2. 서울 가격대 ─────────────────────────────────────────────────────────
_h2 = [P("2. 서울 가격대별 — 갈림길은 15억이다", "h")]
rows = [hdr(["서울 가격대"] + HEAD)]
for b in BANDS:
    r = EV_B[b]
    rows.append([P(f"<b>{b}</b>", "tdl"), P(eok(r), "td"),
                 P(pair(r["발표전_건수"], r["발표후_건수"]), "td"), P(ir(r), "td"),
                 P(sign(r["발표전후_변화p"]), "td"), P(sign(r["대조군대비_변화p"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
st = list(TBL)
for i, b in enumerate(BANDS, start=1):
    if float(EV_B[b]["대조군대비_변화p"]) <= -10:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st.append(("LINEBELOW", (0, 2), (-1, 2), 1.1, BLUE))   # 10~15억 아래 = 15억 경계선
t.setStyle(TableStyle(st))
A(KeepTogether(_h2 + [t]))
A(P("파란 선 위(15억 미만)는 평상시와 거의 같고, 아래(15억 이상)는 값 올리는 집이 크게 줄었다. "
    "붉게 칠한 줄은 평상시보다 10%p 넘게 줄어든 구간이다.", "cap"))

A(box(
    "<b>15억을 경계로 시장이 둘로 갈렸다</b><br/>"
    f"· <b>15억 미만은 거의 그대로였다.</b> 10~15억은 평상시 대비 "
    f"{sign(b1015['대조군대비_변화p'], bold=False)}로 사실상 변화가 없고, 10억 미만도 "
    f"{sign(b10['대조군대비_변화p'], bold=False)}로 완만하다. 발표 뒤에도 값 고친 집의 절반 "
    f"안팎은 여전히 값을 올린다(10~15억 100채 중 {round(float(b1015['발표후_인상률']))}채).<br/>"
    f"· <b>15억을 넘으면 값 올리는 집이 확 줄었다.</b> 15~20억 "
    f"{sign(b1520['대조군대비_변화p'], bold=False)} · 20~30억 "
    f"{sign(EV_B['20~30억']['대조군대비_변화p'], bold=False)} · 30억 이상 "
    f"{sign(b30['대조군대비_변화p'], bold=False)}로 모두 두 자리 감소.<br/>"
    f"· <b>30억대는 값 고친 집 100채 중 {round(float(b30['발표후_인상률']))}채만 올리고 "
    f"{round(100 - float(b30['발표후_인상률']))}채가 내렸다.</b> 평상시(100채 중 "
    f"{round(float(b30['대조군_인상률']))}채 올림)의 3분의 1 수준이다."))

# ── 3. 지역 ────────────────────────────────────────────────────────────────
A(Spacer(1, 5))
_h3 = [P("3. 지역별 — 흔들린 건 비싼 동네다", "h"),
       P("부동산 기사에서 흔히 묶는 권역 단위다. 중간 호가가 비싼 동네일수록 값 올리는 집이 "
         "크게 줄었다.", "body")]
ZN = {"강남3구": "강남·서초·송파", "마용성": "마포·용산·성동", "양천·강서": "양천·강서",
      "노도강": "노원·도봉·강북", "그 외 서울": "나머지 14개 구"}
rows = [hdr(["권역"] + HEAD)]
for r in ZONE:
    rows.append([P(f"<b>{r['권역']}</b> <font size=7 color='#8B95A5'>{ZN.get(r['권역'],'')}</font>", "tdl"),
                 P(eok(r), "td"), P(pair(r["발표전_건수"], r["발표후_건수"]), "td"), P(ir(r), "td"),
                 P(sign(r["발표전후_변화p"]), "td"), P(sign(r["대조군대비_변화p"]), "td")])
t = Table(rows, colWidths=[32 * mm, 12 * mm, 28 * mm, 44 * mm, 16 * mm, 20 * mm], repeatRows=1)
st = list(TBL) + [("BACKGROUND", (0, 1), (-1, 1), HOTBG)]
for i in (3, 5):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h3 + [t]))
A(P(f"노원·도봉·강북은 발표 뒤에도 값 고친 집 100채 중 {round(float(nodo['발표후_인상률']))}채가 "
    f"올려, 서울에서 값 올리는 쪽이 가장 두텁다.", "cap"))

GU.sort(key=lambda r: float(r["대조군대비_변화p"] or 0))
A(P("자치구별 — 발표 후 값 고친 집이 150채 이상인 25곳, 평상시보다 많이 줄어든 순", "h2"))
rows = [hdr(["자치구"] + HEAD)]
for r in GU:
    thin = int(r["발표후_건수"]) < 150
    rows.append([P(f"<b>{r['자치구']}</b>" + (" <font color='#C9A227'>★</font>" if thin else ""), "tdl"),
                 P(eok(r), "td"), P(pair(r["발표전_건수"], r["발표후_건수"]), "td"), P(ir(r), "td"),
                 P(sign(r["발표전후_변화p"]), "td"), P(sign(r["대조군대비_변화p"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
st = list(TBL)
for i, r in enumerate(GU, start=1):
    if r["자치구"] in ("강남구", "서초구", "송파구"):
        st += [("BACKGROUND", (0, i), (-1, i), HOTBG),
               ("LINEBEFORE", (0, i), (0, i), 2.2, colors.HexColor("#C0392B"))]
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. <b>★</b>는 발표 후 값 고친 집이 150채에 못 미쳐 "
    "비율이 쉽게 흔들리는 구다 — 도봉·종로·금천·중구처럼 튀는 값(양쪽 끝)은 표본이 얕은 탓이니 "
    "그대로 믿기 어렵다. 반대로 송파·강남·서초는 표본이 두터워 믿을 만하다.", "cap"))

# ── 4. 결론 ────────────────────────────────────────────────────────────────
A(Spacer(1, 4))
GU_D = {r["자치구"]: r for r in GU}
mayong = [r for r in ZONE if r["권역"] == "마용성"][0]
A(KeepTogether([
    P("4. 한눈에 정리 — 고가는 식고, 저가는 버텼다", "h"),
    box(
        f"<b>① 15억이 갈림길이다.</b> 15억 미만(10~15억 평상시 대비 "
        f"{sign(b1015['대조군대비_변화p'], bold=False)}, 10억 미만 "
        f"{sign(b10['대조군대비_변화p'], bold=False)})은 평상시와 거의 같은데, 15억을 넘으면 "
        f"15~20억 {sign(b1520['대조군대비_변화p'], bold=False)} · 20~30억 "
        f"{sign(EV_B['20~30억']['대조군대비_변화p'], bold=False)} · 30억 이상 "
        f"{sign(b30['대조군대비_변화p'], bold=False)}로 모두 크게 줄었다.<br/><br/>"
        f"<b>② 비싼 아파트는 값 올리는 집이 확 줄었다.</b> 30억대는 값 고친 집 100채 중 "
        f"{round(float(b30['발표후_인상률']))}채만 올리고 {round(100 - float(b30['발표후_인상률']))}채가 "
        f"내렸다 — 평상시({round(float(b30['대조군_인상률']))}채)의 3분의 1이다. 강남3구는 100채 중 "
        f"{round(float(gn3['발표후_인상률']))}채까지 내려앉았다. "
        f"송파({sign(GU_D['송파구']['대조군대비_변화p'], bold=False)})·"
        f"강남({sign(GU_D['강남구']['대조군대비_변화p'], bold=False)})·"
        f"서초({sign(GU_D['서초구']['대조군대비_변화p'], bold=False)})가 이 흐름을 이끈다.<br/><br/>"
        f"<b>③ 저가는 버텼다.</b> 10~15억은 평상시와 사실상 같고, 발표 뒤에도 값 고친 집 100채 중 "
        f"{round(float(b1015['발표후_인상률']))}채가 값을 올린다. 노원·도봉·강북은 "
        f"{round(float(nodo['발표후_인상률']))}채로 서울에서 값 올리는 쪽이 가장 두텁다. 다만 10억 "
        f"미만이 조금 밀린 건({sign(b10['대조군대비_변화p'], bold=False)}), ‘싼 집이 값을 올렸다’기보다 "
        "관망 분위기가 옅게 번진 정도로 보는 게 맞다.<br/><br/>"
        f"<b>④ 전국이 아니라 서울·고가에 몰린 일이다.</b> 전국은 평상시 대비 "
        f"{sign(EV_O['전국']['대조군대비_변화p'], bold=False)}로 거의 안 움직였는데, 서울은 "
        f"{sign(seoul['대조군대비_변화p'], bold=False)}, 그중에서도 강남3구"
        f"({sign(gn3['대조군대비_변화p'], bold=False)})·마용성"
        f"({sign(mayong['대조군대비_변화p'], bold=False)}) 같은 비싼 동네에 집중됐다.<br/><br/>"
        "<font color='#5A6B80'>※ 이 수치는 ‘값을 고친 집 안에서 올린 쪽과 내린 쪽의 비율’이다. 값을 "
        "그대로 둔 집이나 실제로 얼마나 깎였는지(하락 폭)까지는 이 지표만으로 알 수 없다 — 호가가 "
        "먼저 움직이고 실제 거래가 뒤따른다는 시차를 함께 봐야 한다.</font>")]))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>황인찬</b>　|　런투온라인 대표　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-5942-8014　runtoonline@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="세제개편안 2주, 서울 아파트 호가는 어디로 — 기준① 사건(8/17 기준)",
                        author="황인찬 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
