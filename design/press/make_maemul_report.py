# -*- coding: utf-8 -*-
"""특별시·광역시 아파트 매물(호가) '급매' 분석 보고서 (기자 배포용).
실거래 급매 보고서(make_gapmae_report.py)와 동일 파라미터·양식의 매물 버전.
수치는 design/press/data/의 CSV(박스 실측 산출물)를 그대로 읽어 조판.
Run: python3 design/press/make_maemul_report.py  → design/press/매물급매보고서_특별시광역시.pdf
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
FONTS = HERE.parent / "fonts"
DATA = HERE / "data"
OUT = HERE / "매물급매보고서_특별시광역시.pdf"
SNAP = "2026-07-08"

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
    return s.replace("특별시", "").replace("광역시", "").replace("특별자치시", "")


# ── 데이터 로드 ──
region = list(csv.DictReader(open(DATA / "매물급매_지역요약_0708.csv")))
grid = list(csv.DictReader(open(DATA / "매물급매_지역평형_grid_0708.csv")))
comp = list(csv.DictReader(open(DATA / "매물vs실거래_급매율비교_0708.csv")))

tot_lst = sum(int(r["매물수"]) for r in region)
tot_elig = sum(int(r["참조가능"]) for r in region)
tot_gap = sum(int(r["급매건수"]) for r in region)
tot_rate = tot_gap / tot_elig * 100
seoul = {r["지역"]: r for r in comp}["서울특별시"]

story = []

# ── 표지 ──
story.append(Paragraph("데이터 분석 보고서 · 콕집(koczip.com)", ss["tag"]))
story.append(Paragraph("특별시·광역시 아파트 매물(호가) ‘급매’ 분석", ss["title"]))
story.append(Paragraph("호가는 시세 위에서 시작한다 — 매물 급매율 vs 실거래 급매율", ss["sub"]))

story.append(box("■ 데이터 개요 (모든 수치의 근거)", [
    "· 분석 대상: 콕집 수집 네이버부동산 아파트 매매 매물(호가) — 특별시 1(서울)·광역시 6(부산·대구·인천·광주·대전·울산)·특별자치시 1(세종)",
    f"· 기준 시점: {SNAP} 기준, 그날 노출 중인 매매 매물 {tot_lst:,}건",
    "· 급매 기준선: 국토교통부 아파트 매매 실거래(최근 180일, 공인중개사 거래, 계약해제 건 제외) — 콕집이 단지별로 연결",
    "· 판정 대상: 매매 매물(아파트·재건축) 중 호가가 유효하고, 최근 실거래가 있어 시세와 견줄 수 있는 매물만 급매 여부를 판정",
    "· 출처: 네이버부동산(매물)·국토교통부 실거래가 공개시스템(기준값) / 수집·연결·집계 콕집(koczip.com)",
]))
story.append(Spacer(1, 5 * mm))

# ── 급매 정의 ──
story.append(box("■ ‘급매(시세보다 싸게 내놓은 매물)’ 정의 및 산출 방법", [
    "· <b>급매 매물</b> = 같은 단지·같은 면적에서 <b>최근 180일간 중개거래 실거래가의 중위값</b>보다 "
    "<b>10% 이상 싸게</b> 내놓은 매매 매물",
    "· <b>비교 가능 매물</b> = 그 단지·면적에 최근 180일 실거래가 <b>5건 이상</b> 있어 시세와 견줄 수 있는 매물(미달 시 제외)",
    "· <b>급매율</b> = 급매 매물 수 ÷ 비교 가능 매물 수",
    "· 계산 방식은 콕집 ‘실거래 급매 보고서’와 동일(최근 180일·중개거래 중위값·10% 기준·실거래 5건 이상) — 두 보고서를 그대로 견줄 수 있음",
    "· 매물과 실거래는 전용면적 표기가 ±1㎡ 다를 수 있어 <b>±1.5㎡ 이내면 같은 평형으로 연결</b>(콕집 매물추천과 동일)",
]))
story.append(Spacer(1, 5 * mm))

# ── 핵심 요약 ──
story.append(Paragraph("■ 핵심 요약", ss["h"]))
for t in [
    f"1. 분석한 8개 시·도 <b>전부</b>에서 <b>매물(호가) 급매율이 실거래(중개) 급매율보다 낮았다</b>. "
    "매도자는 호가에는 급매가를 거의 내걸지 않고, 급매는 실제 협상·계약 단계에서 형성된다.",
    f"2. 서울: 매물 급매율 <b>{seoul['매물급매율%']}%</b>(시세와 비교 가능한 {int([r for r in region if r['지역']=='서울특별시'][0]['참조가능']):,}건 중 "
    f"{int([r for r in region if r['지역']=='서울특별시'][0]['급매건수']):,}건)로 사실상 전무 — 실거래 급매율({seoul['실거래중개급매율%']}%)의 "
    f"<b>1/{seoul['실거래대비배율']}</b> 수준. 서울 매도자의 ‘호가 버티기’가 가장 강하다.",
    "3. 지방 대형(전용 135㎡ 초과, 대략 50평 이상)은 예외적으로 내놓는 값에서도 급매가 잦다 — <b>부산 대형 매물 급매율 10.66%</b>로 전 구간 최고. "
    "지방 대형은 실제 거래처럼 매물에서도 싼값이 흔한 유일한 구간이다.",
    f"4. 8개 시·도를 합치면 매물 급매율은 <b>{tot_rate:.2f}%</b>(시세와 비교 가능한 {tot_elig:,}건 중 급매 {tot_gap:,}건). "
    "급매의 중위 할인율은 전 지역·평형에서 11~15%로, 기준선(10%) 바로 위에 고르게 분포한다.",
]:
    story.append(Paragraph(t, ss["body"]))
story.append(Spacer(1, 3 * mm))

# ── 표1: 지역 요약 ──
story.append(Paragraph("표1. 지역별 매물 요약 — 매물수·중간 호가·급매율", ss["h"]))
hdr1 = [P("지역", "th"), P("매매 매물수<br/>(건)", "th"), P("중간 호가<br/>(억원)", "th"),
        P("시세 비교<br/>가능(건)", "th"), P("급매<br/>(건)", "th"), P("급매율<br/>(%)", "th")]
data1 = [hdr1]
for r in region:
    data1.append([P(short(r["지역"]), "tdl"), P(f"{int(r['매물수']):,}"), P(r["중위호가억"]),
                  P(f"{int(r['참조가능']):,}"), P(f"{int(r['급매건수']):,}"), P(f"<b>{r['급매율%']}</b>")])
data1.append([P("합계", "tdl"), P(f"{tot_lst:,}"), P("—"), P(f"{tot_elig:,}"),
              P(f"{tot_gap:,}"), P(f"<b>{tot_rate:.2f}</b>")])
story.append(styled(data1, [26 * mm, 28 * mm, 24 * mm, 24 * mm, 20 * mm, 20 * mm]))
story.append(Paragraph(
    f"근거: {SNAP} 콕집 매물 기준. ‘중간 호가’는 해당 지역 매매 호가의 중위값(억원).", ss["cap"]))

# ── 표2: 매물 vs 실거래 비교 ──
story.append(Paragraph("표2. 매물(호가) 급매율 vs 실거래(중개) 급매율 — 지역별 격차", ss["h"]))
hdr2 = [P("지역", "th"), P("매물 급매율<br/>(%)", "th"), P("실거래 중개<br/>급매율(%)", "th"),
        P("실거래/매물<br/>배수", "th")]
data2 = [hdr2]
for r in comp:
    data2.append([P(short(r["지역"]), "tdl"), P(f"<b>{r['매물급매율%']}</b>"),
                  P(r["실거래중개급매율%"]), P(f"{r['실거래대비배율']}배")])
story.append(styled(data2, [34 * mm, 34 * mm, 34 * mm, 30 * mm]))
story.append(Paragraph(
    "근거: 매물 급매율은 이 보고서(2026-07-08 기준), 실거래 급매율은 콕집 실거래 급매 보고서(2024-01~2026-06, 동일 방식). "
    "호가가 실거래보다 잘 안 내려가는 것은 구조적 성질이라, 기간을 맞춰도 매물<실거래 방향은 유지된다.", ss["cap"]))

# ── 표3: 지역 × 평형 (급매율) ──
story.append(Paragraph("표3. 지역 × 대표 평형 — 매물수·중간 호가·급매율", ss["h"]))
gd = {(r["지역"], r["평형"]): r for r in grid}
hdr3top = [P("지역", "th"), P("59㎡형 (전용 55~66㎡)", "th"), "", "",
           P("84㎡형 (전용 79~90㎡)", "th"), "", "", P("대형 (전용 135㎡ 초과)", "th"), "", ""]
hdr3sub = [P("", "th")] + [P(x, "th") for x in ["매물수", "중간 호가<br/>(억)", "급매율<br/>(%)"]] * 3
data3 = [hdr3top, hdr3sub]
warn3 = []
for ri, reg in enumerate({r["지역"] for r in grid} and [r["지역"] for r in region]):
    row = [P(short(reg), "tdl")]
    for ci, b in enumerate(["59㎡", "84㎡", "대형"]):
        cc = gd.get((reg, b))
        n = int(cc["매물수"]) if cc else 0
        med = cc["중위호가억"] if cc and cc["중위호가억"] not in ("", "None") else "—"
        rate = cc["급매율%"] if cc and cc["급매율%"] not in ("", "None") else "—"
        row += [P(f"{n:,}"), P(med), P(rate)]
        elig = int(cc["참조가능"]) if cc else 0
        if elig < 200:
            warn3.append((1 + ci * 3 + 2, ri + 2))
    data3.append(row)
cw3 = [18 * mm] + [17 * mm, 16 * mm, 15 * mm] * 3
spans3 = [((1, 0), (3, 0)), ((4, 0), (6, 0)), ((7, 0), (9, 0)), ((0, 0), (0, 1))]
story.append(styled(data3, cw3, header_rows=2, spans=spans3, warn_cells=warn3))
story.append(Paragraph(
    "근거: 표1과 동일. 붉은 급매율은 비교 가능 매물 200건 미만 소표본(개별 수치는 참고용). 세 평형 구간 밖(66~79㎡ 등)은 제외.", ss["cap"]))

# ── 표4: 지역 × 평형 상세 ──
story.append(Paragraph("표4. 지역 × 대표 평형 — 상세 표", ss["h"]))
hdr4 = [P("지역", "th"), P("평형", "th"), P("매물수<br/>(건)", "th"), P("중간 호가<br/>(억)", "th"),
        P("시세 비교<br/>가능(건)", "th"), P("급매<br/>(건)", "th"), P("급매율<br/>(%)", "th"),
        P("급매 실제<br/>할인폭(%)", "th")]
data4 = [hdr4]
warn4 = []
for r in grid:
    ri = len(data4)
    med = r["중위호가억"] if r["중위호가억"] not in ("", "None") else "—"
    rate = r["급매율%"] if r["급매율%"] not in ("", "None") else "—"
    disc = r["급매중위할인%"] if r["급매중위할인%"] not in ("", "None") else "—"
    data4.append([P(short(r["지역"]), "tdl"), P(r["평형"]), P(f"{int(r['매물수']):,}"), P(med),
                  P(f"{int(r['참조가능']):,}"), P(f"{int(r['급매건수']):,}"), P(f"<b>{rate}</b>"), P(disc)])
    if int(r["참조가능"]) < 50:
        warn4.append((6, ri))
cw4 = [22 * mm, 14 * mm, 18 * mm, 16 * mm, 20 * mm, 15 * mm, 16 * mm, 22 * mm]
story.append(styled(data4, cw4, warn_cells=warn4))
story.append(Paragraph(
    "근거: 표1을 지역·평형으로 분류. 붉은 급매율은 비교 가능 매물 50건 미만 소표본(개별 수치는 참고용). "
    "‘급매 실제 할인폭’은 급매 매물이 시세보다 얼마나 싼지의 중위값.", ss["cap"]))

# ── 한계 ──
story.append(Paragraph("■ 분석의 한계와 해석 유의사항", ss["h"]))
for t in [
    "· <b>내놓은 값 ≠ 실제 팔린 값</b>: 매물 호가는 파는 사람이 부르는 값이고, 실제 계약가는 흥정으로 더 내려갈 수 있습니다. 이 보고서의 "
    "‘매물 급매율’은 ‘내놓을 때부터 이미 시세보다 싼’ 매물의 비율이며, 실거래 급매율과의 차이 자체가 이 흥정 여지를 보여줍니다.",
    "· <b>비싼 매물이 쌓이는 효과</b>: 매물은 안 팔리고 남은 재고라 비싼 단지가 많이 섞여, ‘중간 호가’가 실제 팔린 값의 중간보다 높게 나옵니다"
    "(예: 서울 59㎡형 매물 중간 호가 15.5억 vs 실제 팔린 값 중간 8~9억). 다만 급매율(비율)은 이 쏠림의 영향을 받지 않습니다.",
    "· <b>층·향·전망은 반영 못 함</b>: 같은 면적이라도 층·향·전망 차이는 값에 반영하지 못했습니다. 다만 기준값을 공인중개사 실거래로 통일했으므로 지역끼리 비교에는 무리가 없습니다.",
    "· <b>하루 기준</b>: 이 표는 2026-07-08 하루치입니다. 서울 매물 급매율은 최근 7주간 3.0%→2.1%(5% 이상 기준)로 줄어드는 추세이고, "
    "이 보고서의 ‘10% 이상’ 급매는 그보다 더 드뭅니다.",
    "· <b>집값이 오르면 급매가 적게 잡힘</b>: 기준값이 최근 180일 실거래라, 집값 상승기에는 급매가 실제보다 적게 잡힙니다. "
    "그래서 급매율의 절대 수치보다 ‘매물 vs 실거래’, ‘지역·평형 간 차이’를 핵심으로 봐야 합니다.",
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
                    f"콕집(koczip.com) · 네이버부동산 매물 + 국토부 실거래 기준선 · 매물 기준 {SNAP}")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=15 * mm,
                        title="특별시·광역시 아파트 매물 급매 분석 보고서")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("pdf:", OUT)
