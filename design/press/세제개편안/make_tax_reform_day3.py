# -*- coding: utf-8 -*-
"""2026년 세제개편안 발표 사흘째 아파트 매물 시장 반응 보고서 (기자 배포용).

발표 이틀째 보고서(make_tax_reform_day2.py)의 현행화판. 3일차(8월 6일)를 이어 붙이고,
'매물 증가폭 정상 대비' 지표를 '신규 등록 건수 직접 비교'로 교체했다 — 3일차(목요일)는
직전 3주 평균 순증가가 음수여서 비율이 뒤집혀 읽히기 때문(본문 2절에 공개).

수치는 design/press/data/press_3days.csv · press_top_3days.csv · press_tiers.csv 를
그대로 읽어 조판한다(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
산출 스크립트는 design/press/세제개편안/calc_tax_reform_days.py.
Run: python3 design/press/세제개편안/make_tax_reform_day3.py
  → design/press/세제개편안/세제개편안_발표사흘째_매물시장반응.pdf
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
OUT = HERE / "세제개편안_발표사흘째_매물시장반응.pdf"

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
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.2, textColor=INK,
                         alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=10.2, textColor=INK,
                          alignment=1),
    "tdr": ParagraphStyle("tdr", fontName="PB", fontSize=8.5, leading=10.2, textColor=RED,
                          alignment=1),
    "tdg": ParagraphStyle("tdg", fontName="PB", fontSize=8.5, leading=10.2, textColor=GREEN,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.2, textColor=INK,
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


T = {(r["일차"], r["거래"], r["구분"]): r for r in read("press_3days.csv")}
TOPA = read("press_top_3days.csv")
# 평당가는 첫 배포본 값을 그대로 쓴다. 그 뒤 실거래가 더 신고되면서 중위값이 몇십만원씩
# 움직이는데, 같은 시리즈의 같은 표에서 값이 달라지면 안 된다.
PUB = {r["지역"]: r for r in read("press_top.csv")}
QS = ("5분위", "4분위", "3분위", "2분위", "1분위", "전국")
TRS = ("매매", "전세", "월세")
DD = ("1일차", "2일차", "3일차")

n = lambda v: f"{int(float(v)):,}"                      # noqa: E731
pc = lambda v: f"{float(v):+.1f}%"                      # noqa: E731
sn = lambda v: f"{int(float(v)):+,}"                    # noqa: E731
g = lambda d, t, q, f: T[(d, t, q)][f]                  # noqa: E731
SM = '<br/><font size=6.1 color="#6B7684">'

story = []
A = story.append

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트", "tag"))
A(P("세제개편안 사흘째 — 최고가 지역에 매물이 다시 나오기 시작했다", "title"))
A(P(f"5분위 신규 매물 {pc(g('1일차','매매','5분위','nchg'))} → "
    f"{pc(g('2일차','매매','5분위','nchg'))} → <b>{pc(g('3일차','매매','5분위','nchg'))}</b> · "
    "이틀 만에 평소를 넘어섰다. 다만 거래로 사라지는 매물은 여전히 평소보다 적다", "sub"))
A(P("발표 2026. 8. 3.(월) 18:00　|　관측 2026. 8. 4.(화)~8. 6.(목)　|　"
    "자료 콕집(koczip.com) 전국 아파트 매물 전수", "cap"))
A(Spacer(1, 10))

A(P(
    "세제개편안 발표 사흘째까지의 전국 아파트 매물 흐름을 확인했다. 이틀째 보고서에서 "
    "<b>고가 지역의 매물 정지가 더 깊어졌다</b>고 전한 것은 사흘째에 <b>반전됐다</b>. "
    "5분위(최고가)에 새로 올라온 매매 매물이 평소보다 많아졌다. 다만 "
    "<b>거래·회수로 사라지는 매물은 여전히 평소의 4분의 3 수준</b>이어서, 파는 쪽은 "
    "돌아왔지만 사는 쪽은 아직 돌아오지 않은 모습이다.", "lead"))

# ── 1 ───────────────────────────────────────────────────────────────────
A(P("1. 사흘째, 5분위 신규 매물이 평소를 넘었다", "h"))
A(P(
    "전국 219개 시군구를 최근 1년 아파트 실거래 평당가 중위값으로 5등분했다(5분위가 최고가). "
    "왼쪽은 <b>실질소멸</b>(거래·회수로 사라진 매물, 광고 기간만료 제외), 오른쪽은 "
    "<b>신규 등록</b>(그날 새로 올라온 매물)이며, 둘 다 직전 3주 같은 요일 평균과 견준 값이다."))

rows = [hdr(["구분", "거래", "실질소멸 증감", "", "", "신규 등록 증감", "", ""]),
        hdr(["", "", "1일차", "2일차", "3일차", "1일차", "2일차", "3일차"])]
hot, seps = [], []
for q in QS:
    seps.append(len(rows))
    for ti, tr in enumerate(TRS):
        isq = q == "5분위"
        tot = q == "전국"
        cells = [P(f"<b>{q}</b>" if ti == 0 else "", "tdb"),
                 P(tr, "tdb" if isq or tot else "td")]
        for f in ("chg", "nchg"):
            for d in DD:
                v = float(g(d, tr, q, f))
                last = d == "3일차"
                sty = ("tdg" if v > 0 else "tdr") if (last and (isq or tot)) else \
                      ("tdb" if isq or tot else "td")
                cells.append(P(f"{pc(v)}", sty))
        if isq:
            hot.append(len(rows))
        rows.append(cells)
total_at = len(rows) - 3

t = Table(rows, colWidths=[15 * mm, 12 * mm] + [23.5 * mm] * 6, repeatRows=2)
st = [("BACKGROUND", (0, 0), (-1, 1), BLUE),
      ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)),
      ("SPAN", (2, 0), (4, 0)), ("SPAN", (5, 0), (7, 0)),
      ("GRID", (0, 0), (-1, -1), 0.4, LINE),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("LINEAFTER", (4, 0), (4, -1), 1.0, BLUE_DK),
      ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
      ("BACKGROUND", (0, total_at), (-1, total_at + 2), ROWALT),
      ("LINEABOVE", (0, total_at), (-1, total_at), 1.0, BLUE_DK)]
for r in hot:
    st.append(("BACKGROUND", (0, r), (-1, r), HOTBG))
for k in seps[1:]:
    st.append(("LINEABOVE", (0, k), (-1, k), 0.7, LINE))
t.setStyle(TableStyle(st))
A(t)
A(P("1일차는 8월 4일(화), 2일차는 8월 5일(수), 3일차는 8월 6일(목)이며 각각 직전 3주 같은 요일 "
    "평균과 비교했다(요일 효과 제거). ‘실질소멸’은 그날 사라진 매물에서 광고 기간만료를 뺀 "
    "건수다 — 네이버 부동산 광고는 확인일자로부터 31일이 지나면 자동으로 내려가며, 이 물량은 "
    "시장 상황과 무관하므로 전부 걷어냈다. <b>실질소멸이 마이너스면 매물이 평소보다 덜 "
    "사라졌다는 뜻이고, 신규 등록이 플러스면 평소보다 많이 나왔다는 뜻이다.</b>", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>사흘째에 갈린 것 — 내놓는 쪽은 돌아왔고, 팔리는 쪽은 아직이다</b><br/>"
    f"· <b>5분위(최고가) 매매</b> — 신규 등록이 {g('1일차','매매','5분위','nchg')}% → "
    f"{g('2일차','매매','5분위','nchg')}% → <b>{g('3일차','매매','5분위','nchg')}%</b>로 "
    f"사흘째 평소를 넘어섰다(당일 {n(g('3일차','매매','5분위','n4'))}건, 3주 평균 "
    f"{n(g('3일차','매매','5분위','n3'))}건). 반면 실질소멸은 "
    f"{g('2일차','매매','5분위','chg')}%에서 {g('3일차','매매','5분위','chg')}%로 "
    "돌아오다 말았다 — 여전히 평소의 4분의 3 수준이다.<br/>"
    f"· <b>5분위 전세</b>도 신규 등록이 {g('1일차','전세','5분위','nchg')}% → "
    f"{g('3일차','전세','5분위','nchg')}%로 거의 평소 수준을 회복했다. 이틀째까지 "
    "‘집주인이 들어가 살기로 해 전세가 잠긴다’고 본 해석은 <b>사흘을 넘기지 못했다.</b><br/>"
    f"· <b>전국 매매</b>도 신규 등록이 {g('1일차','매매','전국','nchg')}% → "
    f"{g('2일차','매매','전국','nchg')}% → <b>{g('3일차','매매','전국','nchg')}%</b>로 "
    "플러스 전환했다.<br/>"
    f"· <b>중저가(1~3분위)</b>는 애초에 크게 멈추지 않았다. 3분위 신규 등록은 사흘 내내 "
    f"플러스({g('1일차','매매','3분위','nchg')}% → {g('2일차','매매','3분위','nchg')}% → "
    f"{g('3일차','매매','3분위','nchg')}%)였다."))

A(Spacer(1, 6))
A(box(
    "<b>‘매물이 덜 사라졌다’를 거래 감소로 바로 읽으면 안 된다</b><br/>"
    "실질소멸은 <b>팔려서 내려간 것</b>과 <b>집주인이 거둬들인 것</b>을 구분하지 않는다. "
    "3일차 5분위 매매가 여전히 평소보다 25% 덜 사라진 것은 둘 중 어느 쪽 때문인지 이 지표만으로는 "
    "알 수 없다. 확정은 실거래 신고가 채워지는 9월 초에 가능하다.", WARNBG, WARNLN))

# ── 2 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("2. 지표를 하나 바꿨다 — ‘정상 대비’에서 ‘신규 등록 직접 비교’로", "h"))
A(P(
    "앞선 1·2일차 보고서는 ‘매물 증가폭이 평소의 몇 %인가’를 썼다. 매물 증가폭은 "
    "<b>신규 등록에서 실질소멸을 뺀 순증가</b>이고, ‘정상 대비’는 이를 직전 3주 평균 순증가로 "
    "나눈 값이다. 1·2일차(화·수)는 평소 순증가가 뚜렷한 플러스여서 문제가 없었다."))
A(box(
    f"그런데 <b>목요일은 재고가 구조적으로 줄어드는 요일</b>이다. 직전 3주 목요일 전국 매매 "
    f"순증가는 평균 <b>{n(g('3일차','매매','전국','inc3'))}건</b>으로 마이너스였다"
    "(7월 16·23·30일 모두 감소). 기준값이 음수면 ‘정상 대비 %’는 음수를 음수로 나눈 값이 되어 "
    "<b>부호가 뒤집혀 읽힌다</b> — 실제로는 재고가 줄었는데 표에는 ‘평소의 130%’처럼 나온다.<br/>"
    "그래서 이번 회차부터 순증가 비율 대신 <b>신규 등록 건수를 직전 3주 같은 요일 평균과 직접 "
    "비교</b>한다. 신규 등록은 항상 양수여서 요일과 무관하게 같은 뜻으로 읽힌다. "
    "<b>1·2일차 값도 같은 새 기준으로 다시 계산해 실었다</b> — 표 안에서 세 날짜가 같은 자로 "
    "재어져야 하기 때문이다.<br/>"
    f"· 참고로 3일차 전국 매매 재고는 하루 새 {n(g('3일차','매매','전국','inc4'))}건 줄었는데, "
    f"이는 평소 목요일 감소폭({n(g('3일차','매매','전국','inc3'))}건)의 절반 수준이다. "
    "방향은 감소, 폭은 평소보다 작다.", WARNBG, WARNLN))

# ── 3 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("3. 왜 고가만 이틀을 멈췄나", "h"))
A(P(
    "이번 개편안의 부동산 항목은 대부분 <b>고가 주택과 조정대상지역</b>에 집중돼 있다. "
    "종합부동산세 과세 기준은 1세대 1주택 공시가격 14억원(시가 약 20억원), 그 외 9억원이며, "
    "세율 인상 구간도 과세표준 12억원 초과부터다. 5분위에는 서울 강남·서초·송파·용산·성동구와 "
    "경기 과천시, 성남시 분당구 등이 포함된다. 발표 직후 이틀간 이 구간만 신규 등록이 "
    "30% 안팎 줄어든 것은, 내용을 확인하기 전까지 <b>내놓기를 미룬 것</b>으로 읽힌다."))
A(box(
    "<b>이틀을 멈추게 한 두 조항</b><br/>"
    "· <b>매도 보류</b> — 다주택자 조정대상지역 양도세 중과가 2027년 +5%p, 2028년 +10%p로 "
    "한시 완화된다(현행 +20%p). 2026년 양도분도 2027년 1월 1일 이후 신고하면 완화 세율이 "
    "적용돼, 올해 안에 서둘러 팔 이유가 사라졌다.<br/>"
    "· <b>전세 잠김</b> — 장기보유특별공제가 거주 중심으로 이원화되고(1세대 1주택 거주공제 "
    "연 8%·최대 80%, 2029년), 종부세 기본공제도 1주택 거주 14억원 / 비거주 9억원으로 갈린다. "
    "세제 혜택을 받으려면 본인이 들어가 살아야 하고, 그러면 그 집을 전세로 내놓을 수 없다.<br/>"
    f"→ 다만 <b>사흘째 수치는 이 해석의 지속성을 지지하지 않는다.</b> 5분위 전세 신규 등록이 "
    f"{g('3일차','전세','5분위','nchg')}%로 평소 수준에 복귀했다. 발표 직후의 위축은 "
    "세 부담을 계산한 결과라기보다 <b>내용 확인까지의 관망</b>이었을 가능성이 크다."))

# ── 4 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h4 = [P("4. 최상위 10개 시군구 (매매)", "h"),
       P("평당가 상위 10개 시군구의 1~3일차 개별 수치다. 시군구 단위는 표본이 작아 편차가 "
         "크므로 개별 값보다 분위 단위 추세로 읽는 것이 적절하다.")]
rows = [hdr(["지역", "평당가", "매매 매물", "실질소멸 증감", "", "", "신규 등록 증감", "", ""]),
        hdr(["", "", "", "1일차", "2일차", "3일차", "1일차", "2일차", "3일차"])]
BYD = {(r["일차"], r["지역"]): r for r in TOPA}
REG = [r["지역"] for r in TOPA if r["일차"] == "3일차"]
for reg in REG:
    r3 = BYD[("3일차", reg)]
    cells = [P(reg, "tdl"), P(f"{n(PUB.get(reg, {'평당가만원': r3['평당가만원']})['평당가만원'])}만", "td"),
             P(n(r3["매물수"]), "td")]
    for f in ("소멸증감", "신규증감"):
        for d in DD:
            v = float(BYD[(d, reg)][f])
            cells.append(P(pc(v), "tdb" if d == "3일차" else "td"))
    rows.append(cells)
t = Table(rows, colWidths=[30 * mm, 17 * mm, 16 * mm] + [17.5 * mm] * 6, repeatRows=2)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 1), BLUE),
    ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)), ("SPAN", (2, 0), (2, 1)),
    ("SPAN", (3, 0), (5, 0)), ("SPAN", (6, 0), (8, 0)),
    ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("LINEAFTER", (5, 0), (5, -1), 1.0, BLUE_DK),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether(_h4 + [t]))
A(P("‘평당가’는 최근 1년 실거래 중위값이며, 시리즈 내 일관성을 위해 첫 배포본 값을 그대로 썼다. "
    "‘매매 매물’은 3일차(8월 6일) 기준 그 지역에 걸려 있는 매매 광고 수다.", "cap"))

# ── 5 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(KeepTogether([
    P("5. 해석 시 유의사항", "h"),
    box(
        "· <b>사흘치 관측이다.</b> 발표 다음 날부터 사흘을 각각 직전 3주 같은 요일과 비교한 "
        "결과다. 이틀째까지의 판단이 사흘째에 뒤집힌 것처럼, 며칠 더 쌓아야 추세가 확정된다.<br/>"
        "· <b>8월 7일(금)은 제외했다.</b> 그날 수집이 8월 6일 수집 종료 3시간 반 뒤인 "
        "0시 30분에 시작돼, 하루치 변화로 볼 수 없다.<br/>"
        "· <b>매도 보류와 매수 위축은 이 지표만으로 구분되지 않는다.</b> 매물이 덜 사라진 것이 "
        "파는 쪽이 멈춰서인지, 사는 쪽이 줄어서인지는 실거래 확정 후 판단이 가능하다.<br/>"
        "· <b>1·2분위는 표본이 작다.</b> 전세·월세는 하루 수십~수백 건이어서 증감률의 진폭이 "
        "크다. 해당 구간은 방향만 참고하는 것이 적절하다.<br/>"
        "· <b>실거래 통계로는 아직 확인할 수 없다.</b> 부동산 거래는 계약 후 30일 이내 신고여서 "
        "8월 초 계약분은 9월 초에야 집계가 채워진다. 일시적 2주택 특례 경과조치 기준일인 "
        "8월 3일 전후의 계약 변화도 그때 확인 가능하다.<br/>"
        "· <b>앞선 보도자료와 일부 수치가 다르다.</b> 2절에 적은 대로 지표를 바꿔 1·2일차를 "
        "다시 계산했고, 실질소멸도 그 뒤 확인일자가 갱신되며 0.1% 안팎 움직였다. "
        "표 안의 세 날짜는 모두 같은 기준으로 산출됐다.<br/>"
        "· <b>개정 ‘안’이다.</b> 국회 논의 과정에서 내용이 바뀔 수 있다.", WARNBG, WARNLN),
]))
A(Spacer(1, 12))
A(P("런투온라인 대표 황인찬　|　부동산 데이터 서비스 ‘콕집’　"
    "<font color='#1268D3'>koczip.com</font>", "small"))
A(P("010-5942-8014　runtoonline@gmail.com", "small"))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="세제개편안 발표 사흘째 매물 시장 반응", author="런투온라인")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
