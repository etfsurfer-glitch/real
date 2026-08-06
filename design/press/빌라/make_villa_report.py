# -*- coding: utf-8 -*-
"""특별시·광역시 빌라(연립·다세대) 매물 분석 보고서 (기자 배포용).
아파트 매물급매보고서(make_maemul_report.py)와 동일 양식 — 빌라는 매물에 건물명이
공개되지 않아 '급매 판정' 대신 ①중간 호가 vs 중간 실거래가(호가 프리미엄)
②실거래 급매율(국토부 같은 건물끼리, 아파트 보고서와 동일 기준)로 구성.
Run: python3 design/press/빌라/make_villa_report.py → design/press/빌라/빌라매물보고서_특별시광역시.pdf
"""
import csv
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data" / "villa"
OUT = HERE / "빌라매물보고서_특별시광역시.pdf"
SNAP = "2026-07-13"

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
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=10.5, textColor=colors.white, alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.3, leading=10.5, textColor=INK, alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.3, leading=10.5, textColor=INK, alignment=0),
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


def styled(data, cw, header_rows=1, spans=None, warn_cells=None):
    t = Table(data, colWidths=cw, repeatRows=header_rows)
    stl = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADBG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in range(header_rows, len(data)):
        if (r - header_rows) % 2 == 1:
            stl.append(("BACKGROUND", (0, r), (-1, r), ROWALT))
    for (a, b) in (spans or []):
        stl.append(("SPAN", a, b))
    for (c0, r0) in (warn_cells or []):
        stl.append(("TEXTCOLOR", (c0, r0), (c0, r0), RED))
    t.setStyle(TableStyle(stl))
    return t


def short(s):
    return s.replace("특별시", "").replace("광역시", "")


# ── 데이터 로드 ──
region = [r for r in csv.DictReader(open(DATA / "빌라_지역요약.csv")) if r["매매매물"] != "0"]
grid = list(csv.DictReader(open(DATA / "빌라_지역평형_grid.csv")))
rh = list(csv.DictReader(open(DATA / "빌라_실거래급매_동일기준.csv")))
trend = list(csv.DictReader(open(DATA / "빌라_매물수추이.csv")))

tot_sale = sum(int(r["매매매물"]) for r in region)
tot_js = sum(int(r["전세매물"]) for r in region)
tot_ws = sum(int(r["월세매물"]) for r in region)
seoul = next(r for r in region if r["지역"] == "서울특별시")
CITY6 = [r["지역"] for r in region]
t0, t1 = trend[0], trend[-1]
sum6_0 = sum(int(t0[c]) for c in CITY6)
sum6_1 = sum(int(t1[c]) for c in CITY6)
chg6 = (sum6_1 - sum6_0) / sum6_0 * 100
chg_seoul = (int(t1["서울특별시"]) - int(t0["서울특별시"])) / int(t0["서울특별시"]) * 100
rh_seoul = next(r for r in rh if r["지역"] == "서울특별시")

story = []

# ── 표지 ──
story.append(Paragraph("데이터 분석 보고서 · 콕집(koczip.com)", ss["tag"]))
story.append(Paragraph("특별시·광역시 빌라(연립·다세대) 매물 분석", ss["title"]))
story.append(Paragraph("빌라 호가는 실거래보다 위에서 시작한다 — 서울 +11%, 지방은 최대 +47%", ss["sub"]))

story.append(box("■ 데이터 개요 (모든 수치의 근거)", [
    "· 분석 대상: 콕집 수집 네이버부동산 <b>빌라(연립·다세대) 매물</b> — 서울·부산·대구·인천·대전·울산 6개 시"
    " (광주는 현재 빌라 매물 수집 대상이 아니어서 제외)",
    f"· 기준 시점: {SNAP} 기준, 그날 노출 중인 빌라 매물 — 매매 {tot_sale:,}건 · 전세 {tot_js:,}건 · 월세 {tot_ws:,}건",
    "· 가격 기준선: 국토교통부 연립·다세대 매매 실거래(최근 180일, 공인중개사 거래, 계약해제 건 제외, 지상층)",
    "· 출처: 네이버부동산(매물)·국토교통부 실거래가 공개시스템(기준값) / 수집·연결·집계 콕집(koczip.com)",
]))
story.append(Spacer(1, 5 * mm))

story.append(box("■ 산출 방법 — 빌라는 아파트와 무엇이 다른가", [
    "· 빌라 매물에는 <b>건물 이름이 공개되지 않아</b>(개인정보 보호) 아파트처럼 매물을 특정 건물의 실거래와 1:1로 연결할 수 없습니다.",
    "· 그래서 이 보고서는 <b>같은 지역·같은 평형대</b>의 ①<b>매물 중간 호가</b>와 ②<b>실거래 중간 가격</b>을 비교해 "
    "‘<b>호가 프리미엄</b>(내놓는 값이 팔린 값보다 몇 % 위인가)’을 계산합니다. 중간값끼리 비교라 특정 신축·고가 매물에 휘둘리지 않습니다.",
    "· <b>실거래 급매율</b>은 국토부 실거래 안에서 <b>같은 건물끼리</b> 비교(같은 건물·비슷한 면적의 다른 거래 중간값보다 10% 이상 싼 거래) — "
    "콕집 아파트 급매 보고서와 같은 기준입니다.",
    "· 지하·반지하 매물과 거래는 가격 통계에서 제외(비교 왜곡 방지). 평형대는 전용면적 20/40/60/85㎡ 구간.",
]))
story.append(Spacer(1, 5 * mm))

# ── 핵심 요약 ──
story.append(Paragraph("■ 핵심 요약", ss["h"]))
for t in [
    f"1. 6개 시에서 지금 팔겠다고 내놓은 빌라는 <b>매매 {tot_sale:,}건</b> — 서울이 {int(seoul['매매매물']):,}건으로 3분의 2를 차지한다. "
    f"전세 매물은 {tot_js:,}건으로 매매의 5분의 1 수준이고, 서울 밖에서는 빌라 전세 매물 자체가 드물다(부산 865·대구 161·울산 48건).",
    f"2. <b>빌라 호가는 실거래보다 위에서 시작한다</b>: 서울은 중간 호가 {seoul['매물중위호가억']}억 vs 실거래 중간 {seoul['실거래중위억(180일)']}억으로 "
    f"<b>+{seoul['호가프리미엄%']}%</b>. 지방은 격차가 더 커서 인천 +31.1%, 대전 +32.5%, <b>울산 +46.6%</b> — "
    "빌라를 내놓는 값과 실제 팔리는 값의 거리가 지방일수록 멀다.",
    "3. 서울에서 호가와 실거래가 가장 밀착한 구간은 <b>전용 20~40㎡(+4.8%)</b> — 거래가 가장 활발한 실수요 구간이다. "
    "반대로 전세가율(호가 기준)은 <b>전용 60~85㎡에서 91.8%</b>까지 올라, 전세가가 매매 호가의 9할을 넘는 ‘깡통 경계’ 구간이 존재한다.",
    f"4. 실거래 안에서 같은 건물 시세보다 10% 이상 싸게 팔린 ‘실거래 급매’는 서울 <b>{rh_seoul['급매율%']}%</b> — "
    "아파트 실거래 급매율(서울 1.26%, 콕집 아파트 보고서와 동일 기준)의 <b>약 8배</b>다. 빌라는 계약 단계에서 값이 훨씬 크게 꺾인다.",
    f"5. 매물 수는 수집 기간(6/21~7/13) 23일간 6개 시 합계 {sum6_0:,}건 → {sum6_1:,}건(<b>{chg6:+.1f}%</b>), "
    f"서울 {chg_seoul:+.1f}%로 완만한 감소 흐름이다.",
]:
    story.append(Paragraph(t, ss["body"]))
story.append(Spacer(1, 3 * mm))

# ── 표1: 지역 요약 ──
story.append(Paragraph("표1. 지역별 빌라 매물 요약 — 매물수·중간 호가·호가 프리미엄", ss["h"]))
hdr1 = [P("지역", "th"), P("매매 매물<br/>(건)", "th"), P("전세 매물<br/>(건)", "th"), P("월세 매물<br/>(건)", "th"),
        P("중간 호가<br/>(억원)", "th"), P("실거래 중간<br/>(억원, 180일)", "th"), P("호가 프리미엄<br/>(%)", "th")]
data1 = [hdr1]
for r in region:
    data1.append([P(short(r["지역"]), "tdl"), P(f"{int(r['매매매물']):,}"), P(f"{int(r['전세매물']):,}"),
                  P(f"{int(r['월세매물']):,}"), P(r["매물중위호가억"]), P(r["실거래중위억(180일)"]),
                  P(f"<b>+{r['호가프리미엄%']}</b>")])
data1.append([P("합계", "tdl"), P(f"{tot_sale:,}"), P(f"{tot_js:,}"), P(f"{tot_ws:,}"), P("—"), P("—"), P("—")])
story.append(styled(data1, [24 * mm, 24 * mm, 22 * mm, 22 * mm, 22 * mm, 28 * mm, 26 * mm]))
story.append(Paragraph(
    f"근거: {SNAP} 콕집 매물 기준. ‘호가 프리미엄’ = (매물 중간 호가 − 실거래 중간 가격) ÷ 실거래 중간 가격. "
    "중간값끼리의 비교로, 개별 매물이 그만큼 비싸다는 뜻이 아니라 매물군과 거래군의 가격 수준 차이를 뜻함.", ss["cap"]))

# ── 표2: 지역 × 평형 ──
story.append(Paragraph("표2. 지역 × 평형 — 매물수·호가 프리미엄·전세가율", ss["h"]))
hdr2 = [P("지역", "th"), P("평형(전용)", "th"), P("매매 매물<br/>(건)", "th"), P("중간 호가<br/>(억)", "th"),
        P("실거래<br/>(건, 180일)", "th"), P("실거래 중간<br/>(억)", "th"), P("호가 프리미엄<br/>(%)", "th"),
        P("전세 중간<br/>(억)", "th"), P("전세가율<br/>(%, 호가)", "th")]
data2 = [hdr2]
warn2 = []
for r in grid:
    ri = len(data2)
    prem = f"+{r['호가프리미엄%']}" if r["호가프리미엄%"] else "—"
    jr = r["전세가율%(호가기준)"] or "—"
    data2.append([P(short(r["지역"]), "tdl"), P(r["평형"]), P(f"{int(r['매매매물']):,}"), P(r["매물중위호가억"]),
                  P(f"{int(r['실거래건수180일']):,}"), P(r["실거래중위억"] or "—"), P(f"<b>{prem}</b>"),
                  P(r["전세중위억"] or "—"), P(jr)])
    if r["호가프리미엄%"] and int(r["실거래건수180일"]) < 100:
        warn2.append((6, ri))
    if jr != "—" and float(jr) >= 85:
        warn2.append((8, ri))
story.append(styled(data2, [17 * mm, 19 * mm, 19 * mm, 18 * mm, 20 * mm, 20 * mm, 23 * mm, 18 * mm, 20 * mm], warn_cells=warn2))
story.append(Paragraph(
    "근거: 표1과 동일. 프리미엄의 붉은 값은 실거래 100건 미만 소표본(참고용), 전세가율의 붉은 값은 85% 이상(깡통 경계). "
    "서울 85㎡ 이상 프리미엄(+90%)은 신축 고급 빌라 매물과 기존 주택 거래의 구성 차이가 커서 해석 주의. "
    "매물 30건 미만 구간은 표에서 제외.", ss["cap"]))

# ── 표3: 실거래 급매율 ──
story.append(Paragraph("표3. (참고) 빌라 실거래 급매율 — 같은 건물 시세보다 10% 이상 싸게 팔린 거래", ss["h"]))
hdr3 = [P("지역", "th"), P("판정 대상 거래<br/>(건, 최근 90일)", "th"), P("급매 거래<br/>(건)", "th"),
        P("실거래 급매율<br/>(%)", "th"), P("아파트 실거래<br/>급매율(%)", "th")]
apt_rh = {"서울특별시": "1.26", "부산광역시": "6.2", "대구광역시": "5.09", "인천광역시": "3.5",
          "광주광역시": "8.42", "대전광역시": "5.8", "울산광역시": "4.97"}
data3 = [hdr3]
warn3 = []
for r in rh:
    ri = len(data3)
    data3.append([P(short(r["지역"]), "tdl"), P(f"{int(r['판정대상90일']):,}"), P(r["급매건수"]),
                  P(f"<b>{r['급매율%']}</b>"), P(apt_rh.get(r["지역"], "—"))])
    if int(r["판정대상90일"]) < 100:
        warn3.append((3, ri))
story.append(styled(data3, [26 * mm, 34 * mm, 26 * mm, 30 * mm, 30 * mm]))
story.append(Paragraph(
    "근거: 국토부 연립·다세대 실거래(최근 90일 거래를, 같은 건물·전용 ±1.5㎡의 최근 180일 다른 거래 2건 이상의 중간값과 비교, 10% 기준). "
    "붉은 값은 판정 대상 100건 미만 소표본. 아파트 급매율은 콕집 아파트 실거래 급매 보고서(동일 10% 기준)에서 인용.", ss["cap"]))

# ── 표4: 매물수 추이 ──
story.append(Paragraph("표4. 빌라 매물수 추이 — 수집 23일(6/21~7/13)", ss["h"]))
picks = ["2026-06-21", "2026-06-28", "2026-07-05", "2026-07-13"]
tsel = [r for r in trend if r["date"] in picks]
hdr4 = [P("날짜", "th")] + [P(short(c), "th") for c in CITY6] + [P("6개시 합계", "th")]
data4 = [hdr4]
for r in tsel:
    tot = sum(int(r[c]) for c in CITY6)
    data4.append([P(r["date"], "tdl")] + [P(f"{int(r[c]):,}") for c in CITY6] + [P(f"<b>{tot:,}</b>")])
story.append(styled(data4, [24 * mm, 22 * mm, 20 * mm, 20 * mm, 22 * mm, 20 * mm, 20 * mm, 24 * mm]))
story.append(Paragraph(
    "근거: 콕집 일별 수집 로그(매매+전세+월세 광고 합계). 수집은 하루도 거르지 않고 23일 연속.", ss["cap"]))

# ── 한계 ──
story.append(Paragraph("■ 분석의 한계와 해석 유의사항", ss["h"]))
for t in [
    "· <b>호가 프리미엄은 ‘같은 집’의 비교가 아닙니다</b>: 매물군과 거래군의 구성(연식·위치·상태)이 다를 수 있어, 프리미엄에는 "
    "‘비싸게 부르는 정도’와 ‘매물 구성이 더 좋은 정도’가 함께 담깁니다. 다만 중간값 비교라 소수 고가 매물에는 휘둘리지 않으며, "
    "지역 간·평형 간 상대 비교에는 무리가 없습니다.",
    "· <b>내놓은 값 ≠ 실제 팔릴 값</b>: 호가는 협상 출발점입니다. 프리미엄이 큰 지역일수록 실제 계약까지 가격이 많이 꺾인다는 뜻으로 읽는 것이 안전합니다.",
    "· <b>매물은 안 팔린 재고</b>: 매물 중간 호가는 팔린 값의 중간보다 높게 형성되는 경향이 있습니다(아파트 보고서와 동일한 성질).",
    "· <b>층·향·수리 상태 미반영</b>: 지하·반지하는 제외했지만 층수·수리 여부까지는 반영하지 못했습니다.",
    "· <b>수집 기간</b>: 빌라 매물 수집은 2026-06-21 시작(23일). 추이는 이 기간에 한정되며, 급매율의 시계열 비교는 다음 보고서부터 가능합니다.",
    "· <b>광주 미포함</b>: 광주는 현재 빌라 매물 수집 대상이 아니어서 매물 통계에서 제외(실거래 표3에는 포함).",
]:
    story.append(Paragraph(t, ss["small"]))

story.append(Spacer(1, 4 * mm))
story.append(Paragraph(
    "문의: 런투온라인 · 콕집(koczip.com) · runtoonline@gmail.com · 010-5942-8014 (황인찬 대표) / 원자료 CSV 제공 가능", ss["cap"]))


def footer(canv, doc):
    canv.saveState()
    canv.setFont("P", 7.5)
    canv.setFillColor(GRAY)
    canv.drawString(18 * mm, 10 * mm,
                    f"콕집(koczip.com) · 네이버부동산 빌라 매물 + 국토부 연립·다세대 실거래 · 매물 기준 {SNAP}")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=15 * mm,
                        title="특별시·광역시 빌라 매물 분석 보고서")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("pdf:", OUT)
