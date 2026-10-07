# -*- coding: utf-8 -*-
"""매도인 자금 제공 매물 광고 — 일별 상세 데이터 보고서(독립 보도자료 · 2026-09-07 발행).

기자 요청(지역별·가격대별 일별 추이 / 중복 제거 물건 수) 대응.
엑셀 미배포 방침 — 일별 전체 수치를 본문 표로 전부 수록한다.
산출: 매도인자금제공_일별상세보고서.docx / .pdf + data/sf2_daily_*.png
원칙: 의견 없이 집계 사실만. 정의(물건 근사)는 본문에 명기.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = Path("/Users/hcode/auto/naverreal/design/fonts")
DATA = HERE.parent / "data"
DD = HERE / "일별상세"
C_REGION = DATA / "sf2_daily_region.png"
C_BAND = DATA / "sf2_daily_band.png"
C_NEW = DATA / "sf2_daily_new.png"
BLUE = (0x12 / 255, 0x68 / 255, 0xD3 / 255)

ST = json.load(open(DD / "sf_daily_detail.json"))
DAYS = ST["days"]
LBL = [d[5:] for d in DAYS]

DOCTYPE = "데이터 분석 보고서 (취재 참고자료)"
TITLE = "매도인 자금 제공 매물 광고 일별 전수 데이터 — 지역·가격대·물건 수"
SUBTITLE = ("전국 아파트·오피스텔 매매 광고 설명 문구 일별 전수 분석 · 2026년 6월 16일 ~ 9월 7일(83개 일자) · "
            "일자별 전체 수치를 본문 표로 수록")

SUMMARY = [
    ("분석 대상", "매매 광고 설명 문구에서 매도인이 매수인에게 자금을 대준다고 밝힌 광고(‘집주인 대출 가능’, ‘매도인 근저당 가능’ 등)"),
    ("게재 광고", "7월 22일까지 하루 2~6건 → 7월 23일부터 증가 → 8월 19일 이후 250건 안팎(9월 7일 261건)"),
    ("물건 수", "같은 (단지·면적형·호가)를 한 물건으로 본 근사치 — 9월 7일 151건(광고 261건), 8월 이후 물건당 광고 1.7~2.0배"),
    ("수록 표", "표1 일별 종합(전체·물건·지역·가격대) · 표2 시군구 상위 12곳 일별 — 83개 일자 전체 수치"),
    ("유의 사항", "광고 문구 집계이며 등기부상 실제 근저당 설정 건수가 아닙니다. 광고 건수는 물건 수와 다릅니다"),
]

BODY = [
    ("1. 집계 정의",
     "‘게재 광고’는 각 일자 수집 스냅샷에서 그날 게재 중이던 해당 조건(매도인 자금 제공) 광고 수입니다. "
     "‘중복 제거 물건 수’는 같은 단지·면적형·호가 "
     "조합을 한 물건으로 본 근사치로, 같은 물건을 여러 중개사가 중복 광고하는 효과를 제거한 "
     "값입니다(등기부 기준의 물건 식별은 아닙니다). 6월 28일 스냅샷은 수집 결측으로 제외돼 "
     "있습니다. 추출·분류 기준(주체어와 자금어의 인접 표기, 무융자 등 반대 표기·대출승계·무관 "
     "결합 제외)은 같은 날짜의 분석 보고서와 동일합니다."),
    ("2. 일별 추이 — 광고·물건",
     "게재 광고는 7월 22일까지 하루 2~6건에서 7월 23일 16건으로 늘기 시작해 8월 19일 이후 "
     "250건 안팎을 유지하고 있습니다(9월 7일 261건). 중복 제거 물건 수는 9월 7일 "
     "151건으로 광고 수(261건)의 58% 수준이며, 광고가 크게 늘어난 8월 이후 물건 1건당 "
     "광고 수는 1.7~2.0배 사이에서 유지되고 있습니다."),
    ("3. 지역별 일별 추이",
     "증가 초기(7월 말)부터 서울이 대부분을 차지했고, 8월 중순부터 경기가 하루 40~60건대로 "
     "늘었습니다. 9월 7일 기준 서울 188건, 경기 62건, 그 외(부산·대구·인천·충북 등) 11건입니다. "
     "시군구 단위로는 관측 기간 합계 기준 송파·서초·강남·성동·성남 분당 순이며, 상위 12개 "
     "시군구의 일별 수치를 표2에 실었습니다(이 12곳이 전체의 74%)."),
    ("4. 가격대별 일별 추이",
     "증가 초기에는 20억원 이상 위주였으나, 8월 들어 10~20억원대가 늘며 9월 7일에는 10~20억원 "
     "88건, 20~30억원 54건, 30억원 이상 98건, 10억원 미만 21건의 분포가 됐습니다. 일자별 "
     "구간 수치는 표1에 있습니다."),
    ("5. 유의 사항",
     "광고 문구 기준 집계로 등기부상 실제 근저당 설정과는 다릅니다. 물건 수는 위 "
     "정의에 따른 근사치입니다. 광고는 수시로 등록·삭제되므로 열람 시점에 따라 수치가 달라질 "
     "수 있습니다."),
]

NOTE = (
    "작성 | 콕집(koczip.com) 데이터팀 · 황인찬 · runtoonline@gmail.com · 010-5942-8014  ※ 본 집계는 2026년 9월 7일 최신 수집 데이터를 기준으로 재산정한 값입니다. 관측 기간 중간의 수집 스냅샷이 보강되면서, 앞서 배포된 잠정치와는 게재 광고·물건 수 등 일부 수치가 소폭 조정되었습니다. "
    "모든 수치는 저희가 자체 구축한 DB에서 집계했습니다(각 일자 수집 스냅샷 기준). 수치 정의는 "
    "본문 1장과 같습니다. 다른 구간·다른 조건의 집계가 필요하시면 언제든 요청해 주시기 바랍니다."
)

# ── 표 데이터 로드 ──────────────────────────────────────────────
def _read(fp):
    return list(csv.reader(open(DD / fp)))

SIDO_ROWS = {r[0]: r[1:] for r in _read("일별_지역별.csv")[1:]}
BAND_ROWS = {r[0]: r[1:] for r in _read("일별_가격대별.csv")[1:]}
SUM_ROWS = {r[0]: r[1:] for r in _read("일별요약.csv")[1:]}

TOP_SGG = ["서울 송파구", "서울 서초구", "서울 강남구", "서울 성동구", "경기 성남시 분당구",
           "서울 동대문구", "서울 마포구", "서울 용산구", "경기 과천시", "서울 영등포구",
           "경기 남양주시", "경기 용인시 수지구"]
SGG_SHORT = ["송파", "서초", "강남", "성동", "분당", "동대문", "마포", "용산", "과천", "영등포", "남양주", "용인수지"]
_sgg_raw = _read("일별_시군구별.csv")
_sgg_head = _sgg_raw[0][1:]
_sgg_idx = [_sgg_head.index(n) for n in TOP_SGG]
SGG_ROWS = {}
for r in _sgg_raw[1:]:
    vals = r[1:]
    picked = [vals[i] for i in _sgg_idx]
    rest = sum(int(v) for v in vals) - sum(int(v) for v in picked)
    SGG_ROWS[r[0]] = picked + [str(rest)]

# 표1: 날짜 | 전체 | 물건 | 서울 경기 인천 그외 | 5개 밴드  (11열)
T1_HEADS = ["날짜", "게재", "물건", "서울", "경기", "인천", "그 외",
            "5억↓", "5~10", "10~20", "20~30", "30억↑"]


def t1_rows():
    out = []
    for d in DAYS:
        s = SUM_ROWS[d]                       # 전체, 신규, 물건
        sido = SIDO_ROWS[d]                   # 서울 경기 인천 부산 대구 충북 그외
        etc = sum(int(x) for x in sido[3:])
        band = BAND_ROWS[d]
        out.append([d[5:], s[0], s[2], sido[0], sido[1], sido[2], str(etc)] + band)
    return out


T2_HEADS = ["날짜"] + SGG_SHORT + ["그 외"]


def t2_rows():
    return [[d[5:]] + SGG_ROWS[d] for d in DAYS]


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


def chart_region():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.3), dpi=200)
    series = [("서울", "#1268D3"), ("경기", "#7aa3cf"), ("인천", "#c3d3e6")]
    others = [sum(ST["sido_series"][s][i] for s in ST["sido_series"]
                  if s not in ("서울", "경기", "인천")) for i in range(len(DAYS))]
    bottom = [0.0] * len(DAYS)
    xs = list(range(len(DAYS)))
    for name, col in series:
        ys = ST["sido_series"][name]
        ax.bar(xs, ys, 0.86, bottom=bottom, color=col, label=name, linewidth=0)
        bottom = [b + y for b, y in zip(bottom, ys)]
    ax.bar(xs, others, 0.86, bottom=bottom, color="#e6d3c3", label="그 외", linewidth=0)
    _ticks(ax)
    ax.legend(ncol=4, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("광고 수(건)", fontsize=9)
    fig.suptitle("지역별 일별 추이 — 게재 광고(해당 조건) (2026.6.16 ~ 9.7)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(C_REGION, bbox_inches="tight")
    print("chart:", C_REGION)


def chart_band():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.3), dpi=200)
    colors = {"5억 미만": "#dbe4ee", "5~10억": "#a9bed6", "10~20억": "#7aa3cf",
              "20~30억": "#5b86bd", "30억 이상": "#d64545"}
    xs = list(range(len(DAYS)))
    bottom = [0.0] * len(DAYS)
    for name, col in colors.items():
        ys = ST["band_series"][name]
        ax.bar(xs, ys, 0.86, bottom=bottom, color=col, label=name, linewidth=0)
        bottom = [b + y for b, y in zip(bottom, ys)]
    _ticks(ax)
    ax.legend(ncol=5, fontsize=8.4, frameon=False, loc="upper left")
    ax.set_ylabel("광고 수(건)", fontsize=9)
    fig.suptitle("가격대별 일별 추이 — 게재 광고(해당 조건) (2026.6.16 ~ 9.7)", fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(C_BAND, bbox_inches="tight")
    print("chart:", C_BAND)


def chart_new():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.1), dpi=200)
    xs = list(range(len(DAYS)))
    tot = [ST["tot"][d] for d in DAYS]
    new = [ST["new"][d] for d in DAYS]
    items = [ST["items"][d] for d in DAYS]
    ax.plot(xs, tot, color="#1268D3", lw=2.0, label="게재 광고")
    ax.plot(xs, items, color="#0e9f6e", lw=1.8, ls="--", label="중복 제거 물건 수(단지·면적·호가 기준)")
    ax.bar(xs, new, 0.86, color="#f0b429", alpha=.85, label="신규 포착 광고(당일)")
    _ticks(ax)
    ax.legend(ncol=3, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("건", fontsize=9)
    fig.suptitle("게재 광고 · 신규 포착 · 중복 제거 물건 수 — 일별 (2026.6.16 ~ 9.7)",
                 fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig(C_NEW, bbox_inches="tight")
    print("chart:", C_NEW)


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
    for img in (C_REGION, C_BAND):
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
                        rr.font.size = Pt(7)

    big_table("■ 표1 — 일별 종합: 전체·물건 / 지역(시도) / 가격대 (단위: 건)", T1_HEADS, t1_rows())
    big_table("■ 표2 — 시군구 상위 12곳 일별 (단위: 건 · 12곳=전체의 74%)", T2_HEADS, t2_rows())
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
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=13 * mm, bottomMargin=13 * mm)

    def img(pth):
        w, h = PImage.open(pth).size
        cw = 182 * mm
        return RLImage(str(pth), width=cw, height=cw * h / w)
    sum_tbl = Table([[Paragraph(k, ss["sumk"]), Paragraph(v, ss["sumv"])] for k, v in SUMMARY],
                    colWidths=[26 * mm, 156 * mm])
    sum_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.88, 0.92)),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.955, 0.97, 0.99)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    def data_table(heads, rows, widths):
        t = Table([heads] + rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "PB", 6.8),
            ("FONT", (0, 1), (-1, -1), "P", 6.8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.91, 0.945, 0.988)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.85, 0.88, 0.92)),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.975, 0.982, 0.99)]),
        ]))
        return t

    story = [
        Paragraph(DOCTYPE, ss["tag"]),
        Paragraph(TITLE, ss["title"]),
        Paragraph(SUBTITLE, ss["sub"]),
        Paragraph("■ 요약", ss["head"]), sum_tbl, Spacer(1, 4 * mm),
        img(C_REGION), Spacer(1, 2 * mm),
        img(C_BAND), Spacer(1, 3 * mm),
    ]
    for head, body in BODY:
        story.append(Paragraph("■ " + head, ss["head"]))
        story.append(Paragraph(body, ss["body"]))
    story.append(Paragraph("■ 표1 — 일별 종합: 전체·물건 / 지역(시도) / 가격대 (단위: 건)", ss["head"]))
    w1 = [15 * mm] + [12.8 * mm] * 12
    story.append(data_table(T1_HEADS, t1_rows(), w1))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("■ 표2 — 시군구 상위 12곳 일별 (단위: 건 · 이 12곳이 전체의 74%)", ss["head"]))
    w2 = [15 * mm] + [12.6 * mm] * 13
    story.append(data_table(T2_HEADS, t2_rows(), w2))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story)
    print("pdf:", out)


if __name__ == "__main__":
    chart_region()
    chart_band()
    make_docx(HERE / "매도인자금제공_일별상세보고서.docx")
    make_pdf(HERE / "매도인자금제공_일별상세보고서.pdf")
