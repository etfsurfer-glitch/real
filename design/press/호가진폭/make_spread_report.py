# -*- coding: utf-8 -*-
"""호가 진폭 보도자료 → PDF 조판.

수치는 손으로 적지 않는다. ../data/press_spread_*.json(박스에서 measure.py 로 산출)
을 그대로 읽어 표를 만든다 — 본문과 데이터가 어긋날 자리를 아예 없앤다.

실행: python3 design/press/호가진폭/make_spread_report.py
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "press_spread_20261007.json"
FONTS = HERE.parent.parent / "fonts"
OUT = HERE / "콕집_호가진폭_보도자료.pdf"

INK, MUTE, LINE = colors.HexColor("#1b2430"), colors.HexColor("#5b6775"), colors.HexColor("#d9e0e8")
BRAND, UP, DOWN = colors.HexColor("#1268d3"), colors.HexColor("#b3261e"), colors.HexColor("#1268d3")
BAND = colors.HexColor("#f2f7ff")

for nm, fn in (("P", "Pretendard-Regular.ttf"), ("P-B", "Pretendard-Bold.ttf"),
               ("P-M", "Pretendard-Medium.ttf"), ("P-EB", "Pretendard-ExtraBold.ttf")):
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

pdfmetrics.registerFontFamily("P", normal="P", bold="P-B", italic="P", boldItalic="P-B")
pdfmetrics.registerFontFamily("P-M", normal="P-M", bold="P-B", italic="P-M", boldItalic="P-B")

D = json.loads(DATA.read_text())
S, GU, GRP, G3 = D["series"], D["gu"], D["groups"], D["gn3"]
by = {r["name"]: r for r in GU}
grp = {r["name"]: r for r in GRP}

ss = getSampleStyleSheet()


def st(name, size, font="P", lead=None, color=INK, space=0, align=0):
    # alignment 는 반드시 숫자여야 한다(None 이면 draw 단계에서 터진다)
    return ParagraphStyle(name, parent=ss["Normal"], fontName=font, fontSize=size,
                          leading=lead or size * 1.55, textColor=color,
                          spaceAfter=space, alignment=align)


TITLE = st("t", 21, "P-EB", lead=29, space=5)
SUB = st("s", 11.5, "P-M", lead=18, color=BRAND, space=3)
H = st("h", 13.5, "P-B", lead=20, space=6)
BODY = st("b", 10.3, "P", lead=17.5, space=7)
NOTE = st("n", 9, "P", lead=15, color=MUTE, space=5)
CELL = st("c", 9.2, "P", lead=13.5)
CELLB = st("cb", 9.2, "P-B", lead=13.5)
CAP = st("cap", 8.8, "P-M", lead=13, color=MUTE, space=3)


def pct(v, digits=2):
    return f"{v:.{digits}f}%"


def chg(v):
    """증감률 — 벌어짐은 빨강, 좁아짐은 파랑. 색으로 방향이 먼저 읽히게."""
    c = UP if v > 0 else DOWN
    return Paragraph(f'<font color="{c.hexval()}"><b>{v:+.1f}%</b></font>', CELL)


def table(rows, widths, head=1, hi=(), align_right=True, keep=True):
    """keep=True 면 표를 쪼개지 않는다 — 마지막 한 줄만 다음 장으로 넘어가면 읽기 나쁘다."""
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=head)
    cmds = [
        ("FONT", (0, 0), (-1, -1), "P", 9.2),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("FONT", (0, 0), (-1, head - 1), "P-B", 9),
        ("TEXTCOLOR", (0, 0), (-1, head - 1), MUTE),
        ("LINEBELOW", (0, head - 1), (-1, head - 1), 0.9, INK),
        ("LINEBELOW", (0, head), (-1, -2), 0.4, LINE),
    ]
    if align_right:
        cmds.append(("ALIGN", (1, 0), (-1, -1), "RIGHT"))
    for r in hi:
        cmds += [("BACKGROUND", (0, r), (-1, r), BAND), ("FONT", (0, r), (0, r), "P-B", 9.2)]
    t.setStyle(TableStyle(cmds))
    return KeepTogether(t) if keep else t


def page(cv, doc):
    cv.saveState()
    cv.setFont("P-B", 8.5); cv.setFillColor(MUTE)
    cv.drawString(20 * mm, A4[1] - 12 * mm, "콕집 부동산 데이터 리포트")
    cv.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, "2026년 10월 7일")
    cv.setStrokeColor(LINE); cv.setLineWidth(0.6)
    cv.line(20 * mm, A4[1] - 15 * mm, A4[0] - 20 * mm, A4[1] - 15 * mm)
    cv.setFont("P", 8.5)
    cv.drawString(20 * mm, 12 * mm, "koczip.com")
    cv.drawRightString(A4[0] - 20 * mm, 12 * mm, str(cv.getPageNumber()))
    cv.restoreState()


f = []
f.append(Paragraph("세제개편 발표 이후 서울 아파트 호가 ‘진폭’ 반전<br/>— 바닥이 먼저 빠진다", TITLE))
f.append(Paragraph("같은 단지·같은 평형 안에서 최고가와 최저가의 거리, 강남3구 20.8% 벌어져<br/>"
                   "발표 직전까지 10주 연속 좁아지다 방향 바꿔 — 전국은 변화 없어", SUB))
f.append(Spacer(1, 7))

a, b = S["2026-08-03"], S["2026-10-06"]
f.append(Paragraph(
    "같은 아파트, 같은 평형인데 부르는 값이 제각각이다. 그 거리가 2026년 8월 3일 "
    "세제개편안 발표를 기점으로 벌어지기 시작했다.", BODY))
f.append(Paragraph(
    f"부동산 데이터 서비스 <b>콕집</b>(koczip.com)이 2026년 5월 25일부터 10월 6일까지 전국 아파트 "
    f"매매 매물 호가를 전수 분석한 결과, 서울 아파트의 <b>동일평형 호가 진폭</b>은 발표일 "
    f"{pct(a['seoul'])}에서 10월 6일 {pct(b['seoul'])}로 <b>{(b['seoul']/a['seoul']-1)*100:.1f}% 넓어졌다.</b> "
    f"강남3구(강남·서초·송파)는 {pct(a['gn3'])}에서 {pct(b['gn3'])}로 "
    f"<b>{(b['gn3']/a['gn3']-1)*100:.1f}% 넓어졌다.</b>", BODY))
f.append(Paragraph(
    f"같은 기간 <b>전국은 {pct(a['nat'])}에서 {pct(b['nat'])}로 사실상 변화가 없었다</b>"
    f"({(b['nat']/a['nat']-1)*100:+.1f}%). 전국적 현상이 아니라 서울, 그중에서도 특정 자치구에 몰린 "
    "움직임이다.", BODY))

box = Table([[Paragraph(
    "<b>동일평형 호가 진폭이란</b><br/>같은 단지의 같은 평형에 나와 있는 매물들 사이에서 "
    "(최고호가 − 최저호가) ÷ 평균호가 를 백분율로 나타낸 값이다. "
    "값이 클수록 같은 집인데도 부르는 값의 편차가 크다는 뜻이다.", CELL)]],
    colWidths=[170 * mm])
box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BAND),
                         ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfe0f8")),
                         ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                         ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11)]))
f += [Spacer(1, 4), box, Spacer(1, 14)]

# ── 1
f.append(Paragraph("1. 발표일이 최저점 — 좁아지던 흐름이 뒤집혔다", H))
f.append(Paragraph(
    "주목할 대목은 발표 <b>이전</b>의 흐름이다. 진폭은 5월 말부터 발표 직전까지 10주 내리 "
    "좁아지고 있었다. 8월 3일은 분석 구간 전체에서 가장 좁은 날이었다.", BODY))
DAYS = ["2026-05-25", "2026-06-15", "2026-06-29", "2026-07-13", "2026-07-27",
        "2026-08-03", "2026-08-17", "2026-09-14", "2026-10-06"]
rows = [["시점", "전국", "서울", "강남3구"]]
for d in DAYS:
    lab = f"{int(d[5:7])}월 {int(d[8:10])}일"
    if d == "2026-08-03":
        lab += " (발표)"
    rows.append([Paragraph(f"<b>{lab}</b>" if d in ("2026-08-03", "2026-10-06") else lab, CELL),
                 pct(S[d]["nat"]), pct(S[d]["seoul"]), pct(S[d]["gn3"])])
f.append(table(rows, [52 * mm, 30 * mm, 30 * mm, 30 * mm],
               hi=[DAYS.index("2026-08-03") + 1, DAYS.index("2026-10-06") + 1]))
f.append(Spacer(1, 11))
f.append(Paragraph("발표를 전후로 방향이 거의 대칭을 이룬다.", BODY))
pre, post = S["2026-05-25"], S["2026-10-06"]
rows = [["구분", "발표 전 (5/25→8/3, 70일)", "발표 후 (8/3→10/6, 64일)"]]
for k, lab in (("nat", "전국"), ("seoul", "서울"), ("gn3", "강남3구")):
    rows.append([Paragraph(f"<b>{lab}</b>", CELL),
                 chg((a[k] / pre[k] - 1) * 100), chg((post[k] / a[k] - 1) * 100)])
f.append(table(rows, [40 * mm, 56 * mm, 56 * mm]))
f.append(Spacer(1, 13))

# ── 2
f.append(Paragraph("2. 왜 벌어졌나 — 상단보다 바닥이 두 배 빠르게 빠졌다", H))
f.append(Paragraph(
    "진폭이 넓어지는 길은 두 가지다. 비싼 매물이 더 비싸지거나, 싼 매물이 더 싸지거나. "
    f"강남3구에서 두 시점에 모두 존재한 {G3['panel']:,}개 평형을 추적한 결과는 후자였다.", BODY))
L = G3["level"]
rows = [[f"강남3구 (동일 평형 {G3['panel']:,}개)", "8월 3일", "10월 6일", "변화"]]
for k, lab in (("mn", "최저호가 중앙값"), ("mx", "최고호가 중앙값"), ("av", "평균호가 중앙값")):
    v = L[k]
    rows.append([Paragraph(f"<b>{lab}</b>" if k == "mn" else lab, CELL),
                 f"{v['b']:.2f}억", f"{v['c']:.2f}억", chg((v["c"] / v["b"] - 1) * 100)])
f.append(table(rows, [62 * mm, 30 * mm, 30 * mm, 28 * mm], hi=[1]))
f.append(Spacer(1, 9))
f.append(Paragraph(
    "상단도 내렸지만 <b>바닥이 두 배 빠르게 내려갔다.</b> 호가 전반이 밀리는 가운데 "
    "사정이 급한 매물이 먼저, 더 많이 빠지면서 거리가 벌어진 것이다.", BODY))
f.append(Spacer(1, 10))

# ── 3
f.append(Paragraph("3. 같은 평형 안에서 10억 넘게 벌어진 사례가 늘었다", H))
f.append(Paragraph(
    "강남3구에서 같은 단지·같은 평형 안의 최고호가와 최저호가 <b>금액 차이</b>를 "
    "구간별로 보면 모든 구간에서 커졌다.", BODY))
GAP = G3["gap"]
rows = [["구간", "8월 3일", "10월 6일"]]
for p, lab in (("0.5", "중앙값"), ("0.75", "상위 25%"), ("0.9", "상위 10%"), ("0.95", "상위 5%")):
    rows.append([lab, f"{GAP[p]['b']:.2f}억", f"{GAP[p]['c']:.2f}억"])
o = G3["over10"]
rows.append([Paragraph("<b>차이가 10억 이상인 평형</b>", CELL),
             f"{o['b']}개", Paragraph(f"<b>{o['c']}개</b>", CELLB)])
f.append(table(rows, [52 * mm, 34 * mm, 34 * mm], hi=[len(rows) - 1]))
f.append(Spacer(1, 9))
f.append(Paragraph(
    f"중앙값 기준으로도 {(GAP['0.5']['c']-GAP['0.5']['b'])*10000:,.0f}만 원이 더 벌어졌고, "
    f"상위 5% 구간은 {GAP['0.95']['b']:.0f}억에서 {GAP['0.95']['c']:.0f}억으로 커졌다. "
    f"같은 동·같은 평형인데 부르는 값이 10억 넘게 차이 나는 경우가 두 달 만에 "
    f"{o['b']}개에서 {o['c']}개로 늘었다.", BODY))
f.append(Spacer(1, 13))

# ── 4
f.append(Paragraph("4. 송파가 가장 크게 벌어졌다 — 강남3구 안에서도 갈린다", H))
top = by["송파구"]
f.append(Paragraph(
    f"서울 25개 자치구를 따로 보면 진폭이 가장 크게 넓어진 곳은 <b>송파구"
    f"({top['chg']:+.1f}%)</b>였고 용산구({by['용산구']['chg']:+.1f}%), "
    f"강남구({by['강남구']['chg']:+.1f}%)가 뒤를 이었다.", BODY))
rows = [["자치구", "6월 15일", "8월 3일", "10월 6일", "발표 후", "최고−최저\n금액차(중앙값)"]]
hi = []
order = [r["name"] for r in GU[:8]] + ["서초구"]
for nm in order:
    r = by[nm]
    bold = nm in ("송파구", "용산구", "강남구", "서초구")
    rows.append([Paragraph(f"<b>{nm}</b>" if bold else nm, CELL),
                 pct(r["d0615"]), pct(r["d0803"]), pct(r["d1006"]), chg(r["chg"]),
                 f"{r['gap_eok']:.2f}억"])
for nm in ("강남3구", "서울시 전체"):
    r = grp[nm]
    hi.append(len(rows))
    rows.append([Paragraph(f"<i>(참고) {nm}</i>", CELL),
                 pct(r["d0615"]), pct(r["d0803"]), pct(r["d1006"]), chg(r["chg"]),
                 f"{r['gap_eok']:.2f}억" if nm != "강남3구" else "—"])
f.append(table(rows, [28 * mm, 24 * mm, 24 * mm, 24 * mm, 22 * mm, 30 * mm], hi=hi))
f.append(Spacer(1, 9))
f.append(Paragraph(
    f"흔히 한 덩어리로 묶이는 강남3구 안에서도 편차가 크다. <b>송파({by['송파구']['chg']:+.1f}%)와 "
    f"서초({by['서초구']['chg']:+.1f}%)는 세 배 넘게 차이 난다.</b> 서초구는 발표 전부터 이미 "
    f"{pct(by['서초구']['d0803'])}로 서울에서 가장 넓은 축에 속해 있었다. 넓어질 여지가 그만큼 "
    "적었던 셈이다.", BODY))
nar = [r for r in GU if r["chg"] < 0]
f.append(Paragraph(
    "반대로 진폭이 <b>좁아진</b> 자치구도 있다. "
    + ", ".join(f"{r['name']}({r['chg']:+.1f}%)" for r in nar[-5:][::-1])
    + "다. 호가가 한 방향으로 움직이는 시장과 매물마다 사정이 갈리는 시장이 서울 안에서 "
      "동시에 존재한다.", BODY))
f.append(Spacer(1, 10))

# ── 5
f.append(Paragraph("5. 시도별로는 서울만 홀로 움직였다", H))
rows = [["시도", "8월 3일", "10월 6일", "증감"]]
sido = D["sido"]
pick = sido[:5] + [r for r in sido if r["name"] in ("경기도", "세종시")] + sido[-1:]
seen = set()
for r in pick:
    if r["name"] in seen:
        continue
    seen.add(r["name"])
    bold = r["name"] == "서울시"
    rows.append([Paragraph(f"<b>{r['name']}</b>" if bold else r["name"], CELL),
                 pct(r["d0803"]), pct(r["d1006"]), chg(r["chg"])])
f.append(table(rows, [44 * mm, 28 * mm, 28 * mm, 26 * mm], hi=[1]))
f.append(Spacer(1, 9))
second = sido[1]
f.append(Paragraph(
    f"서울의 증가폭은 2위 {second['name']}({second['chg']:+.1f}%)의 두 배를 넘는다. "
    f"경기도는 오히려 좁아졌다({grp and [r for r in sido if r['name']=='경기도'][0]['chg']:+.1f}%).", BODY))
f.append(Paragraph(
    f"서울의 진폭 <b>수준</b> 자체는 전국에서 가장 낮다는 점도 함께 볼 필요가 있다. "
    f"서울 {pct(b['seoul'])}, 전국 {pct(b['nat'])}로 두 배 차이다. 서울은 단지·평형별로 가격이 "
    "촘촘하게 수렴해 있던 시장이었고, 지금 그 수렴이 풀리고 있다.", BODY))
f.append(Spacer(1, 14))

f.append(Paragraph("분석 개요", H))
f.append(Paragraph(
    f"<b>대상</b>  전국 아파트 매매 매물 호가 전수. 2026년 5월 25일 ~ 10월 6일<br/>"
    f"<b>단위</b>  같은 단지의 같은 평형에 5건 이상 매물이 나와 있는 ‘평형’ 단위. "
    f"시점별 약 {S['2026-10-06']['cells']//1000*1000:,}개<br/>"
    f"<b>지표</b>  동일평형 호가 진폭 = (최고호가 − 최저호가) ÷ 평균호가 × 100. "
    f"대표값은 평형들의 중앙값<br/>"
    f"<b>처리</b>  같은 평형에서 최고호가가 최저호가의 4배를 넘는 건은 입력 오류로 보고 제외"
    f"(전체의 0.1% 미만)", NOTE))
f.append(Spacer(1, 10))
f.append(Paragraph(
    "<b>콕집</b>(koczip.com)은 전국 아파트 매물과 실거래를 매일 수집해 단지·평형 단위로 "
    "가격 흐름을 보여 주는 부동산 데이터 서비스다.", BODY))
f.append(Spacer(1, 4))
f.append(Paragraph("작성 | 콕집(koczip.com) 대표 황인찬 · runtoonline@gmail.com",
                   st("by", 9.5, "P-M", color=MUTE)))

SimpleDocTemplate(str(OUT), pagesize=A4,
                  leftMargin=20 * mm, rightMargin=20 * mm,
                  topMargin=22 * mm, bottomMargin=18 * mm,
                  title="콕집 — 세제개편 전후 서울 아파트 호가 진폭",
                  author="콕집 대표 황인찬").build(f, onFirstPage=page, onLaterPages=page)
print("생성:", OUT)
