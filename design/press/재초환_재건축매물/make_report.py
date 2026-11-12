# -*- coding: utf-8 -*-
"""재초환 보도 전후 서울 재건축 단지 매물 — 사업 단계별 보도자료 PDF. 수치는 ../data/press_jaecho.json 만 읽는다.
실행: python3 design/press/재초환_재건축매물/make_report.py
"""
import json
import statistics as stt
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
J = json.loads((HERE.parent / "data" / "press_jaecho.json").read_text())
ZONES = json.loads((HERE.parent / "data" / "press_jaecho_zones.json").read_text())
FONTS = HERE.parent.parent / "fonts"
OUT = HERE / "콕집_서울재건축_사업단계별_매물동향.pdf"
CHART = HERE.parent / "data" / "jaecho_chart.png"
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
BODY = st("b", 10.3, "P", lead=17.5, space=7)
NOTE = st("n", 8.8, "P", lead=14.5, color=MUTE, space=5)
CELL = st("c", 8.2, "P", lead=11)

G = J["order"]
WC = J["weekly_change"]
W = J["weekly"]
OCT = ["2026-10-14", "2026-10-21", "2026-10-28"]
LAST, PREV = "2026-11-11", "2026-11-04"


def cut(d, g):
    return WC[d][g]["cut"] * 100


def oct_avg(g):
    return stt.mean(cut(d, g) for d in OCT)


def cnt(d, g):
    return W[d].get(g, 0)


SP = J["span"]
F = J["focus"]
EUN, JAM = F["236"], F["639"]
pe, pj = SP["post"]["complex"]["236"], SP["post"]["complex"]["639"]
ae, aj = SP["since_aug"]["complex"]["236"], SP["since_aug"]["complex"]["639"]
MG, SI, AR, PRE, GEN = G  # order: 관리처분인가, 사업시행인가, 건축심의 통과, 건축심의 전, 일반 아파트


def table(rows, widths, head=1, bold_first=False, hi=()):
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=head)
    cmds = [("FONT", (0, 0), (-1, -1), "P", 8.2), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
            ("FONT", (0, 0), (-1, head - 1), "P-B", 7.9), ("TEXTCOLOR", (0, 0), (-1, head - 1), MUTE),
            ("LINEBELOW", (0, head - 1), (-1, head - 1), 0.9, INK), ("LINEBELOW", (0, head), (-1, -1), 0.4, LINE),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    for r in hi:
        cmds.append(("BACKGROUND", (0, r), (-1, r), BAND))
    if bold_first:
        cmds += [("FONT", (0, head), (-1, head), "P-B", 8.2)]
    t.setStyle(TableStyle(cmds))
    return KeepTogether(t)


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
    cv.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "2026년 11월 12일")
    cv.setStrokeColor(LINE); cv.setLineWidth(0.6)
    cv.line(20 * mm, A4[1] - 15 * mm, A4[0] - 20 * mm, A4[1] - 15 * mm)
    cv.setFont("P", 8.5)
    cv.drawString(20 * mm, 12 * mm, "koczip.com")
    cv.drawRightString(A4[0] - 20 * mm, 12 * mm, str(cv.getPageNumber()))
    cv.restoreState()


def sg(v, digits=2):
    c = UP if v > 0 else DOWN if v < 0 else INK
    return f'<font color="{c.hexval()}">{v:+.{digits}f}%</font>'


# ── 그림: 단계별 주간 호가 내린 집 비율 ──
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Regular.ttf"))
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Bold.ttf"))
plt.rcParams["font.family"] = "Pretendard"
fig, ax = plt.subplots(figsize=(8.6, 3.9), dpi=220)
xs = list(WC)
lab = [f"{int(d[5:7])}/{int(d[8:])}" for d in xs]
STY = {SI: ("#1268d3", 2.4), AR: ("#5aa0f0", 1.8), MG: ("#8a96a6", 1.4), PRE: ("#b9c4d2", 1.4), GEN: ("#b3261e", 2.0)}
for g in G:
    col, lw = STY[g]
    ys = [cut(d, g) for d in xs]
    ax.plot(range(len(xs)), ys, color=col, lw=lw, marker="o", ms=2.6, label=g)
    ax.text(len(xs) - 1 + 0.15, ys[-1], f"{ys[-1]:.1f}%", fontsize=7, color=col, va="center")
ax.axvspan(len(xs) - 1.5, len(xs) - 0.5, color="#fff1d6", zorder=0)
ax.text(len(xs) - 1, ax.get_ylim()[1] * 0.97 if ax.get_ylim()[1] else 30, "재초환 부과\n예정 보도(11/6)\n사전통지(11/9)", fontsize=6.6,
        ha="center", va="top", color="#8a5a00")
ax.set_xticks(range(len(xs))); ax.set_xticklabels(lab, fontsize=7)
ax.set_ylabel("직전 주보다 호가 내린 집(%)", fontsize=8)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", labelsize=7)
ax.grid(axis="y", color="#e6ebf1", lw=0.6); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=7.2, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
ax.set_xlim(-0.4, len(xs) - 0.1)
fig.tight_layout(); fig.savefig(CHART); plt.close(fig)

# ── 본문 ──
f = []
f.append(Paragraph("재초환 부과 현실화된 11월, 사업시행·건축심의 단계 재건축 호가 인하 다시 늘어", TITLE))
f.append(Paragraph(
    f"11월 둘째 주 같은 집 가운데 호가 내린 비율 — 사업시행인가 단지 {cut(LAST, SI):.1f}%, 건축심의 통과 단지 {cut(LAST, AR):.1f}%"
    f"(10월 주 평균 {oct_avg(SI):.1f}%·{oct_avg(AR):.1f}%), 일반 아파트는 {cut(LAST, GEN):.1f}%로 그대로<br/>"
    f"은마 매물 8월 {EUN['counts']['2026-08-05']:.0f}채 → 11월 {EUN['counts'][LAST]:.0f}채, 같은 집 절반({pe['cut'] * 100:.0f}%)이 한 주 새 호가 내려", SUB))
f.append(Spacer(1, 6))
f.append(Paragraph(
    "<b>콕집</b>(koczip.com)이 서울 아파트 재건축 단지의 매매 매물을 서울시 정비사업 추진 단계별로 나눠 매주 비교한 결과, "
    "재건축초과이익환수(재초환) 부담금 부과 절차가 알려진 11월 첫째·둘째 주에 <b>사업시행인가·건축심의 통과 단계 단지에서 호가를 내리는 매물이 다시 늘었다</b>. "
    f"11월 4일부터 11일까지 한 주 동안 같은 집 가운데 호가를 내린 비율은 사업시행인가 단지 {cut(LAST, SI):.1f}%, "
    f"건축심의 통과 단지 {cut(LAST, AR):.1f}%로, 10월 세 주 평균({oct_avg(SI):.1f}%·{oct_avg(AR):.1f}%)의 "
    f"{cut(LAST, SI) / oct_avg(SI):.1f}배·{cut(LAST, AR) / oct_avg(AR):.1f}배였다. 같은 기간 일반 아파트는 "
    f"{cut(LAST, GEN):.1f}%(10월 평균 {oct_avg(GEN):.1f}%)로 거의 변하지 않았다.", BODY))
f.append(Paragraph(
    f"사업시행인가를 받은 은마(7월 2일)와 잠실주공5단지(7월 1일)는 이번 주 같은 집의 절반 이상이 호가를 내렸다"
    f"(은마 {pe['cut'] * 100:.1f}%, 잠실주공5단지 {pj['cut'] * 100:.1f}%). 은마 매물은 8월 5일 {EUN['counts']['2026-08-05']:.0f}채에서 "
    f"11월 11일 {EUN['counts'][LAST]:.0f}채로 {EUN['counts'][LAST] / EUN['counts']['2026-08-05']:.1f}배가 됐고, 11월에도 "
    f"{EUN['counts']['2026-10-28']:.0f} → {EUN['counts'][PREV]:.0f} → {EUN['counts'][LAST]:.0f}채로 늘었다.", BODY))
f.append(Paragraph(
    f"반면 관리처분인가까지 받은 단지는 이번 주 {cut(LAST, MG):.1f}%로 10월 평균({oct_avg(MG):.1f}%)과 비슷했고, "
    f"건축심의 전 단계(구역지정·추진위·조합설립) 단지도 {cut(LAST, PRE):.1f}%(10월 {oct_avg(PRE):.1f}%)로 큰 변화가 없었다.", BODY))
f.append(Spacer(1, 2))
f.append(boxed(
    "<b>이 자료의 기준</b><br/>"
    "· <b>사업 단계</b>: 서울시 「정비사업 추진현황」(2026년 6월 말 기준, 서울 열린데이터광장)의 아파트 재건축 구역. "
    "은마·잠실주공5단지는 7월 사업시행인가를 반영했다. 공사 중(착공) 구역은 뺐다. "
    f"단지 수는 관리처분인가 {J['groups'][MG]}, 사업시행인가 {J['groups'][SI]}, 건축심의 통과 {J['groups'][AR]}, 건축심의 전(구역지정·추진위·조합설립) {J['groups'][PRE]}곳.<br/>"
    "· <b>일반 아파트</b>: 정비구역이 아닌 서울 아파트 단지.<br/>"
    "· <b>같은 집</b>: 비교하는 두 날 모두 매물로 나와 있던 집. 여러 중개사무소가 올린 같은 집 광고는 한 채로 묶고 호가는 그 중앙값이다.<br/>"
    "· <b>실매물</b>: 같은 집 중복 광고를 한 채로 센 집의 수. 매주 수요일 수집분 기준."))
f.append(Spacer(1, 10))
f.append(Image(str(CHART), width=170 * mm, height=170 * mm * 3.9 / 8.6))
f.append(Paragraph("그림 1. 사업 단계별 같은 집 가운데 직전 주보다 호가를 내린 집의 비율(매주 수요일 기준, 추석 주는 9/16→9/30 2주 비교).", NOTE))

# 1. 주간 표
f.append(CondPageBreak(120 * mm))
f.append(Paragraph("1. 단계별 주간 호가 — 같은 집 중 호가 내린 비율", H))
rows = [["주(끝나는 날)"] + G]
for d in list(WC)[-8:]:
    rows.append([f"{int(d[5:7])}월 {int(d[8:])}일"] + [f"{cut(d, g):.1f}%" for g in G])
rows.append(["10월 세 주 평균"] + [f"{oct_avg(g):.1f}%" for g in G])
f.append(table(rows, [26 * mm] + [28.8 * mm] * 5, hi=(len(rows) - 2,)))
f.append(Paragraph("음영은 재초환 부과 예정 보도(11/6)·사전통지(11/9)가 있었던 주. 각 칸은 직전 수요일 대비.", NOTE))
rows = [["단계", "같은 집 수", "호가 내림", "호가 올림", "평균 변동"]]
for g in G:
    x = SP["post"]["groups"][g]
    rows.append([g, f"{x['n']:,}", f"{x['cut'] * 100:.1f}%", f"{x['rise'] * 100:.1f}%", Paragraph(sg(x["mean"] * 100), st("r", 8.2, align=2))])
f.append(Paragraph("11월 4일 → 11월 11일", st("h3", 10, "P-B", space=3)))
f.append(table(rows, [34 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm]))

# 2. 매물 수
f.append(CondPageBreak(80 * mm))
f.append(Paragraph("2. 매물 수 — 단계별 실매물", H))
rows = [["단계", "8월 5일", "10월 28일", "11월 4일", "11월 11일", "8/5 대비", "10/28 대비"]]
for g in G:
    a, b, c, d = (cnt(x, g) for x in ("2026-08-05", "2026-10-28", PREV, LAST))
    rows.append([g, f"{a:,.0f}", f"{b:,.0f}", f"{c:,.0f}", f"{d:,.0f}", f"{(d / a - 1) * 100:+.1f}%", f"{(d / b - 1) * 100:+.1f}%"])
f.append(table(rows, [32 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm]))
f.append(Paragraph(
    "단계별 매물 수는 8월 이후 일반 아파트와 비슷한 속도로 늘었다. 매물 수보다 두드러진 차이는 호가다. "
    f"8월 5일과 11월 11일 모두 나와 있던 같은 집을 보면 일반 아파트는 {SP['since_aug']['groups'][GEN]['cut'] * 100:.0f}%가 호가를 내려 평균 "
    f"{SP['since_aug']['groups'][GEN]['mean'] * 100:+.1f}%였지만, 재건축 단지는 사업시행인가 {SP['since_aug']['groups'][SI]['cut'] * 100:.0f}%"
    f"(평균 {SP['since_aug']['groups'][SI]['mean'] * 100:+.1f}%), 건축심의 통과 {SP['since_aug']['groups'][AR]['cut'] * 100:.0f}%"
    f"({SP['since_aug']['groups'][AR]['mean'] * 100:+.1f}%), 건축심의 전 {SP['since_aug']['groups'][PRE]['cut'] * 100:.0f}%"
    f"({SP['since_aug']['groups'][PRE]['mean'] * 100:+.1f}%)가 내렸다. 은마는 석 달 동안 나와 있던 같은 집 {ae['n']}채가 모두 호가를 내려 평균 "
    f"{ae['mean'] * 100:+.1f}%, 잠실주공5단지는 {aj['n']}채 중 {aj['cut'] * 100:.0f}%가 내려 평균 {aj['mean'] * 100:+.1f}%였다.", BODY))

# 3. 주요 단지
f.append(CondPageBreak(110 * mm))
f.append(Paragraph("3. 주요 재건축 단지", H))
zone_by = {n: z for z in ZONES for n in z["complex_nos"]}
items = []
for no, x in F.items():
    post = SP["post"]["complex"].get(no)
    aug = SP["since_aug"]["complex"].get(no)
    if not post or x["counts"][LAST] < 60:
        continue
    items.append((x, post, aug))
items.sort(key=lambda t: -t[0]["counts"][LAST])
rows = [["단지(자치구)", "단계", "매물 8/5", "매물 11/11", "11/4→11/11\n호가 내린 집", "8/5→11/11\n평균 변동"]]
for x, post, aug in items[:18]:
    rows.append([f"{x['name']}({x['gu'].replace('구', '')})", x["group"], f"{x['counts']['2026-08-05']:.0f}", f"{x['counts'][LAST]:.0f}",
                 f"{post['cut'] * 100:.0f}%", Paragraph(sg(aug["mean"] * 100, 1), st("r2", 8.2, align=2)) if aug else "—"])
f.append(table(rows, [52 * mm, 26 * mm, 20 * mm, 20 * mm, 26 * mm, 26 * mm]))
f.append(Paragraph("11월 11일 실매물 60채 이상인 재건축 단지, 매물 많은 순. 평균 변동은 8월 5일과 11월 11일에 모두 나와 있던 같은 집 기준"
                   "(같은 집 10채 미만이면 ‘—’). 압구정·여의도·반포 등의 단계는 서울시 6월 말 자료 기준이다.", NOTE))
f.append(Spacer(1, 6))
f.append(KeepTogether([Paragraph("분석 개요", H), Paragraph(
    "<b>대상</b>  서울 아파트 매매 매물 호가 전수(오피스텔 제외). 재건축 단지는 서울시 정비사업 추진현황(2026년 6월 말)의 "
    "공동주택재건축·아파트지구재건축 구역을 콕집 단지와 지번·구역명으로 연결<br/>"
    "<b>시점</b>  2026년 8월 5일부터 11월 11일까지 매주 수요일 하루치 수집분<br/>"
    "<b>같은 집</b>  단지·동·층·공급·전용·방향이 같은 광고를 한 채로 묶고 호가는 광고들의 중앙값. ±30% 넘는 변동은 오기재로 보고 제외<br/>"
    "<b>재초환 일정</b>  11월 4일 서초구 제도 폐지 건의, 11월 6일 반포현대 부담금 예정액 사전통지 예정 보도, 11월 9일 사전통지", NOTE)]))
f.append(Spacer(1, 8))
by = st("by", 9.5, "P-M", color=MUTE, lead=15)
f.append(KeepTogether([Paragraph("작성 | 콕집 공동창업자 조용호", by), Paragraph("문의 | 콕집(koczip.com) CTO 황인찬 · runtoonline@gmail.com", by)]))
SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=18 * mm,
                  title="콕집 — 서울 재건축 사업 단계별 매물 동향", author="콕집").build(f, onFirstPage=page, onLaterPages=page)
print("생성:", OUT)
