# -*- coding: utf-8 -*-
"""세제발표 전후 — 서울 준신축 5개 단지 전용 84㎡ 매매 호가 동향. 배포용 보도자료.
   발표전 2026-08-02 → 발표후 2026-08-20. 데이터: measure_5complex_84_0820.py 산출.
Run: python3 design/press/세제개편-호가/make_report_5complex_84.py
"""
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
OUT = HERE / "세제발표_전후_5단지_전용84_호가동향(20260820기준).pdf"

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
    "title": ParagraphStyle("title", fontName="PX", fontSize=17.5, leading=23, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11, textColor=BLUE_DK, leading=16.5, spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.6, leading=15.5, textColor=INK, spaceAfter=6),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.2, leading=17, textColor=INK, spaceAfter=7),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY, spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.2, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.6, leading=11, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.8, leading=11, textColor=INK, alignment=0),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY, spaceAfter=3),
}
def P(t, s="body"): return Paragraph(t, ss[s])
def hdr(cs): return [P(c, "th") for c in cs]
def box(html, bg=BOXBG, ln=LINE):
    t = Table([[P(html, "boxb")]], colWidths=[168 * mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,ln),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    return t

def eok(man):   # 만원 → "26.5억"
    return f"{man/10000:.1f}억"
def epair(b, a):   # 전→후 (억)
    return f"{eok(b)} → <b>{eok(a)}</b>"
def man(v, bold=False):   # 변동액(만원) — 하락 붉게, 상승 초록
    v = int(round(v)); a = abs(v)
    txt = f"{a/10000:.2f}억" if a >= 10000 else f"{a:,}만"
    sign = "−" if v < 0 else ("+" if v > 0 else "")
    c = "#5A6B80" if a < 100 else (RED if v < 0 else GREEN)   # 100만 미만은 사실상 보합
    b0, b1 = ("<b>", "</b>") if bold else ("", "")
    return f"<font color='{c}'>{b0}{sign}{txt}{b1}</font>"
def pct(v, bold=True):
    t = f"{v:+.1f}%".replace("-", "−")
    c = "#5A6B80" if abs(v) < 0.3 else (RED if v < 0 else GREEN)
    b0, b1 = ("<b>", "</b>") if (bold and abs(v) >= 0.3) else ("", "")
    return f"<font color='{c}'>{b0}{t}{b1}</font>"

# ── 데이터 (measure_5complex_84_0820.py 산출, 만원) ─────────────────────────
# 단지, 위치, 전중앙, 후중앙, 전평균, 후평균, 전최저, 후최저, 전매물, 후매물
D = [
    ("마포래미안푸르지오", "마포 아현", 265000, 265000, 263858, 263910, 250000, 249000, 358, 388),
    ("e편한세상 옥수파크힐스", "성동 옥수", 275000, 275000, 273773, 273318, 260000, 260000, 99, 99),
    ("래미안 옥수리버젠", "성동 옥수", 285000, 285000, 287165, 285787, 240000, 240000, 164, 150),
    ("마포 아이파크포레", "마포 신수", 260000, 260000, 257430, 261962, 245000, 245000, 79, 79),
    ("올림픽파크포레온", "강동 둔촌", 310000, 303000, 308287, 303584, 290000, 280000, 508, 599),
]

story = []; A = story.append

# ── 표지 ──────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제발표 후, <b>마포·옥수는 호가 방어 — 둔촌만 밀렸다</b><br/>서울 준신축 5개 단지 전용 84㎡ 매매 호가", "title"))
A(P("발표 후 2주 반, 마포래미안푸르지오·옥수파크힐스·옥수리버젠·마포아이파크포레 <b>4개 단지의 전용 84㎡ "
    "호가는 사실상 보합</b>이다(중앙값 변동 0). 반면 <b>올림픽파크포레온(둔촌)</b>만 뚜렷이 밀렸다 — "
    f"중앙 호가 <b>{man(303000-310000, bold=False)}(−2.3%)</b>, 최저 호가 <b>29억→28억(−1억)</b>, "
    "매물 <b>508→599건(+18%)</b> 적체.", "sub"))
A(P("발표 2026. 8. 3. 18시　|　전용 84㎡ 매매 호가　|　발표 전 2026. 8. 2 → 발표 후 2026. 8. 20　|　"
    "자료 콕집(koczip.com)", "cap"))
A(Spacer(1, 3))

A(P(
    "<b>어떻게 봤나.</b> 다섯 단지 각각의 <b>전용 84㎡ 매매 매물 호가</b>를 세제 발표 직전(8/02)과 발표 후 "
    "2주 반(8/20) 두 시점으로 잘라 비교했다. 대표 지표는 <b>중앙 호가</b>다(소수 고가·저가 매물의 믹스에 강건). "
    "평균·최저 호가와 매물(광고) 수를 함께 실었다.<br/><br/>"
    "<b>‘동일 물건’도 따로 봤다.</b> 발표 전후 두 시점에 모두 존재한 같은 매물(매물번호)을 이어 붙여, "
    "기존 매도인이 부르는 값을 실제로 고쳤는지 확인했다.<br/><br/>"
    "<font color='#5A6B80'>수치는 호가(부르는 값)로 실거래가가 아니다. 매물 수는 광고 건수 기준(한 집을 여러 "
    "중개사가 올린 중복 포함)이라 실제 물건 수보다 많을 수 있다. 호가가 먼저 움직이고 거래가 뒤따른다.</font>", "lead"))

# ── 1. 단지별 표 ─────────────────────────────────────────────────────────────
A(P("1. 단지별 — 전용 84㎡ 매매 호가 (발표 전 → 발표 후)", "h"))
COLS = [34*mm, 30*mm, 20*mm, 19*mm, 30*mm, 21*mm]
HEAD = ["중앙 호가<br/>전 → 후", "중앙<br/>변동", "평균<br/>변동률", "최저 호가<br/>전 → 후", "매물(광고)<br/>전 → 후"]
rows = [hdr(["단지 (위치)"] + HEAD)]
for nm, loc, bm, am, bavg, aavg, blo, alo, bn, an in D:
    dmid = am - bm
    davgp = (aavg - bavg) / bavg * 100
    label = f"<b>{nm}</b><br/><font size=7 color='#8B95A5'>{loc}</font>"
    rows.append([P(label, "tdl"), P(epair(bm, am), "td"), P(man(dmid), "td"),
                 P(pct(davgp), "td"), P(epair(blo, alo), "td"),
                 P(f"{bn} → <b>{an}</b>", "td")])
t = Table(rows, colWidths=COLS, repeatRows=1)
TBL = [("BACKGROUND",(0,0),(-1,0),BLUE),("GRID",(0,0),(-1,-1),0.4,LINE),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),3.2),
       ("BOTTOMPADDING",(0,0),(-1,-1),3.2),("LEFTPADDING",(0,0),(0,-1),5)]
stt = list(TBL) + [("BACKGROUND",(0,5),(-1,5),HOTBG),
                   ("LINEBEFORE",(0,5),(0,5),2.2,colors.HexColor(RED)),
                   ("BACKGROUND",(0,2),(-1,2),ROWALT),("BACKGROUND",(0,4),(-1,4),ROWALT)]
t.setStyle(TableStyle(stt))
A(KeepTogether([t]))
A(P("붉게 칠한 줄(올림픽파크포레온)이 발표 후 값이 내려간 단지다. 붉은 숫자는 <b>내림</b>, 초록은 오름, "
    "회색은 사실상 보합(±100만·±0.3% 미만). ‘매물(광고)’는 중복 광고를 포함한 광고 건수다.", "cap"))

A(box(
    "<b>마포·옥수 4개 단지는 호가를 지켰고, 하락은 둔촌에 집중됐다</b><br/>"
    "· <b>마포래미안푸르지오·옥수파크힐스·옥수리버젠·마포아이파크포레</b>는 발표 후 전용 84㎡ 중앙 호가가 "
    "<b>변동 없이 보합</b>(평균도 ±0.5% 이내)이다. 대장 준신축의 호가 경직성이 확인된다.<br/>"
    "· <b>올림픽파크포레온(둔촌)</b>만 뚜렷이 밀렸다 — 중앙 31.0억→30.3억(−2.3%), 평균 −1.5%, "
    "최저 29억→28억으로 <b>바닥이 1억 빠졌다</b>.<br/>"
    "· <font color='#5A6B80'>마포아이파크포레의 평균 +1.8%는 중앙·최저가 보합인데 평균만 오른 것으로, 소수 "
    "고가 매물(믹스) 영향이다 — 실질은 보합.</font>"))

# ── 2. 올림픽파크포레온 상세 ──────────────────────────────────────────────────
A(P("2. 올림픽파크포레온 — 유일한 뚜렷한 하락", "h"))
mc = [26*mm, 32*mm, 32*mm, 32*mm, 32*mm]
mrow = [hdr(["지표", "중앙 호가", "최저 호가", "평균 호가", "매물(광고) 수"]),
        [P("<b>발표 전</b> (8/02)", "tdl"), P("31.0억", "td"), P("29.0억", "td"), P("30.83억", "td"), P("508건", "td")],
        [P("<b>발표 후</b> (8/20)", "tdl"), P("30.3억", "td"), P("28.0억", "td"), P("30.36억", "td"), P("599건", "td")],
        [P("<b>변동</b>", "tdl"),
         P(f"{man(-7000)}<br/><font size=7 color='#8B95A5'>(−2.3%)</font>", "td"),
         P(f"{man(-10000)}", "td"),
         P(f"{pct(-1.5)}", "td"),
         P(f"<font color='{RED}'><b>+91건 (+18%)</b></font>", "td")]]
mt = Table(mrow, colWidths=mc, repeatRows=1)
mt.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,3),(-1,3),HOTBG)]))
A(KeepTogether([mt]))
A(box(
    "<b>기존 매도인은 호가를 안 내렸다 — 하락은 ‘신규·급매 유입’에서 왔다</b><br/>"
    "· 발표 전후 두 시점에 모두 있던 <b>동일 매물(패널)</b>은 대다수가 호가 <b>동결</b>이었다. 기존 매도인이 "
    "부르는 값을 낮춘 게 아니다.<br/>"
    "· 그런데도 전체 호가 수준이 내려간 것은 <b>더 낮게 나온 신규 매물 유입 + 매물 적체</b>(508→599건) 때문이다. "
    "세대수가 큰 신축 대단지라 물량 부담이 호가 하방으로 직결됐다.<br/>"
    "· <b>최저 호가가 29억→28억으로 1억 빠진 것</b>이 이 흐름의 신호다 — 급매가 바닥을 끌어내리고 있다.",
    bg=HOTBG, ln=colors.HexColor("#E8B4AE")))

# ── 3. 종합 ──────────────────────────────────────────────────────────────────
A(P("3. 종합", "h"))
A(box(
    "<b>① 대장 준신축의 호가는 발표에도 버텼다.</b> 마포·옥수 4개 단지 전용 84㎡ 중앙 호가는 발표 후에도 "
    "보합. 매도 우위 심리가 유지되고 있다.<br/><br/>"
    "<b>② 하락은 신축 대단지(둔촌)에 집중.</b> 올림픽파크포레온만 중앙 −2.3%·최저 −1억·매물 +18%. "
    "물량이 많은 단지일수록 세제 국면에서 먼저, 크게 흔들린다.<br/><br/>"
    "<b>③ 하락의 성격 = 호가 인하가 아니라 급매·신규 유입.</b> 기존 매물은 호가를 유지했고, 새로 나오는 "
    "매물과 급매가 값을 끌어내렸다. 이 적체가 이어지면 호가는 더 내려갈 여지가 있다.<br/><br/>"
    "<font color='#5A6B80'>※ 이 수치는 호가(부르는 값)다. 실제 거래가와는 시차가 있으며, 전용 84㎡ 매매 "
    "매물만을 대상으로 했다.</font>"))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>조용호</b>　|　런투온라인　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-4692-4946　albooooza@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21*mm, rightMargin=21*mm,
                        topMargin=18*mm, bottomMargin=16*mm,
                        title="세제발표 전후 5개 단지 전용84 호가동향(8/20 기준)", author="조용호 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
