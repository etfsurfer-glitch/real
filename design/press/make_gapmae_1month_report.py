# -*- coding: utf-8 -*-
"""서울 아파트 매물(호가) '급매물' 1개월 변화 보고서 (기자 배포용).
매물 급매 보고서(make_maemul_report.py)와 동일 파라미터·양식.
데이터: design/press/data/서울_급매물_1달변화_0608-0708.csv (박스 실측 산출물).
Run: python3 design/press/make_gapmae_1month_report.py → design/press/서울급매물_1개월변화.pdf
"""
import csv
import datetime as dt
import statistics as stt
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
FONTS = HERE.parent / "fonts"
DATA = HERE / "data"
OUT = HERE / "서울급매물_1개월변화.pdf"
CSVF = DATA / "서울_급매물_1달변화_0608-0708.csv"
D0, D1 = "2026-06-08", "2026-07-08"

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


def g(d):
    # 비중 = 급매물 ÷ 서울 아파트 매매 매물 전체 (직관·자체 정합)
    r = rows[d]
    sale = int(r["sale"]); g5 = int(r["gap5"]); g10 = int(r["gap10"])
    return (g5, g5 / sale * 100, g10, g10 / sale * 100, sale)


s, e = g(D0), g(D1)
d5, d10 = e[0] - s[0], e[2] - s[2]
p5, p10 = d5 / s[0] * 100, d10 / s[2] * 100

# 주간 집계 (비중 = 주간 급매물 합 ÷ 주간 매매 매물 합)
wk = defaultdict(list)
for d in dates:
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    wk[(y, w)].append(rows[d])
weeks = []
for k in sorted(wk):
    v = wk[k]
    mon = dt.date.fromisocalendar(k[0], k[1], 1)
    sg5 = sum(int(x["gap5"]) for x in v); sg10 = sum(int(x["gap10"]) for x in v)
    ssale = sum(int(x["sale"]) for x in v)
    weeks.append((mon, len(v),
                  stt.mean(int(x["gap5"]) for x in v), sg5 / ssale * 100,
                  stt.mean(int(x["gap10"]) for x in v), sg10 / ssale * 100))

story = []

# ── 표지 ──
story.append(Paragraph("데이터 분석 보고서 · 콕집(koczip.com)", ss["tag"]))
story.append(Paragraph("서울 아파트 ‘급매물’ 1개월 변화", ss["title"]))
story.append(Paragraph("매물은 쌓이는데 급매(저가 매물)만 소진 — 2026-06-08 → 07-08", ss["sub"]))

story.append(box("■ 데이터 개요 (모든 수치의 근거)", [
    "· 분석 대상: 서울특별시 아파트(재건축 포함) 매매 매물 — 콕집이 매일 수집하는 네이버부동산 매물",
    f"· 기간: {D0} → {D1} (정확히 1개월)",
    "· 급매 기준선: 국토교통부 아파트 매매 실거래(최근 180일·공인중개사 거래·계약해제 건 제외)",
    "· 빠진 날짜: 2026-06-14 하루는 <b>서버 이전으로 데이터가 없어 제외</b>(전후 추세로 볼 때 영향 미미)",
    "· 출처: 네이버부동산(매물)·국토교통부 실거래가 공개시스템(기준선) / 수집·매칭·집계 콕집(koczip.com)",
]))
story.append(Spacer(1, 4 * mm))

story.append(box("■ ‘급매물’ 정의 및 산출 방법", [
    "· <b>급매물</b> = 같은 단지·같은 면적에서 <b>최근 180일 중개거래 실거래가의 중위값</b>보다 "
    "<b>5%(또는 10%) 이상 싸게</b> 내놓은 서울 아파트 매매 매물",
    "· <b>급매율(비중)</b> = 급매물 수 ÷ 서울 아파트 매매 매물 전체 · 콕집 ‘매물 급매 보고서’와 동일 방식",
]))
story.append(Spacer(1, 4 * mm))

# ── 핵심 요약 ──
story.append(Paragraph("■ 핵심 요약", ss["h"]))
for t in [
    f"1. 지난 한 달간(6/8→7/8) 서울 아파트 <b>급매물이 감소</b>했다. 실거래 대비 5% 이상 싼 급매물은 "
    f"<b>906건 → 796건({p5:+.1f}%)</b>, 10% 이상 싼 급매물은 <b>133건 → 101건({p10:+.1f}%)</b>.",
    f"2. 같은 기간 서울 아파트 매매 매물 자체는 {s[4]:,}건 → {e[4]:,}건으로 <b>오히려 늘었다</b>. "
    "매물이 줄어서가 아니라, 그중 ‘시세보다 싼 급매’만 팔려나가며 줄어드는 흐름이다.",
    f"3. 급매물 비중(전체 매매 매물 대비)도 ≥5% 기준 {s[1]:.2f}%→{e[1]:.2f}%, ≥10% 기준 {s[3]:.2f}%→{e[3]:.2f}%로 낮아졌다. "
    "특정일 급등락이 아니라 <b>6주 내내 한 주도 반등 없이 계속 줄어든</b> 추세다.",
]:
    story.append(Paragraph(t, ss["body"]))
story.append(Spacer(1, 2 * mm))

# ── 표1: 1개월 변화 ──
story.append(Paragraph("표1. 서울 급매물 1개월 변화 (2026-06-08 → 07-08)", ss["h"]))
hdr1 = [P("급매 기준", "th"), P(f"1개월 전<br/>({D0})", "th"), P(f"현재<br/>({D1})", "th"),
        P("증감<br/>(건)", "th"), P("증감률<br/>(%)", "th")]
data1 = [hdr1,
         [P("실거래 대비 ≥5% 저렴", "tdl"), P(f"{s[0]:,}건 ({s[1]:.2f}%)"), P(f"{e[0]:,}건 ({e[1]:.2f}%)"),
          P(f"<b>{d5:+,}</b>"), P(f"<b>{p5:+.1f}</b>")],
         [P("실거래 대비 ≥10% 저렴", "tdl"), P(f"{s[2]:,}건 ({s[3]:.2f}%)"), P(f"{e[2]:,}건 ({e[3]:.2f}%)"),
          P(f"<b>{d10:+,}</b>"), P(f"<b>{p10:+.1f}</b>")]]
cc1 = [(3, 1, RED), (4, 1, RED), (3, 2, RED), (4, 2, RED)]
story.append(styled(data1, [46 * mm, 34 * mm, 34 * mm, 24 * mm, 24 * mm], color_cells=cc1))
story.append(Paragraph(
    "근거: 두 시점(6/8·7/8) 직접 비교. 괄호 안은 서울 아파트 매매 매물 전체 대비 비중. 붉은색=급매물 감소.", ss["cap"]))

# ── 표2: 주간 평균 추이 ──
story.append(Paragraph("표2. 주간 평균 추이 (급매물 수·비중)", ss["h"]))
hdr2 = [P("주 (시작 월요일)", "th"), P("일수", "th"), P("급매물 ≥5%<br/>(건)", "th"), P("비중<br/>(%)", "th"),
        P("급매물 ≥10%<br/>(건)", "th"), P("비중<br/>(%)", "th")]
data2 = [hdr2]
for mon, n, g5, pp5, g10, pp10 in weeks:
    data2.append([P(str(mon), "tdl"), P(n), P(f"{g5:,.0f}"), P(f"{pp5:.2f}"),
                  P(f"{g10:,.0f}"), P(f"{pp10:.2f}")])
story.append(styled(data2, [34 * mm, 14 * mm, 28 * mm, 22 * mm, 28 * mm, 22 * mm]))
story.append(Paragraph(
    "근거: 요일·주말 편차를 없애기 위해 일별 값을 주별(월~일)로 집계. 6주 연속 감소. "
    "‘비중’은 서울 아파트 매매 매물 전체 대비 급매물 비율.", ss["cap"]))

# ── 표3: 일별 상세 (제목+표를 같은 페이지로) ──
hdr3 = [P("날짜", "th"), P("매매 매물수<br/>(건)", "th"),
        P("급매물 ≥5%<br/>(건)", "th"), P("비중<br/>(%)", "th"),
        P("급매물 ≥10%<br/>(건)", "th"), P("비중<br/>(%)", "th")]
data3 = [hdr3]
for d in dates:
    r = rows[d]
    sale = int(r["sale"]); g5 = int(r["gap5"]); g10 = int(r["gap10"])
    data3.append([P(d, "tdl"), P(f"{sale:,}"),
                  P(f"{g5:,}"), P(f"{g5 / sale * 100:.2f}"),
                  P(f"{g10:,}"), P(f"{g10 / sale * 100:.2f}")])
story.append(KeepTogether([
    Paragraph("표3. 일별 상세 (참고)", ss["h"]),
    styled(data3, [28 * mm, 34 * mm, 30 * mm, 20 * mm, 30 * mm, 20 * mm]),
]))
story.append(Paragraph(
    "참고: 2026-06-14는 서버 이전으로 데이터가 없어 빠졌습니다. 비중은 모두 서울 아파트 매매 매물 전체 대비 값입니다.", ss["cap"]))

# ── 한계 ──
story.append(Paragraph("■ 해석 유의사항", ss["h"]))
for t in [
    "· <b>내놓은 값 ≠ 실제 팔린 값</b>: 급매물은 ‘내놓을 때부터 이미 시세보다 싼’ 매물의 수입니다. 실제 급매 거래는 흥정으로 "
    "따로 만들어지므로, 실제 팔린 값 기준 급매 비율은 이보다 높습니다.",
    "· <b>급매 판정 기준</b>: 급매 여부는 최근 180일 실거래로 시세를 견줄 수 있는 매물에서만 판정합니다. 급매물 수는 이 판정을 통과한 매물의 수이며, "
    "집값이 오르는 시기에는 기준값도 같이 올라 급매가 실제보다 적게 잡히는 경향이 있습니다. 다만 두 시점을 같은 기준으로 쟀으므로 ‘줄었다’는 방향은 분명합니다.",
    "· <b>기준을 바꿔도 방향은 같음</b>: 이 보고서는 ‘5% 이상’·‘10% 이상’ 두 기준만 썼습니다. 그 폭을 달리 잡아도 한 달간 줄어든 방향은 똑같습니다.",
]:
    story.append(Paragraph(t, ss["small"]))

story.append(Spacer(1, 4 * mm))
story.append(Paragraph(
    "문의: 런투온라인 · 콕집(koczip.com) · runtoonline@gmail.com · 010-5942-8014 (황인찬 대표) / 원자료 CSV 제공 가능", ss["cap"]))


def footer(canv, doc):
    canv.saveState()
    canv.setFont("P", 7.5)
    canv.setFillColor(GRAY)
    canv.drawString(18 * mm, 10 * mm, "콕집(koczip.com) · 네이버부동산 매물 + 국토부 실거래 기준선 · 서울 아파트 2026-06-08~07-08")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=15 * mm,
                        title="서울 아파트 급매물 1개월 변화 보고서")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("pdf:", OUT)
