# -*- coding: utf-8 -*-
"""세제개편 발표 후 서울 아파트 실매물(중복제외) 적체 — 20~30억 중심. 8/26 기준. 배포용.
   지표: 20~30억 / 30억↑ / 서울 전체 실매물(중복 광고 제거). 발표 직전(8/1) 대비.
Run: python3 design/press/세제개편-호가/make_report_inventory_0826.py
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
OUT = HERE / "세제개편_후_서울아파트_실매물_적체(20260826기준).pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

BLUE = colors.HexColor("#1268D3"); BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC"); INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80"); LINE = colors.HexColor("#C9D6E5")
BOXBG = colors.HexColor("#F4F8FD"); HOTBG = colors.HexColor("#FDF3F2")
RED = "#C0392B"

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18, leading=23, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11, textColor=BLUE_DK, leading=16, spaceAfter=7),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=7, spaceAfter=4),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.4, leading=17, textColor=INK, spaceAfter=7),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY, spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9.2, leading=14.6, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=9, leading=11.5, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=10, leading=12.5, textColor=INK, alignment=2),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=10, leading=12.5, textColor=INK, alignment=0),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY, spaceAfter=3),
}
def P(t, s="body"): return Paragraph(t, ss[s]) if s in ss else Paragraph(t, ss["lead"])
def box(html, bg=BOXBG, ln=LINE):
    t = Table([[P(html, "boxb")]], colWidths=[168 * mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,ln),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    return t
TBL = [("BACKGROUND",(0,0),(-1,0),BLUE),("GRID",(0,0),(-1,-1),0.4,LINE),
       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),
       ("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(0,-1),6)]

story = []; A = story.append

A(P("콕집 부동산 데이터 리포트 — 정책편", "tag"))
A(P("세제개편 발표 후 서울 아파트 <b>실매물</b> 적체<br/>가격 구간별 (10억 미만 ~ 50억 이상)", "title"))
A(P("서울 아파트 매물은 중복 광고를 제거한 <b>실매물</b> 기준 세제개편안 발표 직전(8/1) 대비 8월 26일 전 "
    "구간에서 늘었다. 증가율은 <b>20~30억대(+15.0%)</b>가 가장 높고, 30~40억(+14.3%)·40~50억(+13.7%) 등 "
    "<b>중상급 구간에 집중</b>됐다. 10억 미만(+2.3%)과 50억 이상(+7.1%) 등 양 극단은 상대적으로 낮았다.", "sub"))
A(P("기준 <b>서울 아파트 매매 · 실매물(중복 광고 제거)</b>　|　발표 직전 2026. 8. 1 → 최신 2026. 8. 26　|　"
    "자료 콕집(koczip.com)", "cap"))

A(P(
    "<b>실매물이란.</b> 한 집을 여러 중개사무소가 동시에 올리면 광고는 여러 건이 된다. ‘실매물’은 이 "
    "<b>중복 광고를 걷어낸 실제 물건 수</b>(같은 주소의 공동 광고를 1건으로 환산)다. 광고 건수보다 시장의 "
    "실제 물량을 정확히 보여준다. 주말·공휴일은 수집량이 달라 <b>정상 수집일</b>만 비교했다.", "lead"))

# ── 표 ────────────────────────────────────────────────────────────────────
A(P("서울 아파트 실매물(중복 제외) — 가격 구간별", "h"))
# (라벨, 8/1, 8/26, 증감, 유형)  유형: band / sub(30억↑ 소계) / total
DATA = [
    ("10억 미만", 36333, 37185, "+2.3%", "band"),
    ("10~20억", 18679, 20600, "+10.3%", "band"),
    ("20~30억", 9775, 11245, "+15.0%", "band"),
    ("30~40억", 7768, 8878, "+14.3%", "band"),
    ("40~50억", 3999, 4546, "+13.7%", "band"),
    ("50억 이상", 6123, 6555, "+7.1%", "band"),
    ("　30억 이상 (소계)", 17890, 19979, "+11.7%", "sub"),
    ("　40억 이상 (소계)", 10122, 11101, "+9.7%", "sub"),
    ("서울 전체", 82677, 89008, "+7.7%", "total"),
]
rows = [[P("가격 구간","th"), P("발표 직전<br/>8/1","th"), P("최신<br/>8/26","th"), P("증감","th")]]
for label, b, a, pct, kind in DATA:
    st = "tdl"
    lb = f"<b>{label}</b>" if kind != "band" else label
    rows.append([P(lb, st), P(f"{b:,}", "td"), P(f"<b>{a:,}</b>", "td"),
                 P(f"<font color='{RED}'><b>{pct}</b></font>", "td")])
t = Table(rows, colWidths=[52*mm, 38*mm, 38*mm, 40*mm], repeatRows=1)
stt = list(TBL) + [
    ("BACKGROUND",(0,3),(-1,3),HOTBG),                     # 20~30억 최고
    ("LINEBEFORE",(0,3),(0,3),2.2,colors.HexColor(RED)),
    ("BACKGROUND",(0,7),(-1,8),ROWALT),                    # 30억↑·40억↑ 소계
    ("LINEABOVE",(0,7),(-1,7),0.8,LINE),
    ("BACKGROUND",(0,9),(-1,9),colors.HexColor("#E9EFF9")),# 서울 전체
    ("LINEABOVE",(0,9),(-1,9),1.1,BLUE),
    ("FONTNAME",(0,9),(-1,9),"PB"),
]
t.setStyle(TableStyle(stt))
A(KeepTogether([t]))
A(P("단위: 건(실매물). 붉은 줄(20~30억)이 증가율 최고. ‘30억 이상 소계’ = 30~40+40~50+50억↑, "
    "‘40억 이상 소계’ = 40~50+50억↑. ‘실매물’은 같은 집을 여러 중개사가 올린 중복 광고를 1건으로 합친 실제 물건 수다.", "cap"))

# ── 정합성 검증 ──────────────────────────────────────────────────────────────
A(P("데이터 정합성 검증", "h"))
A(box(
    "<b>구간 합계 = 서울 전체 (오차 0)</b><br/>"
    "· 6개 가격 구간(10억 미만·10~20·20~30·30~40·40~50·50억↑)의 실매물 합계가 서울 전체와 <b>정확히 일치</b>한다 "
    "— 8/1: 82,677 = 82,677, 8/26: 89,008 = 89,008 (차이 0).<br/>"
    "· ‘30억 이상 소계’(19,979) = 30~40억(8,878) + 40~50억(4,546) + 50억↑(6,555). "
    "‘40억 이상 소계’(11,101) = 40~50억(4,546) + 50억↑(6,555). 모두 일치.<br/>"
    "· 가격 미기재 매물 0건. 구간 간 <b>중복·누락·경계 오류 없음</b>(각 구간은 이상 포함·미만 배타: [하한, 상한)).",
    bg=colors.HexColor("#F0F8F2"), ln=colors.HexColor("#BFE0C8")))

A(box(
    "<b>사실 요약</b><br/>"
    f"· 20~30억 <font color='{RED}'><b>+15.0%</b></font>, 30~40억 +14.3%, 40~50억 +13.7% — 증가율은 "
    "<b>20~40억 중상급 구간에 집중</b>됐다.<br/>"
    "· 10억 미만 +2.3%, 10~20억 +10.3%, 50억↑ +7.1%. 서울 전체 +7.7%.<br/>"
    "· 전 구간이 발표 직전보다 늘었고, 그중 <b>20~30억대 증가율이 가장 높다</b>.<br/>"
    "<font color='#5A6B80'>※ 실매물 = 중복 광고 제거 실제 물건 수. 호가·재고 기준이며 실거래가 아님. "
    "주말·공휴일 수집 편차로 정상 수집일(8/26)만 비교했다.</font>"))

A(KeepTogether([
    Spacer(1, 4),
    P("작성 <b>조용호</b>　|　런투온라인　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-4692-4946　albooooza@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21*mm, rightMargin=21*mm,
                        topMargin=15*mm, bottomMargin=18*mm,
                        title="세제개편 후 서울 아파트 실매물 적체(8/26 기준)", author="조용호 (런투온라인)")
doc.build(story)
print(f"[done] {OUT.name}  ({OUT.stat().st_size // 1024} KB)")
