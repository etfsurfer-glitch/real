# -*- coding: utf-8 -*-
"""세제개편안 전후 서울 아파트 호가 — 시장 동향 보고서(동일 물건 패널, 8/17 기준·전후 2주).
   ※ 단독 배포용. '기준1/기준2' 등 다른 방법론을 일절 언급하지 않는다(다른 기자 배포).
원자료: design/press/data/panel0817_*.csv
Run: python3 design/press/세제개편-호가/make_report_panel_0817.py
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
OUT = HERE / "세제개편_전후_서울아파트_호가동향(20260817기준).pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

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

EV_O = {r["구분"]: r for r in read("panel0817_overall.csv")}
EV_B = {r["가격대"]: r for r in read("panel0817_band.csv")}
TIER = read("panel0817_tier.csv")
GU = read("panel0817_gu.csv")
STOCK = read("panel0817_stock.csv")
BANDS = ["10억 미만", "10~15억", "15~20억", "20~30억", "30억 이상"]
AREAS = ["전국", "서울", "강남3구", "서울(강남3구 외)"]

pc1 = lambda v: f"{float(v):.1f}%"                                        # noqa: E731
def eok(r): return f"{r['기준_중앙호가_억']}억" if r.get("기준_중앙호가_억") not in ("", None) else "—"
def n(v): return f"{int(float(v)):,}"
def cut100(v):
    """비율(%) → 100채 중 몇 채."""
    return round(float(v))

def pair(a, b):
    return f"{int(float(a)):,} → <b>{int(float(b)):,}</b>"

def dnrate(r):
    """값 내린 집 비율 — 발표 전 → 후."""
    return f"{pc1(r['발표전_인하비율'])} → <b>{pc1(r['발표후_인하비율'])}</b>"

def sign(v, unit="p", bold=True):
    """값 내린 집 비율의 변화 — 늘어난 것(양수)이 이 사안의 신호라 붉게."""
    if v in ("", None): return "—"
    v = float(v)
    t = f"{v:+.1f}{unit}".replace("-", "−")
    if abs(v) < 0.3: return f"<font color='#5A6B80'>{t}</font>"
    c = "#C0392B" if v > 0 else "#1F7A4D"
    return f"<font color='{c}'>{'<b>' if bold else ''}{t}{'</b>' if bold else ''}</font>"

def ratio(v):
    """내린 집 : 올린 집. 1.0 넘으면 내리는 쪽이 많다."""
    if v in ("", None): return "—"
    f = float(v)
    c = "#C0392B" if f >= 1.3 else ("#1F7A4D" if f < 1.0 else "#18233A")
    b = "<b>" if (f >= 1.3 or f < 1.0) else ""
    return f"<font color='{c}'>{b}{f:.2f}배{'</b>' if b else ''}</font>"

def cut(man, pct):
    if man in ("", None): return "—"
    m = int(float(man))
    txt = f"{m/10000:.1f}억" if m >= 10000 else f"{m:,}만"
    return f"{txt} <font size=7 color='#8B95A5'>({float(pct):.1f}%)</font>"

TBL = [("BACKGROUND",(0,0),(-1,0),BLUE),("GRID",(0,0),(-1,-1),0.4,LINE),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),2.4),
       ("BOTTOMPADDING",(0,0),(-1,-1),2.4),("LEFTPADDING",(0,0),(0,-1),5)]
COLS = [24*mm, 13*mm, 26*mm, 34*mm, 15*mm, 20*mm, 24*mm]
HEAD = ["중간<br/>호가", "물건 수<br/>발표 전 → 후", "값 내린 집 비율<br/>발표 전 → 후",
        "변화", "내린 집 :<br/>올린 집", "내릴 때<br/>깎는 폭"]

story = []; A = story.append
seoul, gn3 = EV_O["서울"], EV_O["강남3구"]
b30, b10, b1015, b1520, b2030 = (EV_B["30억 이상"], EV_B["10억 미만"], EV_B["10~15억"],
                                 EV_B["15~20억"], EV_B["20~30억"])
flat_seoul = round(100 - float(seoul["발표후_인하비율"]) - float(seoul["발표후_인상비율"]), 1)

# ── 표지 ──────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제개편 2주, <b>비싼 아파트에서 ‘값 내린 집’이 늘었다</b>", "title"))
A(P(f"호가 수준 자체는 거의 그대로다 — 서울 아파트 물건의 <b>{flat_seoul:.0f}%가 2주 동안 호가를 "
    f"한 번도 안 고쳤다.</b> 움직인 것은 ‘값을 내린 집의 비율’이고, 비쌀수록 늘었다. 30억대는 "
    f"100채 중 <b>{cut100(b30['발표후_인하비율'])}채</b>가 값을 내렸다(2주 전 "
    f"{cut100(b30['발표전_인하비율'])}채). 전국은 미동 — <b>서울, 그중에서도 고가</b>에 몰린 "
    f"현상이다.", "sub"))
A(P("발표 2026. 8. 3. 18시　|　발표 전 2주(7/19→8/02) · 발표 후 2주(8/02→8/17)　|　"
    "서울 아파트 매매　|　2026. 8. 17. 기준　|　자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 4))

A(P(
    "<b>어떻게 봤나.</b> 같은 집을 두 시점에 이어 붙여, 그 사이 호가가 얼마나 움직였는지 봤다. "
    "한 집을 여러 중개사무소가 올리면 광고가 여러 건이지만 <b>같은 집은 한 채로 접었다</b>"
    "(단지·동·층·전용면적·향으로 판정). 값을 고친 집뿐 아니라 <b>값을 그대로 둔 집까지 분모에 "
    "넣어</b>, 시장 전체가 실제로 얼마나 움직였는지를 잰다.<br/><br/>"
    "<b>지표 — ‘값 내린 집 비율’.</b> 전체 물건 100채 중 2주 사이 호가를 <b>내린 집이 몇 채</b>인지다. "
    "이 비율이 높아질수록 값을 내리는 쪽으로 기운 시장이다. ‘발표 전’은 발표 직전 2주"
    "(7/19→8/02)의 변화, ‘발표 후’는 발표를 사이에 낀 2주(8/02→8/17)의 변화다.<br/><br/>"
    "<font color='#5A6B80'>실거래가는 넣지 않았다. 8월 계약은 신고(계약 후 30일)가 아직 절반도 안 "
    "찼고, 싼 거래가 먼저 신고되는 쏠림까지 겹쳐 지금은 쓸 수 없다. 호가가 먼저 움직이고 실제 "
    "거래가 뒤따른다.</font>", "lead"))

# ── 1. 전체 ────────────────────────────────────────────────────────────────
_h1 = [P("1. 전체 — 호가 수준은 그대로, 강남에서만 내리는 집이 늘었다", "h")]
rows = [hdr(["구분"] + HEAD)]
for k in AREAS:
    r = EV_O[k]
    rows.append([P(f"<b>{k}</b>", "tdl"), P(eok(r), "td"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"), P(dnrate(r), "td"),
                 P(sign(r["발표전후_인하비율변화p"]), "td"), P(ratio(r["발표후_인하대인상_배"]), "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,2),(-1,2),ROWALT),("BACKGROUND",(0,3),(-1,3),HOTBG)]))
A(KeepTogether(_h1 + [t]))
A(P("‘변화’는 값 내린 집 비율의 발표 전후 변화(%p)다. 붉은 숫자는 <b>값 내린 집이 늘었다</b>는 뜻. "
    "‘내린 집 : 올린 집’이 1.00배를 넘으면 내리는 쪽이 더 많다.", "cap"))

A(box(
    f"<b>값이 내려간 게 아니라, 내리는 집이 늘었다</b><br/>"
    f"· 서울 물건의 <b>{flat_seoul:.0f}%는 2주 동안 호가를 한 번도 안 고쳤다.</b> 평균 호가 변동률도 "
    f"발표 후 {('%.2f%%' % float(seoul['발표후_전체_평균변동률'])).replace('-', '−')}로 "
    f"사실상 제자리다 — <b>‘값이 폭락했다’는 그림이 아니다.</b><br/>"
    f"· 대신 <b>값을 내린 집의 비율</b>이 강남3구에서 뚜렷이 늘었다("
    f"{pc1(gn3['발표전_인하비율'])} → {pc1(gn3['발표후_인하비율'])}, "
    f"{sign(gn3['발표전후_인하비율변화p'], bold=False)}). 강남3구는 내린 집이 올린 집의 "
    f"<b>{float(gn3['발표후_인하대인상_배']):.1f}배</b>다.<br/>"
    f"· <b>강남3구 밖 서울은 거의 그대로</b>({sign(EV_O['서울(강남3구 외)']['발표전후_인하비율변화p'], bold=False)}, "
    f"내림:올림 {float(EV_O['서울(강남3구 외)']['발표후_인하대인상_배']):.2f}배). 전국도 "
    f"{sign(EV_O['전국']['발표전후_인하비율변화p'], bold=False)}로 미동이다."))

# ── 2. 가격대 ──────────────────────────────────────────────────────────────
_h2 = [P("2. 가격대 — 비쌀수록 값 내린 집이 늘었다", "h")]
rows = [hdr(["서울 가격대"] + HEAD)]
for b in BANDS:
    r = EV_B[b]
    rows.append([P(f"<b>{b}</b>", "tdl"), P(eok(r), "td"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"), P(dnrate(r), "td"),
                 P(sign(r["발표전후_인하비율변화p"]), "td"), P(ratio(r["발표후_인하대인상_배"]), "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
stt = list(TBL)
for i, b in enumerate(BANDS, start=1):
    if float(EV_B[b]["발표전후_인하비율변화p"]) >= 1.0:
        stt.append(("BACKGROUND",(0,i),(-1,i),HOTBG))
    elif i % 2 == 0:
        stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
stt.append(("LINEBELOW",(0,3),(-1,3),1.1,BLUE))
t.setStyle(TableStyle(stt))
A(KeepTogether(_h2 + [t]))
A(P("붉게 칠한 줄은 값 내린 집 비율이 1%p 넘게 늘어난 구간(20억 위)이다. 파란 선(15억) 위는 "
    "올린 집이 더 많고(배수 1.00 미만), 아래는 내린 집이 더 많다.", "cap"))

A(box(
    f"<b>‘내리는 집’이 늘어난 것은 20억 위, ‘내리는 쪽이 많아진’ 것은 15억 위</b><br/>"
    f"· 값 내린 집 비율이 뚜렷이 늘어난 구간은 <b>20억 위</b>다 — 20~30억 "
    f"{sign(b2030['발표전후_인하비율변화p'], bold=False)}, 30억 이상 "
    f"{sign(b30['발표전후_인하비율변화p'], bold=False)}. 15억 미만은 미동"
    f"(10억 미만 {sign(b10['발표전후_인하비율변화p'], bold=False)}, 10~15억 "
    f"{sign(b1015['발표전후_인하비율변화p'], bold=False)}).<br/>"
    f"· ‘내린 집이 올린 집보다 많아지는’ 선은 <b>15억</b>이다 — 15억 미만은 배수 1.00 미만(올린 집이 "
    f"더 많음), 15~20억 {float(b1520['발표후_인하대인상_배']):.2f}배부터 뒤집혀 30억 이상은 "
    f"<b>{float(b30['발표후_인하대인상_배']):.2f}배</b>까지 벌어진다.<br/>"
    f"· <b>깎는 비율은 어느 구간이나 2% 안팎으로 비슷하다.</b> 달라진 것은 얼마나 많은 집이 "
    f"내리느냐다."))

# ── 3. 급지 사다리 ───────────────────────────────────────────────────────────
A(Spacer(1, 5))
TI = {r["급지"]: r for r in TIER}
TG = {"1급지": ("강남·서초·송파", "강남3구"),
      "2급지": ("용산·성동·마포·광진·동작", "한강·도심 상급"),
      "3급지": ("강동·영등포·양천·중구·서대문", "준상급"),
      "4급지": ("동대문·성북·강서·종로·은평", "중급"),
      "5급지": ("관악·구로·중랑·강북·노원·금천·도봉", "외곽·중저가")}
_h3 = [P("3. 급지 사다리 — 똘똘한 한 채일수록 값 내린 집이 늘었다", "h"),
       P("서울 25개 자치구를 값(중간 호가)이 비싼 순서로 다섯 급지로 묶었다. 전국을 5분위로 나누면 "
         "서울은 거의 다 최상위 분위에 몰려 <b>서울 안에서의 차이가 드러나지 않는다.</b> 그래서 서울 "
         "안에서만 똘똘한 한 채(1급지)부터 덜 똘똘한 곳(5급지)까지 다시 줄 세웠다.", "body")]
rows = [hdr(["급지 (구성 자치구)"] + HEAD)]
for g in ("1급지", "2급지", "3급지", "4급지", "5급지"):
    r = TI[g]
    label = (f"<b>{g}</b> · {TG[g][1]}<br/><font size=7 color='#8B95A5'>{TG[g][0]}</font>")
    rows.append([P(label, "tdl"), P(eok(r), "td"),
                 P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"), P(dnrate(r), "td"),
                 P(sign(r["발표전후_인하비율변화p"]), "td"), P(ratio(r["발표후_인하대인상_배"]), "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
stt = list(TBL) + [("BACKGROUND",(0,1),(-1,1),HOTBG),
                   ("LINEBEFORE",(0,1),(0,1),2.2,colors.HexColor("#C0392B"))]
for i in (3, 5): stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(KeepTogether(_h3 + [t]))
A(P("위에서 아래로 갈수록 값이 싼 급지다. <b>1급지에서만 값 내린 집이 뚜렷이 늘고</b>(붉은 줄), "
    "3급지 아래로는 제자리거나 오히려 줄었다(배수 1.00 미만은 올린 집이 더 많다는 뜻).", "cap"))

t1, t2t, t3, t4, t5 = TI["1급지"], TI["2급지"], TI["3급지"], TI["4급지"], TI["5급지"]
A(box(
    f"<b>사다리를 한 칸 내려올 때마다 신호가 옅어진다</b><br/>"
    f"· <b>1급지(강남3구, 중간 {eok(t1)})</b> — 값 내린 집이 {dnrate(t1)}로 뛰었다"
    f"({sign(t1['발표전후_인하비율변화p'], bold=False)}). 내린 집이 올린 집의 "
    f"<b>{float(t1['발표후_인하대인상_배']):.1f}배</b>다.<br/>"
    f"· <b>2급지(용산·성동·마포·광진·동작)</b> — 세기는 절반 남짓"
    f"({sign(t2t['발표전후_인하비율변화p'], bold=False)}, 내림:올림 "
    f"{float(t2t['발표후_인하대인상_배']):.2f}배). 한강변 상급지까지는 신호가 이어진다.<br/>"
    f"· <b>3급지 아래로는 사실상 제자리</b> — 3급지 {sign(t3['발표전후_인하비율변화p'], bold=False)}, "
    f"4급지 {sign(t4['발표전후_인하비율변화p'], bold=False)}, 5급지 "
    f"{sign(t5['발표전후_인하비율변화p'], bold=False)}. <b>4·5급지는 오히려 올린 집이 더 많다</b>"
    f"(배수 {float(t4['발표후_인하대인상_배']):.2f}·{float(t5['발표후_인하대인상_배']):.2f}배).<br/>"
    f"· 똘똘한 한 채일수록 발표에 민감하게 값을 낮췄고, 실수요 위주의 중저가 급지는 흔들리지 않았다."))

GU.sort(key=lambda r: -float(r["발표전후_인하비율변화p"] or 0))
A(P("자치구별 — 300물건 이상 25곳, 값 내린 집이 많이 늘어난 순", "h2"))
rows = [hdr(["자치구"] + HEAD)]
for r in GU:
    thin = int(r["발표후_물건수"]) < 500
    rows.append([P(f"<b>{r['자치구']}</b>" + (" <font color='#C9A227'>★</font>" if thin else ""), "tdl"),
                 P(eok(r), "td"), P(pair(r["발표전_물건수"], r["발표후_물건수"]), "td"), P(dnrate(r), "td"),
                 P(sign(r["발표전후_인하비율변화p"]), "td"), P(ratio(r["발표후_인하대인상_배"]), "td"),
                 P(cut(r["발표후_인하폭_중앙_만원"], r["발표후_인하폭_중앙_률"]), "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
stt = list(TBL)
for i, r in enumerate(GU, start=1):
    if r["자치구"] in ("강남구", "서초구", "송파구"):
        stt += [("BACKGROUND",(0,i),(-1,i),HOTBG),("LINEBEFORE",(0,i),(0,i),2.2,colors.HexColor("#C0392B"))]
    elif i % 2 == 0:
        stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(t)
A(P("왼쪽에 붉은 선이 그어진 세 줄이 강남3구다. <b>★</b>는 물건이 500채에 못 미쳐 비율이 쉽게 "
    "흔들리는 구다. 강남·서초·송파는 물건이 두터워 안정적이다.", "cap"))

# ── 4. 재고 ────────────────────────────────────────────────────────────────
A(Spacer(1, 5))
_h4 = [P("4. 값은 안 내렸지만 매물은 쌓이고 있다", "h"),
       P("같은 2주 동안 서울 물건 수는 전 구간에서 늘었고, 비쌀수록 빠르게 늘었다.", "body")]
rows = [hdr(["서울 가격대", "8월 2일", "8월 17일", "증감", "증감률"])]
for r in STOCK:
    rows.append([P(f"<b>{r['가격대']}</b>", "tdl"), P(n(r["2026-08-02"]), "td"),
                 P(f"<b>{n(r['2026-08-17'])}</b>", "td"),
                 P(f"{int(r['발표후_증감']):+,}".replace("-", "−"), "td"),
                 P(sign(r["발표후_증감률"], unit="%"), "td")])
t = Table(rows, colWidths=[32*mm,28*mm,28*mm,24*mm,26*mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,5),(-1,5),HOTBG),
    ("BACKGROUND",(0,2),(-1,2),ROWALT),("BACKGROUND",(0,4),(-1,4),ROWALT)]))
A(KeepTogether(_h4 + [t]))
A(P("증감률의 붉은색은 매물이 늘었다는 뜻이다.", "cap"))

# ── 5. 결론 ────────────────────────────────────────────────────────────────
A(Spacer(1, 4))
st30 = [r for r in STOCK if r["가격대"] == "30억 이상"][0]
A(KeepTogether([
    P("5. 정리 — 값은 버텼지만, 고가에서 균열이 시작됐다", "h"),
    box(
        f"<b>① 호가 수준 자체는 거의 움직이지 않았다.</b> 서울 아파트 물건의 {flat_seoul:.0f}%가 2주 "
        f"동안 호가를 한 번도 안 고쳤고, 평균 변동률도 제자리다. ‘발표로 값이 폭락했다’는 그림은 "
        "아직 아니다.<br/><br/>"
        f"<b>② 움직인 것은 ‘값 내린 집의 수’이고, 비쌀수록 늘었다.</b> 30억대는 100채 중 "
        f"{cut100(b30['발표후_인하비율'])}채가 값을 내렸다(2주 전 {cut100(b30['발표전_인하비율'])}채, "
        f"{sign(b30['발표전후_인하비율변화p'], bold=False)}). 강남3구는 내린 집이 올린 집의 "
        f"{float(gn3['발표후_인하대인상_배']):.1f}배다. 반면 15억 미만은 미동이다. 급지 사다리로 보면 "
        f"1급지(강남3구) {sign(t1['발표전후_인하비율변화p'], bold=False)} → 2급지 "
        f"{sign(t2t['발표전후_인하비율변화p'], bold=False)} → 3급지 아래 제자리로, <b>한 칸 내려올수록 "
        f"신호가 옅어진다.</b><br/><br/>"
        f"<b>③ 분기선이 지표마다 다르다.</b> ‘값 내린 집이 늘어난’ 구간은 <b>20억 위</b>뿐이고, "
        f"‘내리는 쪽이 올리는 쪽보다 많아지는’ 선은 <b>15억</b>이다. 두 선을 섞어 말하면 안 된다.<br/><br/>"
        f"<b>④ 깎는 폭이 아니라 깎는 집의 수가 달라졌다.</b> 값을 내릴 때 깎는 비율은 어느 가격대나 "
        f"2% 안팎으로 비슷하다. 고가에서 벌어진 일은 한 집이 크게 깎은 것이 아니라 내리는 집이 "
        f"늘어난 것이다.<br/><br/>"
        f"<b>⑤ 매물은 전 구간에서 쌓이고 있다 — 이것이 앞으로의 압력이다.</b> 2주 만에 서울 물건은 "
        f"30억 이상 {sign(st30['발표후_증감률'], unit='%', bold=False)} 늘었다. 부르는 값과 사려는 "
        f"값의 거리가 벌어지고 있다는 뜻이고, 이 상태가 이어지면 다음에 움직이는 것은 호가다.<br/><br/>"
        "<font color='#5A6B80'>※ 이 수치는 호가(부르는 값)다. 실제 거래가와는 시차가 있으며, 호가가 "
        "먼저 움직이고 거래가 뒤따른다.</font>")]))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>조용호</b>　|　런투온라인　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-4692-4946　albooooza@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21*mm, rightMargin=21*mm,
                        topMargin=18*mm, bottomMargin=16*mm,
                        title="세제개편 2주, 서울 아파트 호가 동향(8/17 기준)", author="조용호 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
