# -*- coding: utf-8 -*-
"""고가 재건축 단지 급매 보고서 (기자 배포용).

수치는 design/press/data/press_gm_*.csv 를 그대로 읽어 조판한다
(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
원천은 콕집 listings_current(매물 호가 전수)와 국토부 실거래(해제거래 제외).
Run: python3 design/press/급매/make_gm_report.py
  → design/press/급매/고가재건축단지_급매_보고서.pdf
"""
import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
OUT = HERE / "고가재건축단지_급매_보고서.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="PB", italic="P", boldItalic="PB")
pdfmetrics.registerFontFamily("PM", normal="PM", bold="PB", italic="PM", boldItalic="PB")

BLUE = colors.HexColor("#1268D3")
BLUE_DK = colors.HexColor("#0C4EA0")
ROWALT = colors.HexColor("#F2F6FC")
INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80")
LINE = colors.HexColor("#C9D6E5")
RED = colors.HexColor("#C0392B")
GREEN = colors.HexColor("#1F7A4D")
BOXBG = colors.HexColor("#F4F8FD")
HOTBG = colors.HexColor("#FDF3F2")
WARNBG = colors.HexColor("#FFF8EC")
WARNLN = colors.HexColor("#E0A85E")

ss = {
    "tag": ParagraphStyle("tag", fontName="PB", fontSize=10, textColor=BLUE, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="PX", fontSize=18.5, leading=25, textColor=INK,
                            spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="PS", fontSize=11.2, textColor=BLUE_DK, leading=17,
                          spaceAfter=10),
    "h": ParagraphStyle("h", fontName="PB", fontSize=12.5, textColor=INK, spaceBefore=12,
                        spaceAfter=5),
    "body": ParagraphStyle("body", fontName="P", fontSize=9.6, leading=15.5, textColor=INK,
                           spaceAfter=6),
    "lead": ParagraphStyle("lead", fontName="PM", fontSize=10.2, leading=17, textColor=INK,
                           spaceAfter=7),
    "small": ParagraphStyle("small", fontName="P", fontSize=8.2, leading=12.8, textColor=GRAY,
                            spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="P", fontSize=8, leading=12, textColor=GRAY,
                          spaceBefore=3, spaceAfter=10),
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.0, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white,
                         alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK,
                         alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=0),
    "tds": ParagraphStyle("tds", fontName="P", fontSize=7.6, leading=10, textColor=GRAY,
                          alignment=0),
}


def P(t, s="body"):
    return Paragraph(t, ss[s])


# 매물 원문에는 한자가 섞여 있는데 Pretendard 에 글리프가 없어 두부(▯)로 찍힌다.
# 뜻이 있는 글자는 우리말로 옮기고, 그 밖에 폰트에 없는 글자는 지운다.
_HANJA = {"急": "급", "賣": "매", "物": "물", "買": "매", "價": "가", "室": "실",
          "層": "층", "洞": "동", "南": "남", "東": "동", "西": "서", "北": "북"}
_HAVE = set(pdfmetrics.getFont("P").face.charToGlyph)


def clean(t):
    out = []
    for ch in t or "":
        ch = _HANJA.get(ch, ch)
        if ord(ch) in _HAVE or ord(ch) < 128:
            out.append(ch)
    return "".join(out).replace("  ", " ").strip()


def read(fn):
    with open(DATA / fn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hdr(cells):
    return [P(c, "th") for c in cells]


def box(html, bg=BOXBG, ln=LINE):
    t = Table([[P(html, "boxb")]], colWidths=[168 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("BOX", (0, 0), (-1, -1), 0.6, ln),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


CX = read("press_gm_complex.csv")
FL = read("press_gm_floor.csv")
CH = read("press_gm_cheap.csv")
QT = read("press_gm_quintile.csv")
SR = read("press_gm_series.csv")
RD = read("press_gm_reform_daily.csv")          # 발표 전후 일별(전국·시도·분위)
RF = read("press_gm_reform.csv")                # 발표 전후 요약
RT = read("press_gm_reform_target.csv")         # 대상 9개 평형 전후
M = {r["항목"]: r["값"] for r in read("press_gm_meta.csv")}

n = lambda v: f"{int(float(v)):,}"                                        # noqa: E731
eok = lambda v: f"{float(v) / 1e8:,.2f}억"                                # noqa: E731
eok1 = lambda v: f"{float(v) / 1e8:,.1f}억"                               # noqa: E731
sgn = lambda v: f"{float(v):+.1f}%".replace("+", "+").replace("-", "−")   # noqa: E731


def gap(r):  # noqa: D401
    """최저 호가가 중앙값보다 얼마나 아래에 있나 — 그 평형의 '꼬리 길이'."""
    lo, md = float(r["최저호가"]), float(r["호가중앙"])
    return (lo - md) / md * 100


def col(v, txt=None):
    """음수는 붉게, 양수는 푸르게 — Paragraph 셀이라 폰트 마크업으로 칠한다."""
    t = txt if txt is not None else sgn(v)
    c = "#C0392B" if float(v) < 0 else "#1F7A4D"
    return f"<font color='{c}'><b>{t}</b></font>"


def dp(v):
    """급매율 차이(%p). 0.05p 미만은 색을 빼고 회색으로 — 없는 신호를 색으로 만들지 않는다."""
    v = float(v)
    t = f"{v:+.2f}p".replace("-", "−")
    if abs(v) < 0.05:
        return f"<font color='#5A6B80'>{t}</font>"
    return f"<font color='{'#C0392B' if v > 0 else '#1F7A4D'}'><b>{t}</b></font>"


_gmax = min(CX, key=gap)          # 최저↔중앙 간격이 가장 벌어진 평형

TBL = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
       ("GRID", (0, 0), (-1, -1), 0.4, LINE),
       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8)]

story = []
A = story.append

# ── 표지 ────────────────────────────────────────────────────────────────
n_low = sum(1 for r in CX if float(r["중앙차이율6"]) < 0)
lo_max = min(float(r["차이율6"]) for r in CX)          # 최저 호가가 가장 크게 벌어진 폭
md_max = max(float(r["중앙차이율6"]) for r in CX)      # 호가 중앙값이 가장 높이 선 폭

# ── 시계열 — 같은 지표를 시점끼리 견줘야 '변했다/안 변했다'를 말할 수 있다 ──
SR_DAYS = sorted({r["날짜"] for r in SR})
D0, D1 = SR_DAYS[0], SR_DAYS[-1]
MARKS = [d for d in ("2026-07-10", "2026-07-17", "2026-07-24", "2026-07-31",
                     "2026-08-07", "2026-08-10") if d in SR_DAYS]
KEYS = [(r["단지"], r["전용"]) for r in CX]          # 1절 표와 같은 순서로 늘어놓는다


def srow(nm, ar, day):
    m = [r for r in SR if r["단지"] == nm and r["전용"] == str(ar) and r["날짜"] == day]
    return m[0] if m else None


def chg(nm, ar, fld):
    a, b = srow(nm, ar, D0), srow(nm, ar, D1)
    if not (a and b) or not float(a[fld]):
        return None
    return (float(b[fld]) - float(a[fld])) / float(a[fld]) * 100


MED_CHG = {k: chg(k[0], k[1], "중앙") for k in KEYS}
LOW_CHG = {k: chg(k[0], k[1], "최저") for k in KEYS}
_mv = [v for v in MED_CHG.values() if v is not None]
_lv = [v for v in LOW_CHG.values() if v is not None]
MED_LO, MED_HI, LOW_LO = min(_mv), max(_mv), min(_lv)

# ── 세제개편안(8/3 18시) 전후 ────────────────────────────────────────────
REFORM = "2026-08-03"
SEOUL = sorted([r for r in RD if r["구분"] == "시도11" and r["날짜"] >= "2026-07-27"],
               key=lambda r: r["날짜"])
_pre = [r for r in SEOUL if r["날짜"] < REFORM]
_post = [r for r in SEOUL if r["날짜"] > REFORM]
# 하루당 기울기 — 구간 첫날과 끝날의 급매율 차이를 날수로 나눈다
SLOPE_PRE = (float(_pre[-1]["급매율"]) - float(_pre[0]["급매율"])) / (len(_pre) - 1)
SLOPE_POST = (float(_post[-1]["급매율"]) - float(_post[0]["급매율"])) / (len(_post) - 1)
RF_S = {r["구분"]: r for r in RF}
T_PRE = sum(float(r["전_급매"]) for r in RT) / sum(float(r["전_매물"]) for r in RT) * 100
T_POST = sum(float(r["후_급매"]) for r in RT) / sum(float(r["후_매물"]) for r in RT) * 100
A(P("콕집 부동산 데이터 리포트 — 단지편", "tag"))
A(P("강남 재건축 ‘급매’, 한 달간 빠진 건 바닥값뿐 — 호가의 허리는 제자리였다", "title"))
A(P(f"서울 주요 재건축·대단지 9개 평형을 한 달간 매일 따라간 결과. 매물 전체의 한가운데인 "
    f"<b>호가 중앙값은 {sgn(MED_LO)}~{sgn(MED_HI)}</b>로 거의 움직이지 않은 반면, "
    f"<b>가장 싼 매물은 최대 {sgn(LOW_LO)}</b> 내려갔다", "sub"))
A(P(f"집계 기간 {D0.replace('-', '. ')}~{D1.replace('-', '. ')} 매일　|　"
    f"매물 {n(M['대상매물합계'])}건 전수({M['기준일']} 기준)　|　"
    "자료 콕집(koczip.com) 아파트 매물 전수 · 국토교통부 실거래가", "cap"))
A(Spacer(1, 10))

A(P(
    "은마아파트에 급매가 나왔다는 이야기에서 시작한 조사다. 콕집은 매물 광고를 <b>날마다 통째로 "
    "저장</b>해 두기 때문에, 같은 단지 같은 평형의 호가가 시간에 걸쳐 어떻게 움직였는지 되짚을 수 "
    f"있다. 서울 주요 재건축 단지와 대단지 9개 평형을 {D0[5:].replace('-', '월 ')}일부터 "
    f"{D1[5:].replace('-', '월 ')}일까지 한 달간 하루도 빠짐없이 따라가 봤다.<br/><br/>"
    "값이 빠진 자리는 한 곳으로 모인다. <b>매물 전체의 한가운데(호가 중앙값)는 한 달 동안 "
    f"{sgn(MED_LO)}~{sgn(MED_HI)} 사이에서 거의 제자리였는데, 가장 싼 매물(최저 호가)은 "
    f"최대 {sgn(LOW_LO)}까지 내려갔다.</b> 값을 부르는 사람들 전체가 물러선 것이 아니라, "
    "<b>분포의 아래쪽 꼬리만 떨어져 나온 모양</b>이다.<br/><br/>"
    "다만 <b>대치동은 달랐다</b>. 은마 77㎡·84㎡와 한보미도 159㎡는 중앙값까지 한 달 새 "
    "각각 −2.4%, −2.6%, −3.8% 내려와, 호가대가 통째로 아래로 밀린 유일한 곳이었다.", "lead"))

# ── 1 · 시계열 ───────────────────────────────────────────────────────────
A(P(f"1. 한 달 추이 — 중앙값은 {sgn(MED_LO)}~{sgn(MED_HI)}, 최저가는 {sgn(LOW_LO)}까지", "h"))
A(P("‘값이 내렸다’를 말하려면 <b>같은 지표를 시점끼리</b> 견줘야 한다. 아래는 매일 저장한 "
    "매물에서 뽑은 <b>호가 중앙값</b>의 한 달치 궤적이다. 실거래와 견주지 않고 호가끼리만 "
    "비교하므로, 값이 실제로 움직였는지 아닌지가 그대로 드러난다.", "body"))
rows = [hdr(["단지 · 전용"] + [d[5:].replace("-", "/") for d in MARKS] + ["한 달 변화"])]
for nm, ar in KEYS:
    cells = [P(f"<b>{nm}</b> {ar}㎡", "tdl")]
    for d in MARKS:
        r = srow(nm, ar, d)
        cells.append(P(eok1(r["중앙"]) if r else "—", "td"))
    v = MED_CHG[(nm, ar)]
    cells.append(P(col(v) if v is not None else "—", "td"))
    rows.append(cells)
t = Table(rows, colWidths=[40 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm,
                           22 * mm], repeatRows=1)
st = list(TBL)
for i, (nm, ar) in enumerate(KEYS, start=1):
    v = MED_CHG[(nm, ar)]
    if v is not None and v <= -2:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st += [("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(t)
A(P("표에는 이레 간격 여섯 시점만 실었지만 계산은 32일 전부를 썼다. 붉게 칠한 줄은 한 달 새 "
    "중앙값이 2% 넘게 내린 평형 — 모두 대치동이다.", "cap"))

A(Spacer(1, 4))
rows = [hdr(["단지 · 전용"] + [d[5:].replace("-", "/") for d in MARKS] + ["한 달 변화"])]
for nm, ar in KEYS:
    cells = [P(f"<b>{nm}</b> {ar}㎡", "tdl")]
    for d in MARKS:
        r = srow(nm, ar, d)
        cells.append(P(eok1(r["최저"]) if r else "—", "td"))
    v = LOW_CHG[(nm, ar)]
    cells.append(P(col(v) if v is not None else "—", "td"))
    rows.append(cells)
t = Table(rows, colWidths=[40 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm,
                           22 * mm], repeatRows=1)
st = list(TBL)
for i, (nm, ar) in enumerate(KEYS, start=1):
    v = LOW_CHG[(nm, ar)]
    if v is not None and v <= -2:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st += [("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(t)
A(P("같은 기간 <b>최저 호가</b>(그 평형에서 가장 싼 매물 한 건)의 궤적이다. 위 표와 "
    "같은 날짜, 같은 매물 집단에서 뽑았다.", "cap"))

A(Spacer(1, 4))
A(box(
    "<b>핵심 — 허리는 그대로인데 바닥만 빠졌다</b><br/>"
    f"· 한 달 동안 호가 중앙값이 움직인 폭은 <b>{sgn(MED_LO)}~{sgn(MED_HI)}</b>다. "
    "압구정 신현대 183㎡는 32일 내내 <b>105.0억에서 한 번도 움직이지 않았고</b>, "
    "반포 신반포2차와 올림픽훼밀리타운도 변화가 0.0%였다.<br/>"
    f"· 반면 최저 호가는 목동신시가지11 52㎡가 <b>{sgn(LOW_CHG[('목동신시가지11', '52')])}</b>, "
    f"잠실주공5 83㎡ {sgn(LOW_CHG[('잠실주공5', '83')])}, "
    f"대치 은마 84㎡ {sgn(LOW_CHG[('대치 은마', '84')])}로 내려갔다.<br/>"
    "· <b>대치동만 성격이 다르다.</b> 은마 77㎡ 중앙값은 34.0억 → 33.5억(7/31) → 33.2억으로 "
    "계단처럼 내려왔고, 84㎡도 38.0억 → 37.0억으로 밀렸다. 바닥만이 아니라 호가대 전체가 "
    "움직인 곳은 여기뿐이다.<br/>"
    "· <b>세제개편안(8월 3일 18시)이 원인이라고 보기는 어렵다.</b> 은마의 중앙값 하락은 "
    "발표 전인 7월 31일에 이미 나타났고, 발표 이후 나머지 단지의 중앙값은 거의 움직이지 "
    "않았다. 시장 전체로 넓혀 확인한 결과는 2절에 실었다."))

# ── 2 · 세제개편안 전후 ──────────────────────────────────────────────────
A(Spacer(1, 6))
_hr = [P("2. 세제개편안 전후 — 급매는 발표가 만든 것이 아니다", "h"),
       P("8월 3일 18시 세제개편안 발표가 급매를 불렀는지 확인했다. 발표 전 이레"
         "(7/27~8/2)와 발표 후 이레(8/4~8/10)를 대칭으로 갈랐고, 하루 안에 전후가 섞이는 "
         "<b>8월 3일은 경계일로 빼</b> 두었다. 결론부터 쓰면 <b>발표일에 꺾인 자리가 없다</b> — "
         "서울 급매율은 발표 전부터 이미 매일 오르고 있었다.", "body")]
# 날짜 머리글은 앞의 0을 떼고, 값에서 단위를 빼 한 줄에 들어가게 한다
rows = [hdr(["날짜"] + [f"{int(r['날짜'][5:7])}/{int(r['날짜'][8:10])}" for r in SEOUL])]
rows.append([P("<b>서울 급매율</b>(%)", "tdl")] +
            [P((f"<b>{float(r['급매율']):.2f}</b>" if r["날짜"] == REFORM
                else f"{float(r['급매율']):.2f}"), "td") for r in SEOUL])
rows.append([P("<b>매물</b>(천건)", "tdl")] +
            [P(f"{float(r['매물수']) / 1000:.0f}", "td") for r in SEOUL])
t = Table(rows, colWidths=[27 * mm] + [9.4 * mm] * len(SEOUL), repeatRows=1)
st = list(TBL)
_bi = [i for i, r in enumerate(SEOUL) if r["날짜"] == REFORM][0] + 1
st += [("BACKGROUND", (0, 2), (-1, 2), ROWALT),
       ("BACKGROUND", (_bi, 1), (_bi, -1), HOTBG),
       ("BACKGROUND", (_bi, 0), (_bi, 0), BLUE_DK),
       ("LINEBEFORE", (_bi, 0), (_bi, -1), 1.1, RED),
       ("LINEAFTER", (_bi, 0), (_bi, -1), 1.1, RED),
       ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
       ("LEFTPADDING", (0, 0), (0, -1), 4)]
t.setStyle(TableStyle(st))
A(KeepTogether(_hr + [t]))
A(P("붉게 두른 칸이 발표일(8월 3일)이다. 급매율은 그 앞뒤로 끊김 없이 같은 방향으로 "
    "이어진다. 매물 수도 14만5천~15만 건 사이에서 움직여, 발표 뒤 매물이 쏟아진 흔적은 없다.",
    "cap"))

A(Spacer(1, 2))
rows = [hdr(["구분", "발표 전 이레<br/>급매 표기율", "발표 후 이레<br/>급매 표기율",
             "차이", "매물 수<br/>(전 → 후, 일평균)"])]
for key in ("전국", "서울", "5분위", "4분위", "3분위", "2분위", "1분위"):
    r = RF_S.get(key)
    if not r:
        continue
    hot = key in ("서울", "5분위")
    rows.append([P(f"<b>{key}</b>" + (" (가장 비쌈)" if key == "5분위" else
                                      " (가장 쌈)" if key == "1분위" else ""), "tdl"),
                 P(f"{float(r['전_급매율']):.2f}%", "td"),
                 P((f"<b>{float(r['후_급매율']):.2f}%</b>" if hot
                    else f"{float(r['후_급매율']):.2f}%"), "td"),
                 P(dp(r["급매율차"]), "td"),
                 P(f"{float(r['전_매물평균']):,.0f} → {float(r['후_매물평균']):,.0f}", "td")])
rows.append([P("<b>이번 조사 9개 평형</b>", "tdl"), P(f"{T_PRE:.2f}%", "td"),
             P(f"<b>{T_POST:.2f}%</b>", "td"),
             P(dp(T_POST - T_PRE), "td"),
             P(f"{sum(float(r['전_매물']) for r in RT):,.0f} → "
               f"{sum(float(r['후_매물']) for r in RT):,.0f}", "td")])
t = Table(rows, colWidths=[36 * mm, 30 * mm, 30 * mm, 22 * mm, 40 * mm], repeatRows=1)
st = list(TBL)
for i in (2, 4, 6):
    st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
st += [("BACKGROUND", (0, 8), (-1, 8), HOTBG),
       ("LINEABOVE", (0, 8), (-1, 8), 1.0, BLUE),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(t)
A(P("‘분위’는 단지 평당가로 5등분한 것이며, 날마다 다시 나누면 단지가 갈아타 비교가 깨지므로 "
    "<b>마지막 날 기준 한 벌을 전 기간에 그대로 적용</b>했다. 급매 표기율은 그 구간 "
    "이레치를 합쳐 낸 값이다.", "cap"))

A(Spacer(1, 4))
A(box(
    "<b>발표가 방아쇠는 아니었다 — 다만 속도는 빨라졌다</b><br/>"
    f"· 서울 급매율은 발표 전 이레에도 이미 {float(_pre[0]['급매율']):.2f}% → "
    f"{float(_pre[-1]['급매율']):.2f}%로 오르는 중이었고, 발표 뒤에도 "
    f"{float(_post[0]['급매율']):.2f}% → {float(_post[-1]['급매율']):.2f}%로 "
    "<b>같은 방향으로 이어졌다</b>. 발표일을 경계로 꺾이거나 튄 자리가 없다.<br/>"
    f"· 다만 <b>기울기는 가팔라졌다</b> — 하루당 {SLOPE_PRE:+.3f}p에서 {SLOPE_POST:+.3f}p로 "
    f"약 {SLOPE_POST / SLOPE_PRE:.1f}배다. 방향을 바꾼 것이 아니라 진행 중이던 흐름을 "
    "밀어준 쪽에 가깝다.<br/>"
    f"· <b>값이 싼 쪽은 미동도 없다.</b> 1~4분위의 급매율 변화는 "
    f"{min(abs(float(RF_S[k]['급매율차'])) for k in ('1분위', '2분위', '3분위', '4분위')):.2f}"
    f"~{max(abs(float(RF_S[k]['급매율차'])) for k in ('1분위', '2분위', '3분위', '4분위')):.2f}p로 "
    f"사실상 0이고, 움직인 것은 <b>5분위(+{float(RF_S['5분위']['급매율차']):.2f}p)와 "
    f"서울(+{float(RF_S['서울']['급매율차']):.2f}p)뿐</b>이다.<br/>"
    f"· 정작 <b>이번 조사 9개 평형은 {T_PRE:.2f}% → {T_POST:.2f}%로 그대로</b>다. "
    "이들의 급매는 시장 평균의 두 배가 넘는 수준으로 <b>발표 전부터 이미 높았고</b>, "
    "발표가 그것을 더 밀어올리지는 않았다."))

# ── 3 · 현 시점 분포 ────────────────────────────────────────────────────
A(Spacer(1, 6))
A(P("3. 지금 이 순간의 분포 — 최저와 중앙이 얼마나 벌어져 있나", "h"))
A(P("1절이 ‘시간에 걸쳐 얼마나 변했나’라면, 이 표는 ‘지금 값이 얼마나 흩어져 있나’다. <b>호가가 실거래보다 높은 것은 정상</b>이라는 점을 먼저 짚어 둔다 — 팔린 집은 목록에서 빠지고 안 팔린 집이 남아 쌓이기 때문에, 남아 있는 매물의 중앙값은 구조적으로 체결가 위에 선다. 그러니 이 표는 <b>얼마나 내렸나</b>가 아니라 <b>최저와 중앙이 얼마나 벌어져 있나</b>를 읽어야 한다.", "body"))
rows = [hdr(["단지 · 전용", "세대", "준공", "매물", "‘급매’<br/>표기", "최저 호가",
             "호가<br/>중앙값", "최저↔중앙<br/>간격", "실거래 평균<br/>(6개월·건수)",
             "최저<br/>대비", "중앙<br/>대비"])]
for r in CX:
    rows.append([P(f"<b>{r['단지']}</b> {r['전용']}㎡", "tdl"),
                 P(n(r["세대"]), "td"), P(r["준공"], "td"), P(n(r["매물수"]), "td"),
                 P(f"<b>{r['급매표기']}</b>" if int(r["급매표기"]) else "0", "td"),
                 P(eok(r["최저호가"]), "tdb"), P(eok(r["호가중앙"]), "td"),
                 P(col(gap(r)), "td"),
                 P(f"{eok(r['실거래평균6'])} ({r['실거래건수6']})", "td"),
                 P(col(r["차이율6"]), "td"), P(col(r["중앙차이율6"]), "td")])
t = Table(rows, colWidths=[35 * mm, 11 * mm, 11 * mm, 11 * mm, 12 * mm, 19 * mm, 18 * mm,
                           18 * mm, 24 * mm, 13 * mm, 13 * mm], repeatRows=1)
st = list(TBL)
for i in range(1, len(rows)):
    if i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
    if float(CX[i - 1]["중앙차이율6"]) < 0:
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
st += [("LEFTPADDING", (0, 0), (0, -1), 5), ("LEFTPADDING", (1, 0), (-1, -1), 2),
       ("RIGHTPADDING", (1, 0), (-1, -1), 2)]
t.setStyle(TableStyle(st))
A(t)
A(P("전용면적은 ±1.5㎡ 범위로 같은 평형을 묶었다. ‘최저↔중앙 간격’은 가장 싼 매물이 "
    "중앙값보다 얼마나 아래에 있는지로, 그 평형의 <b>꼬리가 얼마나 길게 늘어졌는지</b>를 "
    "보여준다. 실거래는 매칭된 단지의 최근 6개월 매매 평균이며 <b>해제(취소)거래는 제외</b>했다. "
    "붉게 칠한 줄은 호가 중앙값이 실거래 평균을 밑도는 평형이다.", "cap"))

A(Spacer(1, 4))
A(box(
    "<b>꼬리가 길어진 곳과 호가대가 밀린 곳은 다르다</b><br/>"
    f"· 최저 호가는 중앙값보다 {abs(max(gap(r) for r in CX)):.1f}~{abs(min(gap(r) for r in CX)):.1f}% "
    f"아래에 있다. 꼬리가 가장 긴 곳은 <b>{_gmax['단지']} {_gmax['전용']}㎡"
    f"({sgn(gap(_gmax))})</b>다.<br/>"
    "· 압구정 신현대 183㎡가 −19.1%인 것도 같은 성격이다 — 중앙값 105.0억이 한 달 내내 "
    "꿈쩍 않는 사이 84.9억짜리 한 건이 따로 떨어져 있다는 뜻이지, 그 평형 값이 19% 내렸다는 "
    "말이 아니다.<br/>"
    "· 반대로 대치 은마 77㎡의 간격은 −4.5%로 좁다. 싼 물건 하나가 튀어나온 것이 아니라 "
    "<b>호가대 전체가 아래로 내려앉아</b> 있어서다. 1절의 중앙값 하락과 같은 이야기다.<br/>"
    "· <b>실거래와의 비교는 참고로만 읽어야 한다.</b> 호가는 부르는 값이고 실거래는 "
    "지난 6개월 평균이라, 두 값의 차이에는 ‘안 팔려 남은 매물’과 ‘그동안의 시세 변동’이 "
    "함께 섞여 있다. 값이 실제로 움직였는지는 1절의 호가끼리 비교라야 답할 수 있다.<br/>"
    f"· 그 단서로만 보면, 호가 중앙값이 실거래 평균을 밑도는 곳은 {n_low}곳(대치 은마 77·84㎡, "
    "한보미도 159㎡)이고 나머지는 위에 있다."))

A(Spacer(1, 6))
_h2 = [P("4. 싸게 나온 이유는 ‘층’이 아니다", "h"),
       P("싼 매물이 나오면 보통 저층·비선호 향이라 설명한다. 실제로 그런지 "
         "가장 매물이 많은 <b>대치 은마 77㎡</b>의 싼 순 5건을 층까지 열어 봤다. "
         "설명이 맞지 않는다 — <b>5건 중 3건이 고층</b>이고, 그 3건이 오히려 "
         "같은 층대 실거래 평균보다 더 크게 낮았다.", "body")]
rows = [hdr(["호가", "층", "층대", "향", "같은 층대<br/>실거래 대비", "중개사가 적은 매물 설명"])]
for r in CH:
    rows.append([P(f"<b>{eok(r['호가'])}</b>", "tdb"), P(r["층"], "td"), P(r["층대"], "td"),
                 P(r["향"], "td"),
                 P(col(r["같은층대대비"]) if r["같은층대대비"] else "—", "td"),
                 P(clean(r["문구"]), "tds")])
t = Table(rows, colWidths=[20 * mm, 14 * mm, 13 * mm, 15 * mm, 22 * mm, 84 * mm], repeatRows=1)
st = list(TBL)
for i in range(1, len(rows)):
    if CH[i - 1]["층대"] == "고층":
        st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
    elif i % 2 == 0:
        st.append(("BACKGROUND", (0, i), (-1, i), ROWALT))
t.setStyle(TableStyle(st))
A(KeepTogether(_h2 + [t]))
A(P("층 표기는 네이버 매물 원문 그대로다(저/중/고 + 총층). ‘같은 층대 실거래 대비’는 "
    "같은 층대에서 최근 6개월 안에 실제로 팔린 값의 평균과 견준 것이다. 붉은 줄이 고층이며, "
    "매물 설명에 섞인 한자는 우리말로 옮겨 실었다.", "cap"))

A(Spacer(1, 2))
rows = [hdr(["단지 · 전용", "층대", "실거래 평균", "건수", "호가 중앙값", "매물 수"])]
for r in FL:
    rows.append([P(f"<b>{r['단지']}</b> {r['전용']}㎡" if r["층대"] == "저층" else "", "tdl"),
                 P(r["층대"], "td"),
                 P(eok(r["실거래평균"]) if r["실거래평균"] else "—", "td"),
                 P(r["실거래건수"], "td"),
                 P(eok(r["호가중앙"]) if r["호가중앙"] else "—", "tdb"),
                 P(r["호가건수"], "td")])
t = Table(rows, colWidths=[38 * mm, 18 * mm, 26 * mm, 14 * mm, 26 * mm, 16 * mm], repeatRows=1)
st = list(TBL)
st.append(("LINEABOVE", (0, 4), (-1, 4), 0.7, LINE))
st += [("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
# 단지명을 저층 행에만 넣었으므로 표가 쪽을 넘어 갈리면 어느 단지인지 알 수 없다 — 통째로 묶는다
A(KeepTogether([t,
                P("층대는 저층 ⅓ / 중층 ⅓ / 고층 ⅓으로 나눴다. 실거래 건수가 3~11건으로 적어 "
                  "층별 평균은 참고치다.", "cap")]))

A(Spacer(1, 4))
A(box(
    "<b>층 서열이 호가에서 무너져 있다</b><br/>"
    "· 은마 77㎡ 실거래는 저층 34.40억 · 중층 35.91억 · 고층 35.93억으로 <b>층 서열이 뚜렷하다</b>"
    "(저층이 고층보다 4.3% 싸다).<br/>"
    "· 그런데 <b>호가 중앙값은 저층 33.00억 · 중층 33.50억 · 고층 33.50억</b>으로, 중층과 고층이 "
    "같고 저층과의 차이도 1.5%로 좁혀졌다. 실거래에서 벌어져 있던 층 프리미엄이 "
    "지금 부르는 값에서는 거의 사라졌다.<br/>"
    "· 84㎡는 아예 뒤집혀 있다 — 실거래는 저층 39.56억 · 중층 39.02억으로 <b>저층이 더 비싸게</b> "
    "팔렸고, 호가 중앙값은 저층 36.90억 · 중층 37.00억 · 고층 37.00억으로 층 구분이 없다.<br/>"
    "· <b>결론 — 지금 싸게 나온 물건은 ‘나쁜 층’이라서 싼 것이 아니다.</b> 층·향으로는 "
    "설명되지 않는, 파는 쪽의 개별 사정이 값을 결정하고 있다."))

tot = int(M["대상매물합계"])

# ── 4 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
q5 = [r for r in QT if r["분위"] == "5분위"][0]
q1 = [r for r in QT if r["분위"] == "1분위"][0]
gm_all = sum(int(r["급매표기"]) for r in QT) / sum(int(r["매물수"]) for r in QT) * 100
_h4 = [P("5. 시장 전체와 견주면 — 비싼 동네일수록 급매는 드물다, 그런데 이 9곳은 아니다", "h"),
       P(f"전국 아파트 매매 매물 {n(M['전체아파트매물'])}건을 단지 평당가 순으로 5등분해 "
         "‘급매’ 표기 비율을 봤다. <b>비쌀수록 급매가 드물다</b>는 규칙이 뚜렷하다. "
         "그 규칙에 이번 9개 평형만 어긋난다.", "body")]
rows = [hdr(["분위", "단지 수", "매물 수", "‘급매’ 표기", "급매 표기율", "평당가 중앙값"])]
for r in QT:
    top = r["분위"] == "5분위"
    rows.append([P(f"<b>{r['분위']}</b>" + (" (가장 비쌈)" if top else
                                            " (가장 쌈)" if r["분위"] == "1분위" else ""), "tdl"),
                 P(n(r["단지수"]), "td"), P(n(r["매물수"]), "td"), P(n(r["급매표기"]), "td"),
                 P(f"<b>{r['급매율']}%</b>" if top else f"{r['급매율']}%", "td"),
                 P(f"{n(r['평당중앙만원'])}만원", "td")])
rows.append([P("<b>이번 조사 9개 평형</b>", "tdl"), P("9", "td"), P(n(tot), "td"),
             P(n(M["대상급매표기"]), "td"),
             P(col(-1, f"{M['대상급매율']}%"), "td"), P("—", "td")])
t = Table(rows, colWidths=[36 * mm, 22 * mm, 24 * mm, 24 * mm, 26 * mm, 26 * mm], repeatRows=1)
st = list(TBL)
st += [("BACKGROUND", (0, 1), (-1, 1), ROWALT), ("BACKGROUND", (0, 3), (-1, 3), ROWALT),
       ("BACKGROUND", (0, 5), (-1, 5), ROWALT),
       ("BACKGROUND", (0, 6), (-1, 6), HOTBG),
       ("LINEABOVE", (0, 6), (-1, 6), 1.0, BLUE),
       ("LEFTPADDING", (0, 0), (0, -1), 5)]
t.setStyle(TableStyle(st))
A(KeepTogether(_h4 + [t]))
A(P(f"단지별 평당가 중앙값(공급면적 기준)으로 단지를 5등분했다. 매물이 3건 미만인 단지는 "
    f"평당가가 흔들려 제외했다. 전체 평균 급매 표기율은 {gm_all:.1f}%다. 이 표는 "
    f"<b>{M['기준일']} 하루</b> 기준이라, 이레치를 합쳐 낸 2절의 값과 소수점에서 다르다.",
    "cap"))

A(Spacer(1, 4))
A(box(
    "<b>급매는 원래 싼 동네의 언어다 — 이번엔 비싼 쪽에서 나왔다</b><br/>"
    f"· 급매 표기율은 1분위 <b>{q1['급매율']}%</b>에서 5분위 <b>{q5['급매율']}%</b>까지 "
    "값이 비싸질수록 계단처럼 내려간다. 비싼 집일수록 급하게 팔 이유가 적고, "
    "급하다고 광고에 쓰지도 않는다.<br/>"
    f"· 그런데 이번 9개 평형은 모두 5분위에 속하면서 급매 표기율이 <b>{M['대상급매율']}%</b>다. "
    f"5분위 평균({q5['급매율']}%)의 <b>{float(M['대상급매율']) / float(q5['급매율']):.1f}배</b>, "
    f"가장 싼 1분위({q1['급매율']}%)보다도 높다.<br/>"
    "· 다만 이것을 ‘고가 시장이 무너졌다’로 읽으면 1절의 추이와 어긋난다. "
    "<b>급매 표기가 많은 것과 호가대가 내려간 것은 별개</b>이고, 한 달 동안 호가대까지 "
    "실제로 밀린 곳은 대치동뿐이었다."))

# ── 5 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 5))
A(KeepTogether([
    P("6. 집계 방법과 유의사항", "h"),
    box(
        "· <b>무엇을 셌나</b> — 콕집이 매일 수집하는 아파트 매물 광고 가운데, 대상 9개 평형에 "
        f"올라와 있는 매매 매물 {n(tot)}건 전부다({M['기준일']} 기준). 표본이 아니라 전수다.<br/>"
        "· <b>같은 평형을 어떻게 묶었나</b> — 전용면적 ±1.5㎡ 범위로 묶었다. 같은 평형이라도 "
        "타입에 따라 전용이 조금씩 달라 이 폭이 필요하다.<br/>"
        "· <b>실거래는 해제거래를 뺐다.</b> 계약 후 취소된 거래가 시세와 신고가를 오염시키므로 "
        "모두 제외했다. 기준은 최근 6개월 매매 평균이며, 평형에 따라 실거래가 "
        "<b>3~20건</b>으로 적다. 표에 건수를 함께 실은 이유다.<br/>"
        "· <b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이며, 실제로 그 값에 팔린다는 뜻이 "
        "아니다. 반대로 실거래는 계약 후 30일 이내 신고를 거쳐 집계되므로, <b>8월 계약분은 "
        "9월 초에야 채워진다</b>. 지금의 호가 움직임이 거래로 이어졌는지는 아직 확인할 수 없다.<br/>"
        "· <b>호가와 실거래를 맞대 ‘시세가 얼마나 변했다’고 읽으면 안 된다.</b> 남아 있는 매물은 "
        "안 팔린 것들이라 그 중앙값은 구조적으로 체결가 위에 서고, 실거래 평균에는 지난 6개월의 "
        "시세 변동이 섞여 있다. 이 보고서가 ‘변했다/안 변했다’를 말하는 근거는 <b>1절의 호가끼리 "
        "시점 비교</b>뿐이며, 2절의 실거래 비교는 참고 지표다.<br/>"
        "· <b>한 달은 짧다.</b> 저장된 매물이 " + str(len(SR_DAYS)) + "일치여서 그 이전은 "
        "되짚을 수 없다. 이번 한 달의 움직임이 추세인지 일시적인지는 이 자료만으로 알 수 없다.<br/>"
        "· <b>‘최저 호가’는 한 건이다.</b> 단 하나의 매물이 표를 끌어내릴 수 있어, 같은 표에 "
        "<b>호가 중앙값</b>을 나란히 실었다. 두 값이 갈리는 것이 이번 조사의 핵심이다.<br/>"
        "· <b>‘급매’는 중개사의 표기다.</b> 값이 실제로 싼지와 무관하게 광고 문구에 쓰인 말을 "
        "센 것이고, 급매를 한자로 적은 건 등은 잡히지 않아 하한선이다.<br/>"
        "· <b>세는 단위는 광고다.</b> 같은 집을 여러 중개사무소가 올렸으면 각각 1건으로 센다.",
        WARNBG, WARNLN),
]))

A(KeepTogether([
    Spacer(1, 9),
    P("작성 <b>황인찬</b>　|　런투온라인 대표　|　부동산 데이터 서비스 ‘콕집’　"
      "<font color='#1268D3'>koczip.com</font>", "small"),
    P("010-5942-8014　runtoonline@gmail.com", "small"),
]))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="강남 재건축 급매 — 한 달간 빠진 건 바닥값뿐", author="황인찬 (런투온라인)")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
