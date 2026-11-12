# -*- coding: utf-8 -*-
"""재초환 부과 절차 전후 서울 재건축 단지 매물 호가 — 보도자료 PDF. 수치는 ../data/press_jaecho.json 만 읽는다.

논리(2026-11-12 검증):
 1) 호가를 내린 집과 올린 집을 함께 본다(같은 집, 직전 수요일 대비). 한쪽만 보면 방향이 왜곡된다.
 2) 비교 기준은 10월 세 주(10/14·10/21·10/28 주) 평균. 8월 이후 누적은 쓰지 않는다(석 달 남은 집만 남아 인하 쪽으로 쏠림).
 3) 은마·잠실5단지가 사업시행인가 묶음 같은 집의 1/3 — 두 단지를 뺀 숫자를 함께 낸다.
 4) 몇 단지의 움직임이 아님을 보이려고 '내린 집이 더 많은 단지 / 올린 집이 더 많은 단지' 수를 센다(같은 집 5채 이상 단지).
 5) 시점은 사실만: 변화가 11월 첫째 주부터 나타나 둘째 주에 커졌다. 재초환 일정과 겹친다고만 쓰고 원인으로 단정하지 않는다.
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
FONTS = HERE.parent.parent / "fonts"
OUT = HERE / "콕집_서울재건축_사업단계별_매물동향.pdf"
CH1 = HERE.parent / "data" / "jaecho_chart1.png"
CH2 = HERE.parent / "data" / "jaecho_chart2.png"
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
CR = st("cr", 8.2, "P", lead=11, align=2)

# ── 데이터 ──
WC, WX, W, F = J["weekly_change"], J["weekly_complex"], J["weekly"], J["focus"]
MG, SI, AR, PRE, GEN = J["order"]
ALL, SIX = "재건축 전체", "사업시행인가(은마·잠실5 제외)"
OCT = ["2026-10-14", "2026-10-21", "2026-10-28"]
O28, N1, N2 = "2026-10-28", "2026-11-04", "2026-11-11"
STAGES = [MG, SI, SIX, AR, PRE, ALL, GEN]


def wk(d, g, k):
    return WC[d][g][k] * 100


def octv(g, k):
    return stt.mean(wk(d, g, k) for d in OCT)


def breadth(d, grp=None):
    """재건축 단지 중 내린 집이 더 많은 단지 / 올린 집이 더 많은 단지 / 전체(같은 집 5채 이상)."""
    c = r = n = 0
    for no, x in WX[d].items():
        if no not in F or (grp and F[no]["group"] != grp):
            continue
        n += 1
        c += x["cut"] > x["rise"]
        r += x["rise"] > x["cut"]
    return c, r, n


def cx(no, d):
    return WX[d].get(no)


B = {d: breadth(d) for d in WX if d >= "2026-09-30"}
r_oct = max(B[d][1] for d in OCT)
d_oct = [d for d in OCT if B[d][1] == r_oct][0]
EUN, JAM = "236", "639"
NAMED = {x["name"]: no for no, x in F.items()}
K6, K7, SB2 = NAMED["개포주공6단지"], NAMED["개포주공7단지"], NAMED["신반포2차"]


def lbl(d):
    return f"{int(d[5:7])}월 {int(d[8:])}일"


def pc(no, d, k):
    return cx(no, d)[k] * 100


def table(rows, widths, head=1, hi=(), bold_rows=()):
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=head)
    cmds = [("FONT", (0, 0), (-1, -1), "P", 8.2), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
            ("FONT", (0, 0), (-1, head - 1), "P-B", 7.9), ("TEXTCOLOR", (0, 0), (-1, head - 1), MUTE),
            ("LINEBELOW", (0, head - 1), (-1, head - 1), 0.9, INK), ("LINEBELOW", (0, head), (-1, -1), 0.4, LINE),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    for r in hi:
        cmds.append(("BACKGROUND", (0, r), (-1, r), BAND))
    for r in bold_rows:
        cmds.append(("FONT", (0, r), (-1, r), "P-B", 8.2))
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


def sgn(v, d=2):
    c = UP if v > 0 else DOWN if v < 0 else INK
    return Paragraph(f'<font color="{c.hexval()}">{v:+.{d}f}%</font>', CR)


def cr_(no, d):
    x = cx(no, d)
    return f"{x['cut'] * 100:.0f}% / {x['rise'] * 100:.0f}%" if x else "—"


# ── 그림 1: 재건축 전체 vs 일반 아파트, 내린 집·올린 집 ──
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Regular.ttf"))
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Bold.ttf"))
plt.rcParams["font.family"] = "Pretendard"
xs = list(WC)
lab = [f"{int(d[5:7])}/{int(d[8:])}" for d in xs]
fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=220)
for g, k, col, ls, name in ((ALL, "cut", "#1268d3", "-", "재건축 · 내린 집"), (ALL, "rise", "#1268d3", "--", "재건축 · 올린 집"),
                            (GEN, "cut", "#b3261e", "-", "일반 아파트 · 내린 집"), (GEN, "rise", "#b3261e", "--", "일반 아파트 · 올린 집")):
    ys = [wk(d, g, k) for d in xs]
    ax.plot(range(len(xs)), ys, color=col, ls=ls, lw=2.0 if k == "cut" else 1.6, marker="o", ms=2.4, label=name)
    ax.text(len(xs) - 1 + 0.15, ys[-1], f"{ys[-1]:.1f}%", fontsize=7, color=col, va="center")
ax.axvspan(xs.index(OCT[0]) - 0.5, xs.index(OCT[-1]) + 0.5, color="#eef2f7", zorder=0)
ax.axvspan(xs.index(N1) - 0.5, xs.index(N2) + 0.5, color="#fff1d6", zorder=0)
top = max(wk(d, ALL, "cut") for d in xs) * 1.15
ax.text(xs.index(OCT[1]), top, "10월 비교 기준", fontsize=6.8, ha="center", va="top", color="#5b6775")
ax.text(xs.index(N1) + 0.5, top, "11월 1·2주", fontsize=6.8, ha="center", va="top", color="#8a5a00")
ax.set_ylim(0, top * 1.02)
ax.set_xticks(range(len(xs))); ax.set_xticklabels(lab, fontsize=7)
ax.set_ylabel("같은 집 중 비율(%)", fontsize=8)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", labelsize=7)
ax.grid(axis="y", color="#e6ebf1", lw=0.6); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=7.2, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
ax.set_xlim(-0.4, len(xs) - 0.1)
fig.tight_layout(); fig.savefig(CH1); plt.close(fig)

# ── 그림 2: 내린 집이 더 많은 단지 / 올린 집이 더 많은 단지 ──
bx = list(B)
fig, ax = plt.subplots(figsize=(8.6, 2.6), dpi=220)
cuts = [B[d][0] for d in bx]; rises = [B[d][1] for d in bx]
ax.bar([i - 0.2 for i in range(len(bx))], cuts, 0.38, color="#1268d3", label="내린 집이 더 많은 단지")
ax.bar([i + 0.2 for i in range(len(bx))], rises, 0.38, color="#e0a43a", label="올린 집이 더 많은 단지")
for i, (c, r) in enumerate(zip(cuts, rises)):
    ax.text(i - 0.2, c + 1.5, str(c), ha="center", fontsize=7, color="#1b2430")
    ax.text(i + 0.2, r + 1.5, str(r), ha="center", fontsize=7, color="#1b2430")
ax.set_xticks(range(len(bx))); ax.set_xticklabels([f"{int(d[5:7])}/{int(d[8:])} 주" for d in bx], fontsize=7.5)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.set_yticks([]); ax.set_ylim(0, max(cuts) * 1.2)
ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncol=2)
fig.tight_layout(); fig.savefig(CH2); plt.close(fig)

# ── 본문 ──
f = []
c_all_o, r_all_o = octv(ALL, "cut"), octv(ALL, "rise")
c_all, r_all = wk(N2, ALL, "cut"), wk(N2, ALL, "rise")
f.append(Paragraph("10월 ‘올리는 집’ 늘던 서울 재건축 호가,<br/>11월 들어 ‘내리는 집’ 쪽으로", TITLE))
f.append(Paragraph(
    f"재건축 단지 같은 집 중 호가 내린 집 {c_all:.1f}%·올린 집 {r_all:.1f}%(10월 평균 {c_all_o:.1f}%·{r_all_o:.1f}%) — "
    f"일반 아파트는 {wk(N2, GEN, 'cut'):.1f}%·{wk(N2, GEN, 'rise'):.1f}%로 그대로<br/>"
    f"올린 집이 더 많던 재건축 단지 {r_oct}곳({lbl(d_oct)} 주) → {B[N2][1]}곳(11월 11일 주) · 은마·잠실5단지는 이번 주 절반 이상이 내려", SUB))
f.append(Spacer(1, 6))
f.append(Paragraph(
    "<b>콕집</b>(koczip.com)이 서울 아파트 재건축 단지의 매매 매물을 매주 같은 집끼리 비교한 결과, 10월에 호가를 올리는 집이 늘던 "
    "재건축 단지가 <b>11월 들어 호가를 내리는 쪽으로 기울었다</b>. 11월 4일부터 11일까지 한 주 동안 재건축 단지에서 호가를 내린 집은 "
    f"{c_all:.1f}%, 올린 집은 {r_all:.1f}%였다. 10월 세 주 평균(내린 집 {c_all_o:.1f}%, 올린 집 {r_all_o:.1f}%)보다 "
    "내린 집은 늘고 올린 집은 줄었다. 같은 기간 일반 아파트는 내린 집 "
    f"{wk(N2, GEN, 'cut'):.1f}%·올린 집 {wk(N2, GEN, 'rise'):.1f}%(10월 평균 {octv(GEN, 'cut'):.1f}%·{octv(GEN, 'rise'):.1f}%)로 거의 변하지 않았다.", BODY))
f.append(Paragraph(
    f"변화는 일부 단지에 그치지 않았다. 같은 집이 5채 이상인 재건축 단지 가운데 올린 집이 내린 집보다 많은 단지는 "
    f"{lbl(d_oct)} 주 {r_oct}곳에서 11월 11일 주 <b>{B[N2][1]}곳</b>으로 줄었고, 내린 집이 더 많은 단지는 "
    f"{B[d_oct][0]}곳에서 <b>{B[N2][0]}곳</b>으로 늘었다(전체 {B[N2][2]}곳). 이 흐름은 11월 첫째 주부터 나타나 둘째 주에 커졌다. "
    "둘째 주는 서초구의 반포현대 재건축초과이익환수(재초환) 부담금 사전통지 예정 보도(11월 6일)와 통지(11월 9일)가 있었던 주다.", BODY))
f.append(Spacer(1, 2))
f.append(boxed(
    "<b>이 자료의 기준</b><br/>"
    "· <b>같은 집</b>: 비교하는 두 수요일 모두 매물로 나와 있던 집. 여러 중개사무소가 올린 같은 집 광고는 한 채로 묶고 호가는 그 중앙값. "
    "<b>내린 집·올린 집</b>은 직전 수요일보다 호가가 낮아진·높아진 집의 비율이고, 나머지는 호가를 그대로 둔 집이다.<br/>"
    "· <b>10월 평균</b>: 10월 14일·21일·28일로 끝나는 세 주의 평균.<br/>"
    "· <b>재건축 단지</b>: 서울시 「정비사업 추진현황」(2026년 6월 말 기준, 서울 열린데이터광장)의 아파트 재건축 구역에 속한 단지. "
    "은마·잠실주공5단지는 7월 사업시행인가를 반영했고, 공사 중(착공) 구역은 뺐다. "
    f"관리처분인가 {J['groups'][MG]}곳·사업시행인가 {J['groups'][SI]}곳·건축심의 통과 {J['groups'][AR]}곳·건축심의 전(구역지정·추진위·조합설립) {J['groups'][PRE]}곳.<br/>"
    "· <b>일반 아파트</b>: 정비구역이 아닌 서울 아파트 단지."))
f.append(Spacer(1, 10))
f.append(Image(str(CH1), width=170 * mm, height=170 * mm * 3.6 / 8.6))
f.append(Paragraph("그림 1. 같은 집 가운데 직전 수요일보다 호가를 내린·올린 집의 비율. 9월 30일 칸은 추석 주를 건너뛴 2주 비교.", NOTE))

# 1. 단계별
f.append(CondPageBreak(110 * mm))
f.append(Paragraph("1. 사업 단계별 — 10월과 11월", H))
rows = [["단계", "10월 평균\n내린 집 / 올린 집", "11월 4일 주\n내린 집 / 올린 집", "11월 11일 주\n내린 집 / 올린 집", "11월 11일 주\n평균 변동", "같은 집\n(11/11 주)"]]
for g in STAGES:
    rows.append([g, f"{octv(g, 'cut'):.1f}% / {octv(g, 'rise'):.1f}%", f"{wk(N1, g, 'cut'):.1f}% / {wk(N1, g, 'rise'):.1f}%",
                 f"{wk(N2, g, 'cut'):.1f}% / {wk(N2, g, 'rise'):.1f}%", sgn(WC[N2][g]["mean"] * 100), f"{WC[N2][g]['n']:,}"])
iall = STAGES.index(ALL) + 1
f.append(table(rows, [44 * mm, 27 * mm, 27 * mm, 27 * mm, 21 * mm, 18 * mm], hi=(iall,), bold_rows=(iall,)))
f.append(Paragraph("평균 변동은 같은 집 각각의 호가 변동률(그대로 둔 집 0% 포함)의 평균.", NOTE))
f.append(Paragraph(
    f"· <b>사업시행인가</b>: 10월 평균은 내린 집 {octv(SI, 'cut'):.1f}%·올린 집 {octv(SI, 'rise'):.1f}%였고, 11월 11일 주에는 "
    f"{wk(N2, SI, 'cut'):.1f}%·{wk(N2, SI, 'rise'):.1f}%가 됐다. 이 묶음 같은 집의 3분의 1이 은마·잠실주공5단지라 두 단지를 빼고도 봤다. "
    f"10월 28일 주에는 내린 집 {wk(O28, SIX, 'cut'):.1f}%·올린 집 {wk(O28, SIX, 'rise'):.1f}%로 올린 집이 많았는데, "
    f"11월 11일 주에는 {wk(N2, SIX, 'cut'):.1f}%·{wk(N2, SIX, 'rise'):.1f}%로 뒤집혔다.<br/>"
    f"· <b>건축심의 통과</b>: 10월 평균 {octv(AR, 'cut'):.1f}%·{octv(AR, 'rise'):.1f}% → 11월 11일 주 {wk(N2, AR, 'cut'):.1f}%·{wk(N2, AR, 'rise'):.1f}%.<br/>"
    f"· <b>건축심의 전</b>: 내린 집 {octv(PRE, 'cut'):.1f}% → {wk(N2, PRE, 'cut'):.1f}%, 올린 집 {octv(PRE, 'rise'):.1f}% → {wk(N2, PRE, 'rise'):.1f}%.<br/>"
    f"· <b>관리처분인가</b>: 내린 집은 {octv(MG, 'cut'):.1f}% → {wk(N2, MG, 'cut'):.1f}%로 비슷하고, 올린 집이 "
    f"{octv(MG, 'rise'):.1f}% → {wk(N2, MG, 'rise'):.1f}%로 줄었다.", BODY))

# 2. 단지 수
f.append(CondPageBreak(90 * mm))
f.append(Paragraph("2. 몇몇 단지의 일이 아니다 — 방향별 단지 수", H))
f.append(Image(str(CH2), width=170 * mm, height=170 * mm * 2.6 / 8.6))
f.append(Paragraph(f"그림 2. 같은 집이 5채 이상인 재건축 단지({B[N2][2]}곳 안팎)를 그 주에 내린 집과 올린 집 중 어느 쪽이 많았는지로 나눈 수. "
                   "두 쪽이 같은 단지는 뺐다.", NOTE))
mg2, si2 = breadth(N2, MG), breadth(N2, SI)
f.append(Paragraph(
    f"올린 집이 더 많은 단지는 10월 세 주 {min(B[d][1] for d in OCT)}~{max(B[d][1] for d in OCT)}곳이었다가 11월 4일 주 {B[N1][1]}곳, "
    f"11일 주 {B[N2][1]}곳으로 줄었다. 11월 11일 주에 관리처분인가 단지는 {mg2[2]}곳 가운데 올린 집이 더 많은 곳이 {mg2[1]}곳, "
    f"사업시행인가 단지는 {si2[2]}곳 가운데 {si2[1]}곳이었다.", BODY))

# 3. 주요 단지
f.append(CondPageBreak(120 * mm))
f.append(Paragraph("3. 주요 단지 — 10월 말부터 주별로", H))
f.append(Paragraph(
    f"은마와 잠실주공5단지는 내린 집이 매주 늘고 올린 집은 줄었다. 은마는 내린 집이 10월 28일 주 {pc(EUN, O28, 'cut'):.0f}% → "
    f"11월 4일 주 {pc(EUN, N1, 'cut'):.0f}% → 11일 주 {pc(EUN, N2, 'cut'):.0f}%, 올린 집은 {pc(EUN, O28, 'rise'):.0f}% → "
    f"{pc(EUN, N1, 'rise'):.0f}% → {pc(EUN, N2, 'rise'):.0f}%였다. 잠실주공5단지도 내린 집 {pc(JAM, O28, 'cut'):.0f}% → "
    f"{pc(JAM, N2, 'cut'):.0f}%, 올린 집 {pc(JAM, O28, 'rise'):.0f}% → {pc(JAM, N2, 'rise'):.0f}%다. "
    f"10월 28일 주에 올린 집이 더 많았던 개포주공6단지(올린 집 {pc(K6, O28, 'rise'):.0f}%)·개포주공7단지({pc(K7, O28, 'rise'):.0f}%)도 "
    f"11월 11일 주에는 내린 집이 더 많았다({pc(K6, N2, 'cut'):.0f}%·{pc(K7, N2, 'cut'):.0f}%). "
    f"신반포2차는 11월 4일 주 올린 집 {pc(SB2, N1, 'rise'):.0f}%에서 11일 주 {pc(SB2, N2, 'rise'):.0f}%로 줄고 내린 집이 {pc(SB2, N2, 'cut'):.0f}%였다.", BODY))
KEY = [EUN, JAM, K6, K7, SB2] + [n for n, _ in sorted(F.items(), key=lambda t: -t[1]["counts"][N2]) if n not in (EUN, JAM, K6, K7, SB2)][:7]
DS = ["2026-10-21", O28, N1, N2]
rows = [["단지(자치구)", "단계"] + [f"{lbl(d)} 주" for d in DS] + ["매물\n11/11"]]
for no in KEY:
    x = F[no]
    rows.append([f"{x['name']}({x['gu'].replace('구', '')})", x["group"]] + [cr_(no, d) for d in DS] + [f"{x['counts'][N2]:.0f}"])
f.append(table(rows, [44 * mm, 22 * mm, 21 * mm, 21 * mm, 21 * mm, 21 * mm, 14 * mm]))
f.append(Paragraph("각 칸은 그 주 같은 집 중 내린 집 / 올린 집 비율(직전 수요일 대비, 같은 집 5채 미만이면 ‘—’). "
                   "위 5곳은 본문에 든 단지, 아래 7곳은 11월 11일 매물이 많은 재건축 단지 순. 단계는 서울시 6월 말 자료 기준(은마·잠실주공5단지는 7월 사업시행인가 반영).", NOTE))

# 4. 매물 수
f.append(CondPageBreak(60 * mm))
f.append(Paragraph("4. 매물 수", H))
rows = [["구분", "10월 28일", "11월 4일", "11월 11일", "10/28 대비"]]
for g in [MG, SI, AR, PRE, GEN]:
    a, b, c = (W[d].get(g, 0) for d in (O28, N1, N2))
    rows.append([g, f"{a:,.0f}", f"{b:,.0f}", f"{c:,.0f}", f"{(c / a - 1) * 100:+.1f}%"])
for no in (EUN, JAM):
    x = F[no]["counts"]
    rows.append([F[no]["name"], f"{x[O28]:.0f}", f"{x[N1]:.0f}", f"{x[N2]:.0f}", f"{(x[N2] / x[O28] - 1) * 100:+.1f}%"])
f.append(table(rows, [42 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm], hi=(6, 7)))
f.append(Paragraph(
    f"매물 수는 단계별로 일반 아파트({(W[N2][GEN] / W[O28][GEN] - 1) * 100:+.1f}%)와 비슷하게 조금 늘었다. 은마는 8월 5일 "
    f"{F[EUN]['counts']['2026-08-05']:.0f}채에서 11월 11일 {F[EUN]['counts'][N2]:.0f}채로 늘었고 11월에도 증가가 이어졌다. "
    "잠실주공5단지는 11월에 조금 줄었다. 단위는 실매물(같은 집 중복 광고를 한 채로 센 수).", BODY))
# 5. 얼마나 내렸나 — 인하 폭(기자 요청 추가, ../data/press_jaecho_cut.json · measure_cut.py)
C = json.loads((HERE.parent / "data" / "press_jaecho_cut.json").read_text())
CW, CS, CX_, CE = C["weekly"], C["span"], C["weekly_complex"], C["examples"]


def man(won):
    return f"{won / 1e4:,.0f}만원"


def amt(won):
    """억 단위 금액: 3억 / 1억 7,500만원 / 4,000만원."""
    m = round(abs(won) / 1e4)
    eok, rest = divmod(m, 10000)
    return (f"{eok}억" + (f" {rest:,}만원" if rest else "")) if eok else f"{rest:,}만원"


def cw(d, g, k):
    return CW[d][g][k]


def co(g, k):
    return stt.mean(cw(d, g, k) for d in OCT)


def cut_med(d, g, k="amt_med"):
    return CW[d][g]["cut"][k]


def sp(name, g=None, no=None):
    return CS[name]["complex"][no] if no else CS[name]["groups"][g]


f.append(CondPageBreak(110 * mm))
f.append(Paragraph("5. 얼마나 내렸나 — 인하 폭", H))
ea, eb = sp("pre", no=EUN), sp("post", no=EUN)
ja, jb = sp("pre", no=JAM), sp("post", no=JAM)
eun_cut = sorted(abs(CX_[d][EUN]["cut"]["amt_med"]) for d in OCT)
f.append(Paragraph(
    "호가를 내린 집이 늘었을 뿐 아니라 같은 집의 평균 호가도 더 많이 내려갔다. 내린 집·그대로 둔 집·올린 집을 모두 넣은 "
    f"같은 집 평균 변동은 재건축 단지가 10월 세 주 평균 주당 {co(ALL, 'net_pct_mean') * 100:.2f}%"
    f"(한 채당 {man(co(ALL, 'net_amt_mean'))})에서 11월 4일 주 {cw(N1, ALL, 'net_pct_mean') * 100:.2f}%, "
    f"11일 주 <b>{cw(N2, ALL, 'net_pct_mean') * 100:.2f}%(한 채당 {man(cw(N2, ALL, 'net_amt_mean'))})</b>로 커졌다. "
    f"일반 아파트는 같은 기간 {co(GEN, 'net_pct_mean') * 100:.2f}%에서 {cw(N2, GEN, 'net_pct_mean') * 100:.2f}%로 큰 변화가 없었다.", BODY))
f.append(Paragraph(
    f"2주 단위로 보면 차이가 더 뚜렷하다. 10월 28일과 11월 11일에 모두 나와 있던 재건축 단지 같은 집 {sp('post', ALL)['n']:,}채의 호가는 "
    f"한 채당 평균 <b>{man(-sp('post', ALL)['net_amt_mean'])}({-sp('post', ALL)['net_pct_mean'] * 100:.2f}%)</b> 내려갔다. "
    f"바로 앞 2주(10월 14일→28일)에는 {man(-sp('pre', ALL)['net_amt_mean'])}({-sp('pre', ALL)['net_pct_mean'] * 100:.2f}%)이었다. "
    f"사업시행인가 단지는 앞 2주 {sp('pre', SI)['net_pct_mean'] * 100:+.2f}%로 오르다가 {sp('post', SI)['net_pct_mean'] * 100:+.2f}%로 돌아섰다.", BODY))
f.append(Paragraph(
    f"<b>은마</b>는 내리는 폭 자체가 커졌다. 호가를 내린 집의 인하액(중앙값)이 10월에는 주당 {eun_cut[0] / 1e4:,.0f}만~{amt(eun_cut[-1])}이었는데 "
    f"11월 4일 주 {amt(CX_[N1][EUN]['cut']['amt_med'])}, 11일 주 <b>{amt(CX_[N2][EUN]['cut']['amt_med'])}"
    f"({CX_[N2][EUN]['cut']['pct_med'] * -100:.1f}%)</b>으로 늘었다. 10월 28일→11월 11일 2주 동안 같은 집 {eb['n']}채 중 "
    f"{eb['cut']['n']}채가 호가를 내렸고, 한 채당 평균 변동은 <b>{man(eb['net_amt_mean'])}({eb['net_pct_mean'] * 100:.2f}%)</b>으로 "
    f"앞 2주({man(ea['net_amt_mean'])}, {ea['net_pct_mean'] * 100:.2f}%)의 두 배를 넘었다. 3% 넘게 내린 집도 "
    f"{ea['cut_ge3'] * 100:.0f}%에서 {eb['cut_ge3'] * 100:.0f}%로 늘었다. "
    f"<b>잠실주공5단지</b>는 내린 집의 인하액이 매주 {amt(CX_[N2][JAM]['cut']['amt_med'])}(약 {CX_[N2][JAM]['cut']['pct_med'] * -100:.1f}%) 안팎으로 "
    f"비슷했지만 내리는 집이 늘면서 2주 평균 변동이 {man(ja['net_amt_mean'])}에서 <b>{man(jb['net_amt_mean'])}"
    f"({jb['net_pct_mean'] * 100:.2f}%)</b>으로 커졌다.", BODY))
f.append(Paragraph(
    f"재건축 단지 전체로 보면 내린 집 한 채의 인하율(중앙값)은 10월 평균 {stt.mean(cut_med(d, ALL, 'pct_med') for d in OCT) * -100:.1f}%, "
    f"11월 11일 주 {cut_med(N2, ALL, 'pct_med') * -100:.1f}%로 비슷했다. 평균 호가가 더 내려간 것은 주로 내리는 집이 늘고 올리는 집이 줄어든 결과이고, "
    "은마는 여기에 인하 폭까지 커졌다.", BODY))

rows = [["구분", "같은 집 평균 변동(주간)", None, None, "2주 한 채당 평균 변동", None],
        [None, "10월 평균", "11/4 주", "11/11 주", "10/14→10/28", "10/28→11/11"]]
for g in [MG, SI, SIX, AR, PRE, ALL, GEN]:
    rows.append([g, sgn(co(g, "net_pct_mean") * 100), sgn(cw(N1, g, "net_pct_mean") * 100), sgn(cw(N2, g, "net_pct_mean") * 100),
                 f"{sp('pre', g)['net_amt_mean'] / 1e4:+,.0f}만원", f"{sp('post', g)['net_amt_mean'] / 1e4:+,.0f}만원"])
for no in (EUN, JAM):
    w = [CX_[d][no]["net_pct_mean"] for d in OCT]
    rows.append([F[no]["name"], sgn(stt.mean(w) * 100), sgn(CX_[N1][no]["net_pct_mean"] * 100), sgn(CX_[N2][no]["net_pct_mean"] * 100),
                 f"{sp('pre', no=no)['net_amt_mean'] / 1e4:+,.0f}만원", f"{sp('post', no=no)['net_amt_mean'] / 1e4:+,.0f}만원"])
t = table(rows, [46 * mm, 22 * mm, 22 * mm, 22 * mm, 29 * mm, 29 * mm], head=2, hi=(7, 9, 10), bold_rows=(7,))
t._content[0].setStyle(TableStyle([("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (3, 0)), ("SPAN", (4, 0), (5, 0)),
                                   ("ALIGN", (1, 0), (-1, 0), "CENTER"), ("LINEBELOW", (1, 0), (-1, 0), 0.4, LINE)]))
f.append(t)
f.append(Paragraph("같은 집 평균 변동 = 내린 집·그대로 둔 집(0%)·올린 집을 모두 넣은 평균. 주간은 직전 수요일 대비, 2주는 두 날 모두 나와 있던 같은 집의 호가 차이 평균.", NOTE))

rows = [["단지", "동", "층", "전용", "10월 28일", "11월 11일", "인하"]]
for no in (EUN, JAM):
    for e in CE[no][:5]:
        rows.append([F[no]["name"], e["dong"], e["floor"] + "층",
                     f"{e['area2']:.0f}㎡", amt(e["before"]), amt(e["after"]), amt(e["after"] - e["before"])])
f.append(Spacer(1, 4))
f.append(table(rows, [36 * mm, 15 * mm, 20 * mm, 16 * mm, 28 * mm, 28 * mm, 27 * mm]))
f.append(Paragraph("10월 28일→11월 11일 호가를 가장 많이 내린 같은 집 5곳씩(광고 호가 기준, 같은 집 광고가 여럿이면 중앙값). "
                   "층은 ‘해당 층/전체 층’이며 저·중·고는 광고에 표시된 그대로.", NOTE))

f.append(Spacer(1, 2))
f.append(KeepTogether([Paragraph("분석 개요", H), Paragraph(
    "<b>대상</b>  서울 아파트 매매 매물 호가 전수(오피스텔 제외). 재건축 단지는 서울시 정비사업 추진현황(2026년 6월 말)의 "
    "공동주택재건축·아파트지구재건축 구역을 콕집 단지와 지번·구역명으로 연결(161개 구역)<br/>"
    "<b>시점</b>  2026년 8월 5일부터 11월 11일까지 매주 수요일 하루치 수집분, 직전 수요일과 비교<br/>"
    "<b>같은 집</b>  단지·동·층·공급·전용·방향이 같은 광고를 한 채로 묶고 호가는 광고들의 중앙값. ±30% 넘는 변동은 오기재로 보고 제외<br/>"
    "<b>재초환 일정</b>  11월 4일 서초구 제도 폐지 건의, 11월 6일 반포현대 부담금 예정액 사전통지 예정 보도, 11월 9일 사전통지", NOTE)]))
f.append(Spacer(1, 2))
by = st("by", 9.5, "P-M", color=MUTE, lead=14)
f.append(KeepTogether([Paragraph("작성 | 콕집 공동창업자 조용호", by), Paragraph("문의 | 콕집(koczip.com) CTO 황인찬 · runtoonline@gmail.com", by)]))
SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=21 * mm, bottomMargin=16 * mm,
                  title="콕집 — 서울 재건축 사업 단계별 매물 호가", author="콕집").build(f, onFirstPage=page, onLaterPages=page)
print("생성:", OUT)
