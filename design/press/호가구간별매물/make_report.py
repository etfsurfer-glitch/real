# -*- coding: utf-8 -*-
"""서울 아파트 매매 매물 호가 5억 구간별 — 보도자료 PDF.

수치는 ../data/press_hoga_band.json(박스에서 measure.py 로 산출)만 읽는다. 본문 숫자도 여기서 계산한다.
실행: python3 design/press/호가구간별매물/make_report.py
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
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
J = json.loads((HERE.parent / "data" / "press_hoga_band.json").read_text())
FONTS = HERE.parent.parent / "fonts"
OUT = HERE / "콕집_서울아파트_호가구간별_매물동향.pdf"
CHART = HERE.parent / "data" / "hoga_band_chart.png"

INK, MUTE, LINE = colors.HexColor("#1b2430"), colors.HexColor("#5b6775"), colors.HexColor("#d9e0e8")
BRAND, UP, DOWN = colors.HexColor("#1268d3"), colors.HexColor("#b3261e"), colors.HexColor("#1268d3")
BAND = colors.HexColor("#f2f7ff")
for nm, fn in (("P", "Pretendard-Regular.ttf"), ("P-B", "Pretendard-Bold.ttf"),
               ("P-M", "Pretendard-Medium.ttf"), ("P-EB", "Pretendard-ExtraBold.ttf")):
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="P-B", italic="P", boldItalic="P-B")
ss = getSampleStyleSheet()


def st(name, size, font="P", lead=None, color=INK, space=0, align=0):
    return ParagraphStyle(name, parent=ss["Normal"], fontName=font, fontSize=size,
                          leading=lead or size * 1.55, textColor=color, spaceAfter=space, alignment=align)


TITLE = st("t", 19.5, "P-EB", lead=27, space=5)
SUB = st("s", 11, "P-M", lead=17.5, color=BRAND, space=3)
H = st("h", 13.5, "P-B", lead=20, space=6)
BODY = st("b", 10.3, "P", lead=17.5, space=7)
NOTE = st("n", 8.8, "P", lead=14.5, color=MUTE, space=5)
CELL = st("c", 8.6, "P", lead=12)
CELLS = st("cs", 7.9, "P", lead=11, align=2)

B = J["bands"]
D = list(J["dates"])
A, Z = D[0], D[-1]
DAYS = {"2026-08-03": 0, "2026-09-01": 29, "2026-10-01": 59, "2026-11-11": 100}
ZONES = ["강남3구", "마용성", "노도강", "금관구", "그 외 13개구"]


def md(d):
    return f"{int(d[5:7])}/{int(d[8:10])}"


def obj(d, b, key="obj"):
    return J["dates"][d]["all"][b][key]


def tot(d, key="obj"):
    return J["dates"][d]["total"][key]


def zobj(d, z, bs):
    return sum(J["dates"][d]["by_zone"][z][b]["obj"] for b in bs)


def pct(a, b):
    return (b / a - 1) * 100 if a else None


def sg(v, d=1, unit="%"):
    if v is None:
        return "—"
    c = UP if v > 0 else DOWN if v < 0 else INK
    return Paragraph(f'<font color="{c.hexval()}"><b>{v:+.{d}f}{unit}</b></font>', CELL)


def table(rows, widths, head=1, hi=(), bold_last=False):
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=head)
    cmds = [("FONT", (0, 0), (-1, -1), "P", 8.6), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4.5), ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
            ("FONT", (0, 0), (-1, head - 1), "P-B", 8.2), ("TEXTCOLOR", (0, 0), (-1, head - 1), MUTE),
            ("LINEBELOW", (0, head - 1), (-1, head - 1), 0.9, INK),
            ("LINEBELOW", (0, head), (-1, -2), 0.4, LINE), ("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    for r in hi:
        cmds += [("BACKGROUND", (0, r), (-1, r), BAND)]
    if bold_last:
        cmds += [("FONT", (0, -1), (-1, -1), "P-B", 8.6), ("LINEABOVE", (0, -1), (-1, -1), 0.9, INK)]
    t.setStyle(TableStyle(cmds))
    return KeepTogether(t)


def boxed(html):
    t = Table([[Paragraph(html, CELL)]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BAND),
                           ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfe0f8")),
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


# ── 계산 ───────────────────────────────────────────
G = {b: pct(obj(A, b), obj(Z, b)) for b in B}
MID = B[1:5]                                   # 10~30억
HIGH = B[5:9]                                  # 30~50억
inc_all = tot(Z) - tot(A)
inc_mid = sum(obj(Z, b) - obj(A, b) for b in MID)
share = lambda d, bs: sum(obj(d, b) for b in bs) / tot(d) * 100
top = max(B, key=lambda b: G[b])
MV = J["move"]; TR = J["trans"]; NEW = J["new"]
net_in = {c: sum(TR[b][c] for b in B if b != c) - sum(TR[c][x] for x in B if x != c) for c in B}
cut_hi = [MV[b]["cut_r"] for b in HIGH + [B[-1]]]
pace = []
for a, c in zip(D, D[1:]):
    n = DAYS[c] - DAYS[a]
    pace.append((a, c, tot(c) - tot(a), (tot(c) - tot(a)) / n * 30))

# ── 그림 ───────────────────────────────────────────
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Regular.ttf"))
font_manager.fontManager.addfont(str(FONTS / "Pretendard-Bold.ttf"))
plt.rcParams["font.family"] = "Pretendard"
fig, ax = plt.subplots(figsize=(8.6, 3.9), dpi=220)
x = range(len(B)); wdt = 0.2
cols = ["#c9d6e6", "#93b1d6", "#5a8ac6", "#1268d3"]
for i, d in enumerate(D):
    ax.bar([k + (i - 1.5) * wdt for k in x], [obj(d, b) for b in B], wdt, color=cols[i],
           label=f"{int(d[5:7])}월 {int(d[8:])}일")
for k, b in enumerate(B):
    ax.text(k, max(obj(d, b) for d in D) + 350, f"{G[b]:+.0f}%", ha="center", fontsize=8.5,
            fontweight="bold", color="#b3261e" if b == top else "#1b2430")
ax.set_xticks(list(x)); ax.set_xticklabels(B, fontsize=8)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.tick_params(axis="y", labelsize=8, colors="#5b6775")
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#5b6775")
ax.grid(axis="y", color="#e6ebf1", linewidth=0.6); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper right", bbox_to_anchor=(1, 1.13))
ax.set_ylabel("실매물(채)", fontsize=8, color="#5b6775")
ax.set_ylim(0, max(obj(d, b) for d in D for b in B) * 1.12)
fig.tight_layout(); fig.savefig(CHART); plt.close(fig)

# ── 본문 ───────────────────────────────────────────
f = []
f.append(Paragraph(f"서울 아파트 매물 석 달 새 {pct(tot(A), tot(Z)):.0f}% 늘어<br/>— 10억~30억 중간 가격대가 증가의 {inc_mid / inc_all * 100:.0f}%", TITLE))
f.append(Paragraph(
    f"매매 실매물 {tot(A):,}채(8/3) → {tot(Z):,}채(11/11). 가장 많이 는 구간은 {top} {G[top]:+.0f}%, "
    f"10억 미만 {G[B[0]]:+.0f}%<br/>"
    f"30억 이상 고가 구간은 같은 집의 {min(cut_hi):.0f}~{max(cut_hi):.0f}%가 호가를 내려 — "
    "10~15억대는 올린 집이 더 많아", SUB))
f.append(Spacer(1, 7))
f.append(Paragraph(
    f"<b>콕집</b>(koczip.com)이 서울 아파트(재건축·분양권 포함) 매매 매물을 호가 5억 원 단위로 나눠 "
    f"8월 3일·9월 1일·10월 1일·11월 11일 네 시점을 비교한 결과, 서울 매매 실매물은 8월 3일 {tot(A):,}채에서 "
    f"11월 11일 {tot(Z):,}채로 <b>{pct(tot(A), tot(Z)):.1f}%({inc_all:+,}채)</b> 늘었다. "
    f"증가는 10억~30억 원 구간에 몰렸다. 이 네 구간에서만 {inc_mid:+,}채가 늘어 전체 증가분의 "
    f"<b>{inc_mid / inc_all * 100:.0f}%</b>를 차지했고, 구간별 증가율도 {min(G[b] for b in MID):.0f}~{max(G[b] for b in MID):.0f}%로 "
    f"서울 평균을 웃돌았다. 반면 10억 원 미만은 {G[B[0]]:+.1f}%, 50억 원 이상은 {G[B[-1]]:+.1f}%에 그쳤다.", BODY))
f.append(Paragraph(
    f"같은 기간 두 시점에 모두 나와 있던 집의 호가를 비교하면, 30억 원 이상 구간에서는 호가를 내린 집이 "
    f"{min(cut_hi):.0f}~{max(cut_hi):.0f}%로 절반을 넘었다. 10억~15억 원 구간은 올린 집({MV[B[1]]['rise_r']:.0f}%)이 "
    f"내린 집({MV[B[1]]['cut_r']:.0f}%)보다 많았다. 가격대가 높을수록 같은 집의 평균 호가 변동률이 "
    f"{MV[B[0]]['mean_pct']:+.1f}%(10억 미만)에서 {MV[B[-1]]['mean_pct']:+.1f}%(50억 이상)로 차례로 낮아졌다.", BODY))
f.append(Spacer(1, 2))
f.append(boxed(
    "<b>이 자료의 기준</b><br/>"
    "· <b>실매물</b>: 같은 집을 여러 중개사무소가 올린 광고를 한 채로 센 실제 집의 수(중복 광고 제외). "
    "아파트·재건축·아파트 분양권 합계로, 일반에 공개되는 서울 매매 매물 일별 집계와 같은 기준이다. 본문 숫자는 모두 실매물이다.<br/>"
    "· <b>광고</b>: 중개사무소가 올린 매매 광고 전부. 한 집을 세 곳이 올리면 3건이다(부록 표).<br/>"
    "· <b>호가 구간</b>: 하한 포함·상한 미포함. 10~15억 = 10억 원 이상 15억 원 미만.<br/>"
    "· <b>시점</b>: 각 날짜 하루치 수집분. 8월 3일은 세제개편안 발표(18시) 전에 수집된 매물이다."))
f.append(Spacer(1, 12))

# 1
f.append(Paragraph("1. 호가 구간별 매물 수", H))
rows = [["호가 구간"] + [md(d) for d in D] + ["증감\n8/3→11/11", "증감률", "구성비\n8/3 → 11/11"]]
for b in B:
    rows.append([Paragraph(f"<b>{b}</b>", CELL)] + [f"{obj(d, b):,}" for d in D]
                + [f"{obj(Z, b) - obj(A, b):+,}", sg(G[b]),
                   f"{obj(A, b) / tot(A) * 100:.1f} → {obj(Z, b) / tot(Z) * 100:.1f}%"])
rows.append(["합계"] + [f"{tot(d):,}" for d in D] + [f"{inc_all:+,}", sg(pct(tot(A), tot(Z))), "100%"])
f.append(table(rows, [22 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 21 * mm, 17 * mm, 26 * mm],
               hi=[2, 3, 4, 5], bold_last=True))
f.append(Paragraph("단위: 채(실매물). 음영은 10억~30억 구간.", NOTE))
f.append(Spacer(1, 4))
f.append(Image(str(CHART), width=170 * mm, height=170 * mm * 3.9 / 8.6))
f.append(Paragraph("그림 1. 호가 구간별 서울 아파트 매매 실매물. 숫자는 8/3 → 11/11 증감률.", NOTE))
f.append(Spacer(1, 4))
f.append(Paragraph(
    f"구성비로 보면 10억~30억 구간이 전체 매물에서 차지하는 비중이 {share(A, MID):.1f}%에서 "
    f"<b>{share(Z, MID):.1f}%</b>로 높아졌다. 10억 원 미만은 {share(A, B[:1]):.1f}% → {share(Z, B[:1]):.1f}%, "
    f"30억 원 이상은 {share(A, B[5:]):.1f}% → {share(Z, B[5:]):.1f}%로 낮아졌다. "
    f"가장 많이 늘어난 구간은 {top}({obj(A, top):,} → {obj(Z, top):,}채, {G[top]:+.1f}%)이다.", BODY))

# 2 속도
f.append(Paragraph("2. 시기별 증가 속도", H))
rows = [["구간", "기간(일)", "증가(채)", "30일 환산"]]
for a, c, n, p30 in pace:
    rows.append([f"{md(a)} → {md(c)}", f"{DAYS[c] - DAYS[a]}", f"{n:+,}", f"{p30:+,.0f}"])
f.append(table(rows, [40 * mm, 25 * mm, 30 * mm, 30 * mm]))
f.append(Paragraph(
    f"세 구간의 길이가 달라 30일 기준으로 환산했다. 9월(9/1→10/1)에 {pace[1][3]:+,.0f}채로 증가 속도가 느려졌다가, "
    f"10월 이후(10/1→11/11) 30일당 {pace[2][3]:+,.0f}채로 8월 수준({pace[0][3]:+,.0f}채)을 다시 회복했다. "
    f"10월 이후 늘어난 {pace[2][2]:,}채 중 10억~30억 구간이 "
    f"{sum(obj(Z, b) - obj(D[2], b) for b in MID) / pace[2][2] * 100:.0f}%다.", BODY))

# 3 권역
f.append(CondPageBreak(70 * mm))
f.append(Paragraph("3. 권역별 — 어느 가격대가 늘었나", H))
GRP = [("10억 미만", B[:1]), ("10~20억", B[1:3]), ("20~30억", B[3:5]), ("30~50억", B[5:9]), ("50억 이상", B[9:])]
rows = [["권역", "합계\n8/3 → 11/11"] + [g for g, _ in GRP]]
for zn in ZONES:
    r = [Paragraph(f"<b>{zn}</b>", CELL),
         Paragraph(f"{zobj(A, zn, B):,} → {zobj(Z, zn, B):,}<br/><b>{pct(zobj(A, zn, B), zobj(Z, zn, B)):+.1f}%</b>", CELLS)]
    for _, bs in GRP:
        a0, a1 = zobj(A, zn, bs), zobj(Z, zn, bs)
        r.append(Paragraph(f"{a0:,} → {a1:,}<br/><b>{pct(a0, a1):+.0f}%</b>", CELLS) if a0 >= 50
                 else Paragraph(f"{a0:,} → {a1:,}", CELLS))
    rows.append(r)
f.append(table(rows, [20 * mm, 27 * mm] + [24.6 * mm] * 5))
f.append(Paragraph("강남3구=강남·서초·송파, 마용성=마포·용산·성동, 노도강=노원·도봉·강북, 금관구=금천·관악·구로. "
                   "8/3 매물이 50채 미만인 칸은 증감률을 생략했다.", NOTE))
gz = lambda zn, bs: pct(zobj(A, zn, bs), zobj(Z, zn, bs))
f.append(Paragraph(
    f"· <b>강남3구</b>({pct(zobj(A, '강남3구', B), zobj(Z, '강남3구', B)):+.0f}%): 25~30억 구간이 "
    f"{J['dates'][A]['by_zone']['강남3구']['25~30억']['obj']:,} → {J['dates'][Z]['by_zone']['강남3구']['25~30억']['obj']:,}채"
    f"({pct(J['dates'][A]['by_zone']['강남3구']['25~30억']['obj'], J['dates'][Z]['by_zone']['강남3구']['25~30억']['obj']):+.0f}%)로 "
    f"가장 많이 늘었다. 50억 이상은 {gz('강남3구', B[9:]):+.0f}%에 그쳤다. 서울 50억 이상 매물의 "
    f"{zobj(Z, '강남3구', B[9:]) / obj(Z, B[-1]) * 100:.0f}%가 강남3구에 있다.<br/>"
    f"· <b>마용성</b>({pct(zobj(A, '마용성', B), zobj(Z, '마용성', B)):+.0f}%): 권역 중 증가율이 가장 높다. "
    f"15~25억 구간이 {pct(sum(J['dates'][A]['by_zone']['마용성'][b]['obj'] for b in B[2:4]), sum(J['dates'][Z]['by_zone']['마용성'][b]['obj'] for b in B[2:4])):+.0f}% 늘었다.<br/>"
    f"· <b>노도강·금관구</b>({pct(zobj(A, '노도강', B), zobj(Z, '노도강', B)):+.0f}%, {pct(zobj(A, '금관구', B), zobj(Z, '금관구', B)):+.0f}%): "
    f"매물의 대부분인 10억 미만은 각각 {gz('노도강', B[:1]):+.0f}%, {gz('금관구', B[:1]):+.0f}%로 덜 늘고, "
    f"10~15억 구간이 {pct(J['dates'][A]['by_zone']['노도강']['10~15억']['obj'], J['dates'][Z]['by_zone']['노도강']['10~15억']['obj']):+.0f}%, "
    f"{pct(J['dates'][A]['by_zone']['금관구']['10~15억']['obj'], J['dates'][Z]['by_zone']['금관구']['10~15억']['obj']):+.0f}% 늘었다.<br/>"
    f"· <b>그 외 13개구</b>({pct(zobj(A, '그 외 13개구', B), zobj(Z, '그 외 13개구', B)):+.0f}%): "
    f"10~30억 구간이 {gz('그 외 13개구', B[1:5]):+.0f}% 늘어 서울 전체와 같은 모양이다.", BODY))

# 4 같은 집
f.append(CondPageBreak(80 * mm))
f.append(Paragraph("4. 같은 집의 호가 — 비쌀수록 내렸다", H))
f.append(Paragraph(
    "8월 3일과 11월 11일에 <b>모두</b> 나와 있던 집만 골라 두 날의 호가를 비교했다(±30% 넘는 변동은 입력 오류로 제외). "
    "구간은 8월 3일 호가 기준이다. 그사이 팔렸거나 광고를 내린 집, 새로 나온 집은 이 비교에서 빠진다.", BODY))
rows = [["8/3 호가 구간", "같은 집(채)", "내린 집", "올린 집", "평균 변동률", "아래 구간으로\n내려간 집", "11/11 매물 중\n새 매물 비중"]]
for b in B:
    m = MV[b]
    down = f"{m['down']:,} ({m['down'] / m['n'] * 100:.0f}%)" if b != B[0] else "—"
    rows.append([Paragraph(f"<b>{b}</b>", CELL), f"{m['n']:,}", f"{m['cut_r']:.1f}%", f"{m['rise_r']:.1f}%",
                 sg(m["mean_pct"], 2), down, f"{NEW[b]['new'] / NEW[b]['all'] * 100:.0f}%"])
f.append(table(rows, [24 * mm, 20 * mm, 19 * mm, 19 * mm, 22 * mm, 30 * mm, 30 * mm], hi=[6, 7, 8, 9, 10]))
f.append(Paragraph("평균 변동률은 같은 집 각각의 변동률(값을 안 바꾼 집 0% 포함)의 평균. 새 매물은 8/3에 없던 집(새로 나왔거나 "
                   "조건이 바뀐 집). 같은 집 판정은 단지·동·층·전용·향·공급면적이 같은 광고를 한 채로 묶어서 한다.", NOTE))
f.append(Paragraph(
    f"30억 원 이상 구간에서는 같은 집의 {min(cut_hi):.0f}~{max(cut_hi):.0f}%가 호가를 내렸고 평균 변동률은 "
    f"{MV[B[5]]['mean_pct']:+.1f}%(30~35억)에서 {MV[B[-1]]['mean_pct']:+.1f}%(50억 이상)까지 내려갔다. "
    f"30~50억 구간에서는 같은 집의 {min(MV[b]['down'] / MV[b]['n'] * 100 for b in HIGH):.0f}~"
    f"{max(MV[b]['down'] / MV[b]['n'] * 100 for b in HIGH):.0f}%가 호가를 내려 아래 구간으로 옮겨 갔다. "
    f"반대로 10억 미만과 10~15억 구간은 올린 집({MV[B[0]]['rise_r']:.0f}%, {MV[B[1]]['rise_r']:.0f}%)이 "
    f"내린 집({MV[B[0]]['cut_r']:.0f}%, {MV[B[1]]['cut_r']:.0f}%)보다 많았다.", BODY))
f.append(Paragraph(
    f"그렇다면 25~30억 구간이 가장 많이 늘어난 것은 위에서 값을 내린 집이 내려왔기 때문일까. 두 시점 모두 있던 집 가운데 "
    f"25~30억으로 들어온 집과 빠져나간 집을 상계하면 순유입은 <b>{net_in['25~30억']:+,}채</b>로, 이 구간 증가분"
    f"({obj(Z, '25~30억') - obj(A, '25~30억'):+,}채)의 {net_in['25~30억'] / (obj(Z, '25~30억') - obj(A, '25~30억')) * 100:.0f}%다. "
    f"같은 방식으로 50억 이상은 {net_in['50억 이상']:+,}채가 아래로 빠져나갔다. 구간 간 이동이 분포를 조금 아래로 끌어내렸지만, "
    f"<b>증가분 대부분은 새로 나온 매물</b>이다. 11월 11일 매물 중 8월 3일에 없던 집의 비중은 10억 미만~15억에서 "
    f"{NEW[B[0]]['new'] / NEW[B[0]]['all'] * 100:.0f}~{NEW[B[1]]['new'] / NEW[B[1]]['all'] * 100:.0f}%, 40억 이상에서 "
    f"{min(NEW[b]['new'] / NEW[b]['all'] * 100 for b in B[7:]):.0f}~{max(NEW[b]['new'] / NEW[b]['all'] * 100 for b in B[7:]):.0f}%로 "
    "가격대가 낮을수록 매물이 빨리 바뀌었다.", BODY))

# 부록
f.append(CondPageBreak(75 * mm))
f.append(Paragraph("부록. 광고 건수(중복 광고 포함)와 광고배수", H))
rows = [["호가 구간"] + [md(d) for d in D] + ["증감률", "광고배수\n8/3 → 11/11"]]
for b in B:
    rows.append([Paragraph(f"<b>{b}</b>", CELL)] + [f"{obj(d, b, 'ad'):,}" for d in D]
                + [sg(pct(obj(A, b, 'ad'), obj(Z, b, 'ad'))),
                   f"{obj(A, b, 'ad') / obj(A, b):.2f} → {obj(Z, b, 'ad') / obj(Z, b):.2f}"])
rows.append(["합계"] + [f"{tot(d, 'ad'):,}" for d in D] + [sg(pct(tot(A, 'ad'), tot(Z, 'ad'))),
                                                         f"{tot(A, 'ad') / tot(A):.2f} → {tot(Z, 'ad') / tot(Z):.2f}"])
f.append(table(rows, [22 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 30 * mm], bold_last=True))
f.append(Paragraph(
    "광고배수 = 광고 ÷ 실매물. 집 한 채에 광고가 평균 몇 건 붙었는지다. 광고 건수는 같은 집을 여러 중개사무소가 올리면 "
    "그만큼 커지므로 매물 증가율을 말할 때는 실매물을 쓰는 것이 정확하다. "
    f"10~25억 구간은 광고배수가 {min(obj(Z, b, 'ad') / obj(Z, b) for b in B[1:4]):.2f}~{max(obj(Z, b, 'ad') / obj(Z, b) for b in B[1:4]):.2f}로 "
    "가장 높아, 한 집을 여러 사무소가 함께 내놓는 경우가 많다.", NOTE))
f.append(Spacer(1, 8))

f.append(KeepTogether([Paragraph("분석 개요", H), Paragraph(
    "<b>대상</b>  서울 25개 자치구 아파트·재건축·아파트 분양권 매매 매물 호가 전수(오피스텔 제외)<br/>"
    "<b>시점</b>  2026년 8월 3일(세제개편안 발표 전 수집분)·9월 1일·10월 1일·11월 11일, 각 날짜 하루치 수집분<br/>"
    "<b>실매물</b>  같은 집에 붙은 광고를 한 채로 셈(광고마다 1 ÷ 같은 집 광고 수를 더함)<br/>"
    "<b>오기재</b>  같은 단지·같은 전용면적 호가 중앙값의 0.4~2.5배를 벗어난 광고(자릿수 오타)는 제외. 시점별 0~3건<br/>"
    "<b>같은 집</b>  단지·동·층·전용·향·공급면적이 같은 광고를 한 채로 묶고 호가는 광고들의 중앙값. "
    "두 날 모두 있던 집만 비교, ±30% 넘는 변동은 제외<br/>"
    "<b>분양권</b>  분양권은 시점별 300~700채로 비중이 1% 안팎이다<br/>"
    "<b>경계값</b>  호가가 정확히 15억·20억처럼 5억 단위인 매물이 구간마다 500~1,200채 있다. 이 매물은 위 구간에 넣었다"
    "(15억 → 15~20억). ‘초과~이하’로 바꿔 세어도 구간별 증감률 차이는 4%p 이내이고, 10억~30억이 증가분의 66%로 결론은 같다<br/>"
    "<b>일별 출렁임</b>  실매물은 하루 사이 1~2% 오르내린다. 8월 3일(월)은 8월 2일보다 1.4% 적고 8월 4일보다 0.7% 적다. "
    "기준일을 하루 옮기면 전체 증가율은 33~35%다", NOTE)]))
f.append(Spacer(1, 8))
by = st("by", 9.5, "P-M", color=MUTE, lead=15)
f.append(KeepTogether([Paragraph("작성 | 콕집 공동창업자 조용호", by),
                       Paragraph("문의 | 콕집(koczip.com) CTO 황인찬 · runtoonline@gmail.com", by)]))

SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                  topMargin=22 * mm, bottomMargin=18 * mm,
                  title="콕집 — 서울 아파트 호가 구간별 매물 동향", author="콕집").build(f, onFirstPage=page, onLaterPages=page)
print("생성:", OUT)
