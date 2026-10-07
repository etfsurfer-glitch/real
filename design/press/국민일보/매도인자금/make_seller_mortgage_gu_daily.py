# -*- coding: utf-8 -*-
"""매도인 자금 제공 매물 광고 — 자치구별 일별 게재 광고(기자 보완 요청 대응 · 2026-09-07 발행).
구성: 서울 각 자치구·수도권 각 시(구)별 일별 게재 광고 수 + 최근일(9/7) 자치구 순위.
데이터: 일별상세/일별_시군구별.csv (게재 광고 스톡). 수치는 전부 CSV에서 동적 산출.
산출: 매도인자금제공_자치구상세보고서.docx / .pdf + ../data/sfg_*.png
"""
import csv, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = Path("/Users/hcode/auto/naverreal/design/fonts")
DATA = HERE.parent / "data"
BLUE = (0x12/255, 0x68/255, 0xD3/255)

ROWS = list(csv.reader(open(HERE / "일별상세" / "일별_시군구별.csv")))
HEADS = ROWS[0][1:]
DAYS = [r[0] for r in ROWS[1:]]
LBL = [d[5:] for d in DAYS]
M = {h: [int(r[i+1]) for r in ROWS[1:]] for i, h in enumerate(HEADS)}
N = len(DAYS)
LAST = DAYS[-1]

TOP4 = ["서울 강남구", "서울 서초구", "서울 송파구", "서울 용산구"]
SEOUL = [h for h in HEADS if h.startswith("서울")]
GGIC = [h for h in HEADS if h.startswith("경기") or h.startswith("인천")]
ETC = [h for h in HEADS if h not in SEOUL and h not in GGIC]

def series(cols):
    return [sum(M[c][i] for c in cols) for i in range(N)]

S_T4, S_SEOUL, S_GGIC, S_ETC = series(TOP4), series(SEOUL), series(GGIC), series(ETC)
S_SEOUL_X = [a - b for a, b in zip(S_SEOUL, S_T4)]
S_TOT = series(HEADS)

# 최근 7일 평균(게재 활성 순 정렬 기준)
R7 = {h: statistics.mean(M[h][-7:]) for h in HEADS}
t4_last7 = statistics.mean(S_T4[-7:])
seoul_last7 = statistics.mean(S_SEOUL[-7:])

def short(h):
    p = h.split()
    if len(p) < 2:
        return p[0] if p else "미상"
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

# 최근일(9/7) 게재 상위 자치구
RANK_LAST = sorted([h for h in HEADS if M[h][-1] > 0], key=lambda h: (-M[h][-1], -R7[h]))
_top_str = " · ".join(f"{short(h)} {M[h][-1]}" for h in RANK_LAST[:8])

DOCTYPE = "데이터 분석 보고서 — 자치구별 일별 게재 광고 (취재 참고자료)"
TITLE = "매도인 자금 제공 매물 광고 — 서울 자치구·수도권 구별 일별 게재 데이터"
SUBTITLE = (f"2026년 6월 16일 ~ 9월 7일({N}개 일자) · 관측된 전체 {len(HEADS)}개 시군구"
            f"(서울 {len(SEOUL)}개구, 경기·인천 {len(GGIC)}개, 그 외 {len(ETC)}개)의 게재 광고 수를 일별 수록 · "
            "최근일(9/7) 자치구 순위 포함")

SUMMARY = [
    ("구성", "서울 자치구·수도권 시군구별 일별 게재 광고 수 + 최근일(9/7) 자치구 순위 · 상위 구 일별 추이 차트"),
    ("최근일(9/7) 상위", _top_str),
    ("권역 분포(9/7)", f"게재 광고 {S_TOT[-1]}건 중 서울 {S_SEOUL[-1]}건, 경기·인천 {S_GGIC[-1]}건, 그 외 지방 {S_ETC[-1]}건"),
    ("정의", "각 일자 수집 스냅샷에서 그날 게재 중이던 해당 조건 광고를 단지 소재지 시군구로 집계(스톡)"),
]

BODY = [
    ("1. 집계 정의",
     "각 일자 수집 스냅샷에서 그날 게재 중이던 해당 조건(매도인 자금 제공) 광고 수를 광고 대상 "
     "단지 소재지의 시군구 단위로 집계했습니다(각 일자에 게재 중이던 광고의 스톡). 표의 ‘·’는 "
     "0건을 뜻합니다. 광고 대상 단지의 소재지 기준이므로 중개업소 소재지와는 다를 수 있으며, "
     "광고는 수시로 등록·삭제되므로 열람 시점에 따라 수치가 달라질 수 있습니다."),
    ("2. 최근일(9월 7일) 자치구 분포",
     f"9월 7일 기준 게재 광고는 서울 {S_SEOUL[-1]}건, 경기·인천 {S_GGIC[-1]}건, 그 외 지방 "
     f"{S_ETC[-1]}건입니다. 자치구별로는 {_top_str} 순으로 많습니다. 상위 자치구의 일별 추이는 "
     "아래 차트와 표2(서울)·표3(경기·인천·그 외)에서 구별로 확인할 수 있습니다."),
    ("3. 권역별 게재 구성",
     f"강남·서초·송파·용산 4개구의 최근 7일 평균 게재는 하루 {t4_last7:.0f}건으로, 서울 전체 "
     f"게재(하루 {seoul_last7:.0f}건)의 약 {t4_last7/seoul_last7*100:.0f}%입니다. 나머지는 서울 그 외 "
     "자치구와 경기·인천·그 외 지방에 분포합니다. 권역군(강남3구·용산 / 서울 그 외 / 경기·인천 / "
     "그 외)별 일별 게재 구성은 차트1에, 게재 상위 8개 구의 일별 추이는 차트2에 있습니다."),
    ("4. 유의 사항",
     "7월 중순 이전은 게재 표본이 하루 5건 안팎으로 작아 구별 비교에 한계가 있습니다. 광고 문구 "
     "기준 집계로 등기부상 실제 근저당 설정과는 다르며, 같은 물건이 여러 중개사를 통해 복수로 "
     "게재될 수 있어 게재 광고 수는 물건 수보다 많습니다."),
]

NOTE = ("작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  ※ 본 집계는 2026년 9월 7일 최신 수집 데이터를 기준으로 재산정한 값입니다. 관측 기간 중간의 수집 스냅샷이 보강되면서, 앞서 배포된 잠정치와는 게재 광고·물건 수 등 일부 수치가 소폭 조정되었습니다. "
        "본 자료는 같은 조건의 매도인 자금 제공 매물 분석 보고서의 자치구별 상세편입니다. 다른 "
        "구간·다른 지역 묶음의 집계가 필요하시면 언제든 요청해 주시기 바랍니다.")

C_STACK = DATA / "sfg_stack.png"
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
    fig.suptitle("권역군별 일별 게재 광고 — 강남3구·용산 / 서울 그 외 / 경기·인천 / 그 외", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_STACK, bbox_inches="tight")
    print("chart:", C_STACK)

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

# 표1: 자치구 게재 순위(최근일 9/7)
def t1_rows():
    return [[h, f"{M[h][-1]}", f"{R7[h]:.1f}"] for h in RANK_LAST]

T1_HEADS = ["지역", "9/7 게재", "최근 7일 평균"]

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
    for img in (C_STACK, C_GUS):
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
    big_table("■ 표1 — 자치구 게재 광고 순위 (9월 7일 게재 많은 순)", T1_HEADS, t1_rows(), fs=8)
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
                    colWidths=[24*mm, 160*mm])
    sum_tbl.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.Color(0.85,0.88,0.92)),
        ("BACKGROUND", (0,0), (0,-1), colors.Color(0.955,0.97,0.99)),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    def data_table(heads, rows, widths, fs=6.6):
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
             Spacer(1, 4*mm), img(C_STACK), Spacer(1, 2*mm), img(C_GUS), Spacer(1, 3*mm)]
    for head, body in BODY:
        story.append(Paragraph("■ "+head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph("■ 표1 — 자치구 게재 광고 순위 (9월 7일 게재 많은 순)", ss["head"]))
    story.append(data_table(T1_HEADS, t1_rows(), [60*mm, 30*mm, 34*mm], fs=7.6))
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
    chart_stack(); chart_gus()
    make_docx(HERE / "매도인자금제공_자치구상세보고서.docx")
    make_pdf(HERE / "매도인자금제공_자치구상세보고서.pdf")
