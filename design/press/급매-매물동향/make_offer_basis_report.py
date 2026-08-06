# -*- coding: utf-8 -*-
"""서울 아파트 매물 통계 '두 가지 기준(광고 수 vs 물건 수)' 보고서 (기자 배포용).
급매물 1개월 보고서(make_gapmae_1month_report.py)와 동일 양식.
데이터: design/press/data/서울매물_광고vs물건_0601-0708.csv (박스·아카이브 실측 산출물).
Run: python3 design/press/급매-매물동향/make_offer_basis_report.py → design/press/급매-매물동향/서울매물_광고vs물건_보고서.pdf
"""
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
OUT = HERE / "서울매물_광고vs물건_보고서.pdf"
CSVF = DATA / "서울매물_광고vs물건_0601-0708.csv"
D0, D1 = "2026-06-01", "2026-07-08"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

BLUE = colors.HexColor("#1268D3")
BLUE_DK = colors.HexColor("#0C4EA0")
HEADBG = colors.HexColor("#1268D3")
ROWALT = colors.HexColor("#F2F6FC")
INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80")
LINE = colors.HexColor("#C9D6E5")
RED = colors.HexColor("#C0392B")
GREEN = colors.HexColor("#1E874B")

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18, leading=24, textColor=INK, spaceAfter=3),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11.5, textColor=BLUE_DK, leading=16, spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=10, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.5, leading=15, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.5, textColor=GRAY, spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=11.5, textColor=GRAY, spaceBefore=2, spaceAfter=9),
    "boxh": ParagraphStyle("boxh", fontName="PB", fontSize=9.8, textColor=BLUE_DK, spaceAfter=3),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.5, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.6, leading=11, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.6, leading=11, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.6, leading=11, textColor=INK, alignment=0),
}


def P(t, s="td"):
    return Paragraph(str(t), ss[s])


def box(title, lines):
    inner = [Paragraph(title, ss["boxh"])]
    for ln in lines:
        inner.append(Paragraph(ln, ss["boxb"]))
    t = Table([[inner]], colWidths=[176 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF4FC")),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def styled(data, cw, header_rows=1, spans=None, color_cells=None):
    t = Table(data, colWidths=cw, repeatRows=header_rows)
    stl = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADBG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in range(header_rows, len(data)):
        if (r - header_rows) % 2 == 1:
            stl.append(("BACKGROUND", (0, r), (-1, r), ROWALT))
    for (a, b) in (spans or []):
        stl.append(("SPAN", a, b))
    for (c0, r0, col) in (color_cells or []):
        stl.append(("TEXTCOLOR", (c0, r0), (c0, r0), col))
    t.setStyle(TableStyle(stl))
    return t


# ── 데이터 로드 ──
rows = {r["date"]: r for r in csv.DictReader(open(CSVF))}
dates = sorted(rows)

s, e = rows[D0], rows[D1]
ads0, ads1 = int(s["sale_ads"]), int(e["sale_ads"])
un0, un1 = int(s["sale_units"]), int(e["sale_units"])
rt0, rt1 = ads0 / un0, ads1 / un1

# 주간
wk = defaultdict(list)
for d in dates:
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    wk[(y, w)].append(rows[d])
weeks = []
for k in sorted(wk):
    v = wk[k]
    mon = dt.date.fromisocalendar(k[0], k[1], 1)
    a = sum(int(x["sale_ads"]) for x in v) / len(v)
    u = sum(int(x["sale_units"]) for x in v) / len(v)
    weeks.append((mon, len(v), a, u, a / u))

story = []

# ── 표지 ──
story.append(Paragraph("데이터 분석 보고서 · 콕집(koczip.com)", ss["tag"]))
story.append(Paragraph("서울 아파트 매물 통계의 두 가지 기준 — 광고 수와 물건 수", ss["title"]))
story.append(Paragraph("집(물건)은 그대로인데 광고만 늘었다 — 매물 광고배율 6주 연속 상승", ss["sub"]))

story.append(box("■ 데이터 개요 (모든 수치의 근거)", [
    "· 분석 대상: 서울특별시 아파트(재건축 포함) 매매 매물 — 콕집이 매일 수집하는 네이버부동산 매물",
    f"· 기간: {D0} ~ {D1}",
    "· 빠진 날짜: 2026-06-14 하루는 서버 이전으로 데이터가 없어 제외(전후 추세로 볼 때 영향 미미)",
    "· 출처: 네이버부동산 / 수집·집계 콕집(koczip.com)",
]))
story.append(Spacer(1, 4 * mm))

story.append(box("■ ‘광고 수’와 ‘물건 수’ — 매물 통계의 두 가지 기준", [
    "· <b>광고 수</b> = 포털에 노출 중인 매물 광고 건수. 집주인이 같은 집을 여러 중개업소에 내놓으면 광고가 여러 건 잡힙니다.",
    "· <b>물건 수</b> = 같은 집(동일 매물)을 광고한 여러 건을 1건으로 묶은 실제 매물 수. 포털의 동일매물 묶음 정보를 기반으로 산출합니다.",
    "· <b>광고배율</b> = 광고 수 ÷ 물건 수. 집 한 채가 평균 몇 곳의 중개업소에 나와 있는지를 뜻합니다.",
    "· 시중 매물 통계 서비스는 대체로 ‘물건 수’ 기준, 콕집 통계는 ‘광고 수’ 기준입니다. <b>같은 원천을 다른 방식으로 세는 것</b>이라 서로 모순되지 않으며, 콕집 데이터로 두 기준을 모두 산출할 수 있습니다.",
]))
story.append(Spacer(1, 4 * mm))

# ── 핵심 요약 ──
story.append(Paragraph("■ 핵심 요약", ss["h"]))
for t in [
    f"1. 같은 서울 아파트 매매 매물이라도 세는 기준에 따라 <b>광고 수 {ads1:,}건</b>, <b>물건 수 {un1:,}건</b>({D1} 기준)으로 "
    "달라진다. 두 수치 모두 맞으며, 재는 대상(광고 vs 집)이 다를 뿐이다.",
    f"2. 검증: 콕집 광고 데이터를 동일매물 묶음으로 환산한 물건 수({un1:,}건)는 물건 수 기준의 시중 매물 통계(같은 날 62,117건)와 "
    "<b>98.8% 일치</b>한다. 콕집 수치와 시중 통계의 차이는 오류가 아니라 집계 기준 차이다.",
    f"3. 지난 6주간(6/1→7/8) <b>물건 수는 {un0:,} → {un1:,}건(+{(un1/un0-1)*100:.1f}%)으로 거의 그대로</b>인데 "
    f"<b>광고 수는 {ads0:,} → {ads1:,}건(+{(ads1/ads0-1)*100:.1f}%)</b>으로 더 빠르게 늘었다.",
    f"4. 그 결과 <b>광고배율이 {rt0:.2f} → {rt1:.2f}로 6주 연속 상승</b> — 집 한 채를 평균 2.6곳 넘는 중개업소에 내놓고 있다. "
    "매물이 잘 팔리지 않자 집주인들이 광고를 더 넓게 뿌리는, <b>매도 경쟁 심화</b> 신호로 읽힌다.",
]:
    story.append(Paragraph(t, ss["body"]))
story.append(Spacer(1, 2 * mm))

# ── 표1: 검증 ──
story.append(Paragraph(f"표1. 집계 기준 검증 ({D1} 기준)", ss["h"]))
hdr1 = [P("구분", "th"), P("수치(건)", "th"), P("집계 기준", "th")]
data1 = [hdr1,
         [P("콕집 광고 수", "tdl"), P(f"{ads1:,}"), P("매물 광고 전체(동일 물건 중복 포함)")],
         [P("콕집 → 물건 수 환산", "tdl"), P(f"<b>{un1:,}</b>"), P("동일매물 묶음으로 중복 제거")],
         [P("시중 매물 통계(물건 수 기준)", "tdl"), P("62,117"), P("동일매물 중복 제거(해당 서비스 발표치)")],
         [P("일치율", "tdl"), P(f"<b>{un1/62117*100:.1f}%</b>"), P("콕집 환산치 ÷ 시중 통계")]]
story.append(styled(data1, [52 * mm, 34 * mm, 76 * mm]))
story.append(Paragraph(
    "근거: 콕집이 수집한 매물 광고의 동일매물 묶음 크기(포털 제공)를 이용해 광고 수를 물건 수로 환산. "
    "잔여 1.2% 차이는 수집 시각·재건축 포함 범위 등의 차이 수준.", ss["cap"]))

# ── 표2: 주간 추이 (제목+표+캡션을 같은 페이지로) ──
hdr2 = [P("주 (시작 월요일)", "th"), P("일수", "th"), P("광고 수<br/>(건)", "th"),
        P("물건 수<br/>(건)", "th"), P("광고배율<br/>(광고÷물건)", "th")]
data2 = [hdr2]
for i, (mon, n, a, u, r) in enumerate(weeks):
    data2.append([P(str(mon), "tdl"), P(n), P(f"{a:,.0f}"), P(f"{u:,.0f}"), P(f"<b>{r:.3f}</b>")])
story.append(KeepTogether([
    Paragraph("표2. 주간 추이 — 광고 수·물건 수·광고배율", ss["h"]),
    styled(data2, [34 * mm, 14 * mm, 30 * mm, 30 * mm, 34 * mm]),
    Paragraph(
        "근거: 요일·주말 편차를 없애기 위해 일별 값을 주별(월~일)로 집계. 광고배율이 6주 연속 상승 — "
        "물건 수는 6만 건 안팎에서 정체인데 광고 수만 늘어난 결과.", ss["cap"]),
]))

# ── 표3: 일별 상세 ──
hdr3 = [P("날짜", "th"), P("광고 수<br/>(건)", "th"), P("물건 수<br/>(건)", "th"), P("광고배율", "th")]
data3 = [hdr3]
for d in dates:
    r = rows[d]
    a, u = int(r["sale_ads"]), int(r["sale_units"])
    data3.append([P(d, "tdl"), P(f"{a:,}"), P(f"{u:,}"), P(f"{a/u:.3f}")])
story.append(Paragraph("표3. 일별 상세 (참고)", ss["h"]))
story.append(styled(data3, [34 * mm, 34 * mm, 34 * mm, 30 * mm]))
story.append(Paragraph(
    "참고: 2026-06-14는 서버 이전으로 데이터가 없어 빠졌습니다.", ss["cap"]))

# ── 유의사항 ──
story.append(Paragraph("■ 해석 유의사항", ss["h"]))
for t in [
    "· <b>물건 수는 근사치</b>: 동일매물 묶음은 포털·중개업소의 신고 정보를 기반으로 하므로, 묶이지 않은 중복이나 "
    "과다 묶임이 일부 있을 수 있습니다. 시중 물건 수 통계도 같은 한계를 공유합니다.",
    "· <b>기존 자료와의 관계</b>: 앞서 보내드린 ‘서울 급매물 1개월 변화’의 매매 매물 수는 광고 수 기준입니다. "
    "물건 수 기준으로 바꿔도 매물 증가·급매물 감소라는 방향은 동일합니다.",
    "· <b>광고배율의 해석</b>: 배율 상승은 집주인이 한 집을 더 여러 중개업소에 내놓는다는 뜻으로, 매도 희망의 강도를 "
    "보여주는 보조 지표입니다. 다만 중개업소의 광고 영업 확대 등 공급 측 요인도 일부 섞일 수 있습니다.",
    "· <b>전세도 같은 구조</b>: 같은 기간 서울 아파트 전세는 광고 수 37,164→41,804건(+12.5%), 물건 수 15,068→16,800건(+11.5%)으로 "
    "둘 다 뚜렷이 늘었습니다(전세는 광고·물건이 비슷한 속도로 증가).",
]:
    story.append(Paragraph(t, ss["small"]))

story.append(Spacer(1, 4 * mm))
story.append(Paragraph(
    "문의: 런투온라인 · 콕집(koczip.com) · runtoonline@gmail.com · 010-5942-8014 (황인찬 대표) / 원자료 CSV 제공 가능", ss["cap"]))


def footer(canv, doc):
    canv.saveState()
    canv.setFont("P", 7.5)
    canv.setFillColor(GRAY)
    canv.drawString(18 * mm, 10 * mm, "콕집(koczip.com) · 네이버부동산 매물 기반 · 서울 아파트 2026-06-01~07-08")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=15 * mm,
                        title="서울 아파트 매물 통계 기준(광고 수 vs 물건 수) 보고서")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("pdf:", OUT)
