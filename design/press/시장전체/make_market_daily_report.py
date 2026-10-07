# -*- coding: utf-8 -*-
"""전국 아파트·오피스텔 매물 광고 — 시장 전체 일별 전수 데이터 보고서 (2026-09-03 기준).

대상: 특정 조건이 아닌 전체 매물 광고. 일별 79개 스냅샷(6/16~9/2)+당일.
산출: 시장전체_일별전수보고서.docx / .pdf + ../data/mk_*.png
지표: 거래유형별 광고수 · 신규 포착 · 물건 환산(동일주소묶음 Σ1/묶음광고수) ·
매매 가격대 5구간 · 시도별 광고수. 의견 없이 집계 사실만. 작성 황인찬.
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
C_TOT = DATA / "mk_total.png"
C_SIDO = DATA / "mk_sido.png"
C_BAND = DATA / "mk_band.png"
BLUE = (0x12 / 255, 0x68 / 255, 0xD3 / 255)

# ── 데이터 로드 ──────────────────────────────────────────────────
def _read(fp):
    return list(csv.DictReader(open(HERE / "data_daily" / fp)))

ROWS = _read("mk_summary.csv")          # 79일 + 당일
SIDO = {r["day"]: r for r in _read("mk_sido.csv")}
DAYS = [r["day"] for r in ROWS]
LBL = [d[5:] for d in DAYS]
N = {r["day"]: r for r in ROWS}
i9 = ROWS[-1]                            # 9/3
first = ROWS[0]

def _i(r, k):
    v = r.get(k, "")
    return int(float(v)) if str(v).strip() not in ("", "None") else 0

TOT9, SALE9 = _i(i9, "all"), _i(i9, "sale")
JEON9, WOL9 = _i(i9, "jeonse"), _i(i9, "wolse")
CONV9, CONVS9 = _i(i9, "conv_all"), _i(i9, "conv_sale")
NEW9 = _i(i9, "new")
tot_series = [_i(r, "all") for r in ROWS]
sale_series = [_i(r, "sale") for r in ROWS]
new_series = [_i(r, "new") for r in ROWS]
conv_series = [_i(r, "conv_all") for r in ROWS]
new_valid = [x for x in new_series[1:] if x > 0]
NEW_AVG = round(sum(new_valid) / len(new_valid)) if new_valid else 0
TOT_MIN, TOT_MAX = min(tot_series), max(tot_series)
b9 = [_i(i9, k) for k in ("b_u5", "b_5_10", "b_10_20", "b_20_30", "b_30p")]
b1 = [_i(first, k) for k in ("b_u5", "b_5_10", "b_10_20", "b_20_30", "b_30p")]
s9 = SIDO[DAYS[-1]]
SEOUL9, GG9, IC9 = _i(s9, "seoul"), _i(s9, "gg"), _i(s9, "ic")
CAP9 = SEOUL9 + GG9 + IC9

DOCTYPE = "데이터 분석 보고서 (취재 참고자료)"
TITLE = "전국 아파트·오피스텔 매물 광고 일별 전수 데이터"
SUBTITLE = (f"2026년 6월 16일 ~ 9월 3일(79개 일자) · 9월 3일 기준 전체 광고 {TOT9:,}건 · "
            "거래유형·지역·가격대·신규·물건 환산 일별 수치를 본문 표로 수록")

SUMMARY = [
    ("분석 대상", "전국 아파트·오피스텔(분양권 제외) 매물 광고 전수 — 각 일자 수집 스냅샷 기준"),
    ("전체 규모", f"9월 3일 {TOT9:,}건 (매매 {SALE9:,} · 전세 {JEON9:,} · 월세 {WOL9:,}) — 기간 중 {TOT_MIN:,}~{TOT_MAX:,}건"),
    ("물건 환산", f"동일주소묶음 환산 시 9월 3일 {CONV9:,}건 — 광고 1건당 물건 {TOT9/CONV9:.2f}배"),
    ("신규 포착", f"하루 평균 {NEW_AVG:,}건의 광고가 새로 포착(관측 기간, 수집 편차 있는 날 제외) — 9월 3일 {NEW9:,}건"),
    ("지역", f"수도권 {CAP9:,}건({100*CAP9/TOT9:.1f}%) — 경기 {GG9:,} · 서울 {SEOUL9:,} · 인천 {IC9:,}"),
    ("수록 표", "표1 일별 종합(유형·신규·물건·매매 가격대) · 표2 시도별 일별 — 전체 일자 수치"),
]

BODY = [
    ("1. 집계 정의",
     "‘전체 광고’는 각 일자 수집 스냅샷에서 게재 중이던 아파트·오피스텔 매물 광고 수입니다. "
     "‘신규 포착’은 그날 처음 관측된 광고번호의 수로, 관측 시작일(6월 16일)은 기준일이어서 "
     "값을 두지 않았습니다. 광고번호 기준이므로 같은 물건이 재등록되어 새 번호를 받은 경우도 "
     "포함됩니다. 수집이 표기일 새벽에 완료되므로, 각 일자의 신규 포착분은 실제로는 대부분 "
     "그 전날(달력일)에 등록된 광고입니다 — 예컨대 일요일 행의 신규는 토요일 등록분이며, "
     "실제 일요일 등록(월요일 행)은 하루 8천 건 안팎으로 평일의 5~6% 수준입니다. 수집이 부분적으로 이뤄진 날은 신규 수치가 실제보다 작거나 다음 "
     "날로 이월되어 크게 잡힐 수 있어, 요약에는 평균값을 함께 제시했습니다. ‘물건 환산’은 "
     "같은 물건을 여러 중개사가 중복 광고하는 효과를 제거하기 위해 매물 포털의 동일주소묶음 "
     "정보로 환산한 값(Σ 1/묶음광고수)입니다. 매매 가격대는 호가 기준 5개 구간입니다. "
     "6월 28일 스냅샷은 수집 결측으로 제외돼 있습니다."),
    ("2. 전체 규모와 물건 환산",
     f"전체 광고는 관측 기간 {TOT_MIN:,}~{TOT_MAX:,}건 사이에서 움직였고 9월 3일 "
     f"{TOT9:,}건입니다. 거래유형별로는 매매 {SALE9:,}건({100*SALE9/TOT9:.1f}%), 전세 "
     f"{JEON9:,}건({100*JEON9/TOT9:.1f}%), 월세 {WOL9:,}건({100*WOL9/TOT9:.1f}%)입니다. "
     f"동일주소묶음으로 환산한 물건 수는 9월 3일 {CONV9:,}건(매매 {CONVS9:,}건)으로, 광고 "
     f"1건당 물건 환산 배율은 {TOT9/CONV9:.2f}배입니다. 즉 한 물건이 평균 두 곳 이상의 "
     "중개업소에서 광고되고 있습니다."),
    ("3. 신규 포착",
     f"관측 기간 하루 평균 {NEW_AVG:,}건의 광고가 새로 포착됐습니다(9월 3일 {NEW9:,}건). "
     "전체 광고 수가 큰 변동 없이 유지되는 동안에도 이 규모의 등록이 계속된다는 것은, 비슷한 "
     "규모의 광고가 매일 내려가고 있다는 뜻이기도 합니다. 일자별 수치는 표1에 있으며, 수집 "
     "편차로 인한 널뛰기(직전일 부분 수집 시 다음 날로 이월)가 있는 점을 감안해 읽어 주시기 "
     "바랍니다."),
    ("4. 지역별",
     f"9월 3일 기준 경기 {GG9:,}건, 서울 {SEOUL9:,}건, 인천 {IC9:,}건으로 수도권이 "
     f"{100*CAP9/TOT9:.1f}%를 차지합니다. 시도별 일별 수치는 표2에 실었습니다."),
    ("5. 매매 가격대",
     f"9월 3일 매매 광고 {SALE9:,}건의 호가 분포는 5억원 미만 {b9[0]:,}건({100*b9[0]/SALE9:.1f}%), "
     f"5~10억원 {b9[1]:,}건({100*b9[1]/SALE9:.1f}%), 10~20억원 {b9[2]:,}건({100*b9[2]/SALE9:.1f}%), "
     f"20~30억원 {b9[3]:,}건({100*b9[3]/SALE9:.1f}%), 30억원 이상 {b9[4]:,}건"
     f"({100*b9[4]/SALE9:.1f}%)입니다. 일자별 구간 수치는 표1에 있습니다."),
    ("6. 유의 사항",
     "광고 기준 집계로 실제 거래·재고와 다릅니다. 물건 환산은 포털 묶음 정보 기반 근사치이며 "
     "등기부 기준의 물건 식별이 아닙니다. 광고는 수시로 등록·삭제되므로 열람 시점에 따라 "
     "수치가 달라질 수 있습니다."),
]

NOTE = (
    "작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  "
    "모든 수치는 저희가 자체 구축한 DB에서 집계했습니다(각 일자 수집 스냅샷 기준). 수치 정의는 "
    "본문 1장과 같습니다. 특정 지역·가격대·조건의 세부 집계가 필요하시면 언제든 요청해 "
    "주시기 바랍니다."
)

T1_HEADS = ["날짜", "전체", "매매", "전세", "월세", "신규", "물건환산",
            "5억↓", "5~10", "10~20", "20~30", "30억↑"]


def t1_rows():
    out = []
    for r in ROWS:
        out.append([r["day"][5:], f"{_i(r,'all'):,}", f"{_i(r,'sale'):,}", f"{_i(r,'jeonse'):,}",
                    f"{_i(r,'wolse'):,}", (f"{_i(r,'new'):,}" if str(r.get('new','')).strip() else "—"),
                    f"{_i(r,'conv_all'):,}",
                    f"{_i(r,'b_u5'):,}", f"{_i(r,'b_5_10'):,}", f"{_i(r,'b_10_20'):,}",
                    f"{_i(r,'b_20_30'):,}", f"{_i(r,'b_30p'):,}"])
    return out


T2_HEADS = ["날짜", "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종", "그 외"]


def t2_rows():
    out = []
    for d in DAYS:
        r = SIDO[d]
        out.append([d[5:]] + [f"{_i(r,k):,}" for k in
                              ("seoul", "gg", "ic", "bs", "dg", "dj", "gj", "us", "sj", "etc")])
    return out


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
    ax.set_xticks(idx)
    ax.set_xticklabels([LBL[i] for i in idx], fontsize=8.3)
    ax.grid(axis="y", color="#eef2f6", lw=.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def chart_total():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = list(range(len(DAYS)))
    ax.plot(xs, [x / 1e4 for x in tot_series], color="#1268D3", lw=2.0, label="전체 광고")
    ax.plot(xs, [x / 1e4 for x in conv_series], color="#0e9f6e", lw=1.8, ls="--", label="물건 환산(동일주소묶음)")
    ax.bar(xs, [x / 1e4 for x in new_series], 0.86, color="#f0b429", alpha=.85, label="신규 포착(당일)")
    _ticks(ax)
    ax.set_ylabel("만 건", fontsize=9)
    ax.legend(ncol=3, fontsize=8.4, frameon=False, loc="center left")
    fig.suptitle("전체 광고 · 물건 환산 · 신규 포착 — 일별 (2026.6.16 ~ 9.3)", fontsize=11.5,
                 fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(C_TOT, bbox_inches="tight")
    print("chart:", C_TOT)


def chart_sido():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = list(range(len(DAYS)))
    series = [("gg", "경기", "#1268D3"), ("seoul", "서울", "#5b86bd"), ("ic", "인천", "#a9bed6"),
              ("bs", "부산", "#d9a5a5")]
    bottom = [0.0] * len(DAYS)
    for k, name, col in series:
        ys = [_i(SIDO[d], k) / 1e4 for d in DAYS]
        ax.bar(xs, ys, 0.86, bottom=bottom, color=col, label=name, linewidth=0)
        bottom = [b + y for b, y in zip(bottom, ys)]
    others = [(_i(SIDO[d], "dg") + _i(SIDO[d], "dj") + _i(SIDO[d], "gj") + _i(SIDO[d], "us")
               + _i(SIDO[d], "sj") + _i(SIDO[d], "etc")) / 1e4 for d in DAYS]
    ax.bar(xs, others, 0.86, bottom=bottom, color="#e6dcc9", label="그 외", linewidth=0)
    _ticks(ax)
    ax.set_ylabel("만 건", fontsize=9)
    ax.legend(ncol=5, fontsize=8.4, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("시도별 전체 광고 — 일별 (2026.6.16 ~ 9.3)", fontsize=11.5, fontweight="bold", y=1.10)
    fig.tight_layout()
    fig.savefig(C_SIDO, bbox_inches="tight")
    print("chart:", C_SIDO)


def chart_band():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = list(range(len(DAYS)))
    colors = {"b_u5": ("5억 미만", "#dbe4ee"), "b_5_10": ("5~10억", "#a9bed6"),
              "b_10_20": ("10~20억", "#7aa3cf"), "b_20_30": ("20~30억", "#5b86bd"),
              "b_30p": ("30억 이상", "#d64545")}
    bottom = [0.0] * len(DAYS)
    for k, (name, col) in colors.items():
        ys = [_i(N[d], k) / 1e4 for d in DAYS]
        ax.bar(xs, ys, 0.86, bottom=bottom, color=col, label=name, linewidth=0)
        bottom = [b + y for b, y in zip(bottom, ys)]
    _ticks(ax)
    ax.set_ylabel("만 건", fontsize=9)
    ax.legend(ncol=5, fontsize=8.4, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("매매 광고 가격대 구성 — 일별 (2026.6.16 ~ 9.3)", fontsize=11.5, fontweight="bold", y=1.10)
    fig.tight_layout()
    fig.savefig(C_BAND, bbox_inches="tight")
    print("chart:", C_BAND)


def make_docx(out: Path):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "맑은 고딕"
    st.font.size = Pt(10.5)
    st.paragraph_format.line_spacing = 1.45
    st.paragraph_format.space_after = Pt(10)
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
                for rr in pp.runs:
                    rr.font.size = Pt(9)
    for img in (C_TOT, C_SIDO, C_BAND):
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
            c.paragraphs[0].add_run(x).bold = True
        for row in rows:
            for c, x in zip(tb.add_row().cells, row):
                c.paragraphs[0].add_run(str(x))
        for rowx in tb.rows:
            for c in rowx.cells:
                for pp in c.paragraphs:
                    pp.paragraph_format.space_after = Pt(0)
                    pp.paragraph_format.line_spacing = 1.0
                    for rr in pp.runs:
                        rr.font.size = Pt(6.6)
    big_table("■ 표1 — 일별 종합: 거래유형·신규·물건 환산·매매 가격대 (단위: 건)", T1_HEADS, t1_rows())
    big_table("■ 표2 — 시도별 전체 광고 일별 (단위: 건)", T2_HEADS, t2_rows())
    m = d.add_paragraph(); r = m.add_run(NOTE)
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    d.save(out)
    print("docx:", out)


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
    blue = colors.Color(*BLUE)
    gray = colors.Color(0.39, 0.45, 0.55)
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
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=13 * mm, rightMargin=13 * mm,
                            topMargin=13 * mm, bottomMargin=13 * mm)

    def img(pth):
        w, h = PImage.open(pth).size
        cw = 184 * mm
        return RLImage(str(pth), width=cw, height=cw * h / w)
    sum_tbl = Table([[Paragraph(k, ss["sumk"]), Paragraph(v, ss["sumv"])] for k, v in SUMMARY],
                    colWidths=[26 * mm, 158 * mm])
    sum_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.88, 0.92)),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.955, 0.97, 0.99)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    def data_table(heads, rows, widths):
        t = Table([heads] + rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "PB", 6.6),
            ("FONT", (0, 1), (-1, -1), "P", 6.6),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.91, 0.945, 0.988)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.85, 0.88, 0.92)),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.975, 0.982, 0.99)]),
        ]))
        return t
    story = [
        Paragraph(DOCTYPE, ss["tag"]),
        Paragraph(TITLE, ss["title"]),
        Paragraph(SUBTITLE, ss["sub"]),
        Paragraph("■ 요약", ss["head"]), sum_tbl, Spacer(1, 4 * mm),
        img(C_TOT), Spacer(1, 2 * mm),
        img(C_SIDO), Spacer(1, 2 * mm),
        img(C_BAND), Spacer(1, 3 * mm),
    ]
    for head, body in BODY:
        story.append(Paragraph("■ " + head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph("■ 표1 — 일별 종합: 거래유형·신규·물건 환산·매매 가격대 (단위: 건)", ss["head"]))
    story.append(data_table(T1_HEADS, t1_rows(), [13 * mm] + [15.6 * mm] * 11))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("■ 표2 — 시도별 전체 광고 일별 (단위: 건)", ss["head"]))
    story.append(data_table(T2_HEADS, t2_rows(), [13 * mm] + [17.1 * mm] * 10))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story)
    print("pdf:", out)


if __name__ == "__main__":
    chart_total()
    chart_sido()
    chart_band()
    make_docx(HERE / "시장전체_일별전수보고서.docx")
    make_pdf(HERE / "시장전체_일별전수보고서.pdf")
