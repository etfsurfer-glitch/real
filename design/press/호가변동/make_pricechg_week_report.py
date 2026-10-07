# -*- coding: utf-8 -*-
"""최근 1주일 아파트 호가 인상·인하 통계 보고서 (기자 배포용).

수치는 design/press/data/press_pricechg_*.csv 를 그대로 읽어 조판한다
(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
원천은 콕집 article_events(PRICE_CHANGE) — 같은 매물의 호가가 바뀐 순간만 기록한 이벤트로,
매물이 새로 올라오거나 내려간 것과는 별개다.
Run: python3 design/press/호가변동/make_pricechg_week_report.py
  → design/press/호가변동/최근1주일_호가인상인하_통계.pdf
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
OUT = HERE / "최근1주일_호가인상인하_통계.pdf"

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
    "boxb": ParagraphStyle("boxb", fontName="P", fontSize=9, leading=14.8, textColor=INK),
    "th": ParagraphStyle("th", fontName="PB", fontSize=8.3, leading=11, textColor=colors.white,
                         alignment=1),
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK,
                         alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=1),
    "tdr": ParagraphStyle("tdr", fontName="PB", fontSize=8.5, leading=10.4, textColor=RED,
                          alignment=1),
    "tdg": ParagraphStyle("tdg", fontName="PB", fontSize=8.5, leading=10.4, textColor=GREEN,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=0),
}


def P(t, s="body"):
    return Paragraph(t, ss[s])


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


WK = {(r["거래"], r["주"]): r for r in read("press_pricechg_week.csv")}
BAND = read("press_pricechg_band.csv")
DEPTH = read("press_pricechg_depth.csv")
SIDO = read("press_pricechg_sido.csv")
SGG = read("press_pricechg_sgg.csv")
QUINT = {(r["분위"], r["거래"]): r for r in read("press_pricechg_quintile.csv")}
BASE = {r["구분"]: r for r in read("press_pricechg_baseline.csv")}
WEEKS = [k[2:] for k in read("press_pricechg_baseline.csv")[0] if k.startswith("w_")]
M = {r["항목"]: r["값"] for r in read("press_pricechg_meta.csv")}

n = lambda v: f"{int(float(v)):,}"                      # noqa: E731
S = WK[("매매", "최근주")]
Pv = WK[("매매", "직전주")]

story = []
A = story.append

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트", "tag"))
A(P("최근 1주일, 호가 내린 매물이 올린 매물의 2.67배 — 10주 만의 최고", "title"))
A(P(f"전국 아파트 매매 광고 {n(M['매매광고재고_8월6일'])}건 중 "
    f"{n(M['호가변경광고수_최근주'])}건({M['호가변경비율_최근주']}%)이 값을 고쳤다 — "
    f"인하 {n(S['인하'])}건 · 인상 {n(S['인상'])}건 · "
    f"평상시(직전 8주) {BASE['전국']['평상시_최저']}~{BASE['전국']['평상시_최고']}배를 넘어섰다", "sub"))
A(P("집계 기간 2026. 7. 31.(목)~8. 6.(목) 7일　|　비교 2026. 7. 24.~7. 30.　|　"
    "자료 콕집(koczip.com) 전국 아파트 매물 전수", "cap"))
A(Spacer(1, 10))

A(P(
    "콕집은 전국 아파트 매물 광고를 하루 여러 차례 수집하면서 <b>같은 매물의 호가가 바뀐 순간</b>을 "
    "모두 기록한다. 매물이 새로 올라오거나 내려간 것과는 별개로, <b>이미 나와 있던 집이 값을 "
    "고쳐 부른 사건</b>만 센 것이다. 최근 1주일 결과는 <b>인하 "
    f"{n(S['인하'])}건, 인상 {n(S['인상'])}건으로 인하가 {S['배율']}배</b>였다. "
    f"직전 주({Pv['배율']}배)보다 격차가 벌어졌고, <b>관측 이래 10주 중 가장 높다</b>. "
    "다만 <b>인하가 늘어서가 아니라 인상이 줄어서</b>다 — 인하 건수는 평상시보다 오히려 "
    f"{BASE['전국']['인하증감']}% 적었고, 인상이 {BASE['전국']['인상증감']}% 빠졌다.", "lead"))

# ── 1 ───────────────────────────────────────────────────────────────────
A(P("1. 거래 유형별 — 매매는 인상이 한 주 만에 24% 사라졌다", "h"))
rows = [hdr(["거래", "주", "인하", "인상", "인하÷인상", "평균 인하폭", "건당 평균 인하액"])]
for tr in ("매매", "전세", "월세"):
    for wk in ("직전주", "최근주"):
        r = WK[(tr, wk)]
        last = wk == "최근주"
        sty = "tdb" if last else "td"
        rows.append([P(f"<b>{tr}</b>" if wk == "직전주" else "", "tdb"),
                     P("7/24~30" if wk == "직전주" else "<b>7/31~8/6</b>", sty),
                     P(n(r["인하"]), sty), P(n(r["인상"]), sty),
                     P(f"{r['배율']}배", "tdr" if last else "td"),
                     P(f"{r['평균인하율']}%" if r["평균인하율"] else "—", sty),
                     P(f"{n(r['건당평균인하액만원'])}만원" if r["건당평균인하액만원"] else "—", sty)])
t = Table(rows, colWidths=[18 * mm, 26 * mm, 22 * mm, 22 * mm, 24 * mm, 26 * mm, 30 * mm],
          repeatRows=1)
st = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
      ("GRID", (0, 0), (-1, -1), 0.4, LINE),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8)]
for i in (2, 4, 6):
    st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
for i in (3, 5):
    st.append(("LINEABOVE", (0, i), (-1, i), 0.7, LINE))
t.setStyle(TableStyle(st))
A(t)
A(P("월세는 값이 ‘보증금/월세’ 두 축이어서 보증금만으로 계산한 변동률이 수천 %까지 튄다. "
    "건수만 실었다. ‘건당 평균 인하액’은 인하 건의 인하액 평균이다.", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>핵심 — 값을 내린 사람이 늘어난 게 아니라, 올리려던 사람이 사라졌다</b><br/>"
    f"· 매매 인하는 {n(Pv['인하'])}건 → {n(S['인하'])}건으로 "
    f"<b>{(int(S['인하'])-int(Pv['인하']))/int(Pv['인하'])*100:+.1f}%</b>, "
    f"인상은 {n(Pv['인상'])}건 → {n(S['인상'])}건으로 "
    f"<b>{(int(S['인상'])-int(Pv['인상']))/int(Pv['인상'])*100:+.1f}%</b>. "
    "둘 다 줄었지만 인상이 두 배 빠르게 줄어 격차가 벌어졌다.<br/>"
    f"· 중복 광고를 합쳐 집 단위로 세면 인하 <b>{n(M['실매물_인하_최근주'])}채</b>, "
    f"인상 <b>{n(M['실매물_인상_최근주'])}채</b>로 2.25배다(직전 주 "
    f"{n(M['실매물_인하_직전주'])}채 / {n(M['실매물_인상_직전주'])}채, 1.94배). "
    "세는 단위를 바꿔도 방향은 같다.<br/>"
    f"· 한 주 동안 값을 고친 광고는 {n(M['호가변경광고수_최근주'])}건으로 전체 매매 광고의 "
    f"<b>{M['호가변경비율_최근주']}%</b>다. 이 중 {M['중복변경광고수']}건은 한 주 안에 "
    "두 번 이상 고쳤다.<br/>"
    f"· <b>전세는 평소와 다르지 않다.</b> 전세 호가는 원래 인하가 인상보다 훨씬 잦은데"
    f"(직전 주 {WK[('전세','직전주')]['배율']}배), 최근 주는 "
    f"{WK[('전세','최근주')]['배율']}배로 오히려 격차가 줄었다."))


# ── 2 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h2b = [P("2. 평상시와 견주면 — 10주 만의 최고치, 그런데 5분위만 범위를 벗어났다", "h"),
        P("직전 한 주만 견주면 그 주가 평범했는지 알 수 없다. 그래서 관측 전 기간을 "
          "목~수 주 단위로 끊어 <b>평상시 범위</b>를 잡았다. 아래 배율은 모두 "
          "<b>인하÷인상</b>이며, 평상시는 최근 2주를 뺀 <b>직전 8주</b>다.")]
rows = [hdr(["구분"] + [w.replace("2026-", "") for w in WEEKS] +
            ["평상시 범위<br/>(8주)", "평상시<br/>대비"])]
for g in ("전국", "5분위", "4분위", "3분위", "2분위", "1분위"):
    r = BASE[g]
    key = g in ("전국", "5분위")
    out = float(r["평상시대비"])
    cells = [P(f"<b>{g}</b>", "tdb")]
    for i, w in enumerate(WEEKS):
        v = float(r["w_" + w])
        last = i == len(WEEKS) - 1
        cells.append(P(f"{v:.2f}", ("tdr" if key else "tdb") if last else "td"))
    cells.append(P(f"{r['평상시_최저']}~{r['평상시_최고']}", "td"))
    cells.append(P(f"{out:.2f}배", "tdr" if out >= 1.3 else "tdb" if key else "td"))
    rows.append(cells)
t = Table(rows, colWidths=[15 * mm] + [11.3 * mm] * 10 + [22 * mm, 18 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, 2), (-1, 2), HOTBG),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("LINEAFTER", (10, 0), (10, -1), 1.0, BLUE_DK),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (1, 0), (10, -1), 2), ("RIGHTPADDING", (1, 0), (10, -1), 2),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether(_h2b + [t]))
A(P("각 칸은 그 주의 인하÷인상 배율이며 날짜는 주의 시작(목요일)이다. 맨 오른쪽 ‘평상시 대비’는 "
    "최근주 배율 ÷ 평상시 8주 평균이다. 관측은 2026년 5월 19일 시작이라 그 이전 주는 없다.", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>평상시를 벗어난 것은 5분위뿐이다</b><br/>"
    f"· <b>전국</b>은 평상시 {BASE['전국']['평상시_최저']}~{BASE['전국']['평상시_최고']}배 사이를 "
    f"오갔는데 최근주는 <b>{BASE['전국']['최근주']}배</b>로 10주 중 가장 높다"
    f"(평상시 평균의 {BASE['전국']['평상시대비']}배).<br/>"
    f"· <b>5분위는 6월까지 인상이 인하보다 많았다.</b> 배율이 0.67~0.78로 <b>1을 밑돌던</b> "
    "구간이다. 7월 10일 주에 처음 1을 넘었고(1.01), 최근주는 "
    f"<b>{BASE['5분위']['최근주']}배</b> — 평상시 평균의 "
    f"<b>{BASE['5분위']['평상시대비']}배</b>다. <b>값을 올려 부르는 게 더 흔하던 구간이 "
    "뒤집혔다.</b><br/>"
    f"· 나머지 분위는 평상시 범위 안에 있다 — 4분위 {BASE['4분위']['평상시대비']}배, "
    f"3분위 {BASE['3분위']['평상시대비']}배, 1분위 {BASE['1분위']['평상시대비']}배, "
    f"<b>2분위는 {BASE['2분위']['평상시대비']}배로 오히려 평상시보다 덜 기울었다.</b><br/>"
    f"· 움직인 것은 인상 쪽이다. 인상 건수가 평상시 주당 "
    f"{n(BASE['전국']['인상_평상시'])}건 → {n(BASE['전국']['인상_최근주'])}건"
    f"(<b>{BASE['전국']['인상증감']}%</b>), 5분위는 {n(BASE['5분위']['인상_평상시'])}건 → "
    f"{n(BASE['5분위']['인상_최근주'])}건(<b>{BASE['5분위']['인상증감']}%</b>)으로 "
    f"거의 반토막이다. 인하는 전국 {BASE['전국']['인하증감']}%로 오히려 줄었다."))

# ── 3 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h2 = [P("3. 가격대별 — 30억 초과만 인하가 늘었다", "h"),
       P("매매 광고를 <b>값을 고치기 전 호가</b> 기준으로 나눴다. 값이 비쌀수록 인하÷인상 "
         "격차가 크게 벌어졌고, <b>30억 초과 구간만 인하 건수 자체가 늘었다</b>.")]
rows = [hdr(["변경 전 호가", "직전주 인하", "직전주 인상", "직전주 배율",
             "최근주 인하", "최근주 인상", "최근주 배율", "인하 증감", "인상 증감"])]
for r in BAND:
    top = r["가격대"].startswith("6.")
    sty = "tdb" if top else "td"
    dv, uv = float(r["인하증감율"]), float(r["인상증감율"])
    rows.append([P(r["가격대"][3:], "tdl"),
                 P(n(r["직전주_인하"]), "td"), P(n(r["직전주_인상"]), "td"),
                 P(f"{r['직전주_배율']}배", "td"),
                 P(n(r["최근주_인하"]), sty), P(n(r["최근주_인상"]), sty),
                 P(f"{r['최근주_배율']}배", "tdr" if top else "tdb"),
                 P(f"{dv:+.1f}%", "tdg" if dv > 0 else "td"),
                 P(f"{uv:+.1f}%", "tdr" if uv < -25 else "td")])
t = Table(rows, colWidths=[24 * mm, 19 * mm, 19 * mm, 17 * mm, 19 * mm, 19 * mm, 17 * mm,
                           17 * mm, 17 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), HOTBG),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("LINEAFTER", (3, 0), (3, -1), 1.0, BLUE_DK),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
]))
A(KeepTogether(_h2 + [t]))
A(P("‘인하 증감’·‘인상 증감’은 직전 주 대비 건수 증감률이다. 6억 미만 구간의 인하가 많은 것은 "
    "그 구간 매물 자체가 압도적으로 많기 때문이며, 구간끼리는 건수가 아니라 배율로 견주는 것이 "
    "적절하다.", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>30억 초과 — 인하 +22.4%, 인상 -30.6%</b><br/>"
    "전 구간에서 인상이 줄었지만, <b>인하 건수까지 늘어난 것은 30억 초과뿐</b>이다"
    "(608건 → 744건). 인상은 170건에서 118건으로 줄어 인하÷인상이 3.58배에서 "
    "<b>6.31배</b>가 됐다.<br/>"
    "· <b>9~15억 구간은 방향이 뒤집혔다.</b> 직전 주에는 인상이 더 많았는데(0.99배) "
    "최근 주에는 인하가 더 많아졌다(1.14배).<br/>"
    "· <b>6억 미만은 거의 그대로다</b>(3.25배 → 3.62배). 저가 구간은 원래 인하가 잦다."))

# ── 3 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h3q = [P("4. 5분위별 — 값을 올려 부르는 사람이 남은 곳은 5분위뿐이다", "h"),
        P("전국 219개 시군구를 최근 1년 아파트 실거래 평당가 중위값으로 5등분했다"
          "(5분위가 최고가). 앞 절이 <b>매물 하나하나의 값</b>으로 나눈 것이라면, "
          "여기는 <b>그 집이 어느 급지에 있는가</b>로 나눈 것이다. 분위마다 매물 수가 크게 "
          "달라 건수보다 <b>재고 대비 비율</b>로 읽는 것이 적절하다.")]
rows = [hdr(["분위", "평당가 중위값<br/>(만원/평)", "인하", "인상", "인하÷인상",
             "매물 대비<br/>인하", "매물 대비<br/>인상", "인상<br/>증감"])]
for q in ("5분위", "4분위", "3분위", "2분위", "1분위", "전국"):
    r = QUINT[(q, "매매")]
    top = q == "5분위"
    tot = q == "전국"
    sty = "tdb" if top or tot else "td"
    uv = float(r["인상증감율"])
    rows.append([P(f"<b>{q}</b>", "tdb"),
                 P(r["평당가범위"].replace("만원", ""), "td"),
                 P(n(r["인하"]), sty), P(n(r["인상"]), sty),
                 P(f"{r['배율']}배", "tdr" if top else sty),
                 P(f"{r['인하율_재고대비']}%", sty),
                 P(f"{r['인상율_재고대비']}%", "tdr" if top else sty),
                 P(f"{uv:+.1f}%", "tdb" if uv < -25 else "td")])
t = Table(rows, colWidths=[18 * mm, 32 * mm, 20 * mm, 20 * mm, 22 * mm, 22 * mm, 22 * mm,
                           20 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, 1), (-1, 1), HOTBG),
    ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), ROWALT),
    ("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 1.0, BLUE_DK),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
]))
A(KeepTogether(_h3q + [t]))
A(P("‘매물 대비’는 그 분위에 걸려 있는 매매 광고(8월 6일 기준) 대비 비율이다. "
    "5분위에는 서울 강남·서초·송파·용산·성동구와 경기 과천시, 성남시 분당구 등 43개 시군구가 "
    "들어간다.", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>5분위는 인하 쪽으로 가장 덜 기울었지만, 인상이 가장 빨리 빠지고 있다</b><br/>"
    f"· 인하÷인상이 5분위 <b>{QUINT[('5분위','매매')]['배율']}배</b>로 전 분위 중 가장 낮다"
    f"(1분위 {QUINT[('1분위','매매')]['배율']}배, 2분위 {QUINT[('2분위','매매')]['배율']}배). "
    f"매물 대비 인상 비율도 <b>{QUINT[('5분위','매매')]['인상율_재고대비']}%</b>로 "
    f"다른 분위(0.28~0.38%)의 두 배다. <b>아직 값을 올려 부르는 사람이 남아 있는 유일한 "
    "구간</b>이다.<br/>"
    f"· 그런데 <b>그 인상이 가장 빠르게 줄고 있다.</b> 인상 건수 증감은 "
    f"5분위 {QUINT[('5분위','매매')]['인상증감율']}%·4분위 {QUINT[('4분위','매매')]['인상증감율']}%인 반면 "
    f"1분위는 {QUINT[('1분위','매매')]['인상증감율']}%에 그쳤다. <b>상급지일수록 "
    "인상이 빠진다.</b><br/>"
    f"· 매물 대비 인하 비율은 오히려 <b>저가 지역이 높다</b>"
    f"(1분위 {QUINT[('1분위','매매')]['인하율_재고대비']}% > "
    f"5분위 {QUINT[('5분위','매매')]['인하율_재고대비']}%). 값을 내리는 일 자체는 "
    "저가 지역에서 더 흔하다.<br/>"
    f"· <b>전세</b>는 5분위에서 매물 대비 인하가 "
    f"{int(QUINT[('5분위','전세')]['직전주_인하'])/int(QUINT[('5분위','전세')]['재고'])*100:.2f}% → "
    f"<b>{QUINT[('5분위','전세')]['인하율_재고대비']}%</b>로 줄었다"
    f"(전국 {int(QUINT[('전국','전세')]['직전주_인하'])/int(QUINT[('전국','전세')]['재고'])*100:.2f}% → "
    f"{QUINT[('전국','전세')]['인하율_재고대비']}%). 전세는 원래 인하가 잦은 시장이라 "
    "매매와 같은 자로 견주면 안 된다."))

A(Spacer(1, 6))
A(box(
    "<b>‘가격대’와 ‘분위’가 서로 다른 이야기를 한다 — 둘을 섞어 읽으면 안 된다</b><br/>"
    "3절에서 <b>30억 초과 매물</b>은 인하÷인상이 6.31배로 인상이 거의 사라졌는데, "
    "그 집들이 속한 <b>5분위 지역 전체</b>는 1.46배로 가장 낮다. 모순이 아니다 — "
    "5분위 시군구 안에도 소형·중저가 매물이 함께 있고, <b>그쪽에서는 인상이 여전히 "
    "활발</b>하기 때문이다.<br/>"
    "→ 정리하면 <b>‘강남권이 조정받는다’가 아니라 ‘어디에 있든 30억을 넘기면 다르다’</b>가 "
    "이 데이터가 말하는 바다.", WARNBG, WARNLN))

A(Spacer(1, 8))
_h3 = [P("5. 얼마나 내렸나 — 10% 이상 내린 매물은 3.6%", "h"),
       P(f"최근 1주일 매매 인하 {n(S['인하'])}건의 인하 폭 분포다. "
         "대부분은 5% 안쪽의 소폭 조정이다.")]
rows = [hdr(["인하 폭", "건수", "비중", "평균 인하액"])]
for r in DEPTH:
    deep = r["인하폭"] == "10% 이상"
    sty = "tdb" if deep else "td"
    rows.append([P(r["인하폭"], "tdl"), P(n(r["건수"]), sty), P(f"{r['비중']}%", sty),
                 P(f"{n(r['평균인하액만원'])}만원", "tdr" if deep else "td")])
t = Table(rows, colWidths=[40 * mm, 30 * mm, 25 * mm, 35 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), HOTBG),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
]))
A(KeepTogether(_h3 + [t]))
A(P("평균 인하폭은 3.51%, 건당 평균 인하액은 2,588만원이다. ‘호가를 내렸다’가 곧 급매를 뜻하지는 "
    "않는다 — 대부분은 처음 부른 값에서 한 단계 물러선 수준이다.", "cap"))

# ── 4 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h4 = [P("6. 어디서 — 수도권보다 지방이, 서울 안에서는 강남권이", "h"),
       P("최근 1주일 매매 기준이다. 시·도 단위로는 <b>경기(1.47배)·서울(1.89배)이 가장 낮고</b> "
         "강원·제주·충남이 높다. 그런데 시군구로 내려가면 <b>서울 서초구가 6.8배</b>로 상위권에 "
         "올라온다 — 서울 전체가 아니라 고가 자치구만 튀는 구조다.")]
rows = [hdr(["시·도", "인하", "인상", "배율", "평균<br/>인하폭", "  ",
             "시·군·구 (인하 150건 이상)", "인하", "인상", "배율"])]
for i in range(max(len(SIDO), len(SGG))):
    a = SIDO[i] if i < len(SIDO) else None
    b = SGG[i] if i < len(SGG) else None
    seoul = a and a["시도"] == "서울시"
    hotb = b and "서초" in b["시군구"]
    rows.append([
        P(a["시도"].replace("전남광주통합특별시 ", "") if a else "", "tdl"),
        P(n(a["인하"]) if a else "", "tdb" if seoul else "td"),
        P(n(a["인상"]) if a else "", "td"),
        P(f"{a['배율']}배" if a else "", "tdb" if seoul else "td"),
        P(f"{a['평균인하율']}%" if a else "", "td"),
        P("", "td"),
        P(b["시군구"].replace("전남광주통합특별시 ", "") if b else "", "tdl"),
        P(n(b["인하"]) if b else "", "td"),
        P(n(b["인상"]) if b else "", "td"),
        P(f"{b['배율']}배" if b else "", "tdr" if hotb else "tdb")])
t = Table(rows, colWidths=[27 * mm, 13 * mm, 13 * mm, 15 * mm, 13 * mm, 6 * mm,
                           42 * mm, 13 * mm, 13 * mm, 13 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("BACKGROUND", (5, 0), (5, -1), colors.white),
    ("LEFTPADDING", (5, 0), (5, -1), 0), ("RIGHTPADDING", (5, 0), (5, -1), 0),
    ("ROWBACKGROUNDS", (0, 1), (4, -1), [colors.white, ROWALT]),
    ("ROWBACKGROUNDS", (6, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (4, -1), 0.4, LINE),
    ("GRID", (6, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    ("LEFTPADDING", (0, 0), (4, -1), 3), ("RIGHTPADDING", (0, 0), (4, -1), 3),
    ("LEFTPADDING", (6, 0), (-1, -1), 3), ("RIGHTPADDING", (6, 0), (-1, -1), 3),
]))
A(KeepTogether(_h4 + [t]))
A(P("오른쪽 표는 인하 150건 이상인 시군구만 배율 순으로 추렸다(표본이 작은 지역의 극단값 제외). "
    "‘전남광주통합특별시’는 지면상 앞말을 줄였다.", "cap"))

# ── 5 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(KeepTogether([
    P("7. 집계 방법과 유의사항", "h"),
    box(
        "· <b>무엇을 셌나</b> — 콕집이 하루 여러 차례 매물을 수집하면서, <b>같은 매물번호</b>의 "
        "호가가 직전 수집 때와 달라진 건을 기록한 것이다. 한 집이 값을 고쳐 부른 사건만 세며, "
        "새 매물 등록이나 매물 회수는 포함되지 않는다. 한 매물이 한 주에 여러 번 고치면 "
        "각각 1건으로 센다.<br/>"
        "· <b>실제 호가 조정은 이보다 많을 수 있다.</b> 중개사가 광고를 내렸다가 새 번호로 "
        "다시 올리면 매물번호가 바뀌어 ‘값을 고친 것’으로 잡히지 않고 회수·신규로 갈린다. "
        "이 집계는 그런 건을 놓치므로 <b>하한선</b>으로 읽는 것이 안전하다.<br/>"
        f"· <b>방향을 오간 매물도 있다.</b> 최근 1주일에 값을 내리기도 하고 올리기도 한 매물이 "
        "215건 있었다. 전체(2만여 건)에 견주면 1%가 안 된다.<br/>"
        "· <b>세는 단위는 광고다.</b> 같은 집을 여러 중개사무소가 올렸으면 각각 1건으로 센다. "
        f"중복을 합친 집 단위 수치는 1절 상자에 함께 실었다(인하 {n(M['실매물_인하_최근주'])}채).<br/>"
        "· <b>이 기간에 세제개편안 발표(8월 3일 18시)가 포함돼 있다.</b> 최근 주 7일 중 나흘이 "
        "발표 이후다. 다만 이 표만으로 발표가 원인이라고 단정할 수는 없다 — 인상 감소는 "
        "직전 주에도 이미 진행 중이었다.<br/>"
        "· <b>호가는 실거래가 아니다.</b> 파는 쪽이 부르는 값이며, 실제 계약가는 "
        "계약 후 30일 이내 신고를 거쳐 확인된다. 이 주의 계약분은 9월 초에야 집계가 채워진다.<br/>"
        "· <b>‘내렸다’가 급매를 뜻하지는 않는다.</b> 인하 건의 3분의 1은 2% 미만 조정이다.",
        WARNBG, WARNLN),
]))
A(Spacer(1, 12))
A(P("런투온라인 대표 황인찬　|　부동산 데이터 서비스 ‘콕집’　"
    "<font color='#1268D3'>koczip.com</font>", "small"))
A(P("010-5942-8014　runtoonline@gmail.com", "small"))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="최근 1주일 아파트 호가 인상·인하 통계", author="런투온라인")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
