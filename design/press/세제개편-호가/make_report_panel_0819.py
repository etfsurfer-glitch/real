# -*- coding: utf-8 -*-
"""세제개편안 전후 서울 아파트 호가 — '얼마나 내렸나'(금액) 보고서. 8/19 기준.
   평상시=발표 전 한 달(7/03→8/02), 발표후=8/02→8/19. 동일 물건 패널.
   ※ 단독 배포용. '기준1/기준2' 등 방법론 명칭 언급 안 함.
원자료: design/press/data/panel0819_*.csv
Run: python3 design/press/세제개편-호가/make_report_panel_0819.py
"""
import csv
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
OUT = HERE / "세제개편_전후_서울아파트_호가하락(20260819기준).pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

BLUE = colors.HexColor("#1268D3"); BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC"); INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80"); LINE = colors.HexColor("#C9D6E5")
BOXBG = colors.HexColor("#F4F8FD"); HOTBG = colors.HexColor("#FDF3F2")
RED = "#C0392B"; GREEN = "#1F7A4D"

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18, leading=24, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11, textColor=BLUE_DK, leading=16.5, spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="PB", fontSize=10.5, textColor=BLUE_DK, spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.6, leading=15.5, textColor=INK, spaceAfter=6),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.2, leading=17, textColor=INK, spaceAfter=7),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY, spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.2, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.4, textColor=INK, alignment=0),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY, spaceAfter=3),
}
def P(t, s="body"): return Paragraph(t, ss[s])
def read(fn):
    with open(DATA / fn, encoding="utf-8") as f:
        return list(csv.DictReader(f))
def hdr(cs): return [P(c, "th") for c in cs]
def box(html, bg=BOXBG, ln=LINE):
    t = Table([[P(html, "boxb")]], colWidths=[168 * mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,ln),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    return t

EV_O = {r["구분"]: r for r in read("panel0819_overall.csv")}
EV_B = {r["가격대"]: r for r in read("panel0819_band.csv")}
TIER = read("panel0819_tier.csv")
GU = read("panel0819_gu.csv")
STOCK = read("panel0819_stock.csv")
BANDS = ["10억 미만", "10~15억", "15~20억", "20~30억", "30억 이상"]
AREAS = ["전국", "서울", "강남3구", "서울(강남3구 외)"]

def eok(r): return f"{r['기준_중앙호가_억']}억" if r.get("기준_중앙호가_억") not in ("", None) else "—"
def n(v): return f"{int(float(v)):,}"
def pair(a, b): return f"{int(float(a)):,} → <b>{int(float(b)):,}</b>"

def man(v, bold=False):
    """만원 단위 변동액 — 하락(음수)은 붉게. 1만↑은 '억'으로."""
    if v in ("", None): return "—"
    v = int(float(v))
    a = abs(v)
    txt = (f"{a/10000:.2f}억" if a >= 10000 else f"{a:,}만")
    sign = "−" if v < 0 else ("+" if v > 0 else "")
    c = "#5A6B80" if a < 40 else (RED if v < 0 else GREEN)   # 40만 미만은 사실상 무변동→중립
    b0, b1 = ("<b>", "</b>") if bold else ("", "")
    return f"<font color='{c}'>{b0}{sign}{txt}{b1}</font>"

def dpair(bef, aft):
    return f"{man(bef)} → {man(aft, bold=True)}"

def pct(v, bold=True):
    if v in ("", None): return "—"
    f = float(v)
    t = f"{f:+.2f}%".replace("-", "−")
    c = "#5A6B80" if abs(f) < 0.1 else (RED if f < 0 else GREEN)   # ±0.1% 미만은 중립
    b0, b1 = ("<b>", "</b>") if (bold and abs(f) >= 0.1) else ("", "")
    return f"<font color='{c}'>{b0}{t}{b1}</font>"

def cut(man_v, pct_v):
    if man_v in ("", None): return "—"
    m = int(float(man_v))
    txt = f"{m/10000:.1f}억" if m >= 10000 else f"{m:,}만"
    return f"{txt} <font size=7 color='#8B95A5'>({float(pct_v):.1f}%)</font>"

TBL = [("BACKGROUND",(0,0),(-1,0),BLUE),("GRID",(0,0),(-1,-1),0.4,LINE),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),2.6),
       ("BOTTOMPADDING",(0,0),(-1,-1),2.6),("LEFTPADDING",(0,0),(0,-1),5)]
COLS = [26*mm, 15*mm, 30*mm, 40*mm, 22*mm, 23*mm]
HEAD = ["중간<br/>호가", "물건 수<br/>평상시 → 후", "채당 평균 호가 변동<br/>평상시 → 발표후",
        "발표후<br/>변동률", "발표 전후<br/>차이"]

story = []; A = story.append
seoul, gn3, gn3o = EV_O["서울"], EV_O["강남3구"], EV_O["서울(강남3구 외)"]
b30, b2030, b1520, b1015, b10 = (EV_B["30억 이상"], EV_B["20~30억"], EV_B["15~20억"],
                                 EV_B["10~15억"], EV_B["10 미만"] if "10 미만" in EV_B else EV_B["10억 미만"])

# ── 표지 ──────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제개편 2주 반, <b>서울 아파트 호가가 실제로 내렸다 — 금액으로 확인</b>", "title"))
A(P(f"발표 후 2주 반 만에 서울 아파트 호가가 <b>채당 평균 {man(seoul['발표후_평균변동액_만원'])}</b> 내렸다. "
    f"발표 전 한 달은 오히려 소폭 오르던 시장이다(평상시 {pct(seoul['평상시_평균변동률'], bold=False)}). "
    f"내림은 <b>비쌀수록 크다</b> — 강남3구 {man(gn3['발표후_평균변동액_만원'])}, 30억대 "
    f"{man(b30['발표후_평균변동액_만원'])}. 반면 중저가는 여전히 오름세라 <b>양극화</b>가 뚜렷하다.", "sub"))
A(P("발표 2026. 8. 3. 18시　|　평상시 = 발표 전 한 달(7/03→8/02) · 발표 후 2주 반(8/02→8/19)　|　"
    "서울 아파트 매매　|　2026. 8. 19. 기준　|　자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 4))

A(P(
    "<b>어떻게 봤나.</b> 같은 집을 두 시점에 이어 붙여, 그 사이 <b>부르는 값(호가)이 실제로 얼마나(원·%) "
    "움직였는지</b> 쟀다. 한 집을 여러 중개사무소가 올리면 광고가 여러 건이지만 <b>같은 집은 한 채로 "
    "접었고</b>(단지·동·층·전용면적·향), <b>값을 그대로 둔 집까지 분모에 넣어</b> 시장 전체의 평균 변동을 본다.<br/><br/>"
    "<b>평상시 기준을 '한 달'로 넓혔다.</b> 발표 직전 한 달(7/03→8/02)을 정상 시장으로 삼아, 발표 후 2주 "
    "반(8/02→8/19)과 비교한다. <b>평상시(한 달)가 발표후(2주 반)보다 기간이 긴데도</b>, 고가에서는 발표후에 "
    "더 크게 내렸다 — 짧은 기간에 더 큰 하락이라 <b>발표 효과가 뚜렷하다</b>는 뜻이다.<br/><br/>"
    "<font color='#5A6B80'>실거래가는 넣지 않았다. 8월 계약은 신고(계약 후 30일)가 아직 절반도 안 찼고, 싼 "
    "거래가 먼저 신고되는 쏠림까지 겹쳐 지금은 쓸 수 없다. 호가가 먼저 움직이고 실제 거래가 뒤따른다.</font>", "lead"))

# ── 1. 전체 ────────────────────────────────────────────────────────────────
_h1 = [P("1. 전체 — 오르던 서울 호가가 발표 후 내림으로 돌아섰다", "h")]
rows = [hdr(["구분"] + HEAD)]
for k in AREAS:
    r = EV_O[k]
    rows.append([P(f"<b>{k}</b>", "tdl"), P(eok(r), "td"),
                 P(pair(r["평상시_물건수"], r["발표후_물건수"]), "td"),
                 P(dpair(r["평상시_평균변동액_만원"], r["발표후_평균변동액_만원"]), "td"),
                 P(pct(r["발표후_평균변동률"]), "td"),
                 P(man(r["대비_평균변동액차_만원"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,2),(-1,2),ROWALT),("BACKGROUND",(0,3),(-1,3),HOTBG)]))
A(KeepTogether(_h1 + [t]))
A(P("‘채당 평균 호가 변동’은 값을 안 고친 집까지 포함한 한 채당 평균 변동액이다. 붉은 숫자는 <b>내림</b>, "
    "초록은 오름. ‘발표 전후 차이’는 발표후에서 평상시를 뺀 값(붉을수록 발표 후 더 내렸다는 뜻).", "cap"))

A(box(
    f"<b>서울 호가, 발표 후 채당 평균 {man(seoul['발표후_평균변동액_만원'], bold=False)} 내렸다</b><br/>"
    f"· 발표 전 한 달 서울 아파트 호가는 <b>소폭 오름세</b>였다(평상시 {pct(seoul['평상시_평균변동률'], bold=False)}, "
    f"채당 {man(seoul['평상시_평균변동액_만원'], bold=False)}). 발표 후엔 <b>내림으로 전환</b>—채당 평균 "
    f"{man(seoul['발표후_평균변동액_만원'], bold=False)}({pct(seoul['발표후_평균변동률'], bold=False)}).<br/>"
    f"· 내림은 <b>강남3구에 집중</b>됐다 — 채당 {man(gn3['발표후_평균변동액_만원'], bold=False)}"
    f"({pct(gn3['발표후_평균변동률'], bold=False)})로, 평상시 내림폭({man(gn3['평상시_평균변동액_만원'], bold=False)})의 "
    f"약 세 배다.<br/>"
    f"· <b>강남3구 밖 서울</b>은 평상시 오름세({man(gn3o['평상시_평균변동액_만원'], bold=False)})가 발표 후 "
    f"거의 멈췄다({man(gn3o['발표후_평균변동액_만원'], bold=False)}). 전국은 미동—대부분의 움직임이 "
    f"<b>서울, 그중 고가</b>에 몰렸다."))

# ── 2. 가격대 ──────────────────────────────────────────────────────────────
_h2 = [P("2. 가격대 — 비쌀수록 큰 폭으로 내렸고, 중저가는 여전히 올랐다(양극화)", "h")]
rows = [hdr(["서울 가격대"] + HEAD)]
for b in BANDS:
    r = EV_B[b]
    rows.append([P(f"<b>{b}</b>", "tdl"), P(eok(r), "td"),
                 P(pair(r["평상시_물건수"], r["발표후_물건수"]), "td"),
                 P(dpair(r["평상시_평균변동액_만원"], r["발표후_평균변동액_만원"]), "td"),
                 P(pct(r["발표후_평균변동률"]), "td"),
                 P(man(r["대비_평균변동액차_만원"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
stt = list(TBL)
for i, b in enumerate(BANDS, start=1):
    if float(EV_B[b]["발표후_평균변동액_만원"]) < 0:
        stt.append(("BACKGROUND",(0,i),(-1,i),HOTBG))
    elif i % 2 == 0:
        stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
stt.append(("LINEBELOW",(0,3),(-1,3),1.1,BLUE))
t.setStyle(TableStyle(stt))
A(KeepTogether(_h2 + [t]))
A(P("붉게 칠한 줄(20억 위)이 발표 후 값이 내려간 구간이다. 파란 선(15억) 위는 내림, 아래는 여전히 오름. "
    "‘내릴 때 깎는 폭’은 30억 이상에서 중앙 1억에 이른다.", "cap"))

A(box(
    f"<b>20억이 분기선 — 위는 내리고 아래는 오른다</b><br/>"
    f"· <b>30억 이상</b>은 발표 후 채당 평균 {man(b30['발표후_평균변동액_만원'], bold=False)}"
    f"({pct(b30['발표후_평균변동률'], bold=False)}) 내렸다. 평상시({man(b30['평상시_평균변동액_만원'], bold=False)})보다 "
    f"두 배 반 큰 폭이고, 값을 내릴 땐 <b>한 번에 중앙 1억</b>씩 깎는다.<br/>"
    f"· <b>20~30억</b>도 평상시 거의 제자리에서 발표 후 {man(b2030['발표후_평균변동액_만원'], bold=False)}로 "
    f"돌아섰다. 15~20억은 오름세가 멈췄다({man(b1520['발표후_평균변동액_만원'], bold=False)}).<br/>"
    f"· 반면 <b>15억 미만은 발표 후에도 올랐다</b> — 10~15억 {man(b1015['발표후_평균변동액_만원'], bold=False)}, "
    f"10억 미만 {man(b10['발표후_평균변동액_만원'], bold=False)}(오름폭은 평상시보다 줄었다). "
    f"고가는 내리고 중저가는 오르는 <b>양극화</b>다."))

# ── 3. 급지 사다리 ───────────────────────────────────────────────────────────
A(Spacer(1, 5))
TI = {r["급지"]: r for r in TIER}
TG = {"1급지": ("강남·서초·송파", "강남3구"),
      "2급지": ("용산·성동·마포·광진·동작", "한강·도심 상급"),
      "3급지": ("강동·영등포·양천·중구·서대문", "준상급"),
      "4급지": ("동대문·성북·강서·종로·은평", "중급"),
      "5급지": ("관악·구로·중랑·강북·노원·금천·도봉", "외곽·중저가")}
_h3 = [P("3. 급지 사다리 — 똘똘한 한 채일수록 큰 폭으로 내렸다", "h"),
       P("서울 25개 자치구를 값(중간 호가)이 비싼 순서로 다섯 급지로 묶었다. 위(1급지)일수록 내림폭이 크고, "
         "아래로 갈수록 오히려 오른다.", "body")]
rows = [hdr(["급지 (구성 자치구)"] + HEAD)]
for g in ("1급지", "2급지", "3급지", "4급지", "5급지"):
    r = TI[g]
    label = f"<b>{g}</b> · {TG[g][1]}<br/><font size=7 color='#8B95A5'>{TG[g][0]}</font>"
    rows.append([P(label, "tdl"), P(eok(r), "td"),
                 P(pair(r["평상시_물건수"], r["발표후_물건수"]), "td"),
                 P(dpair(r["평상시_평균변동액_만원"], r["발표후_평균변동액_만원"]), "td"),
                 P(pct(r["발표후_평균변동률"]), "td"),
                 P(man(r["대비_평균변동액차_만원"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
stt = list(TBL) + [("BACKGROUND",(0,1),(-1,1),HOTBG),
                   ("LINEBEFORE",(0,1),(0,1),2.2,colors.HexColor(RED))]
for i in (3, 5): stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(KeepTogether(_h3 + [t]))
t1, t5 = TI["1급지"], TI["5급지"]
A(P("위에서 아래로 갈수록 값이 싼 급지다. <b>1급지(강남3구)만 큰 폭으로 내리고</b>, 4·5급지는 발표 후에도 "
    "오름세다.", "cap"))
A(box(
    f"<b>사다리를 내려올수록 내림이 오름으로 바뀐다</b><br/>"
    f"· <b>1급지(강남3구)</b> 발표 후 채당 {man(t1['발표후_평균변동액_만원'], bold=False)}—평상시"
    f"({man(t1['평상시_평균변동액_만원'], bold=False)})보다 <b>{abs(int(float(t1['대비_평균변동액차_만원']))):,}만원 더</b> 내렸다.<br/>"
    f"· <b>2급지</b> {man(TI['2급지']['발표후_평균변동액_만원'], bold=False)}, <b>3급지</b>는 오름세가 멈췄다"
    f"({man(TI['3급지']['발표후_평균변동액_만원'], bold=False)}).<br/>"
    f"· <b>4·5급지(중저가·외곽)는 발표 후에도 올랐다</b> — 5급지 {man(t5['발표후_평균변동액_만원'], bold=False)}. "
    f"똘똘한 한 채에 매길수록 발표에 민감하게 값을 낮췄고, 실수요 위주의 중저가는 흔들리지 않았다."))

# ── 4. 자치구 ──────────────────────────────────────────────────────────────
GU.sort(key=lambda r: float(r["발표후_평균변동액_만원"]))
A(P("자치구별 — 발표 후 많이 내린 순 (영등포구는 고가지역 ‘여의도’를 따로 표시)", "h2"))
rows = [hdr(["자치구"] + HEAD)]
for r in GU:
    thin = int(r["발표후_물건수"]) < 500
    rows.append([P(f"<b>{r['자치구']}</b>" + (" <font color='#C9A227'>★</font>" if thin else ""), "tdl"),
                 P(eok(r), "td"), P(pair(r["평상시_물건수"], r["발표후_물건수"]), "td"),
                 P(dpair(r["평상시_평균변동액_만원"], r["발표후_평균변동액_만원"]), "td"),
                 P(pct(r["발표후_평균변동률"]), "td"),
                 P(man(r["대비_평균변동액차_만원"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
stt = list(TBL)
for i, r in enumerate(GU, start=1):
    if r["자치구"] in ("강남구", "서초구", "송파구"):
        stt += [("BACKGROUND",(0,i),(-1,i),HOTBG),("LINEBEFORE",(0,i),(0,i),2.2,colors.HexColor(RED))]
    elif i % 2 == 0:
        stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. <b>서초구가 발표 후 채당 −3,170만으로 가장 큰 폭</b>. "
    "<b>여의도(영등포구 내, 중간 38억)는 −1,297만</b>으로 강남권과 나란한 반면, 여의도를 뺀 영등포구(14억)는 "
    "거의 제자리다. 용산·송파는 평상시 오름세에서 내림으로 돌아섰다. <b>★</b>는 물건이 500채 미만이라 값이 "
    "쉽게 흔들리는 구다.", "cap"))

# ── 5. 재고 ────────────────────────────────────────────────────────────────
A(Spacer(1, 5))
_h4 = [P("5. 매물은 전 구간에서 쌓이고 있다 — 앞으로의 압력", "h"),
       P("같은 기간 서울 물건 수는 전 구간에서 늘었고, 비쌀수록 빠르게 늘었다.", "body")]
rows = [hdr(["서울 가격대", "8월 2일", "8월 19일", "증감", "증감률"])]
for r in STOCK:
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"), P(n(r["2026-08-02"]), "td"),
                 P(f"<b>{n(r['2026-08-19'])}</b>", "td"),
                 P(f"{int(r['발표후_증감']):+,}".replace("-", "−"), "td"),
                 P(f"<font color='{RED}'>{float(r['발표후_증감률']):+.1f}%</font>", "td")])
t = Table(rows, colWidths=[32*mm,28*mm,28*mm,24*mm,26*mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,5),(-1,5),HOTBG),
    ("BACKGROUND",(0,2),(-1,2),ROWALT),("BACKGROUND",(0,4),(-1,4),ROWALT)]))
A(KeepTogether(_h4 + [t]))
st30 = [r for r in STOCK if r["가격대"] == "30억 이상"][0]
A(P("증감률의 붉은색은 매물이 늘었다는 뜻이다. 30억 이상이 가장 빠르게 쌓인다.", "cap"))

# ── 6. 결론 ────────────────────────────────────────────────────────────────
A(Spacer(1, 4))
A(KeepTogether([
    P("6. 정리 — 고가에서 시작된 하락, 금액으로 확인됐다", "h"),
    box(
        f"<b>① 서울 호가가 실제로 내렸다.</b> 발표 후 2주 반 만에 서울 아파트 호가는 채당 평균 "
        f"{man(seoul['발표후_평균변동액_만원'], bold=False)} 내렸다. 발표 전 한 달은 오히려 소폭 오르던 시장이라, "
        f"방향이 <b>오름→내림으로 바뀐 것</b>이 핵심이다.<br/><br/>"
        f"<b>② 비쌀수록 큰 폭.</b> 강남3구 {man(gn3['발표후_평균변동액_만원'], bold=False)}, 30억대 "
        f"{man(b30['발표후_평균변동액_만원'], bold=False)}(깎을 땐 한 번에 1억), 서초구는 채당 −3,170만으로 가장 컸다. "
        f"강남3구의 발표후 내림폭은 평상시의 약 세 배다.<br/><br/>"
        f"<b>③ 중저가·외곽은 여전히 올랐다 — 양극화.</b> 15억 미만과 4·5급지(중저가)는 발표 후에도 오름세다"
        f"(5급지 {man(TI['5급지']['발표후_평균변동액_만원'], bold=False)}). 실수요 위주의 시장은 흔들리지 않았다.<br/><br/>"
        f"<b>④ 짧은 기간에 더 큰 하락 = 발표 효과.</b> 평상시는 한 달, 발표후는 2주 반으로 <b>발표후가 더 짧은데도</b> "
        f"고가에서 더 크게 내렸다. 기간이 짧을수록 하락이 가팔라졌다는 뜻이다.<br/><br/>"
        f"<b>⑤ 매물은 전 구간에서 쌓이고 있다.</b> 2주 반 만에 30억 이상 매물이 "
        f"<font color='{RED}'>+{float(st30['발표후_증감률']):.1f}%</font> 늘었다. 부르는 값과 사려는 값의 거리가 "
        f"벌어지고 있다는 뜻이고, 이 상태가 이어지면 호가는 더 내려간다.<br/><br/>"
        "<font color='#5A6B80'>※ 이 수치는 호가(부르는 값)다. 실제 거래가와는 시차가 있으며, 호가가 먼저 "
        "움직이고 거래가 뒤따른다.</font>")]))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>조용호</b>　|　런투온라인　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-4692-4946　albooooza@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21*mm, rightMargin=21*mm,
                        topMargin=18*mm, bottomMargin=16*mm,
                        title="세제개편 후 서울 아파트 호가 하락(8/19 기준)", author="조용호 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
