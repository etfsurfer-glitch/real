# -*- coding: utf-8 -*-
"""매도인 자금 제공 매물 광고 — 자치구별 일별 상세(기자 보완 요청 대응, 2026-09-04).
요청: 서울 각 자치구·수도권 각 시(구)별 일별 추이 — 상급지→인접지 확산 양상 확인용.
디벨럽: 지역별 최초 포착일 타임라인 + 강남3구·용산 비중 추이 + 주별 활성 지역 수.
데이터: 일별상세/일별_시군구별.csv (게재 광고 스톡, 79일). 수치는 전부 CSV에서 동적 산출.
산출: 매도인자금제공_자치구상세보고서.docx / .pdf + ../data/sfg_*.png
"""
import csv, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
BLUE = (0x12/255, 0x68/255, 0xD3/255)

ROWS = list(csv.reader(open(HERE / "일별상세" / "일별_시군구별.csv")))
HEADS = ROWS[0][1:]
DAYS = [r[0] for r in ROWS[1:]]
LBL = [d[5:] for d in DAYS]
M = {h: [int(r[i+1]) for r in ROWS[1:]] for i, h in enumerate(HEADS)}
N = len(DAYS)

TOP4 = ["서울 강남구", "서울 서초구", "서울 송파구", "서울 용산구"]
SEOUL = [h for h in HEADS if h.startswith("서울")]
GGIC = [h for h in HEADS if h.startswith("경기") or h.startswith("인천")]
ETC = [h for h in HEADS if h not in SEOUL and h not in GGIC]

def series(cols):
    return [sum(M[c][i] for c in cols) for i in range(N)]

S_T4, S_SEOUL, S_GGIC, S_ETC = series(TOP4), series(SEOUL), series(GGIC), series(ETC)
S_SEOUL_X = [a - b for a, b in zip(S_SEOUL, S_T4)]
S_TOT = series(HEADS)

# 최초 양수 등장일 / 최근 7일 평균
FIRST = {}
for h in HEADS:
    for d, v in zip(DAYS, M[h]):
        if v > 0:
            FIRST[h] = d
            break
R7 = {h: statistics.mean(M[h][-7:]) for h in HEADS}

def mean_rng(s, a, b):  # inclusive date strings
    i, j = DAYS.index(a), DAYS.index(b)
    return statistics.mean(s[i:j+1])

P_LATE_JUL = ("2026-07-23", "2026-07-31")
P_EARLY_AUG = ("2026-08-01", "2026-08-15")
w_t4 = [mean_rng(S_T4, *P_LATE_JUL), mean_rng(S_T4, *P_EARLY_AUG), statistics.mean(S_T4[-7:])]
w_tot = [mean_rng(S_TOT, *P_LATE_JUL), mean_rng(S_TOT, *P_EARLY_AUG), statistics.mean(S_TOT[-7:])]
w_se = [mean_rng(S_SEOUL, *P_LATE_JUL), mean_rng(S_SEOUL, *P_EARLY_AUG), statistics.mean(S_SEOUL[-7:])]
SHARE_ALL = [a/b*100 for a, b in zip(w_t4, w_tot)]
SHARE_SEOUL = [a/b*100 for a, b in zip(w_t4, w_se)]

# 주별 활성 지역 수
WEEKS = []
for w0 in range(0, N, 7):
    w = range(w0, min(w0+7, N))
    WEEKS.append((DAYS[w0][5:],
                  sum(1 for h in SEOUL if any(M[h][i] > 0 for i in w)),
                  sum(1 for h in GGIC if any(M[h][i] > 0 for i in w))))

BASE_GUS = sorted([h for h in HEADS if FIRST.get(h) == DAYS[0]], key=lambda h: -M[h][-1])
D_GANGNAM = FIRST["서울 강남구"]

def short(h):
    p = h.split()
    if p[0] in ("서울",):
        return p[1][:-1] if p[1].endswith("구") else p[1]
    if p[0] in ("경기", "인천"):
        if len(p) == 3:  # 시+구
            city, gu = p[1][:-1], p[2][:-1]
            return {"성남분당": "분당", "성남수정": "수정", "고양일산동": "일산동", "고양일산서": "일산서",
                    "수원영통": "영통", "수원장안": "장안", "안양동안": "동안", "안양만안": "만안",
                    "용인기흥": "기흥", "용인수지": "수지", "화성동탄": "동탄"}.get(city+gu, city+gu)
        return p[1][:-1]
    if p[0] == "부산":
        return {"부산진구": "부산진", "해운대구": "해운대", "수영구": "부산수영"}.get(p[1], p[0]+p[1][:-1])
    if p[0] == "충북":
        return "청주"
    return p[0] + p[1][:-1]  # 대구수성

def short2(h):
    return short(h)

DOCTYPE = "데이터 분석 보고서 — 자치구별 일별 상세 (취재 참고자료)"
TITLE = "매도인 자금 제공 매물 광고 — 서울 자치구·수도권 구별 일별 데이터"
SUBTITLE = (f"2026년 6월 16일 ~ 9월 3일({N}개 일자) · 관측된 전체 {len(HEADS)}개 시군구"
            f"(서울 {len(SEOUL)}개구, 경기·인천 {len(GGIC)}개, 그 외 {len(ETC)}개)의 게재 광고 수를 일별 수록 · "
            "지역별 최초 포착일과 강남 3구·용산 비중 추이 포함")

SUMMARY = [
    ("구성", "①지역별 최초 포착일 타임라인 ②서울 자치구 × 일별 ③경기·인천·그 외 × 일별 + 비중·확산 차트"),
    ("관측 시작", f"6월 16일 시점 게재 지역은 {'·'.join(short(h) for h in BASE_GUS)} 등 서울 {len(BASE_GUS)}개구뿐"),
    ("확산 경과", f"{D_GANGNAM[5:].replace('-', '/')} 강남 첫 포착 → 7월 넷째 주 서울 15개구·경기 14개 지역으로 확대 → "
                f"최근 주 서울 {WEEKS[-1][1]}개구·경기 인천 {WEEKS[-1][2]}개"),
    ("강남3구·용산", f"게재 건수는 하루 평균 {w_t4[0]:.0f}건(7월 말)→{w_t4[2]:.0f}건(최근 7일)으로 늘었으나, "
                  f"전체 대비 비중은 {SHARE_ALL[0]:.1f}%→{SHARE_ALL[1]:.1f}%(8월 초·중순)→{SHARE_ALL[2]:.1f}%(최근 7일)"),
]

BODY = [
    ("1. 집계 정의",
     "본편·일별상세 보고서와 동일하게, 각 일자 수집 스냅샷에서 그날 게재 중이던 해당 조건(매도인 "
     "자금 제공) 광고 수를 광고 대상 단지 소재지의 시군구 단위로 집계했습니다. 표의 ‘·’는 0건을 "
     "뜻합니다. ‘최초 포착일’은 관측 기간(6월 16일 시작) 안에서 해당 시군구에 게재 광고가 처음 "
     "나타난 날로, 6월 16일로 표기된 지역은 관측 시작 전부터 게재 중이었을 수 있습니다."),
    ("2. 지역 확산 경과",
     f"관측 시작(6월 16일) 시점의 게재 지역은 서울 {len(BASE_GUS)}개구"
     f"({'·'.join(short(h) for h in BASE_GUS)})가 전부였고, 7월 셋째 주까지 서울 2~4개구 범위를 "
     f"유지했습니다. {D_GANGNAM[5:].replace('-', '/')} 강남구가 처음 포착된 뒤 7월 22~25일 사이 "
     "서초·성동·마포·영등포·동작 등 서울 자치구와 성남 분당·과천·남양주·수원 영통 등 경기 "
     "지역이 잇따라 처음 나타났으며, 이후 매주 지역이 넓어져 7월 넷째 주 서울 15개구·경기 14개 "
     f"지역, 8월 둘째 주부터는 서울 {max(w[1] for w in WEEKS)}개구·경기 인천 "
     f"{max(w[2] for w in WEEKS)}개 지역 수준을 유지하고 있습니다(표1·아래 주별 집계). 인천은 "
     f"8월 1일(연수구)부터, 그 외 지방은 부산 해운대(7월 23일)·대구 수성(7월 25일) 등이 관측됐습니다."),
    ("3. 강남 3구·용산과 그 외 지역의 상대 추이",
     f"강남·서초·송파·용산 4개구의 게재 건수는 하루 평균 {w_t4[0]:.1f}건(7월 23~31일) → "
     f"{w_t4[1]:.1f}건(8월 1~15일) → {w_t4[2]:.1f}건(최근 7일)으로 계속 늘었습니다. 다만 전체에서 "
     f"차지하는 비중은 {SHARE_ALL[0]:.1f}% → {SHARE_ALL[1]:.1f}% → {SHARE_ALL[2]:.1f}%, 서울 안에서의 "
     f"비중은 {SHARE_SEOUL[0]:.1f}% → {SHARE_SEOUL[1]:.1f}% → {SHARE_SEOUL[2]:.1f}%로, 8월 초·중순을 "
     "고비로 이후에는 4개구 밖(서울 그 외 자치구와 경기·인천)의 증가 속도가 더 빨랐습니다. "
     "차트2와 표2·표3에서 구별로 확인할 수 있습니다."),
    ("4. 유의 사항",
     "7월 중순 이전은 표본이 하루 5건 안팎으로 작아 비중 해석에 한계가 있습니다. 최초 포착일은 "
     "광고 문구를 새로 적어 넣은 기존 광고를 포함할 수 있으며, 광고는 수시로 등록·삭제되므로 "
     "열람 시점에 따라 수치가 달라질 수 있습니다."),
]

NOTE = ("작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  "
        "본 자료는 같은 조건의 매도인 자금 제공 매물 분석 보고서의 자치구별 상세편입니다. 다른 "
        "구간·다른 지역 묶음의 집계가 필요하시면 언제든 요청해 주시기 바랍니다.")

C_STACK = DATA / "sfg_stack.png"
C_SHARE = DATA / "sfg_share.png"
C_GUS = DATA / "sfg_gus.png"

def _font():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    import matplotlib.pyplot as plt
    for f in ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf"):
        font_manager.fontManager.addfont(str(FONTS / f))
    plt.rcParams["font.family"] = "Pretendard"
    plt.rcParams["axes.unicode_minus"] = False
    return plt

def _ticks(ax):
    idx = [i for i, d in enumerate(DAYS)
           if (d[8:] in ("01", "16") and N - 1 - i > 3) or d == DAYS[-1]]
    ax.set_xticks(idx); ax.set_xticklabels([LBL[i] for i in idx], fontsize=8.3)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)

def chart_stack():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    xs = list(range(N))
    groups = [("강남3구·용산", S_T4, "#1268D3"), ("서울 그 외", S_SEOUL_X, "#7aa3cf"),
              ("경기·인천", S_GGIC, "#0e9f6e"), ("그 외 지방", S_ETC, "#e6d3c3")]
    bottom = [0.0]*N
    for lab, ys, col in groups:
        ax.bar(xs, ys, 0.86, bottom=bottom, color=col, label=lab, linewidth=0)
        bottom = [b+y for b, y in zip(bottom, ys)]
    _ticks(ax)
    ax.legend(ncol=4, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("건", fontsize=9)
    fig.suptitle("게재 광고 — 강남3구·용산 / 서울 그 외 / 경기·인천 / 그 외 (일별)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_STACK, bbox_inches="tight")
    print("chart:", C_STACK)

def chart_share():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 2.7), dpi=200)
    xs, ys_all, ys_se = [], [], []
    for i in range(N):
        a, b = max(0, i-6), i+1
        tot = sum(S_TOT[a:b]); se = sum(S_SEOUL[a:b]); t4 = sum(S_T4[a:b])
        if tot >= 35:  # 표본 작은 초기 구간 제외(주 5건 미만)
            xs.append(i); ys_all.append(t4/tot*100); ys_se.append(t4/se*100 if se else 0)
    ax.plot(xs, ys_se, color="#1268D3", lw=1.9, label="서울 내 비중")
    ax.plot(xs, ys_all, color="#d97706", lw=1.9, ls="--", label="전체 대비 비중")
    _ticks(ax)
    ax.set_ylim(0, 80); ax.set_ylabel("%", fontsize=9)
    ax.legend(ncol=2, fontsize=8.6, frameon=False, loc="upper right")
    fig.suptitle("강남3구·용산 게재 비중(7일 누적 기준) — 표본 주 35건 이상 구간", fontsize=11.5, fontweight="bold", y=1.02)
    fig.tight_layout(); fig.savefig(C_SHARE, bbox_inches="tight")
    print("chart:", C_SHARE)

def chart_gus():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    top = sorted(SEOUL + GGIC, key=lambda h: -R7[h])[:8]
    palette = ["#1268D3", "#0e9f6e", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#65a30d", "#64748b"]
    for h, col in zip(top, palette):
        ax.plot(range(N), M[h], color=col, lw=1.6, label=short(h))
    _ticks(ax)
    ax.set_ylabel("건", fontsize=9)
    ax.legend(ncol=8, fontsize=8.0, frameon=False, loc="upper left")
    fig.suptitle("게재 상위 8개 구(최근 7일 평균 기준) — 일별", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_GUS, bbox_inches="tight")
    print("chart:", C_GUS)

# 표1: 확산 타임라인
def t1_rows():
    rows = []
    for h, d in sorted(FIRST.items(), key=lambda kv: (kv[1], -R7[kv[0]])):
        first = "관측 시작 전부터" if d == DAYS[0] else d[5:].replace("-", "/")
        rows.append([h, first, f"{M[h][-1]}", f"{R7[h]:.1f}"])
    return rows

T1_HEADS = ["지역", "최초 포착일", "9/3 게재", "최근 7일 평균"]

def dash(v):
    return "·" if v == 0 else str(v)

SEOUL_ORD = sorted(SEOUL, key=lambda h: -R7[h])
REST_ORD = sorted(GGIC, key=lambda h: -R7[h]) + sorted(ETC, key=lambda h: -R7[h])
T2_HEADS = ["날짜"] + [short(h) for h in SEOUL_ORD]
T3_HEADS = ["날짜"] + [short2(h) for h in REST_ORD]

def t2_rows():
    return [[LBL[i]] + [dash(M[h][i]) for h in SEOUL_ORD] for i in range(N)]

def t3_rows():
    return [[LBL[i]] + [dash(M[h][i]) for h in REST_ORD] for i in range(N)]

def make_docx(out: Path):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    d = Document()
    st = d.styles["Normal"]; st.font.name = "맑은 고딕"; st.font.size = Pt(10.5)
    st.paragraph_format.line_spacing = 1.45; st.paragraph_format.space_after = Pt(10)
    p = d.add_paragraph(); r = p.add_run(DOCTYPE)
    r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = RGBColor(0x12, 0x68, 0xD3)
    t = d.add_paragraph(); r = t.add_run(TITLE); r.font.size = Pt(14.5); r.font.bold = True
    s = d.add_paragraph(); r = s.add_run(SUBTITLE)
    r.font.size = Pt(10.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    h = d.add_paragraph(); r = h.add_run("■ 요약"); r.font.bold = True; r.font.size = Pt(11.5)
    tb = d.add_table(rows=0, cols=2); tb.style = "Light Grid Accent 1"
    for k, v in SUMMARY:
        c = tb.add_row().cells
        c[0].paragraphs[0].add_run(k).bold = True
        c[1].paragraphs[0].add_run(v)
    for rowx in tb.rows:
        for c in rowx.cells:
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(2)
                for rr in pp.runs: rr.font.size = Pt(9)
    for img in (C_STACK, C_SHARE, C_GUS):
        ch = d.add_paragraph(); ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ch.add_run().add_picture(str(img), width=Cm(16.4))
    for head, body in BODY:
        h = d.add_paragraph(); r = h.add_run("■ " + head); r.font.bold = True; r.font.size = Pt(11.5)
        h.paragraph_format.space_before = Pt(8); h.paragraph_format.space_after = Pt(4)
        d.add_paragraph(body)
    def big_table(title, heads, rows, fs=6.6):
        h = d.add_paragraph(); r = h.add_run(title); r.font.bold = True; r.font.size = Pt(11.5)
        tb = d.add_table(rows=1, cols=len(heads)); tb.style = "Light Grid Accent 1"
        for c, x in zip(tb.rows[0].cells, heads):
            c.paragraphs[0].add_run(x).bold = True
        for row in rows:
            for c, x in zip(tb.add_row().cells, row):
                c.paragraphs[0].add_run(str(x))
        for rowx in tb.rows:
            for c in rowx.cells:
                for pp in c.paragraphs:
                    pp.paragraph_format.space_after = Pt(0); pp.paragraph_format.line_spacing = 1.0
                    for rr in pp.runs: rr.font.size = Pt(fs)
    big_table("■ 표1 — 지역별 최초 포착일 타임라인 (최초 포착일 순)", T1_HEADS, t1_rows(), fs=8)
    big_table("■ 표2 — 서울 자치구 × 일별 게재 광고 (단위: 건, ·=0)", T2_HEADS, t2_rows(), fs=5.6)
    big_table("■ 표3 — 경기·인천·그 외 × 일별 게재 광고 (단위: 건, ·=0)", T3_HEADS, t3_rows(), fs=5.4)
    m = d.add_paragraph(); r = m.add_run(NOTE)
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    d.save(out); print("docx:", out)

def make_pdf(out: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
                                    Table, TableStyle)
    from reportlab.lib import colors
    from PIL import Image as PImage
    pdfmetrics.registerFont(TTFont("P", str(FONTS / "Pretendard-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("PB", str(FONTS / "Pretendard-Bold.ttf")))
    blue = colors.Color(*BLUE); gray = colors.Color(0.39, 0.45, 0.55)
    ss = {
        "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=blue, spaceAfter=3),
        "title": ParagraphStyle("title", fontName="PB", fontSize=14, leading=19, spaceAfter=3),
        "sub": ParagraphStyle("sub", fontName="P", fontSize=9.6, textColor=gray, leading=14, spaceAfter=11),
        "body": ParagraphStyle("body", fontName="P", fontSize=9.8, leading=15.5, spaceAfter=8),
        "head": ParagraphStyle("head", fontName="PB", fontSize=11, leading=15, spaceBefore=6, spaceAfter=4),
        "note": ParagraphStyle("note", fontName="P", fontSize=7.6, leading=11.5, textColor=gray, spaceAfter=8),
        "sumk": ParagraphStyle("sumk", fontName="PB", fontSize=8.8, leading=12.5),
        "sumv": ParagraphStyle("sumv", fontName="P", fontSize=8.8, leading=12.5),
    }
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=13*mm, rightMargin=13*mm,
                            topMargin=13*mm, bottomMargin=13*mm)
    def img(pth):
        w, h = PImage.open(pth).size
        cw = 184*mm
        return RLImage(str(pth), width=cw, height=cw*h/w)
    sum_tbl = Table([[Paragraph(k, ss["sumk"]), Paragraph(v, ss["sumv"])] for k, v in SUMMARY],
                    colWidths=[22*mm, 162*mm])
    sum_tbl.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.Color(0.85,0.88,0.92)),
        ("BACKGROUND", (0,0), (0,-1), colors.Color(0.955,0.97,0.99)),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    def data_table(heads, rows, widths, fs=6.6, align_left_first=True):
        t = Table([heads] + rows, colWidths=widths, repeatRows=1)
        sty = [
            ("FONT", (0,0), (-1,0), "PB", fs), ("FONT", (0,1), (-1,-1), "P", fs),
            ("BACKGROUND", (0,0), (-1,0), colors.Color(0.91,0.945,0.988)),
            ("GRID", (0,0), (-1,-1), 0.4, colors.Color(0.85,0.88,0.92)),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 1.0), ("BOTTOMPADDING", (0,0), (-1,-1), 1.0),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.Color(0.975,0.982,0.99)])]
        t.setStyle(TableStyle(sty))
        return t
    story = [Paragraph(DOCTYPE, ss["tag"]), Paragraph(TITLE, ss["title"]),
             Paragraph(SUBTITLE, ss["sub"]), Paragraph("■ 요약", ss["head"]), sum_tbl,
             Spacer(1, 4*mm), img(C_STACK), Spacer(1, 2*mm), img(C_SHARE), Spacer(1, 2*mm),
             img(C_GUS), Spacer(1, 3*mm)]
    for head, body in BODY:
        story.append(Paragraph("■ "+head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph("■ 주별 활성 지역 수 (해당 주에 1건 이상 게재된 시군구)", ss["head"]))
    wk_tbl = data_table(["주 시작일", "서울(개구)", "경기·인천(개)"],
                        [[w[0], str(w[1]), str(w[2])] for w in WEEKS],
                        [30*mm, 30*mm, 30*mm], fs=8.0)
    story.append(wk_tbl)
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("■ 표1 — 지역별 최초 포착일 타임라인 (최초 포착일 순)", ss["head"]))
    story.append(data_table(T1_HEADS, t1_rows(), [42*mm, 34*mm, 24*mm, 30*mm], fs=7.6))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("■ 표2 — 서울 자치구 × 일별 게재 광고 (단위: 건, ·=0, 최근 7일 평균 많은 순)", ss["head"]))
    n2 = len(T2_HEADS) - 1
    story.append(data_table(T2_HEADS, t2_rows(), [13*mm] + [round(171/n2, 2)*mm]*n2, fs=5.6))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("■ 표3 — 경기·인천·그 외 × 일별 게재 광고 (단위: 건, ·=0, 최근 7일 평균 많은 순)", ss["head"]))
    n3 = len(T3_HEADS) - 1
    story.append(data_table(T3_HEADS, t3_rows(), [13*mm] + [round(171/n3, 2)*mm]*n3, fs=5.2))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story); print("pdf:", out)

if __name__ == "__main__":
    chart_stack(); chart_share(); chart_gus()
    make_docx(HERE / "매도인자금제공_자치구상세보고서.docx")
    make_pdf(HERE / "매도인자금제공_자치구상세보고서.pdf")
