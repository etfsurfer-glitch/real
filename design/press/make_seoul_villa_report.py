# -*- coding: utf-8 -*-
"""서울 빌라(연립·다세대) 최근 동향 보고서 (기자 배포용).
기사 방향: 아파트 가격·전세 부담 고착 → 수요가 빌라 매매·전세로 이동.
근거: 국토부 실거래 25개월(수요 이동) + 콕집 일별 매물 수집(데일리) + 광고배율 비교.
Run: python3 design/press/make_seoul_villa_report.py → design/press/서울빌라_동향보고서.pdf
"""
import csv
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
DATA = HERE / "data" / "villa"
OUT = HERE / "서울빌라_동향보고서.pdf"
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
HL = colors.HexColor("#FFF3CD")

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


def styled(data, cw, header_rows=1, warn_cells=None, hl_rows=None, spans=None):
    t = Table(data, colWidths=cw, repeatRows=header_rows)
    stl = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADBG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in range(header_rows, len(data)):
        if (r - header_rows) % 2 == 1:
            stl.append(("BACKGROUND", (0, r), (-1, r), ROWALT))
    for r in (hl_rows or []):
        stl.append(("BACKGROUND", (0, r), (-1, r), HL))
    for (a, b) in (spans or []):
        stl.append(("SPAN", a, b))
    for (c0, r0) in (warn_cells or []):
        stl.append(("TEXTCOLOR", (c0, r0), (c0, r0), RED))
    t.setStyle(TableStyle(stl))
    return t


# ── 데이터 ──
mon = list(csv.DictReader(open(DATA / "서울_수요이동_월별.csv")))
trend = list(csv.DictReader(open(DATA / "빌라_매물수추이.csv")))
aptr = {r["trade"]: r for r in csv.DictReader(open(DATA / "서울_아파트_광고배율.csv"))}
detail = {}
for r in csv.DictReader(open(DATA / "서울_일별_유형상세.csv"),
                        fieldnames=["d", "t", "ads", "units"]):
    detail.setdefault(r["d"], {})[r["t"]] = (int(r["ads"]), int(r["units"]))
natd_daily = list(csv.DictReader(open(DATA / "전국_일별_광고.csv"),
                                  fieldnames=["d", "total", "fixed"]))
nat = list(csv.DictReader(open(DATA / "전국_시도별_매물_0713.csv"),
                           fieldnames=["s", "a1", "a1u", "b1", "b1u", "b2", "b2u"]))
gu = list(csv.DictReader(open(DATA / "서울_구별_빌라매매_증가율.csv"),
                          fieldnames=["구", "h24", "h26", "chg"]))
vilr = {}
for r in csv.DictReader(open(DATA / "빌라_실매물_0713.csv"),
                        fieldnames=["sido", "trade", "ads", "units"]):
    if r["sido"] == "11":
        vilr[r["trade"]] = r

m0, m_last_full = mon[0], mon[-2]          # 2026-06 (마지막 완전월은 아니지만 잠정), -1은 7월 초순
recent3 = mon[-4:-1]                       # 26-04~06
sale_share_recent = max(float(r["sale_share"]) for r in mon[-6:-1])
js_share_recent = max(float(r["js_share"]) for r in mon[-6:-1])
v_ads = int(vilr["A1"]["ads"]); v_units = int(vilr["A1"]["units"])
a_ads = int(aptr["A1"]["apt_ads"]); a_units = int(aptr["A1"]["apt_units"])

story = []
story.append(Paragraph("데이터 분석 보고서 · 콕집(koczip.com)", ss["tag"]))
story.append(Paragraph("서울 빌라(연립·다세대) 최근 동향", ss["title"]))
story.append(Paragraph("아파트 부담이 밀어낸 수요 — 서울 집 계약 3건 중 1건이 빌라가 됐다", ss["sub"]))

story.append(box("■ 데이터 개요 (모든 수치의 근거)", [
    "· 실거래: 국토교통부 실거래가 공개시스템 — 서울 아파트(매매·전세)와 연립·다세대(매매·전세), "
    "2024-07 ~ 2026-07(25개월), 공인중개사 거래 기준·계약해제 건 제외",
    f"· 매물: 콕집 수집 네이버부동산 빌라 매물 — {SNAP} 기준 서울 매매 {v_ads:,}건(광고) · "
    f"중복 광고를 걷어낸 실매물 {v_units:,}건, 일별 수집(6/21~7/13, 23일 연속)",
    "· 전세 = 보증금만 있는 순수 전세(월세 0원). 수집·연결·집계 콕집(koczip.com)",
]))
story.append(Spacer(1, 5 * mm))

story.append(Paragraph("■ 핵심 요약", ss["h"]))
for t in [
    "1. <b>서울 주택 수요가 빌라로 옮겨가고 있다.</b> 아파트+빌라 매매 계약에서 빌라가 차지하는 비중은 "
    f"2024년 7월 <b>19.5%</b>에서 최근 <b>{sale_share_recent:.1f}%</b>(월 기준 최고)까지 올라왔다. "
    "빌라 매매는 월 1,100~2,100건(2024 하반기)에서 2026년 <b>월 2,500~3,500건</b>대로 늘었다.",
    f"2. <b>전세도 같은 방향이다.</b> 서울 전세 계약 중 빌라 비중은 2025년 26~28%에서 2026년 봄 <b>33~35%</b>로 상승 — "
    "아파트 전세 계약이 월 1.2만 건에서 7~8천 건대로 줄어드는 동안 빌라 전세는 4~5천 건을 지켰다.",
    "3. <b>동인은 아파트 전세의 가격 부담이다.</b> 서울 아파트 전세 평균 보증금은 2024년 7월 5.70억 → 2026년 6월 "
    "<b>6.60억(+15.8%)</b>으로 꾸준히 올랐다. 반면 빌라 전세 평균 보증금은 2.3~2.5억으로 아파트의 3분의 1 수준.",
    "4. <b>수요 유입은 빌라 가격에도 반영되고 있다.</b> 서울 빌라 매매 평균가는 3.91억(2024-07) → "
    "4.2~4.5억(2026)으로 <b>약 +12%</b>.",
    f"5. <b>빌라 매물 통계는 ‘광고 거품’이 적다.</b> 같은 집을 여러 중개사무소가 함께 올리는 중복을 걷어내면, "
    f"서울 빌라 매매는 광고 {v_ads:,}건 = 실매물 {v_units:,}건(<b>광고배율 ×{v_ads / v_units:.2f}</b>)인 반면 "
    f"서울 아파트는 광고 {a_ads:,}건 = 실매물 {a_units:,}건(<b>×{a_ads / a_units:.2f}</b>)이다. "
    "아파트는 광고 수가 실물의 2.7배로 부풀지만, 빌라는 광고 수가 곧 실제 매물에 가깝다.",
]:
    story.append(Paragraph(t, ss["body"]))
story.append(Spacer(1, 3 * mm))

# ── 표1: 매매 수요 이동 ──
grp1 = [Paragraph("표1. 서울 매매 — 아파트 vs 빌라 월별 계약과 빌라 비중 (25개월)", ss["h"])]
hdr1 = [P("월", "th"), P("아파트 매매<br/>(건)", "th"), P("빌라 매매<br/>(건)", "th"),
        P("빌라 비중<br/>(%)", "th"), P("빌라 평균가<br/>(억원)", "th")]
data1 = [hdr1]
warn1 = []
for i, r in enumerate(mon):
    ri = len(data1)
    ym = r["ym"]
    prov = ym >= "2026-06"
    data1.append([P(ym + (" *" if prov else ""), "tdl"), P(f"{int(r['apt_sale']):,}"),
                  P(f"{int(r['vil_sale']):,}"), P(f"<b>{r['sale_share']}</b>"), P(r["vil_avg"])])
    if prov:
        warn1.append((0, ri))
grp1.append(styled(data1, [24 * mm, 30 * mm, 30 * mm, 26 * mm, 28 * mm]))
grp1.append(Paragraph(
    "근거: 국토부 실거래(중개거래·해제 제외). 빌라 비중 = 빌라 ÷ (아파트+빌라). "
    "* 2026-06·07은 신고 기한(계약 후 30일)이 안 지난 잠정치 — 건수는 앞으로 더 늘어난다.", ss["cap"]))
story.append(KeepTogether(grp1))

# ── 표2: 전세 수요 이동 ──
grp2 = [Paragraph("표2. 서울 전세 — 아파트 vs 빌라 월별 계약과 빌라 비중", ss["h"])]
hdr2 = [P("월", "th"), P("아파트 전세<br/>(건)", "th"), P("빌라 전세<br/>(건)", "th"),
        P("빌라 비중<br/>(%)", "th"), P("아파트 평균<br/>보증금(억)", "th")]
data2 = [hdr2]
warn2 = []
for r in mon:
    ri = len(data2)
    ym = r["ym"]
    prov = ym >= "2026-06"
    data2.append([P(ym + (" *" if prov else ""), "tdl"), P(f"{int(r['apt_js']):,}"),
                  P(f"{int(r['vil_js']):,}"), P(f"<b>{r['js_share']}</b>"), P(r["aptjs_avg"])])
    if prov:
        warn2.append((0, ri))
grp2.append(styled(data2, [24 * mm, 30 * mm, 30 * mm, 26 * mm, 28 * mm]))
grp2.append(Paragraph(
    "근거: 표1과 동일 출처. 전세 = 보증금만 있는 계약(월세 0원). 아파트 전세 평균 보증금의 상승(5.70→6.60억)이 "
    "빌라 이동의 배경. * 잠정치.", ss["cap"]))
story.append(KeepTogether(grp2))

# ── 표3: 광고배율 ──
grp3 = [Paragraph("표3. 서울 매물 ‘광고 거품’ 비교 — 빌라 vs 아파트 (2026-07-13)", ss["h"])]
hdr3 = [P("구분", "th"), P("광고 수<br/>(건)", "th"), P("실매물<br/>(중복 제거)", "th"), P("광고배율<br/>(광고÷실매물)", "th")]
data3 = [hdr3]
for label, src, key in [("빌라 매매", vilr, "A1"), ("빌라 전세", vilr, "B1"), ("빌라 월세", vilr, "B2")]:
    r = src[key]
    ads, un = int(r["ads"]), int(r["units"])
    data3.append([P(label, "tdl"), P(f"{ads:,}"), P(f"{un:,}"), P(f"×{ads / un:.2f}")])
for label, key in [("아파트 매매", "A1"), ("아파트 전세", "B1"), ("아파트 월세", "B2")]:
    r = aptr[key]
    ads, un = int(r["apt_ads"]), int(r["apt_units"])
    data3.append([P(label, "tdl"), P(f"{ads:,}"), P(f"{un:,}"), P(f"<b>×{ads / un:.2f}</b>")])
grp3.append(styled(data3, [34 * mm, 34 * mm, 34 * mm, 34 * mm]))
grp3.append(Paragraph(
    "근거: 네이버부동산 동일주소 묶음(같은 집을 올린 광고 수)으로 중복을 합산 제거. "
    "아파트는 한 집을 평균 2.7곳이 광고하지만 빌라는 1.2곳 — 빌라 매물 수 통계는 부풀림이 적다.", ss["cap"]))
story.append(KeepTogether(grp3))

# ── 표3-2: 자치구별 ──
grp4 = [Paragraph("표4. 서울 자치구별 빌라 매매 — 2024 하반기 vs 2026 상반기 (같은 6개월끼리 비교)", ss["h"])]
hdr_g = [P("자치구", "th"), P("24년 하반기<br/>(건)", "th"), P("26년 상반기<br/>(건)", "th"), P("증가율<br/>(%)", "th"),
         P("자치구", "th"), P("24년 하반기<br/>(건)", "th"), P("26년 상반기<br/>(건)", "th"), P("증가율<br/>(%)", "th")]
half_g = (len(gu) + 1) // 2
data_g = [hdr_g]
for i in range(half_g):
    row = []
    for r in (gu[i], gu[i + half_g] if i + half_g < len(gu) else None):
        if r is None:
            row += [P(""), P(""), P(""), P("")]
        else:
            row += [P(r["구"], "tdl"), P(f"{int(r['h24']):,}"), P(f"{int(r['h26']):,}"), P(f"<b>+{r['chg']}</b>")]
    data_g.append(row)
grp4.append(styled(data_g, [20 * mm, 23 * mm, 23 * mm, 20 * mm, 20 * mm, 23 * mm, 23 * mm, 20 * mm]))
grp4.append(Paragraph(
    "근거: 국토부 실거래(중개거래·해제 제외). 서울 25개 자치구 <b>전부</b>에서 빌라 매매가 늘었다 — "
    "영등포(+168%)·송파(+137%)·광진(+120%)·성북(+111%)·동작(+106%)·강남(+104%) 순. 가장 적게 늘어난 용산도 +27%.", ss["cap"]))
story.append(KeepTogether(grp4))

grp5 = [Paragraph("표5. 어떤 빌라가 팔리나 — 가격대·연식별 매매 변화 (24년 하반기 → 26년 상반기)", ss["h"])]
hdr_p = [P("가격대", "th"), P("24H2 (건)", "th"), P("26H1 (건)", "th"), P("증가율", "th"),
         P("연식", "th"), P("24H2 (건)", "th"), P("26H1 (건)", "th"), P("증가율", "th")]
pb = [("2억 미만", 1670, 2078), ("2~4억", 5673, 8520), ("4~6억", 2101, 4196),
      ("6~10억", 784, 2403), ("10억 이상", 250, 768)]
ag = [("신축(5년 내)", 605, 1270), ("준신축(6~20년)", 5316, 8546), ("구축(20년+)", 4557, 8149), ("", "", ""), ("", "", "")]
data_p = [hdr_p]
for (n1, a1, b1), (n2, a2, b2) in zip(pb, ag):
    row = [P(n1, "tdl"), P(f"{a1:,}"), P(f"{b1:,}"), P(f"<b>+{(b1 - a1) * 100 // a1}%</b>")]
    if n2:
        row += [P(n2, "tdl"), P(f"{a2:,}"), P(f"{b2:,}"), P(f"<b>+{(b2 - a2) * 100 // a2}%</b>")]
    else:
        row += [P(""), P(""), P(""), P("")]
    data_p.append(row)
grp5.append(styled(data_p, [20 * mm, 21 * mm, 21 * mm, 18 * mm, 26 * mm, 21 * mm, 21 * mm, 18 * mm]))
grp5.append(Paragraph(
    "근거: 표4와 동일. 증가율이 가장 높은 구간은 <b>6~10억(+206%)·10억 이상(+207%)</b>. 6~10억 증가분은 신축 분양 물량이 아니다 — 26년 상반기 6~10억 거래의 <b>88%가 기존 주택</b>(구축 50%·준신축 38%, 신축 5년 내 12%) — 아파트를 대신할 수 있는 "
    "중고가 빌라로 수요가 확산되고 있다는 뜻이다. 연식으로는 신축(+109%)이 가장 빠르지만 구축(+78%)도 함께 늘었다. "
    "참고로 빌라 임대 시장 안에서는 전세 비중이 42.8%(24H2)→37.8%(26년)로 낮아지는 월세화가 동시에 진행 중 — "
    "아파트 대비 빌라 전세 ‘비중’ 상승(표2)은 아파트 전세 계약이 더 빠르게 줄어든 결과다.", ss["cap"]))
story.append(KeepTogether(grp5))

# ── 표6a: 데일리 전체 광고(23일, 빈칸 없음) ──
grp6 = [Paragraph("표6. 서울 빌라 매물 일별 추이 — 전체 광고, 수집 23일 전체", ss["h"])]
hdr6 = [P("날짜", "th"), P("광고(건)", "th"), P("전일 대비", "th"),
        P("날짜", "th"), P("광고(건)", "th"), P("전일 대비", "th")]
rows6 = []
prev = None
for r in trend:
    n = int(r["서울특별시"])
    d = (n - prev) if prev is not None else None
    rows6.append((r["date"], n, d))
    prev = n
half6 = (len(rows6) + 1) // 2
data6 = [hdr6]
for i in range(half6):
    row = []
    for x in (rows6[i], rows6[i + half6] if i + half6 < len(rows6) else None):
        if x is None:
            row += [P(""), P(""), P("")]
        else:
            dv = "—" if x[2] is None else (("+" if x[2] > 0 else "") + f"{x[2]:,}")
            row += [P(x[0], "tdl"), P(f"{x[1]:,}"), P(dv)]
    data6.append(row)
grp6.append(styled(data6, [23 * mm, 25 * mm, 20 * mm, 23 * mm, 25 * mm, 20 * mm]))
s0, s1 = rows6[0][1], rows6[-1][1]
grp6.append(Paragraph(
    f"근거: 콕집 일별 수집 로그(23일 연속, 결번 없음). 23일간 {s0:,} → {s1:,}건({(s1 - s0) / s0 * 100:+.1f}%) — "
    "수요 유입 속 매물이 완만히 줄어드는 흐름. 하루 1~3% 출렁임(예: 6/28 −3,243건)은 주말·광고 게재기간 만료가 몰리는 날의 자연스러운 변동으로, 수집 커버리지는 전 기간 동일(서울 373개 동)했다.", ss["cap"]))
story.append(KeepTogether(grp6))

# ── 표8: (참고) 전국 시도별 ──
SIDO_NM = {"11": "서울특별시", "26": "부산광역시", "27": "대구광역시", "28": "인천광역시",
           "29": "광주광역시", "30": "대전광역시", "31": "울산광역시", "36": "세종특별자치시",
           "41": "경기도", "51": "강원특별자치도", "43": "충청북도", "44": "충청남도",
           "52": "전북특별자치도", "46": "전라남도", "47": "경상북도", "48": "경상남도", "50": "제주특별자치도"}
SIDO_ORD = ["11", "26", "27", "28", "29", "30", "31", "36", "41", "51", "43", "44", "52", "46", "47", "48", "50"]
grp8 = [Paragraph("표7. (참고) 전국 시·도별 빌라 매물 종합 — 광고와 실매물 (2026-07-13)", ss["h"])]
hdr8a = [P("시·도", "th"), P("매매", "th"), "", P("전세", "th"), "", P("월세", "th"), "", P("전체 광고", "th")]
hdr8b = [P("", "th")] + [P(x, "th") for x in ["광고", "실매물"] * 3] + [P("(건)", "th")]
data8 = [hdr8a, hdr8b]
natd = {r["s"]: r for r in nat}
tots = [0] * 7
for sc in SIDO_ORD:
    r = natd.get(sc)
    if not r:
        continue
    v = [int(r[k] or 0) for k in ("a1", "a1u", "b1", "b1u", "b2", "b2u")]
    tot = v[0] + v[2] + v[4]
    for i in range(6):
        tots[i] += v[i]
    tots[6] += tot
    data8.append([P(SIDO_NM[sc], "tdl"), P(f"{v[0]:,}"), P(f"<b>{v[1]:,}</b>"), P(f"{v[2]:,}"),
                  P(f"<b>{v[3]:,}</b>"), P(f"{v[4]:,}"), P(f"<b>{v[5]:,}</b>"), P(f"{tot:,}")])
data8.append([P("전국 합계", "tdl")] + [P(f"<b>{tots[i]:,}</b>") for i in (0, 1, 2, 3, 4, 5)] + [P(f"<b>{tots[6]:,}</b>")])
spans8 = [((1, 0), (2, 0)), ((3, 0), (4, 0)), ((5, 0), (6, 0)), ((0, 0), (0, 1)), ((7, 0), (7, 1))]
grp8.append(styled(data8, [30 * mm, 19 * mm, 19 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 21 * mm],
                    header_rows=2, spans=spans8))
grp8.append(Paragraph(
    "근거: 콕집 빌라 매물 일별 집계(2026-07-13). 실매물 = 같은 집의 중복 광고를 하나로 합친 수. "
    "네이버는 광주·전남을 하나의 지역코드로 서빙해 콕집이 행정구역 기준으로 재분류했다. "
    "수도권(서울·경기·인천)이 전국 빌라 매물의 대부분을 차지하며, 지방 시·도의 빌라 광고 시장은 매우 작다.", ss["cap"]))
story.append(KeepTogether(grp8))

# ── 한계 ──
story.append(Paragraph("■ 분석의 한계와 해석 유의사항", ss["h"]))
for t in [
    "· <b>신고 지연</b>: 실거래는 계약 후 30일 안에 신고돼, 최근 1~2개월(*표시)은 잠정치이며 확정 수치는 더 커진다. 비중(%)은 분자·분모가 함께 늘어 왜곡이 작다.",
    "· <b>평균가의 구성 효과</b>: 평균가는 어떤 집이 거래됐는지(지역·신축 비중)에 따라 흔들린다. 빌라 평균가 상승(+12%)은 수요 유입과 신축 거래 증가가 섞인 값이다.",
    "· <b>아파트 매매가는 ‘상승 중’이라 단정하지 않았다</b>: 서울 아파트 평균 매매가는 2025년 초 급등 뒤 횡보 흐름이라, 이 보고서는 "
    "‘가격·전세가가 높은 수준에 고착되며 수요가 밀려난다’는 프레임을 데이터 근거로 삼는다(전세 보증금 +15.8%는 일관 상승).",
    "· <b>매물 수집 기간</b>: 빌라 매물 일별 수집은 2026-06-21 시작(23일). 유형(매매·전세·월세)·실매물 구분의 일별 집계는 2026-07-11부터 축적을 시작했으며, 축적이 쌓이는 다음 보고서부터 일별 상세 표로 제공한다.",
    "· 빌라 = 연립·다세대(국토부 분류). 오피스텔·단독·다가구는 포함하지 않는다.",
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
                    f"콕집(koczip.com) · 국토부 실거래 25개월 + 네이버부동산 빌라 매물 일별 수집 · 기준 {SNAP}")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=15 * mm,
                        title="서울 빌라 최근 동향 보고서")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("pdf:", OUT)
