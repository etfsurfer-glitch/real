# -*- coding: utf-8 -*-
"""서울 아파트 매매 매물 20~35억 세 구간 — 자치구별 보도자료 PDF. 수치는 ../data/press_hoga_band_gu.json 만 읽는다.
실행: python3 design/press/호가구간별매물_자치구/make_report.py
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent
J = json.loads((HERE.parent / "data" / "press_hoga_band_gu.json").read_text())
FONTS = HERE.parent.parent / "fonts"
OUT = HERE / "콕집_서울아파트_20~35억_자치구별_매물동향.pdf"
CHART = HERE.parent / "data" / "hoga_band_gu_chart.png"
INK, MUTE, LINE = colors.HexColor("#1b2430"), colors.HexColor("#5b6775"), colors.HexColor("#d9e0e8")
BRAND, UP, DOWN = colors.HexColor("#1268d3"), colors.HexColor("#b3261e"), colors.HexColor("#1268d3")
BAND = colors.HexColor("#f2f7ff")
for nm, fn in (("P", "Pretendard-Regular.ttf"), ("P-B", "Pretendard-Bold.ttf"), ("P-M", "Pretendard-Medium.ttf"), ("P-EB", "Pretendard-ExtraBold.ttf")):
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="P-B", italic="P", boldItalic="P-B")
ss = getSampleStyleSheet()


def st(name, size, font="P", lead=None, color=INK, space=0, align=0):
    return ParagraphStyle(name, parent=ss["Normal"], fontName=font, fontSize=size, leading=lead or size * 1.55,
                          textColor=color, spaceAfter=space, alignment=align)


TITLE = st("t", 19, "P-EB", lead=27, space=5)
SUB = st("s", 11, "P-M", lead=17.5, color=BRAND, space=3)
H = st("h", 13.5, "P-B", lead=20, space=6)
H2 = st("h2", 11, "P-B", lead=16, space=4)
BODY = st("b", 10.3, "P", lead=17.5, space=7)
NOTE = st("n", 8.8, "P", lead=14.5, color=MUTE, space=5)
CELL = st("c", 8.2, "P", lead=11)
CELLR = st("cr", 8.2, "P", lead=11, align=2)

A, Z = "2026-08-03", "2026-11-11"
B, GUS = J["bands"], J["gus"]
MIN_BASE = 30                                   # 8/3 30채 미만이면 증감률 대신 건수만


def o(d, b, g=None):
    x = J["dates"][d][b]
    return x["obj_total"] if g is None else x["obj"][g]


def inc(b, g=None):
    return o(Z, b, g) - o(A, b, g)


def pct(b, g=None):
    a = o(A, b, g)
    return (o(Z, b, g) / a - 1) * 100 if a else None


def sgp(v, base):
    if base < MIN_BASE or v is None:
        return Paragraph('<font color="#5b6775">—</font>', CELLR)
    c = UP if v > 0 else DOWN if v < 0 else INK
    return Paragraph(f'<font color="{c.hexval()}"><b>{v:+.0f}%</b></font>', CELLR)


def table(rows, widths, head=1, hi=(), bold_first=False, keep=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=head)
    cmds = [("FONT", (0, 0), (-1, -1), "P", 8.2), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
            ("FONT", (0, 0), (-1, head - 1), "P-B", 7.9), ("TEXTCOLOR", (0, 0), (-1, head - 1), MUTE),
            ("LINEBELOW", (0, head - 1), (-1, head - 1), 0.9, INK), ("LINEBELOW", (0, head), (-1, -1), 0.4, LINE),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    for r in hi:
        cmds.append(("BACKGROUND", (0, r), (-1, r), BAND))
    if bold_first:
        cmds += [("FONT", (0, head), (-1, head), "P-B", 8.2), ("LINEBELOW", (0, head), (-1, head), 0.8, INK)]
    t.setStyle(TableStyle(cmds))
    return KeepTogether(t) if keep else t


def boxed(html):
    t = Table([[Paragraph(html, CELL)]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BAND), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfe0f8")),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    return t


def page(cv, doc):
    cv.saveState()
    cv.setFont("P-B", 8.5); cv.setFillColor(MUTE)
    cv.drawString(20 * mm, A4[1] - 12 * mm, "콕집 부동산 데이터 리포트")
    cv.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "2026년 11월 11일")
    cv.setStrokeColor(LINE); cv.setLineWidth(0.6)
    cv.line(20 * mm, A4[1] - 15 * mm, A4[0] - 20 * mm, A4[1] - 15 * mm)
    cv.setFont("P", 8.5)
    cv.drawString(20 * mm, 12 * mm, "koczip.com")
    cv.drawRightString(A4[0] - 20 * mm, 12 * mm, str(cv.getPageNumber()))
    cv.restoreState()


def rank(b, n=5):
    return sorted(GUS, key=lambda g: -inc(b, g))[:n]


def pn(b, g="서울"):
    return J["panel"][b].get(g) or {"n": 0, "cut": 0, "rise": 0, "mean": None}


def mv(b, g="서울"):
    return J["move"][b].get(g) or {}


def net(b, g="서울"):
    m = mv(b, g)
    return m.get("in_above", 0) + m.get("in_below", 0) - m.get("out_down", 0) - m.get("out_up", 0)


B20, B25, B30 = B
BIG4 = ["송파구", "강남구", "서초구", "강동구"]
big4_25 = sum(inc(B25, g) for g in BIG4)
top25, top20, top30 = rank(B25), rank(B20), rank(B30)
cutr = lambda b, g="서울": pn(b, g)["cut"] / pn(b, g)["n"] * 100 if pn(b, g)["n"] else 0

# ── 그림: 25~30억 자치구별 8/3 vs 11/11(상위 12개 구) ──
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Regular.ttf"))
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Bold.ttf"))
plt.rcParams["font.family"] = "Pretendard"
fig, axs = plt.subplots(1, 3, figsize=(8.6, 4.1), dpi=220, sharey=False)
for ax, b in zip(axs, B):
    gs = sorted([g for g in GUS if o(Z, b, g) >= 40 or o(A, b, g) >= 40], key=lambda g: o(Z, b, g))[-10:]
    y = range(len(gs))
    ax.barh([k + 0.2 for k in y], [o(A, b, g) for g in gs], 0.38, color="#c9d6e6", label="8월 3일")
    ax.barh([k - 0.2 for k in y], [o(Z, b, g) for g in gs], 0.38, color="#1268d3", label="11월 11일")
    ax.set_yticks(list(y)); ax.set_yticklabels([g.replace("구", "") for g in gs], fontsize=8)
    for k, g in enumerate(gs):
        ax.text(o(Z, b, g) + 15, k - 0.2, f"{inc(b, g):+,}", va="center", fontsize=6.8, color="#1b2430")
    ax.set_title(b, fontsize=9.5, fontweight="bold", color="#1b2430", loc="left")
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="x", labelsize=7, colors="#5b6775"); ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#e6ebf1", linewidth=0.6); ax.set_axisbelow(True)
    ax.set_xlim(0, max(o(Z, b, g) for g in gs) * 1.22)
axs[0].legend(frameon=False, fontsize=7.5, loc="lower right")
fig.tight_layout(); fig.savefig(CHART); plt.close(fig)

# ── 본문 ──
f = []
f.append(Paragraph(f"서울 25~30억 아파트 매물 석 달 새 {pct(B25):.0f}% 늘어<br/>— 송파 두 배, 강남3구·강동이 증가의 {big4_25 / inc(B25) * 100:.0f}%", TITLE))
f.append(Paragraph(
    f"25~30억 구간 실매물 {o(A, B25):,}채(8/3) → {o(Z, B25):,}채(11/11). 송파 {o(A, B25, '송파구'):,} → {o(Z, B25, '송파구'):,}채"
    f"({pct(B25, '송파구'):+.0f}%), 강동 {pct(B25, '강동구'):+.0f}%<br/>"
    f"20~25억은 강동·성동·송파가 고르게, 30~35억은 강남이 증가분의 {inc(B30, '강남구') / inc(B30) * 100:.0f}% — "
    f"송파·강동 30억대는 거의 안 늘고 같은 집 {min(cutr(B30, '송파구'), cutr(B30, '강동구')):.0f}% 이상이 호가 내려", SUB))
f.append(Spacer(1, 6))
f.append(Paragraph(
    f"<b>콕집</b>(koczip.com)이 서울 아파트(재건축·분양권 포함) 매매 매물을 호가 20~25억·25~30억·30~35억 원 세 구간으로 나눠 "
    f"8월 3일과 11월 11일의 자치구별 실매물을 비교한 결과, 세 구간 가운데 <b>25~30억 원대가 {pct(B25):.1f}%({inc(B25):+,}채)</b>로 "
    f"가장 많이 늘었다. 같은 기간 20~25억은 {pct(B20):+.1f}%({inc(B20):+,}채), 30~35억은 {pct(B30):+.1f}%({inc(B30):+,}채)였다.", BODY))
f.append(Paragraph(
    f"25~30억 구간의 증가는 강남3구와 강동에 몰렸다. 송파({inc(B25, '송파구'):+,}채)·강남({inc(B25, '강남구'):+,})·"
    f"강동({inc(B25, '강동구'):+,})·서초({inc(B25, '서초구'):+,}) 네 곳이 이 구간 증가분의 <b>{big4_25 / inc(B25) * 100:.0f}%</b>를 차지했다. "
    f"특히 송파는 {o(A, B25, '송파구'):,}채에서 {o(Z, B25, '송파구'):,}채로 <b>{pct(B25, '송파구'):.0f}%</b> 늘어 두 배가 됐고, "
    f"서울 25~30억 매물에서 송파가 차지하는 비중도 {o(A, B25, '송파구') / o(A, B25) * 100:.0f}%에서 "
    f"{o(Z, B25, '송파구') / o(Z, B25) * 100:.0f}%로 높아졌다. 강동은 {o(A, B25, '강동구')}채에서 {o(Z, B25, '강동구')}채로 "
    f"{pct(B25, '강동구'):.0f}% 늘어 증가율이 가장 높았다.", BODY))
f.append(Spacer(1, 2))
f.append(boxed(
    "<b>이 자료의 기준</b><br/>"
    "· <b>실매물</b>: 같은 집을 여러 중개사무소가 올린 광고를 한 채로 센 실제 집의 수(중복 광고 제외). 아파트·재건축·아파트 분양권 합계. "
    "서울 전체 숫자는 앞서 낸 「호가 구간별 매물 동향」과 같다.<br/>"
    "· <b>호가 구간</b>: 하한 포함·상한 미포함. 25~30억 = 25억 원 이상 30억 원 미만.<br/>"
    "· <b>시점</b>: 각 날짜 하루치 수집분. 8월 3일은 세제개편안 발표(18시) 전에 수집된 매물이다.<br/>"
    "· <b>같은 집</b>: 두 날 모두 매물로 나와 있던 집. 호가를 내리거나 올린 비율은 이 기준이다."))
f.append(Spacer(1, 10))
f.append(Image(str(CHART), width=170 * mm, height=170 * mm * 4.1 / 8.6))
f.append(Paragraph("그림 1. 구간별 실매물 상위 10개 구(11월 11일 기준). 숫자는 8/3 → 11/11 증감(채).", NOTE))

# 1. 전체 표
f.append(CondPageBreak(150 * mm))
f.append(Paragraph("1. 자치구별 매물 수 — 8월 3일 → 11월 11일", H))
hdr1 = ["자치구"] + [x for b in B for x in (b, "", "")]
hdr2 = [""] + [x for _ in B for x in ("8/3", "11/11", "증감률")]
rows = [hdr1, hdr2]
r = ["서울 전체"]
for b in B:
    r += [f"{o(A, b):,}", f"{o(Z, b):,}", sgp(pct(b), o(A, b))]
rows.append(r)
for g in GUS:
    r = [g]
    for b in B:
        r += [f"{o(A, b, g):,}", f"{o(Z, b, g):,}", sgp(pct(b, g), o(A, b, g))]
    rows.append(r)
t = Table(rows, colWidths=[20 * mm] + [16.6 * mm, 16.6 * mm, 16.6 * mm] * 3, hAlign="LEFT", repeatRows=2)
cmds = [("FONT", (0, 0), (-1, -1), "P", 8.2), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("FONT", (0, 0), (-1, 1), "P-B", 7.9), ("TEXTCOLOR", (0, 0), (-1, 1), MUTE),
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (3, 0)), ("SPAN", (4, 0), (6, 0)), ("SPAN", (7, 0), (9, 0)),
        ("ALIGN", (1, 0), (-1, 0), "CENTER"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LINEBELOW", (1, 0), (-1, 0), 0.4, LINE), ("LINEBELOW", (0, 1), (-1, 1), 0.9, INK),
        ("FONT", (0, 2), (-1, 2), "P-B", 8.2), ("LINEBELOW", (0, 2), (-1, 2), 0.8, INK), ("LINEBELOW", (0, 3), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (4, 2), (6, -1), BAND), ("LINEBEFORE", (4, 0), (4, -1), 0.4, LINE), ("LINEBEFORE", (7, 0), (7, -1), 0.4, LINE)]
t.setStyle(TableStyle(cmds))
f.append(t)
f.append(Paragraph(f"단위: 채(실매물). 음영은 25~30억 구간. 8월 3일 매물이 {MIN_BASE}채 미만인 칸은 증감률을 ‘—’로 두었다(적은 수의 변화가 큰 비율로 보이는 것을 막으려고). "
                   "구 순서는 행정 코드 순.", NOTE))

# 2. 구간별 증가 상위
f.append(CondPageBreak(95 * mm))
f.append(Paragraph("2. 구간별로 어디가 늘었나", H))
rows = [["순위"] + [x for b in B for x in (b, "증가(채)", "비중")]]
for i in range(5):
    r = [str(i + 1)]
    for b, tp in ((B20, top20), (B25, top25), (B30, top30)):
        g = tp[i]
        r += [g, f"{inc(b, g):+,}", f"{inc(b, g) / inc(b) * 100:.0f}%"]
    rows.append(r)
f.append(table(rows, [11 * mm] + [19 * mm, 18 * mm, 16 * mm] * 3))
f.append(Paragraph("비중 = 서울 전체 그 구간 증가분 중 그 구의 몫.", NOTE))
f.append(Paragraph(
    f"· <b>20~25억</b>: 강동({inc(B20, '강동구'):+,})·성동({inc(B20, '성동구'):+,})·송파({inc(B20, '송파구'):+,})·"
    f"강남({inc(B20, '강남구'):+,})·마포({inc(B20, '마포구'):+,}) 순으로, 한 구에 쏠리지 않고 한강 주변 여러 구에서 고르게 늘었다. "
    f"마용성(마포·용산·성동)만 합쳐도 {inc(B20, '마포구') + inc(B20, '용산구') + inc(B20, '성동구'):+,}채다. "
    f"증가율은 양천({pct(B20, '양천구'):+.0f}%)·강동({pct(B20, '강동구'):+.0f}%)이 높았다.<br/>"
    f"· <b>25~30억</b>: 송파 한 곳이 증가분의 {inc(B25, '송파구') / inc(B25) * 100:.0f}%를 차지했다. "
    f"강남·서초·강동을 더한 네 곳이 {big4_25 / inc(B25) * 100:.0f}%다. 강남3구 밖에서는 성동({inc(B25, '성동구'):+,})·영등포({inc(B25, '영등포구'):+,})가 뒤를 이었다.<br/>"
    f"· <b>30~35억</b>: 강남이 {inc(B30, '강남구'):+,}채로 증가분의 {inc(B30, '강남구') / inc(B30) * 100:.0f}%, 서초가 "
    f"{inc(B30, '서초구') / inc(B30) * 100:.0f}%다. 반면 송파는 {pct(B30, '송파구'):+.0f}%, 강동은 {pct(B30, '강동구'):+.0f}%로 "
    "거의 늘지 않았다.", BODY))

# 3. 송파·강동: 30억대는 내리고 25~30억이 늘었다
f.append(CondPageBreak(90 * mm))
f.append(Paragraph("3. 같은 집의 호가 — 송파·강동 30억대는 내렸다", H))
f.append(Paragraph(
    "8월 3일과 11월 11일에 모두 나와 있던 같은 집의 호가를 비교했다(구간은 8월 3일 호가 기준). "
    f"서울 전체로는 30~35억 구간의 같은 집 {cutr(B30):.0f}%가 호가를 내렸고, 25~30억은 {cutr(B25):.0f}%, 20~25억은 {cutr(B20):.0f}%였다.", BODY))
KEY = ["송파구", "강남구", "서초구", "강동구", "성동구", "마포구", "용산구", "영등포구", "양천구", "동작구"]
rows = [["자치구"] + [x for b in B for x in (b, "평균 변동")]]
rows.append(["서울 전체"] + [x for b in B for x in (f"내림 {cutr(b):.0f}% · 올림 {pn(b)['rise'] / pn(b)['n'] * 100:.0f}%", f"{pn(b)['mean']:+.1f}%")])
for g in KEY:
    r = [g]
    for b in B:
        p = pn(b, g)
        if p["n"] >= 30:
            r += [f"내림 {p['cut'] / p['n'] * 100:.0f}% · 올림 {p['rise'] / p['n'] * 100:.0f}%", f"{p['mean']:+.1f}%"]
        else:
            r += ["—", "—"]
    rows.append(r)
f.append(table(rows, [18 * mm] + [32 * mm, 18.5 * mm] * 3, bold_first=True))
f.append(Paragraph("같은 집 30채 이상인 칸만 표시. 평균 변동은 같은 집 각각의 호가 변동률(값을 안 바꾼 집 0% 포함)의 평균.", NOTE))
f.append(Paragraph(
    f"송파의 30~35억 구간은 같은 집 <b>{cutr(B30, '송파구'):.0f}%</b>가 호가를 내렸고 평균 {pn(B30, '송파구')['mean']:+.1f}%였다. "
    f"강동도 {cutr(B30, '강동구'):.0f}%가 내렸다(평균 {pn(B30, '강동구')['mean']:+.1f}%). 두 구 모두 30억대 매물은 거의 늘지 않은 채 "
    "호가를 낮추는 쪽으로 움직였다. 강남(30~35억 내림 "
    f"{cutr(B30, '강남구'):.0f}%)·서초({cutr(B30, '서초구'):.0f}%)도 절반 이상이 내렸지만, 두 구는 30억대 매물 자체가 크게 늘었다.", BODY))

# 4. 25~30억 증가분 구성
f.append(CondPageBreak(80 * mm))
f.append(Paragraph("4. 25~30억 증가분은 어디서 왔나 — 새 매물이 대부분", H))
rows = [["자치구", "실매물 증가", "위 구간에서\n내려온 집", "아래 구간에서\n올라온 집", "이 구간에서\n빠져나간 집", "구간 이동\n순증", "11/11 매물 중\n새 매물"]]
for g in ["서울"] + ["송파구", "강남구", "강동구", "서초구", "성동구", "영등포구"]:
    m = mv(B25, g)
    rows.append(["서울 전체" if g == "서울" else g, f"{inc(B25, None if g == '서울' else g):+,}", f"{m.get('in_above', 0):,}", f"{m.get('in_below', 0):,}",
                 f"{m.get('out_down', 0) + m.get('out_up', 0):,}", f"{net(B25, g):+,}", f"{m.get('new', 0):,}"])
f.append(table(rows, [20 * mm, 22 * mm, 24 * mm, 24 * mm, 24 * mm, 22 * mm, 24 * mm], bold_first=True))
f.append(Paragraph("구간 이동은 두 날 모두 있던 같은 집이 호가를 바꿔 구간을 옮긴 수. 새 매물은 8월 3일에 없던 집. "
                   "구간 이동·새 매물은 같은 집 판정(단지·동·층·전용·향·공급면적) 단위로 센 것이라 실매물 수와 단위가 조금 다르다.", NOTE))
f.append(Paragraph(
    f"25~30억 구간으로 위에서 내려온 집은 서울 전체 {mv(B25)['in_above']:,}채, 이 구간에서 빠져나간 집을 빼면 순증은 "
    f"{net(B25):+,}채로 증가분({inc(B25):+,}채)의 {net(B25) / inc(B25) * 100:.0f}%다. 송파도 순증 {net(B25, '송파구'):+,}채로 "
    f"증가분({inc(B25, '송파구'):+,}채)의 {net(B25, '송파구') / inc(B25, '송파구') * 100:.0f}%에 그친다. "
    "호가를 내린 30억대 매물이 25~30억으로 내려온 효과는 있지만, <b>증가분의 대부분은 이 가격대에 새로 나온 매물</b>이다.", BODY))
f.append(Spacer(1, 6))
f.append(KeepTogether([Paragraph("분석 개요", H), Paragraph(
    "<b>대상</b>  서울 25개 자치구 아파트·재건축·아파트 분양권 매매 매물 호가 전수(오피스텔 제외)<br/>"
    "<b>시점</b>  2026년 8월 3일(세제개편안 발표 전 수집분)·11월 11일, 각 날짜 하루치 수집분<br/>"
    "<b>실매물</b>  같은 집에 붙은 광고를 한 채로 셈. 구별 숫자의 합이 서울 전체와 같도록 맞췄다<br/>"
    "<b>오기재</b>  같은 단지·같은 전용면적 호가 중앙값의 0.4~2.5배를 벗어난 광고(자릿수 오타)는 제외<br/>"
    "<b>같은 집</b>  단지·동·층·전용·향·공급면적이 같은 광고를 한 채로 묶고 호가는 광고들의 중앙값. ±30% 넘는 변동은 제외", NOTE)]))
f.append(Spacer(1, 8))
by = st("by", 9.5, "P-M", color=MUTE, lead=15)
f.append(KeepTogether([Paragraph("작성 | 콕집 공동창업자 조용호", by), Paragraph("문의 | 콕집(koczip.com) CTO 황인찬 · runtoonline@gmail.com", by)]))
SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=18 * mm,
                  title="콕집 — 서울 아파트 20~35억 자치구별 매물 동향", author="콕집").build(f, onFirstPage=page, onLaterPages=page)
print("생성:", OUT)
