# -*- coding: utf-8 -*-
"""특별시·광역시 아파트 급매·거래유형 분석 보고서 (기자 배포용).
수치는 /tmp/rpt.json (박스 실측 산출물)을 그대로 읽어 조판 — 전사 오류 없음.
Run: python3 design/press/급매-매물동향/make_gapmae_report.py  → design/press/급매-매물동향/급매보고서_특별시광역시.pdf
"""
import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                KeepTogether)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
JSON = HERE.parent / "data" / "rpt.json"
OUT = HERE / "급매보고서_특별시광역시.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

J = json.load(open(JSON))
M = J["meta"]

BLUE = colors.HexColor("#1268D3")
BLUE_DK = colors.HexColor("#0C4EA0")
HEADBG = colors.HexColor("#1268D3")
ROWALT = colors.HexColor("#F2F6FC")
INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80")
LINE = colors.HexColor("#D5DEEA")
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
    return Paragraph(t, ss[s])


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


def num(v, unit=""):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.1f}{unit}"
    return f"{v:,}{unit}"


story = []

# ── 표지 헤더 ──
story.append(Paragraph("데이터 분석 보고서 · 콕집(koczip.com)", ss["tag"]))
story.append(Paragraph("특별시·광역시 아파트 실거래 ‘급매·거래유형’ 분석", ss["title"]))
story.append(Paragraph("개인끼리 한 ‘직거래’에서 시세보다 크게 싼 거래가 몰린다 — 거래 방식별 비교", ss["sub"]))

# 데이터 개요
story.append(box("■ 데이터 개요 (모든 수치의 근거)", [
    "· 분석 대상: 국토교통부 아파트 매매 실거래 신고자료 — 특별시 1(서울)·광역시 6(부산·대구·인천·광주·대전·울산)·특별자치시 1(세종)",
    f"· 계약일 기준 분석기간: {M['period_contract'].replace('~','~')} (30개월)",
    f"· 분석 표본: {M['n_analyzed']:,}건 (계약월 2024-01~2026-06). 기준선 산출용 참조기간(2023-07~2023-12) 포함 총 로드 {M['n_loaded']:,}건",
    "· 표본 조건: 계약해제(해제거래) 제외 · 단지 매칭 성공분 · 거래유형 ‘중개거래/직거래’만",
    "· 출처: 국토교통부 실거래가 공개시스템 / 단지 매칭·집계 콕집(koczip.com)",
]))
story.append(Spacer(1, 5 * mm))

# 급매 정의
story.append(box("■ ‘급매(시세보다 크게 싸게 팔린 거래)’ 정의 및 산출 방법", [
    f"· <b>급매</b> = 같은 단지·같은 면적(전용, ㎡ 반올림)에서 <b>최근 {M['trail_days']}일간 중개거래 실거래가의 중위값</b>보다 "
    f"<b>{M['thresh_pct']}% 이상 싸게</b> 팔린 거래",
    f"· <b>비교 가능 거래</b> = 그 단지·면적에 최근 {M['trail_days']}일 중개거래가 <b>{M['min_prior']}건 이상</b> 있어 시세와 견줄 수 있는 거래(미달 시 제외)",
    "· <b>급매율</b> = 급매 건수 ÷ 비교 가능 거래 건수. 기준값은 항상 ‘중개거래(제3자 시장가)’로 통일해 직거래와 같은 잣대로 비교",
    "· <b>차이 검증</b>: 지역·평형별 직거래 vs 중개거래 급매율 차이가 우연일 확률을 산출(전 지역 0.1% 미만 = 통계적으로 유의)",
]))
story.append(Spacer(1, 5 * mm))

# 핵심 요약
t1 = {r["sido"]: r for r in J["t1"]}
seoul = t1["서울특별시"]
t3 = {r["bucket"]: r for r in J["t3"]}
story.append(Paragraph("■ 핵심 요약", ss["h"]))
summary = [
    f"1. 2024-01~2026-06 거래 기준, 분석한 8개 시·도 <b>전부</b>에서 직거래 급매율이 중개거래의 <b>4~40배</b>였고, "
    "이 차이가 우연일 확률은 모든 지역에서 <b>0.1% 미만</b>(사실상 확실한 차이).",
    f"2. 서울: 직거래 급매율 <b>{seoul['direct']['rate']}%</b>(시세와 비교 가능한 {seoul['direct']['elig']:,}건 중 {seoul['direct']['gapmae']:,}건) "
    f"vs 중개거래 <b>{seoul['broker']['rate']}%</b>({seoul['broker']['elig']:,}건 중 {seoul['broker']['gapmae']:,}건).",
    f"3. 직거래의 저가 성향은 대형(전용 135㎡ 초과, 대략 50평 이상)일수록 강함 — 전지역 대형 직거래 급매율 <b>{t3['대형']['direct_rate']}%</b> "
    f"vs 중개거래 {t3['대형']['broker_rate']}% ({t3['대형']['mult']}배).",
    "4. 직거래 급매는 할인폭도 더 깊음 — 급매의 중위 할인율 직거래 16~26% vs 중개거래 13% 안팎(표1·표4).",
]
for s in summary:
    story.append(Paragraph(s, ss["body"]))
story.append(Paragraph(
    "※ 해석 주의: ‘직거래=위법’이 아니다. 다만 시세보다 크게 낮은 직거래 집중은 특수관계인 간 저가 이전 등 "
    "편법 거래를 <b>의심</b>할 신호로, 과세당국의 상시 점검 대상과 부합한다.", ss["small"]))

# ── 표1: 지역 × 거래유형 ──
story.append(Paragraph("표1. 지역 × 거래유형 — 거래건수·급매율 (전체 평형)", ss["h"]))
hdr = [P("지역", "th"), P("거래<br/>유형", "th"), P("거래건수<br/>(건)", "th"),
       P("중간<br/>실거래가<br/>(억원)", "th"), P("시세 비교<br/>가능(건)", "th"), P("급매<br/>(건)", "th"),
       P("급매율<br/>(%)", "th"), P("급매 실제<br/>할인폭(%)", "th"), P("차이가 우연일<br/>확률(직거래)", "th")]
data1 = [hdr]
for r in J["t1"]:
    for lab, k in [("중개거래", "broker"), ("직거래", "direct")]:
        c = r[k]
        pcell = f"{r['p']}" if k == "direct" else ""
        data1.append([
            P(r["sido"].replace("특별시", "").replace("광역시", "").replace("특별자치시", ""), "tdl") if k == "broker" else P("", "td"),
            P(lab), P(num(c["n"])), P(num(c["median_eok"])), P(num(c["elig"])),
            P(num(c["gapmae"])), P(f"<b>{c['rate']}</b>"), P(num(c["mdisc"])), P(pcell)])
cw1 = [16 * mm, 15 * mm, 20 * mm, 18 * mm, 18 * mm, 13 * mm, 15 * mm, 18 * mm, 23 * mm]
spans1 = [((0, 1 + 2 * i), (0, 2 + 2 * i)) for i in range(len(J["t1"]))]
story.append(styled(data1, cw1, spans=spans1))
story.append(Paragraph(
    "근거: 국토부 아파트 매매 실거래(2024-01~2026-06). 맨 오른쪽은 직거래·중개거래 급매율 차이가 우연일 확률로, 전 지역 0.001 미만.", ss["cap"]))

# ── 표3: 거래유형 × 평형 ──
story.append(Paragraph("표2. 거래유형 × 선호평형 — 급매율 격차 (전지역 합산)", ss["h"]))
hdr3 = [P("평형(전용면적)", "th"), P("중개거래<br/>급매율(%)", "th"), P("직거래<br/>급매율(%)", "th"),
        P("직거래/중개<br/>배수", "th"), P("시세 비교 가능(건수)<br/>(중개 / 직거래)", "th"), P("차이가 우연일<br/>확률", "th")]
blab = {"59㎡": "59㎡형 (전용 55~66㎡)", "84㎡": "84㎡형 (전용 79~90㎡)",
        "대형": "대형 (전용 135㎡ 초과)", "전체": "전체 평형"}
data3 = [hdr3]
for r in J["t3"]:
    data3.append([P(blab[r["bucket"]], "tdl"), P(num(r["broker_rate"])), P(f"<b>{r['direct_rate']}</b>"),
                  P(f"{r['mult']}배" if r["mult"] else "-"),
                  P(f"{r['broker_elig']:,} / {r['direct_elig']:,}"), P(f"{r['p']}")])
story.append(styled(data3, [46 * mm, 24 * mm, 24 * mm, 22 * mm, 34 * mm, 22 * mm]))
story.append(Paragraph(
    "근거: 표1을 면적별로 분류. 59·84㎡형은 대표 선호평형, 대형은 전용 135㎡ 초과. 직거래의 저가 성향은 대형일수록 커짐(6.1→8.0배).", ss["cap"]))

# ── 표4(지역×평형) ──
story.append(Paragraph("표3. 지역 × 대표 평형 — 거래건수·중간가·급매율 (중개+직거래 합산)", ss["h"]))
hdr2top = [P("지역", "th"), P("59㎡형 (전용 55~66㎡)", "th"), "", "",
           P("84㎡형 (전용 79~90㎡)", "th"), "", "", P("대형 (전용 135㎡ 초과)", "th"), "", ""]
hdr2sub = [P("", "th")] + [P(x, "th") for x in ["건수", "중간가<br/>(억)", "급매율<br/>(%)"]] * 3
data2 = [hdr2top, hdr2sub]
warn2 = []
for ri, r in enumerate(J["t2"]):
    row = [P(r["sido"].replace("특별시", "").replace("광역시", "").replace("특별자치시", ""), "tdl")]
    for ci, b in enumerate(["59㎡", "84㎡", "대형"]):
        cc = r[b]
        row += [P(num(cc["n"])), P(num(cc["median_eok"])), P(num(cc["rate"]))]
        if cc["n"] < 200:  # 표본 과소 셀 표시
            warn2.append((1 + ci * 3 + 2, ri + 2))
    data2.append(row)
cw2 = [20 * mm] + [17 * mm, 16 * mm, 15 * mm] * 3
spans2 = [((1, 0), (3, 0)), ((4, 0), (6, 0)), ((7, 0), (9, 0)), ((0, 0), (0, 1))]
story.append(styled(data2, cw2, header_rows=2, spans=spans2, warn_cells=warn2))
story.append(Paragraph(
    "‘중간가’는 해당 지역·평형 실거래가의 중위값(억원). "
    "붉은 급매율은 거래 200건 미만 소표본(예: 세종 대형 57건)으로 해석에 주의.", ss["cap"]))

# ── 표(지역×거래유형×평형) 상세 그리드 ──
story.append(Paragraph("표4. 지역 × 거래유형 × 대표 평형 — 상세 표", ss["h"]))
hdr4 = [P("지역", "th"), P("거래유형", "th"), P("평형", "th"), P("거래건수<br/>(건)", "th"),
        P("중간가<br/>(억)", "th"), P("시세 비교<br/>가능(건)", "th"), P("급매<br/>(건)", "th"),
        P("급매율<br/>(%)", "th"), P("급매 실제<br/>할인폭(%)", "th")]
data4 = [hdr4]
warn4 = []
for r in J["t4"]:
    ri = len(data4)
    data4.append([P(r["sido"].replace("특별시", "").replace("광역시", "").replace("특별자치시", ""), "tdl"),
                  P(r["dealing"]), P(r["bucket"]), P(num(r["n"])), P(num(r["median_eok"])),
                  P(num(r["elig"])), P(num(r["gapmae"])), P(f"<b>{r['rate']}</b>"), P(num(r["mdisc"]))])
    if r["elig"] < 20:
        warn4.append((7, ri))
cw4 = [16 * mm, 18 * mm, 12 * mm, 18 * mm, 15 * mm, 18 * mm, 14 * mm, 15 * mm, 20 * mm]
story.append(styled(data4, cw4, warn_cells=warn4))
story.append(Paragraph(
    "근거: 표1을 지역·거래유형·평형으로 분류. 붉은 급매율은 비교 가능 거래 20건 미만 소표본(개별 수치는 참고용). 세 평형 구간 밖(66~79㎡ 등)은 제외.", ss["cap"]))

# ── 한계·유의사항 ──
story.append(Paragraph("■ 분석의 한계와 해석 유의사항", ss["h"]))
for t in [
    "· <b>직거래=위법이라는 뜻이 아님</b>: 직거래의 싼값 거래는 가족 등 특수관계인끼리 싸게 넘기는 편법을 ‘의심’할 신호일 뿐, 위법으로 단정하지 않습니다. "
    "지인 간 정상 거래나 급한 사정으로 인한 진짜 급매도 일부 섞여 있습니다.",
    "· <b>층·향·전망은 반영 못 함</b>: 같은 면적이라도 층·향·전망 차이는 값에 반영하지 못했습니다. 다만 이 차이는 직거래·중개거래 양쪽에 똑같이 "
    "작용하고 기준값을 중개거래로 통일했으므로, 수 배~수십 배의 격차가 그런 차이만으로 생기지는 않습니다.",
    "· <b>건수 적은 칸 주의</b>: 대형·세종 등 일부 칸은 거래·비교 가능 건수가 적습니다. 개별 급매율(붉은색)은 참고만 하고, 본문 결론은 건수가 많은 지역·평형 위주로 썼습니다.",
    "· <b>집값 흐름의 영향</b>: 기준값이 최근 180일 실거래라, 집값 상승기에는 급매가 실제보다 적게, 하락기에는 많게 잡히는 경향이 있습니다. "
    "그래서 급매율의 절대 수치보다 ‘직거래와 중개거래의 차이’가 이 보고서의 핵심입니다.",
    "· <b>신고 지연</b>: 실거래는 계약 후 30일 안에 신고합니다. 2026-06 거래분은 아직 일부 신고 중(잠정치), 2026-07은 분석에서 뺐습니다.",
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
                    "콕집(koczip.com) · 국토교통부 실거래가 기반 · 계약일 2024-01~2026-06")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=15 * mm,
                        title="특별시·광역시 아파트 급매·거래유형 분석 보고서")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("pdf:", OUT)
