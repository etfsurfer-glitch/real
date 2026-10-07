# -*- coding: utf-8 -*-
"""세제개편 이후 서울 아파트 '단지별 다이내믹' — 이슈 단지·급변 단지 발굴 보도자료.
   발표전 2026-08-02 → 발표후 2026-08-20. 전용면적별 중앙 호가(표본 40건↑). 초고가·소표본 제외.
   데이터: scan_v2.py / marquee.py 산출(검증 완료).
Run: python3 design/press/세제개편-호가/make_report_seoul_dynamic.py
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
OUT = HERE / "세제개편_이후_서울아파트_단지별_다이내믹(20260820기준).pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

BLUE = colors.HexColor("#1268D3"); BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC"); INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80"); LINE = colors.HexColor("#C9D6E5")
BOXBG = colors.HexColor("#F4F8FD"); HOTBG = colors.HexColor("#FDF3F2"); UPBG = colors.HexColor("#F0F8F2")
RED = "#C0392B"; GREEN = "#1F7A4D"

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=17, leading=22, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=10.6, textColor=BLUE_DK, leading=16, spaceAfter=9),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12, textColor=INK, spaceBefore=11, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.4, leading=15, textColor=INK, spaceAfter=5),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10, leading=16.5, textColor=INK, spaceAfter=6),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=7.8, leading=11.5, textColor=GRAY, spaceBefore=3, spaceAfter=9),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=8.8, leading=13.8, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.1, leading=10.5, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.4, leading=10.4, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.6, leading=10.4, textColor=INK, alignment=0),
    "tds": ParagraphStyle("tds", fontName="P", fontSize=7.6, leading=9.6, textColor=GRAY, alignment=0),
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
def eok(man): return f"{man/10000:.1f}억"
def epair(b, a): return f"{eok(b)} → <b>{eok(a)}</b>"
def dcell(bm, am):  # 변동액+% 셀
    d = am - bm; p = (am-bm)/bm*100; ad = abs(d)
    txt = f"{ad/10000:.1f}억" if ad >= 10000 else f"{ad:,.0f}만"
    sign = "−" if d < 0 else ("+" if d > 0 else "")
    c = "#5A6B80" if abs(p) < 0.3 else (RED if d < 0 else GREEN)
    return f"<font color='{c}'><b>{sign}{txt}</b><br/><font size=7>({p:+.1f}%)</font></font>"
def ncell(bn, an):
    p = (an-bn)/bn*100
    c = RED if p >= 20 else ("#5A6B80" if abs(p) < 5 else INK.hexval()[2:] if False else "#18233A")
    cc = RED if p >= 20 else ("#1F7A4D" if p <= -10 else "#5A6B80")
    return f"{bn} → <b>{an}</b> <font size=7 color='{cc}'>({p:+.0f}%)</font>"

TBL = [("BACKGROUND",(0,0),(-1,0),BLUE),("GRID",(0,0),(-1,-1),0.4,LINE),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),3),
       ("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(0,-1),5)]

story = []; A = story.append

# ── 표지 ──────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편 ②", "tag"))
A(P("세제개편 이후, <b>서울 아파트 어디가 움직였나</b><br/>대장주는 버텼고 · 신축·대형은 밀렸고 · 매물은 쌓였다", "title"))
A(P("발표 후 2주 반, 잠실·반포 대장주 전용 84㎡ 호가는 대체로 <b>보합</b>으로 버텼다. 반면 "
    "<b>청담르엘·레이크팰리스</b> 등 신축·대형에서 호가가 밀렸고, <b>마포한강아이파크·이촌 한가람</b> 등에선 "
    "매물이 두 배 넘게 쌓였다. 하락은 ‘기존 매도인의 호가 인하’보다 <b>저가 신규 매물 유입·적체</b>에서 왔다.", "sub"))
A(P("발표 2026. 8. 3. 18시　|　서울 아파트 매매 호가　|　발표 전 2026. 8. 2 → 발표 후 2026. 8. 20　|　"
    "전용면적별 중앙 호가(표본 40건↑, 초고가·소표본 제외)　|　자료 콕집(koczip.com)", "cap"))

A(P(
    "<b>어떻게 봤나.</b> 서울 전 단지를 전용면적별로 묶어(표본 40건 이상) 세제 발표 직전(8/02)과 2주 반 뒤(8/20) "
    "<b>중앙 호가</b>를 비교했다. 소수 초고가·소표본(예: 한남더힐 등)은 중앙값이 튀어 <b>제외</b>했고, 단일 매물이 "
    "끌어내린 ‘최저가’ 이벤트도 배제했다. ‘동일 물건(같은 매물번호)’ 변동을 함께 확인해 <b>실제 호가 인하인지, "
    "저가 신규 유입인지</b>를 갈랐다. 수치는 호가(부르는 값)로 실거래가가 아니며, 매물 수는 광고 건수 기준이다.", "lead"))

# ── 1. 대장주 ────────────────────────────────────────────────────────────────
A(P("1. 대장주(전용 84㎡) — 호가는 버텼지만, 매물은 늘기 시작했다", "h"))
MQ = [  # 단지, 구, 전중앙, 후중앙, 전매물, 후매물
    ("잠실 리센츠", "송파", 350000, 350000, 535, 553),
    ("잠실엘스", "송파", 340000, 340000, 555, 650),
    ("잠실 트리지움", "송파", 320000, 320000, 331, 367),
    ("파크리오", "송파", 300000, 300000, 350, 346),
    ("헬리오시티", "송파", 310000, 305000, 800, 909),
    ("아크로리버파크", "서초", 580000, 570000, 250, 244),
    ("래미안퍼스티지", "서초", 530000, 520000, 199, 213),
    ("반포자이", "서초", 480000, 480000, 215, 231),
    ("래미안대치팰리스", "강남", 450000, 442000, 182, 200),
    ("은마(재건축)", "강남", 370000, 365000, 103, 115),
    ("고덕그라시움", "강동", 265000, 265000, 200, 197),
    ("올림픽파크포레온", "강동", 310000, 303000, 508, 599),
]
rows = [hdr(["단지", "구", "중앙 호가 전→후", "변동", "매물(광고) 전→후"])]
for nm, gu, bm, am, bn, an in MQ:
    rows.append([P(f"<b>{nm}</b>", "tdl"), P(gu, "td"), P(epair(bm, am), "td"),
                 P(dcell(bm, am), "td"), P(ncell(bn, an), "td")])
t = Table(rows, colWidths=[40*mm, 15*mm, 36*mm, 27*mm, 42*mm], repeatRows=1)
stt = list(TBL)
for i in range(2, len(MQ)+1, 2): stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(KeepTogether([t]))
A(P("잠실 5총사·반포자이·고덕그라시움은 중앙 호가 <b>보합</b>. 헬리오시티·올림픽파크포레온만 −1.6~−2.3% 소폭 하락. "
    "다만 매물(광고)은 대부분 늘어 — 잠실엘스 +17%, 헬리오시티 +14% — <b>적체가 시작</b>됐다.", "cap"))

# ── 2. 조정 최전선 ────────────────────────────────────────────────────────────
A(P("2. 호가가 실제로 밀린 단지 — 신축·대형이 최전선", "h"))
DROP = [  # 단지, 구, 평형, 전중앙, 후중앙, 전매물, 후매물, 비고
    ("청담르엘", "강남", 84, 600000, 531000, 208, 241, "신축 대단지, 저가 매물 유입(표본 208건)"),
    ("래미안 엘리니티", "동대문", 84, 200000, 180000, 47, 82, "매물 +74% 급증"),
    ("반포센트럴자이", "서초", 84, 550000, 500000, 140, 93, "대형 표본, 중앙 −5억"),
    ("반포써밋", "서초", 84, 430000, 399000, 112, 153, "매물 +37%"),
    ("반포래미안아이파크", "서초", 84, 465000, 400000, 47, 65, "저가 매물 유입(상단 48억 유지)"),
    ("레이크팰리스", "송파", 136, 420000, 380000, 45, 85, "대형, 동일물건도 −4억 · 매물 +89%"),
    ("목동신시가지1단지", "양천", 98, 305000, 285000, 70, 69, "재건축, 동일물건도 −5천"),
]
rows = [hdr(["단지", "구", "전용", "중앙 호가 전→후", "변동", "매물 전→후", "특이사항"])]
for nm, gu, ar, bm, am, bn, an, memo in DROP:
    rows.append([P(f"<b>{nm}</b>", "tdl"), P(gu, "td"), P(f"{ar}", "td"),
                 P(epair(bm, am), "td"), P(dcell(bm, am), "td"),
                 P(f"{bn}→{an}", "td"), P(memo, "tds")])
t = Table(rows, colWidths=[26*mm, 12*mm, 10*mm, 27*mm, 19*mm, 20*mm, 44*mm], repeatRows=1)
stt = list(TBL) + [("BACKGROUND",(0,1),(-1,1),HOTBG),("LINEBEFORE",(0,1),(0,1),2.2,colors.HexColor(RED))]
for i in (3, 5, 7): stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(KeepTogether([t]))
A(P("<b>청담르엘</b>은 표본 208건의 큰 단지인데도 중앙 호가가 60→53.1억으로 밀렸다 — 상단(69억)은 그대로인데 "
    "<b>52~53억대 저가 매물이 대거 유입</b>돼 중앙이 내려앉은 것. <b>레이크팰리스</b>는 동일 물건마저 −4억으로, "
    "기존 매도인까지 호가를 내린 드문 사례다.", "cap"))

# ── 3. 매물 급증 ─────────────────────────────────────────────────────────────
A(P("3. 매물이 두 배 넘게 쌓인 단지 — 다음 하락 압력", "h"))
SURGE = [  # 단지, 구, 평형, 전매물, 후매물, 전중앙, 후중앙
    ("마포한강아이파크", "마포", 59, 51, 127, 175000, 175000),
    ("한가람", "용산(이촌)", 84, 47, 100, 295000, 285000),
    ("올림픽파크포레온", "강동", 59, 98, 175, 279000, 265000),
    ("래미안서초스위트", "서초", 84, 110, 195, 325000, 320000),
    ("올림픽훼밀리타운", "송파", 136, 145, 235, 320000, 315000),
    ("목동신시가지3단지", "양천", 64, 48, 80, 260000, 260000),
]
rows = [hdr(["단지", "구", "전용", "매물(광고) 전→후", "매물 증감", "중앙 호가 전→후"])]
for nm, gu, ar, bn, an, bm, am in SURGE:
    rows.append([P(f"<b>{nm}</b>", "tdl"), P(gu, "td"), P(f"{ar}", "td"),
                 P(f"{bn} → <b>{an}</b>", "td"),
                 P(f"<font color='{RED}'><b>+{(an-bn)/bn*100:.0f}%</b></font>", "td"),
                 P(f"{eok(bm)} → {eok(am)}", "td")])
t = Table(rows, colWidths=[36*mm, 20*mm, 12*mm, 34*mm, 22*mm, 34*mm], repeatRows=1)
stt = list(TBL)
for i in (2, 4, 6): stt.append(("BACKGROUND",(0,i),(-1,i),ROWALT))
t.setStyle(TableStyle(stt))
A(KeepTogether([t]))
A(P("<b>마포한강아이파크(+149%)·이촌 한가람(+113%)</b>은 2주 반 만에 매물이 두 배를 넘겼다. 아직 호가는 "
    "보합~소폭이지만, 매물 적체는 통상 <b>호가 하락의 선행 신호</b>다. 팔려는 값과 사려는 값의 거리가 벌어지고 있다.", "cap"))

# ── 4. 역행 상승 ─────────────────────────────────────────────────────────────
A(P("4. 역행 — 발표 후 오히려 오른 단지", "h"))
RISE = [
    ("휘경해모로프레스티지", "동대문", 84, 142000, 151000, "동일물건도 +9천 — 실제 호가 인상"),
    ("DMC래미안e편한세상", "서대문", 59, 135000, 147000, "매물 그대로인데 호가 상승"),
    ("힐스테이트상도센트럴파크", "동작", 84, 195000, 205000, "매물 −36% 소진되며 강세"),
]
rows = [hdr(["단지", "구", "전용", "중앙 호가 전→후", "변동", "특이사항"])]
for nm, gu, ar, bm, am, memo in RISE:
    rows.append([P(f"<b>{nm}</b>", "tdl"), P(gu, "td"), P(f"{ar}", "td"),
                 P(epair(bm, am), "td"), P(dcell(bm, am), "td"), P(memo, "tds")])
t = Table(rows, colWidths=[38*mm, 16*mm, 10*mm, 28*mm, 20*mm, 46*mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,1),(-1,-1),UPBG)]))
A(KeepTogether([t]))
A(P("도심·비강남 중저가 일부는 발표 후에도 올랐다. 특히 <b>휘경해모로프레스티지</b>는 동일 물건 기준으로도 "
    "호가가 +9,000만원 올라, 실수요가 받치는 지역의 <b>역행 강세</b>를 보여준다.", "cap"))

# ── 종합 ────────────────────────────────────────────────────────────────────
A(box(
    "<b>한 줄 요약 — 세제개편 이후 서울은 ‘차별화 조정’ 국면</b><br/>"
    "<b>① 대장주는 버텼다.</b> 잠실·반포 대장주 전용 84㎡ 호가는 보합~−2%. 심리는 아직 매도 우위다.<br/>"
    "<b>② 하락은 신축·대형에 집중.</b> 청담르엘(−11.5%)·레이크팰리스(−9.5%)·반포 신축들이 최전선. "
    "대부분 ‘저가 신규 매물 유입’이 중앙값을 끌어내렸고, 레이크팰리스·목동은 기존 매도인까지 호가를 내렸다.<br/>"
    "<b>③ 매물 적체가 번지고 있다.</b> 마포한강아이파크·이촌 한가람 등에서 매물이 2배 넘게 쌓였다 — 다음 호가 하락의 선행 신호.<br/>"
    "<b>④ 역행 강세도 있다.</b> 휘경·DMC 등 도심 중저가 실수요 단지는 오히려 올랐다.<br/>"
    "<font color='#5A6B80'>※ 호가(부르는 값) 기준이며 실거래가와는 시차가 있다. 초고가·소표본은 제외했다.</font>"))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>조용호</b>　|　런투온라인　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-4692-4946　albooooza@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=17*mm, bottomMargin=15*mm,
                        title="세제개편 이후 서울 아파트 단지별 다이내믹(8/20 기준)", author="조용호 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
