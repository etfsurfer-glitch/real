# -*- coding: utf-8 -*-
"""매도인 자금 제공 매물 광고 — 지역별 일별 상세(기자 추가 요청 대응 · 2026-09-07 발행).
요청: 날짜 × 지역별 × {전체 광고 / 중복 제거 물건 / 가격대}.
산출: 매도인자금제공_지역상세보고서.docx / .pdf + ../data/sfr_*.png
"""
import csv, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
FONTS = Path("/Users/hcode/auto/naverreal/design/fonts")
DATA = HERE.parent / "data"
DD = HERE / "지역상세"
ST = json.load(open(DD / "region_detail.json"))
DAYS = ST["days"]; LBL = [d[5:] for d in DAYS]
REGS = ["서울", "경기", "그외"]
C_NEW = DATA / "sfr_new.png"
C_ITEM = DATA / "sfr_items.png"
C_REGION = DATA / "sfr_total.png"
BLUE = (0x12/255, 0x68/255, 0xD3/255)

t9 = {g: ST["tot"][g][-1] for g in REGS}
n9 = {g: ST["new"][g][-1] for g in REGS}
i9 = {g: ST["items"][g][-1] for g in REGS}

DOCTYPE = "데이터 분석 보고서 — 지역별 일별 상세 (취재 참고자료)"
TITLE = "매도인 자금 제공 매물 광고 — 지역별 게재·물건·가격대 일별 데이터"
SUBTITLE = ("2026년 6월 16일 ~ 9월 7일(83개 일자) · 지역(서울/경기/그 외)별로 게재 광고·"
            "중복 제거 물건 수·가격대 구성을 일별 수록")

SUMMARY = [
    ("구성", "일별 × 지역(서울/경기/그 외) × {게재 광고 / 중복 제거 물건 수 / 호가 5구간}"),
    ("9월 7일", f"서울 게재 {t9['서울']}건(물건 {i9['서울']}) · 경기 {t9['경기']}건(물건 {i9['경기']}) · 그 외 {t9['그외']}건"),
    ("지역 추이", "증가 초기(7월 말)부터 서울 주도, 8월 중순부터 경기 확대 — 서울·경기 게재가 모두 유지됨"),
    ("정의", "본편·일별상세 보고서와 동일 기준: 스냅샷·광고번호 최초 관측·(단지·면적형·호가) 물건 근사"),
]

BODY = [
    ("1. 집계 정의",
     "‘게재 광고’는 각 일자 수집 스냅샷에서 그날 게재 중이던 해당 조건(매도인 자금 제공) 광고 수, "
     "‘중복 제거 물건 수’는 같은 단지·면적형·호가 조합을 한 물건으로 본 "
     "근사치입니다. 지역은 광고 대상 단지의 소재지 기준 서울/경기/그 외 "
     "3구분입니다."),
    ("2. 지역별 추이 요약",
     f"9월 7일 기준 서울은 광고 {t9['서울']}건·물건 {i9['서울']}건, "
     f"경기는 광고 {t9['경기']}건·물건 {i9['경기']}건, 그 외 지역은 광고 "
     f"{t9['그외']}건·물건 {i9['그외']}건입니다. 증가가 시작된 7월 말에는 서울이 대부분을 "
     "차지했으나 8월 중순부터 경기가 하루 40~60건대로 늘었습니다. "
     "상세 수치는 표1(전체·물건)과 표2(가격대)에 있습니다."),
    ("3. 유의 사항",
     "물건 수는 위 정의에 따른 근사치입니다. 광고는 수시로 등록·삭제되므로 열람 "
     "시점에 따라 수치가 달라질 수 있습니다."),
]

NOTE = ("작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  ※ 본 집계는 2026년 9월 7일 최신 수집 데이터를 기준으로 재산정한 값입니다. 관측 기간 중간의 수집 스냅샷이 보강되면서, 앞서 배포된 잠정치와는 게재 광고·물건 수 등 일부 수치가 소폭 조정되었습니다. "
        "본 자료는 같은 날짜의 매도인 자금 제공 매물 분석 보고서의 지역별 상세편입니다. 다른 "
        "구간·다른 지역 구분의 집계가 필요하시면 언제든 요청해 주시기 바랍니다.")

R1 = list(csv.reader(open(DD / "지역별_광고신규물건.csv")))
R2 = list(csv.reader(open(DD / "지역별_가격대.csv")))
T1_HEADS = ["날짜"] + [f"{g}\n{k}" for g in REGS for k in ("게재", "물건")]
T2_HEADS = ["날짜"] + [f"{g}\n{b}" for g in REGS for b in ("5억↓", "5~10", "10~20", "20~30", "30억↑")]
def t1_rows():
    return [[r[0][5:]] + [(r[i] if str(r[i]).strip() else "—") for i in (1,3,4,6,7,9)] for r in R1[1:]]
def t2_rows():
    return [[r[0][5:]] + r[1:] for r in R2[1:]]

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
    idx = [i for i, d in enumerate(DAYS) if d[8:] in ("01", "16") or d == DAYS[-1]]
    ax.set_xticks(idx); ax.set_xticklabels([LBL[i] for i in idx], fontsize=8.3)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)

def chart_total():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    xs = list(range(len(DAYS)))
    cols = {"서울": "#1268D3", "경기": "#7aa3cf", "그외": "#e6d3c3"}
    bottom = [0.0]*len(DAYS)
    for g in REGS:
        ys = ST["tot"][g]
        ax.bar(xs, ys, 0.86, bottom=bottom, color=cols[g], label=g, linewidth=0)
        bottom = [b+y for b, y in zip(bottom, ys)]
    _ticks(ax)
    ax.legend(ncol=3, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("건", fontsize=9)
    fig.suptitle("지역별 게재 광고(해당 조건) — 일별 (2026.6.16 ~ 9.7)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_REGION, bbox_inches="tight")
    print("chart:", C_REGION)

def chart_new():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    xs = list(range(len(DAYS)))
    cols = {"서울": "#1268D3", "경기": "#7aa3cf", "그외": "#e6d3c3"}
    bottom = [0.0]*len(DAYS)
    for g in REGS:
        ys = ST["new"][g]
        ax.bar(xs, ys, 0.86, bottom=bottom, color=cols[g], label=g, linewidth=0)
        bottom = [b+y for b, y in zip(bottom, ys)]
    _ticks(ax)
    ax.legend(ncol=3, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("건", fontsize=9)
    fig.suptitle("지역별 신규 포착 광고 — 일별 (2026.6.16 ~ 9.7)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_NEW, bbox_inches="tight")
    print("chart:", C_NEW)

def chart_items():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.0), dpi=200)
    xs = list(range(len(DAYS)))
    for g, col, lsty in (("서울", "#1268D3", "-"), ("경기", "#0e9f6e", "--"), ("그외", "#d97706", ":")):
        ax.plot(xs, ST["items"][g], color=col, lw=1.9, ls=lsty, label=g)
    _ticks(ax)
    ax.legend(ncol=3, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("건", fontsize=9)
    fig.suptitle("지역별 중복 제거 물건 수 — 일별 (2026.6.16 ~ 9.7)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_ITEM, bbox_inches="tight")
    print("chart:", C_ITEM)

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
    for img in (C_REGION, C_ITEM):
        ch = d.add_paragraph(); ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ch.add_run().add_picture(str(img), width=Cm(16.4))
    for head, body in BODY:
        h = d.add_paragraph(); r = h.add_run("■ " + head); r.font.bold = True; r.font.size = Pt(11.5)
        h.paragraph_format.space_before = Pt(8); h.paragraph_format.space_after = Pt(4)
        d.add_paragraph(body)
    def big_table(title, heads, rows):
        h = d.add_paragraph(); r = h.add_run(title); r.font.bold = True; r.font.size = Pt(11.5)
        tb = d.add_table(rows=1, cols=len(heads)); tb.style = "Light Grid Accent 1"
        for c, x in zip(tb.rows[0].cells, heads):
            c.paragraphs[0].add_run(x.replace("\n", " ")).bold = True
        for row in rows:
            for c, x in zip(tb.add_row().cells, row):
                c.paragraphs[0].add_run(str(x))
        for rowx in tb.rows:
            for c in rowx.cells:
                for pp in c.paragraphs:
                    pp.paragraph_format.space_after = Pt(0); pp.paragraph_format.line_spacing = 1.0
                    for rr in pp.runs: rr.font.size = Pt(6.6)
    big_table("■ 표1 — 지역별 게재·물건 일별 (단위: 건)", T1_HEADS, t1_rows())
    big_table("■ 표2 — 지역별 가격대 구성 일별 (단위: 건)", T2_HEADS, t2_rows())
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
    def data_table(heads, rows, widths, fs=6.6):
        t = Table([[h.replace("\n"," ") for h in heads]] + rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,0), "PB", fs), ("FONT", (0,1), (-1,-1), "P", fs),
            ("BACKGROUND", (0,0), (-1,0), colors.Color(0.91,0.945,0.988)),
            ("GRID", (0,0), (-1,-1), 0.4, colors.Color(0.85,0.88,0.92)),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 1.0), ("BOTTOMPADDING", (0,0), (-1,-1), 1.0),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.Color(0.975,0.982,0.99)])]))
        return t
    story = [Paragraph(DOCTYPE, ss["tag"]), Paragraph(TITLE, ss["title"]),
             Paragraph(SUBTITLE, ss["sub"]), Paragraph("■ 요약", ss["head"]), sum_tbl,
             Spacer(1, 4*mm), img(C_REGION), Spacer(1, 2*mm),
             img(C_ITEM), Spacer(1, 3*mm)]
    for head, body in BODY:
        story.append(Paragraph("■ "+head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph("■ 표1 — 지역별 게재·물건 일별 (단위: 건)", ss["head"]))
    story.append(data_table(T1_HEADS, t1_rows(), [15*mm] + [24*mm]*6))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("■ 표2 — 지역별 가격대 구성 일별 (단위: 건)", ss["head"]))
    story.append(data_table(T2_HEADS, t2_rows(), [13*mm] + [11.1*mm]*15, fs=6.0))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story); print("pdf:", out)

if __name__ == "__main__":
    chart_total(); chart_items()
    make_docx(HERE / "매도인자금제공_지역상세보고서.docx")
    make_pdf(HERE / "매도인자금제공_지역상세보고서.pdf")
