# -*- coding: utf-8 -*-
"""매도인 자금 제공(주인대출) 매물 광고 — 2026년 9월 현황 보고서.

기자 문의(월별 건수·평균 호가·상위 지역·전체 매물 대비 비중·일별 시계열) 대응.
수치는 전부 일별상세_0928/sf_daily.json 에서 동적 산출한다 — 갱신 시 데이터만 교체.
산출: 매도인자금제공_분석보고서_20260928.docx / .pdf + data/sf4_*.png
원칙: 의견 없이 집계 사실만. 정의·결측·관측 한계를 본문에 명기.
"""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
DD = HERE / "일별상세_0928"
C_TREND = DATA / "sf4_trend.png"
C_REGION = DATA / "sf4_region.png"
C_BAND = DATA / "sf4_band.png"
BLUE = (0x12 / 255, 0x68 / 255, 0xD3 / 255)

S = json.load(open(DD / "sf_daily.json"))
DAYS, DAILY, DEN = S["days"], S["daily"], S["den"]
LBL = [d[5:] for d in DAYS]
BANDS = ["5억 미만", "5~10억", "10~20억", "20~30억", "30억 이상"]
BAND_SHORT = ["5억↓", "5~10", "10~20", "20~30", "30억↑"]
LAST = DAYS[-1]
X = DAILY[LAST]


def KDATE(d):
    y, m, dd = d.split("-")
    return "%s년 %d월 %d일" % (y, int(m), int(dd))


def f(n, d=0):
    return format(round(n, d) if d else int(round(n)), ",.%df" % d)


def month(m):
    return [d for d in DAYS if d.startswith(m)]


def mstat(m):
    ds = month(m)
    tots = [DAILY[d]["tot"] for d in ds]
    dens = [DAILY[d]["den"] for d in ds]
    avgs = [DAILY[d]["avg"] for d in ds if DAILY[d]["avg"]]
    return dict(n=len(ds), mean=sum(tots) / len(tots), lo=min(tots), hi=max(tots),
                last=tots[-1], share=sum(tots) / sum(dens) * 100,
                price=statistics.mean(avgs) if avgs else 0)


M6, M7, M8, M9 = (mstat(m) for m in ("2026-06", "2026-07", "2026-08", "2026-09"))
SIDO_SORT = sorted(X["sido"].items(), key=lambda t: -t[1])
SGG_SORT = sorted(X["sgg"].items(), key=lambda t: -t[1])
MKT = DEN[LAST]["bands"]
MKT_TOT = sum(MKT)
NEW_TOT = sum(DAILY[d]["new"] or 0 for d in DAYS)
UNIQ = S["uniq"]   # 한 번이라도 나타난 고유 광고 수(신규 합계보다 큼)

DOCTYPE = "데이터 분석 보고서 (취재 참고자료)"
TITLE = "매도인 자금 제공 매물 광고 — 2026년 9월 현황과 일별 전수 데이터"
SUBTITLE = ("전국 아파트·오피스텔 매매 광고 설명 문구 전수 분석 · "
            "2026년 6월 16일 ~ 9월 28일(관측 %d개 일자) · 일자별 전체 수치를 본문 표로 수록" % len(DAYS))

SUMMARY = [
    ("분석 대상",
     "매매 광고 설명 문구에서 매도인이 매수인에게 자금을 대준다고 밝힌 광고"
     "(‘집주인 대출 가능’, ‘매도인 근저당 가능’ 등)"),
    ("지표의 성격",
     "매도인이 매수인에게 자금을 대주는 방식 자체는 이전에도 간간이 쓰이던 거래 방법입니다. "
     "이 지표가 측정하는 것은 그 방법이 얼마나 쓰였는지가 아니라, 얼마나 광고에 드러났는지입니다"),
    ("최근 게재 광고",
     "%s 기준 %s건. 9월 하루 평균 %s건(최소 %s · 최대 %s)"
     % (KDATE(LAST), f(X["tot"]),
        f(M9["mean"], 1), f(M9["lo"]), f(M9["hi"]))),
    ("7월 대비",
     "7월 하루 평균 %s건 → 9월 하루 평균 %s건(%.1f배). 6월 중순 하루 %s건 수준에서 "
     "7월 하순부터 늘기 시작했습니다"
     % (f(M7["mean"], 1), f(M9["mean"], 1), M9["mean"] / M7["mean"], f(M6["mean"], 1))),
    ("전체 매물 대비",
     "%s 매매 광고 %s건 중 %s건 — 전체의 %.4f%%(매매 광고 1만 건당 %.1f건)"
     % (KDATE(LAST), f(X["den"]), f(X["tot"]), X["tot"] / X["den"] * 100, X["tot"] / X["den"] * 10000)),
    ("호가",
     "평균 %.1f억원 · 중앙값 %.1f억원. 30억원 이상이 %.1f%%로 매매 광고 전체(%.1f%%)의 %.1f배"
     % (X["avg"], X["med"], X["band"].get("30억 이상", 0) / X["tot"] * 100,
        MKT[4] / MKT_TOT * 100,
        (X["band"].get("30억 이상", 0) / X["tot"]) / (MKT[4] / MKT_TOT))),
    ("지역",
     "%s. 시군구는 %s 순"
     % (" · ".join("%s %s건(%.1f%%)" % (k, f(v), v / X["tot"] * 100) for k, v in SIDO_SORT[:3]),
        " · ".join(k for k, _ in SGG_SORT[:5]))),
    ("물건 수",
     "같은 (단지·면적형·호가)를 한 물건으로 본 근사치 %s건 — 광고 %s건의 %.0f%%"
     % (f(X["itemsA"]), f(X["tot"]), X["itemsA"] / X["tot"] * 100)),
    ("유의 사항",
     "광고 문구 집계이며 등기부상 실제 근저당 설정 건수가 아닙니다. 광고 건수는 물건 수와 다릅니다"),
]

BODY = [
    ("1. 집계 정의와 분류 기준",
     "‘게재 광고’는 각 일자 수집 스냅샷에서 그날 게재 중이던 해당 조건(매도인 자금 제공) 광고 "
     "수입니다. 광고 설명 문구에서 주체어(매도인·매도자·집주인·주인·소유자)와 자금어(대출·융자·"
     "근저당·담보·대여)가 인접해 나타난 광고를 후보로 뽑은 뒤, ①‘대출 없음·무융자·근저당 없이’처럼 "
     "담보가 없다는 반대 표기, ②‘대출 승계’처럼 기존 대출을 넘겨받는다는 표기, ③‘주인세대여서’의 "
     "‘대여’처럼 우연히 글자가 겹친 경우를 제외했습니다. ‘신규 포착 광고’는 그날 처음 관측된 "
     "광고번호의 수입니다. ‘중복 제거 물건 수’는 같은 단지·면적형·호가 조합을 한 물건으로 본 "
     "근사치로, 같은 물건을 여러 중개사가 중복 광고하는 효과를 제거한 값입니다(등기부 기준의 물건 "
     "식별은 아닙니다). 수집이 표기일 새벽에 완료되므로 각 일자의 신규 포착분은 실제로는 대부분 "
     "그 전날 등록된 광고입니다."),
    ("2. 배경 — 이 수치가 측정하는 것",
     "매도인이 매수인에게 자금을 대주는 방식(매도인 근저당 설정 등)은 이전에도 간간이 쓰이던 "
     "거래 방법입니다. 다만 매도인과 매수인이 계약 조건을 조율하는 과정에서 제안되던 조건이어서, "
     "매물 광고에 대놓고 내거는 경우는 드물었습니다. 7월 이후로는 이 조건을 굳이 숨길 필요가 "
     "없다고 본 매도인과 중개사가 매물 등록 단계에서 이를 명시하는 사례가 늘고 있습니다. "
     "따라서 이 보고서의 수치는 해당 거래 방법이 얼마나 쓰였는지가 아니라, 얼마나 광고에 "
     "드러났는지를 측정한 것입니다. 증가분에는 거래 방법 자체가 늘어난 부분과, 이전부터 있었으나 "
     "광고에 적히지 않던 것이 표면으로 드러난 부분이 함께 들어 있으며, 광고 문구만으로는 둘을 "
     "나눌 수 없습니다."),
    ("3. 월별 추이 — 7월과 9월의 차이",
     "6월 16일 관측을 시작한 시점에는 하루 %s건 수준이었습니다. 7월은 하루 평균 %s건이지만 "
     "월 안에서 편차가 커서, 7월 22일까지 하루 2~6건이던 것이 7월 하순부터 늘어 7월 31일 %s건이 "
     "됐습니다. 8월은 하루 평균 %s건(최소 %s · 최대 %s), 9월은 하루 평균 %s건(최소 %s · 최대 %s)"
     "입니다. 9월 하루 평균은 7월 하루 평균의 %.1f배입니다."
     % (f(M6["mean"], 1), f(M7["mean"], 1), f(M7["last"]), f(M8["mean"], 1), f(M8["lo"]), f(M8["hi"]),
        f(M9["mean"], 1), f(M9["lo"]), f(M9["hi"]), M9["mean"] / M7["mean"])
     + " 8월 16일 이후로는 하루 %s~%s건 구간에서 오르내리고 있습니다."
     % (f(min(DAILY[d]["tot"] for d in DAYS if d >= "2026-08-16")),
        f(max(DAILY[d]["tot"] for d in DAYS if d >= "2026-08-16")))),
    ("4. 신규 포착과 물건 수",
     "관측 기간에 한 번이라도 나타난 해당 조건 광고는 고유 광고번호 기준 %s건입니다. 일별 "
     "‘신규 포착’ 열의 합계는 %s건으로 이보다 적은데, 첫 관측일과 결측·제외 직후 일자는 값을 "
     "내지 않았기 때문입니다. 게재 광고 수가 %s~%s건 구간에서 유지되는 "
     "동안에도 신규 광고가 계속 포착되고 있는데, 이는 같은 폭으로 기존 광고가 내려가고 있다는 "
     "뜻이기도 합니다. %s 기준 중복 제거 물건 수는 %s건으로 광고 수(%s건)의 %.0f%% "
     "수준이며, 동일 주소 묶음으로 환산하면 %s건입니다. 실제 물건 수는 두 기준 사이로 보시면 "
     "됩니다."
     % (f(UNIQ), f(NEW_TOT), f(min(DAILY[d]["tot"] for d in DAYS if d >= "2026-08-16")),
        f(max(DAILY[d]["tot"] for d in DAYS if d >= "2026-08-16")),
        KDATE(LAST), f(X["itemsA"]), f(X["tot"]), X["itemsA"] / X["tot"] * 100, f(X["itemsB"], 1))),
    ("5. 지역 분포",
     "%s 기준 %s입니다. 시군구 단위로는 %s입니다. 관측 기간 전체 누적으로도 서울 강남 3구와 "
     "성동구, 경기 성남 분당구가 상위에 있으며, 상위 시군구의 일별 수치는 표2에 실었습니다."
     % (KDATE(LAST),
        " · ".join("%s %s건(전체의 %.1f%%)" % (k, f(v), v / X["tot"] * 100) for k, v in SIDO_SORT[:4]),
        " · ".join("%s %s건" % (k, f(v)) for k, v in SGG_SORT[:6]))),
    ("6. 호가 수준",
     "%s 기준 해당 광고의 평균 호가는 %.1f억원, 중앙값은 %.1f억원입니다. 가격대별로는 %s입니다. "
     "같은 날 전국 아파트·오피스텔 매매 광고 전체의 가격대 분포는 %s로, 5억원 미만이 "
     "%.1f%%를 차지합니다. 30억원 이상 비중은 해당 광고가 %.1f%%로 시장 전체(%.1f%%)의 %.1f배입니다."
     % (KDATE(LAST), X["avg"], X["med"],
        " · ".join("%s %s건(%.1f%%)" % (b, f(X["band"].get(b, 0)), X["band"].get(b, 0) / X["tot"] * 100)
                   for b in BANDS),
        " · ".join("%s %.1f%%" % (b, v / MKT_TOT * 100) for b, v in zip(BANDS, MKT)),
        MKT[0] / MKT_TOT * 100,
        X["band"].get("30억 이상", 0) / X["tot"] * 100, MKT[4] / MKT_TOT * 100,
        (X["band"].get("30억 이상", 0) / X["tot"]) / (MKT[4] / MKT_TOT))),
    ("7. 전체 매물 대비 비중",
     "%s 기준 전국 아파트·오피스텔 매매 광고는 %s건이고 그중 해당 광고는 %s건으로 %.4f%%입니다. "
     "매매 광고 1만 건당 %.1f건에 해당합니다. 7월 한 달 평균은 %.4f%%, 8월은 %.4f%%, 9월은 "
     "%.4f%%였습니다. 절대 건수가 적은 만큼 비중 자체는 낮지만, 7월 대비 9월 비중은 %.1f배입니다."
     % (KDATE(LAST), f(X["den"]), f(X["tot"]), X["tot"] / X["den"] * 100, X["tot"] / X["den"] * 10000,
        M7["share"], M8["share"], M9["share"], M9["share"] / M7["share"])),
    ("8. 관측 기간과 결측",
     "%s"),
    ("9. 유의 사항",
     "광고 문구 기준 집계로 등기부상 실제 근저당 설정 건수와는 다르며, 2장에 적은 대로 해당 거래 방법의 실제 사용 건수와도 다릅니다. 신규 포착·물건 수는 위 "
     "정의에 따른 근사치입니다. 광고는 수시로 등록·삭제되므로 열람 시점에 따라 수치가 달라질 "
     "수 있습니다."),
]

NOTE = (
    "작성 | 콕집(koczip.com) CTO 황인찬 · runtoonline@gmail.com  "
    "모든 수치는 저희가 자체 구축한 DB에서 집계했습니다(각 일자 수집 스냅샷 기준). 수치 정의는 "
    "본문 1장과 같습니다. 다른 구간·다른 조건의 집계가 필요하시면 언제든 요청해 주시기 바랍니다."
)

T1_HEADS = ["날짜", "게재", "신규", "물건", "평균호가", "서울", "경기", "그 외"] + BAND_SHORT
T2_HEADS = None


def missing_days():
    import datetime
    have = set(DAYS)
    d = datetime.date.fromisoformat(DAYS[0])
    end = datetime.date.fromisoformat(DAYS[-1])
    out = []
    while d <= end:
        if d.isoformat() not in have:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def t1_rows():
    out = []
    for d in DAYS:
        x = DAILY[d]
        etc = x["tot"] - x["sido"].get("서울", 0) - x["sido"].get("경기", 0)
        out.append([d[5:], f(x["tot"]), f(x["new"]) if x["new"] is not None else "—",
                    f(x["itemsA"]), "%.1f" % x["avg"],
                    f(x["sido"].get("서울", 0)), f(x["sido"].get("경기", 0)), f(etc)]
                   + [f(x["band"].get(b, 0)) for b in BANDS])
    return out


TOP_SGG = [k for k, _ in sorted(
    {k: sum(DAILY[d]["sgg"].get(k, 0) for d in DAYS)
     for d in DAYS for k in DAILY[d]["sgg"]}.items(), key=lambda t: -t[1])[:12]]
SGG_SHORT = [k.split(" ", 1)[1].replace("시 ", "").replace("구", "") if " " in k else k for k in TOP_SGG]


def t2_rows():
    out = []
    for d in DAYS:
        s = DAILY[d]["sgg"]
        picked = [s.get(k, 0) for k in TOP_SGG]
        out.append([d[5:]] + [f(v) for v in picked] + [f(sum(s.values()) - sum(picked))])
    return out


# ── 차트 ─────────────────────────────────────────────────────
def _font():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    import matplotlib.pyplot as plt
    for fn in ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf"):
        font_manager.fontManager.addfont(str(FONTS / fn))
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


def chart_trend():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = list(range(len(DAYS)))
    ax.plot(xs, [DAILY[d]["tot"] for d in DAYS], color="#1268D3", lw=2.0, label="게재 광고")
    ax.plot(xs, [DAILY[d]["itemsA"] for d in DAYS], color="#0e9f6e", lw=1.8, ls="--",
            label="중복 제거 물건 수(단지·면적·호가 기준)")
    ax.bar(xs, [DAILY[d]["new"] or 0 for d in DAYS], .86, color="#f0b429", alpha=.85,
           label="신규 포착 광고(당일)")
    _ticks(ax)
    ax.legend(ncol=3, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("건", fontsize=9)
    fig.suptitle("게재 광고 · 신규 포착 · 중복 제거 물건 수 — 일별 (2026.6.16 ~ 9.28)",
                 fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_TREND, bbox_inches="tight"); print("chart:", C_TREND)


def chart_region():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = list(range(len(DAYS)))
    bottom = [0.0] * len(DAYS)
    for name, col in (("서울", "#1268D3"), ("경기", "#7aa3cf"), ("인천", "#c3d3e6")):
        ys = [DAILY[d]["sido"].get(name, 0) for d in DAYS]
        ax.bar(xs, ys, .86, bottom=bottom, color=col, label=name, linewidth=0)
        bottom = [b + y for b, y in zip(bottom, ys)]
    etc = [DAILY[d]["tot"] - b for d, b in zip(DAYS, bottom)]
    ax.bar(xs, etc, .86, bottom=bottom, color="#e6d3c3", label="그 외", linewidth=0)
    _ticks(ax)
    ax.legend(ncol=4, fontsize=8.6, frameon=False, loc="upper left")
    ax.set_ylabel("광고 수(건)", fontsize=9)
    fig.suptitle("지역별 일별 추이 — 게재 광고 (2026.6.16 ~ 9.28)",
                 fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_REGION, bbox_inches="tight"); print("chart:", C_REGION)


def chart_band():
    plt = _font()
    fig, ax = plt.subplots(figsize=(10.4, 3.2), dpi=200)
    xs = list(range(len(DAYS)))
    cols = {"5억 미만": "#dbe4ee", "5~10억": "#a9bed6", "10~20억": "#7aa3cf",
            "20~30억": "#5b86bd", "30억 이상": "#d64545"}
    bottom = [0.0] * len(DAYS)
    for name, col in cols.items():
        ys = [DAILY[d]["band"].get(name, 0) for d in DAYS]
        ax.bar(xs, ys, .86, bottom=bottom, color=col, label=name, linewidth=0)
        bottom = [b + y for b, y in zip(bottom, ys)]
    _ticks(ax)
    ax.legend(ncol=5, fontsize=8.4, frameon=False, loc="upper left")
    ax.set_ylabel("광고 수(건)", fontsize=9)
    fig.suptitle("가격대별 일별 추이 — 게재 광고 (2026.6.16 ~ 9.28)",
                 fontsize=11.5, fontweight="bold", y=1.0)
    fig.tight_layout(); fig.savefig(C_BAND, bbox_inches="tight"); print("chart:", C_BAND)


# ── 문서 ─────────────────────────────────────────────────────
def body_filled(miss_text):
    return [(h, (b % miss_text) if "%s" == b else b) for h, b in BODY]


def make_docx(out: Path, body):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "맑은 고딕"; st.font.size = Pt(10.5)
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
                for rr in pp.runs:
                    rr.font.size = Pt(9)
    for img in (C_TREND, C_REGION, C_BAND):
        ch = d.add_paragraph(); ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ch.add_run().add_picture(str(img), width=Cm(16.4))
    for head, txt in body:
        h = d.add_paragraph(); r = h.add_run("■ " + head); r.font.bold = True; r.font.size = Pt(11.5)
        h.paragraph_format.space_before = Pt(8); h.paragraph_format.space_after = Pt(4)
        d.add_paragraph(txt)

    def big(title, heads, rows):
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

    big("■ 표1 — 일별 종합: 게재·신규·물건·평균호가 / 지역 / 가격대 (단위: 건, 호가 억원)",
        T1_HEADS, t1_rows())
    big("■ 표2 — 시군구 상위 12곳 일별 (단위: 건)", ["날짜"] + SGG_SHORT + ["그 외"], t2_rows())
    m = d.add_paragraph(); r = m.add_run(NOTE)
    r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    d.save(out); print("docx:", out)


def make_pdf(out: Path, body):
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
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
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
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))

    def dt(heads, rows, widths):
        t = Table([heads] + rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "PB", 6.6), ("FONT", (0, 1), (-1, -1), "P", 6.6),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.91, 0.945, 0.988)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.85, 0.88, 0.92)),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.975, 0.982, 0.99)])]))
        return t

    story = [Paragraph(DOCTYPE, ss["tag"]), Paragraph(TITLE, ss["title"]),
             Paragraph(SUBTITLE, ss["sub"]), Paragraph("■ 요약", ss["head"]), sum_tbl,
             Spacer(1, 4 * mm), img(C_TREND), Spacer(1, 2 * mm), img(C_REGION),
             Spacer(1, 2 * mm), img(C_BAND), Spacer(1, 3 * mm)]
    for head, txt in body:
        story.append(Paragraph("■ " + head, ss["head"]))
        story.append(Paragraph(txt, ss["body"]))
    story.append(Paragraph("■ 표1 — 일별 종합: 게재·신규·물건·평균호가 / 지역 / 가격대 (단위: 건, 호가 억원)", ss["head"]))
    story.append(dt(T1_HEADS, t1_rows(), [13 * mm] + [11.6 * mm] * 4 + [11.6 * mm] * 3 + [11.6 * mm] * 5))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("■ 표2 — 시군구 상위 12곳 일별 (단위: 건)", ss["head"]))
    story.append(dt(["날짜"] + SGG_SHORT + ["그 외"], t2_rows(), [14 * mm] + [12.9 * mm] * 13))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(NOTE, ss["note"]))
    doc.build(story); print("pdf:", out)


if __name__ == "__main__":
    CHUSEOK = ["2026-09-24", "2026-09-25", "2026-09-26"]
    miss = [m for m in missing_days() if m not in CHUSEOK]

    def kd(m):
        return "%d월 %d일" % tuple(int(x) for x in m.split("-")[1:])
    mtxt = ("관측은 2026년 6월 16일 시작했습니다. 저희 매물 데이터베이스의 수집 개시일이 2026년 "
            "5월 18일이고 광고 설명 문구까지 일자별로 보존한 스냅샷은 6월 16일부터여서, 그 이전 "
            "시점(예: 2025년 9월)과의 비교는 제공해 드릴 수 없습니다. 네이버 부동산은 내려간 광고를 "
            "과거 시점으로 다시 조회할 수 없어 소급 수집도 불가능합니다. "
            "추석 연휴인 %s은 광고 등록·삭제가 사실상 멈추는 기간이어서 추세를 왜곡하지 않도록 "
            "집계에서 제외했습니다. 이와 별개로 %s은 수집 장애로 스냅샷이 없어 표에서 빠져 "
            "있습니다. 결측·제외 일자는 앞뒤 일자 수치에 영향을 주지 않으며, 다만 바로 앞 관측일이 "
            "전날이 아닌 일자는 ‘신규 포착’이 여러 날치를 한꺼번에 잡게 되므로 값을 내지 않고 "
            "‘—’로 두었습니다."
            % (" · ".join(kd(m) for m in CHUSEOK), ", ".join(kd(m) for m in miss)))
    body = [(h, mtxt if b == "%s" else b) for h, b in BODY]
    chart_trend(); chart_region(); chart_band()
    make_docx(HERE / "매도인자금제공_분석보고서_20260928.docx", body)
    make_pdf(HERE / "매도인자금제공_분석보고서_20260928.pdf", body)
