# -*- coding: utf-8 -*-
"""세제개편 발표 후 서울 아파트 '매물 적체' — 광고 매물수 vs 실매물(중복제거) 보도자료.
   발표 직전(8/1) 대비. 데이터: article_events / parquet 스냅샷. 배포용.
Run: python3 design/press/세제개편-호가/make_report_inventory.py
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
OUT = HERE / "세제개편_후_서울아파트_매물적체_광고vs실매물(20260824기준).pdf"

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
    "title": ParagraphStyle("title", fontName="PX", fontSize=17, leading=22, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=10.6, textColor=BLUE_DK, leading=16, spaceAfter=9),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.5, leading=15, textColor=INK, spaceAfter=5),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10, leading=16.5, textColor=INK, spaceAfter=6),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=7.9, leading=11.6, textColor=GRAY, spaceBefore=3, spaceAfter=9),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.2, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=7.6, leading=9.6, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.1, leading=10, textColor=INK, alignment=2),
    "tdc": ParagraphStyle("tdc", fontName="P", fontSize=8.1, leading=10, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.3, leading=10, textColor=INK, alignment=0),
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
def n(v): return f"{v:,}"
TBL = [("BACKGROUND",(0,0),(-1,0),BLUE),("GRID",(0,0),(-1,-1),0.4,LINE),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),3),
       ("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(0,-1),5)]

story = []; A = story.append

# ── 표지 ──────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트 — 정책편 ③", "tag"))
A(P("세제발표 전후 서울 아파트 매물<br/>광고 매물수와 <b>실매물</b> 비교", "title"))
A(P("서울 20~30억대 아파트 매물은 발표 직전(8/1) 대비 광고 기준 <b>+8.3%</b>, 중복광고를 제거한 실매물 기준 "
    "<b>+11.7%</b> 늘었다. 서울 전체는 광고 +4.0%·실매물 +4.7%, 30억 이상은 +6.4%·+9.0%다. 세 구간 모두 "
    "실매물 증가율이 광고 증가율보다 컸다. 증가분은 8월 셋째 주(8/18→8/22)에 집중됐다. 같은 기간 호가를 "
    "수정한 20~30억 매물의 <b>71~75%가 인하</b>였다.", "sub"))
A(P("기준 <b>서울 아파트 매매 · 활성 매물</b>　|　발표 직전 2026. 8. 1 → 최근 2026. 8. 24　|　"
    "자료 콕집(koczip.com)", "cap"))

A(P(
    "<b>어떻게 봤나.</b> 매일 수집하는 네이버 매물을 두 가지로 센다. <b>①광고 매물수</b>는 올라온 광고 건수, "
    "<b>②실매물</b>은 한 집을 여러 중개사가 올린 <b>중복 광고를 걷어낸 실제 물건 수</b>(같은 주소 공동광고를 "
    "1건으로 환산)다. 주말·공휴일 수집량이 흔들리므로 <b>정상 수집일</b>만 골라 비교했고, 호가 방향은 수집주기에 "
    "강건한 <b>인하:인상 비율</b>로 봤다. 수치는 호가(부르는 값) 기준이며 실거래가가 아니다.", "lead"))

# ── 1. 매물 적체 (광고 vs 실매물) ─────────────────────────────────────────────
A(P("1. 매물 적체 — 광고 매물수 vs 실매물", "h"))
ROWS = [  # 날짜, 구분, 서울광고, 서울실, 20광고, 20실, 30광고, 30실
    ("7/28", "발표 전", 200418, 82046, 34349, 9640, 43499, 17790),
    ("8/01", "발표 직전", 203342, 82677, 35081, 9775, 44195, 17890),
    ("8/11", "발표 후", 203143, 83729, 35237, 10098, 44902, 18557),
    ("8/18", "발표 후", 199790, 83241, 35132, 10263, 44179, 18462),
    ("8/22", "발표 후", 215472, 87819, 38290, 10935, 47555, 19673),
    ("8/24", "발표 후", 211464, 86524, 37998, 10916, 47017, 19505),
]
rows = [[P("날짜","th"), P("구분","th"),
         P("서울 전체<br/>광고","th"), P("서울 전체<br/>실매물","th"),
         P("20~30억<br/>광고","th"), P("20~30억<br/>실매물","th"),
         P("30억↑<br/>광고","th"), P("30억↑<br/>실매물","th")]]
for d, tag, sa, sr, a20, r20, a30, r30 in ROWS:
    rows.append([P(f"<b>{d}</b>","tdc"), P(tag,"tdc"),
                 P(n(sa),"td"), P(f"<b>{n(sr)}</b>","td"),
                 P(n(a20),"td"), P(f"<b>{n(r20)}</b>","td"),
                 P(n(a30),"td"), P(f"<b>{n(r30)}</b>","td")])
t = Table(rows, colWidths=[13*mm, 15*mm, 24*mm, 24*mm, 23*mm, 24*mm, 22*mm, 23*mm], repeatRows=1)
stt = list(TBL) + [("BACKGROUND",(0,2),(-1,2),ROWALT),   # 8/01 발표직전 강조선
                   ("LINEBELOW",(0,2),(-1,2),1.1,BLUE),
                   ("BACKGROUND",(0,5),(-1,5),HOTBG)]      # 8/22 고점
t.setStyle(TableStyle(stt))
A(KeepTogether([t]))
A(P("굵은 값이 <b>실매물</b>(중복광고 제거). 파란 선 위 두 줄이 발표 전, 아래가 발표 후. 붉은 줄(8/22)이 "
    "적체 고점. ‘실매물’은 같은 집을 여러 중개사가 올린 광고를 1건으로 합친 실제 물건 수다.", "cap"))

# ── 2. 발표 직전 → 최근 증감 ──────────────────────────────────────────────────
A(P("2. 발표 직전(8/1) → 최근(8/24) 증감 — 실매물이 광고보다 더 늘었다", "h"))
DIFF = [("서울 전체","+4.0%","+4.7%"), ("20~30억","+8.3%","+11.7%"), ("30억 이상","+6.4%","+9.0%")]
rows = [[P("구간","th"), P("광고 매물수 증감","th"), P("실매물(물건) 증감","th")]]
for label, ga, gr in DIFF:
    hot = "20~30" in label
    rows.append([P(f"<b>{label}</b>","tdl"),
                 P(f"<font color='{RED}'>{ga}</font>","tdc"),
                 P(f"<font color='{RED}'><b>{gr}</b></font>","tdc")])
t = Table(rows, colWidths=[40*mm, 64*mm, 64*mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL) + [("BACKGROUND",(0,2),(-1,2),HOTBG),
                                   ("LINEBEFORE",(0,2),(0,2),2.2,colors.HexColor(RED))]))
A(KeepTogether([t]))
A(box(
    "<b>광고 매물수와 실매물 증감 (8/1 → 8/24)</b><br/>"
    f"· 20~30억: 광고 <font color='{RED}'>+8.3%</font>, 실매물 <font color='{RED}'>+11.7%</font>. "
    "서울 전체: 광고 +4.0%, 실매물 +4.7%. 30억↑: 광고 +6.4%, 실매물 +9.0%. 세 구간 모두 실매물 증가율이 "
    "광고 증가율보다 컸다.<br/>"
    "· 물건 1개당 광고 수(8/24): 20~30억 약 <b>3.6개</b>, 30억↑ 2.5개, 서울 평균 2.4개.<br/>"
    "· 시점: 20~30억 실매물은 8/11 10,098 · 8/18 10,263 · <b>8/22 10,935</b> · 8/24 10,916. 증가분은 "
    "8월 셋째 주(8/18→8/22)에 집중됐다."))

# ── 3. 호가 방향 ─────────────────────────────────────────────────────────────
A(P("3. 호가 수정 — 인하 vs 인상 (서울 20~30억)", "h"))
PC = [("~8/04",377,188,"67%","7,236"), ("~8/11",586,197,"75%","6,669"),
      ("~8/18",559,214,"72%","6,233"), ("~8/25",578,238,"71%","5,928")]
rows = [[P("주(週)","th"), P("호가 인하","th"), P("호가 인상","th"), P("인하 비중","th"), P("평균 인하폭","th")]]
for wk, dn, up, ratio, avg in PC:
    rows.append([P(f"<b>{wk}</b>","tdc"),
                 P(f"<font color='{RED}'>{n(dn)}</font>","tdc"), P(n(up),"tdc"),
                 P(f"<font color='{RED}'><b>{ratio}</b></font>","tdc"), P(f"{avg}만","tdc")])
t = Table(rows, colWidths=[28*mm, 30*mm, 30*mm, 30*mm, 30*mm], repeatRows=1)
t.setStyle(TableStyle(list(TBL)))
A(KeepTogether([t]))
A(P("서울 20~30억 매매 매물 중 호가를 수정한 건의 인하·인상 건수. 4주 연속 인하가 인상보다 많았다"
    "(인하 비중 67~75%). 인하 비중은 8/11 75% 이후 71%, 평균 인하폭은 7,236만원에서 5,928만원으로 낮아졌다.", "cap"))

# ── 종합 ────────────────────────────────────────────────────────────────────
A(box(
    "<b>요약 (사실)</b><br/>"
    "· 발표 직전(8/1) → 최근(8/24) 20~30억 매물: 광고 <b>+8.3%</b>, 실매물 <b>+11.7%</b>.<br/>"
    "· 서울 전체 광고 +4.0%·실매물 +4.7%, 30억↑ 광고 +6.4%·실매물 +9.0%. 세 구간 모두 실매물 증가율이 광고 증가율보다 컸다.<br/>"
    "· 20~30억 실매물 증가는 8월 셋째 주(8/18 10,263 → 8/22 10,935)에 집중. 8/22 10,935가 최고, 8/24 10,916.<br/>"
    "· 호가를 수정한 20~30억 매물의 <b>71~75%가 인하</b>(4주 연속). 평균 인하폭 7,236만 → 5,928만원.<br/>"
    "<font color='#5A6B80'>※ 호가(부르는 값) 기준, 실거래가 아님. 이탈 매물은 매도완료·회수·만료가 섞여 있어 구분 불가. 실거래 신고는 30일 지연. 주말·공휴일은 수집량이 달라 정상수집일만 비교했다.</font>"))

A(KeepTogether([
    Spacer(1, 8),
    P("작성 <b>조용호</b>　|　런투온라인　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-4692-4946　albooooza@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=17*mm, bottomMargin=15*mm,
                        title="세제개편 후 서울 아파트 매물 적체 광고vs실매물(8/24 기준)", author="조용호 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
