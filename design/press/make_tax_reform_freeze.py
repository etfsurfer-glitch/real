# -*- coding: utf-8 -*-
"""2026년 세제개편안 발표 직후 아파트 매물 시장 반응 보고서 (기자 배포용).

수치는 design/press/data/press_trade.csv · press_top.csv · press_tiers.csv 를
그대로 읽어 조판한다(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
Run: python3 design/press/make_tax_reform_freeze.py
  → design/press/세제개편안_발표직후_매물시장반응.pdf
"""
import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "fonts"
DATA = HERE / "data"
OUT = HERE / "세제개편안_발표직후_매물시장반응.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

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
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=9.6, textColor=INK, alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=9.6, textColor=INK,
                          alignment=1),
    "tdr": ParagraphStyle("tdr", fontName="PB", fontSize=8.5, leading=9.6, textColor=RED,
                          alignment=1),
    "tdg": ParagraphStyle("tdg", fontName="PB", fontSize=8.5, leading=9.6, textColor=GREEN,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=9.6, textColor=INK,
                          alignment=0),
    "tier": ParagraphStyle("tier", fontName="P", fontSize=7.6, leading=11.6, textColor=INK,
                           alignment=0),
    "credit": ParagraphStyle("credit", fontName="PM", fontSize=9, leading=14.5, textColor=INK),
}


def P(t, s="body"):
    return Paragraph(t, ss[s])


def read(fn):
    with open(DATA / fn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


T = {(r["거래"], r["구분"]): r for r in read("press_trade.csv")}
TOP = read("press_top.csv")
TIERS = read("press_tiers.csv")
# CSV 는 급지 표기(1급지=최고가) — 보도자료는 5분위=최고가 관행을 따른다
T2Q = {"1급지": "5분위", "2급지": "4분위", "3급지": "3분위", "4급지": "2분위", "5급지": "1분위"}
QS = ("5분위", "4분위", "3분위", "2분위", "1분위")
TRS = ("매매", "전세", "월세")
n = lambda v: f"{int(float(v)):,}"          # noqa: E731


def conv3(r):
    """평소 신규 유입을 이번 주 재고 기준으로 환산한 건수.
    '정상 대비'는 건수 비가 아니라 재고 대비 비율의 비여서, 실제 3주 평균 건수로 나누면
    표기된 %가 재현되지 않는다(월세 2분위 149% vs 161%). 같은 재고에 평소 비율을 적용한
    값으로 맞춰야 '몇 건 대비 몇 건'이 표기 %와 일치한다."""
    g3, g4 = float(r["g3"]), float(r["g4"])
    return round(int(r["inc4"]) * g3 / g4) if g4 else 0
pc = lambda v: f"{float(v):+.1f}%"          # noqa: E731
sn = lambda v: f"{int(float(v)):+,}"        # 부호 붙은 건수(증감) # noqa: E731

story = []
A = story.append


def hdr(cells):
    return [P(c, "th") for c in cells]


def box(html, bg=BOXBG, ln=LINE):
    return Table([[P(html, "boxb")]], colWidths=[168 * mm],
                 style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                                   ("BOX", (0, 0), (-1, -1), 0.8, ln),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                   ("TOPPADDING", (0, 0), (-1, -1), 9),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))


# ── 머리 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트", "tag"))
A(P("세제개편안 발표 직후, 고가 지역만 매매·전세가 동시에 멈췄다", "title"))
A(P("5분위 매매 소멸 32.5% 감소 · 전세 신규 유입 평소의 52% · 하위 분위는 오히려 증가", "sub"))
A(Table([[P("발표 2026. 8. 3.(월) 18:00 &nbsp;&nbsp;|&nbsp;&nbsp; 관측 2026. 8. 4.(화) "
            "&nbsp;&nbsp;|&nbsp;&nbsp; 자료 콕집(koczip.com) 전국 아파트 매물·실거래 전수",
            "small")]],
        colWidths=[168 * mm],
        style=TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                          ("LINEBELOW", (0, 0), (-1, -1), 0.8, LINE)])))
A(Spacer(1, 8))

# ── 리드 ────────────────────────────────────────────────────────────────
A(P(
    "2026년 세제개편안이 발표된 다음 날, 전국 아파트 시장에서 <b>고가 지역만 선별적으로 매물이 "
    "멈추는</b> 현상이 관측됐다. 부동산 데이터 서비스 콕집이 전국 아파트 매물 178만여 건을 "
    "전수 분석한 결과, 실제 거래·회수로 시장에서 사라진 매물이 전주 같은 요일 대비 "
    f"매매 {abs(float(T[('매매','전국')]['chg'])):.1f}%, "
    f"전세 {abs(float(T[('전세','전국')]['chg'])):.1f}%, "
    f"월세 {abs(float(T[('월세','전국')]['chg'])):.1f}% 감소했다. "
    "주목할 대목은 감소가 <b>가격대별로 정반대 방향</b>으로 나타났다는 점이다.", "lead"))

# ── 1 ───────────────────────────────────────────────────────────────────
A(P("1. 5분위는 매매·전세가 동시에 얼어붙었다", "h"))
A(P(
    "전국 219개 시군구를 최근 1년 아파트 실거래 평당가 중위값으로 5등분했다(5분위가 최고가). "
    "가격대가 높은 <b>4·5분위에서만</b> 매물 회전이 둔화됐고, 1~3분위는 평소와 같거나 오히려 "
    "활발했다. 분위별 지역 구분은 부록에 실었다."))

rows = [hdr(["구분", "거래", "매물 수", "실질소멸<br/>직전 3주 평균", "실질소멸<br/>8월 4일",
             "증감", "신규 유입<br/>평소", "신규 유입<br/>8월 4일", "정상 대비"])]
hot, seps = [], []
for q in QS:
    seps.append(len(rows))
    for ti, tr in enumerate(TRS):
        r = T[(tr, q)]
        isq = q in ("5분위", "4분위")
        if isq:
            hot.append(len(rows))
        nm = int(r["norm"])
        rows.append([
            P(f"<b>{q}</b>" if ti == 0 else "", "tdb"),
            P(tr, "tdb" if isq else "td"), P(n(r["stock"]), "td"),
            P(n(r["d3"]), "td"), P(n(r["d4"]), "tdb" if isq else "td"),
            P(f'{pc(r["chg"])}<br/><font size=6.1 color="#6B7684">{sn(r["dchg"])}건</font>',
              "tdr" if isq and float(r["chg"]) < 0 else "td"),
            P(f'{r["g3"]}%<br/><font size=6.1 color="#6B7684">{n(r["inc3"])}건</font>', "td"),
            P(f'{r["g4"]}%<br/><font size=6.1 color="#6B7684">{n(r["inc4"])}건</font>', "tdb" if isq else "td"),
            P(f'{nm}%<br/><font size=6.1 color="#6B7684">{n(r["inc4"])}/{n(conv3(r))}건</font>',
              "tdr" if nm < 90 else ("tdg" if nm > 110 else "td"))])
total_at = len(rows)
for ti, tr in enumerate(TRS):
    r = T[(tr, "전국")]
    rows.append([P("<b>전국</b>" if ti == 0 else "", "tdb"), P(tr, "tdb"), P(n(r["stock"]), "tdb"),
                 P(n(r["d3"]), "tdb"), P(n(r["d4"]), "tdb"),
                 P(f'{pc(r["chg"])}<br/><font size=6.1 color="#6B7684">{sn(r["dchg"])}건</font>', "tdb"),
                 P(f'{r["g3"]}%<br/><font size=6.1 color="#6B7684">{n(r["inc3"])}건</font>', "tdb"),
                 P(f'{r["g4"]}%<br/><font size=6.1 color="#6B7684">{n(r["inc4"])}건</font>', "tdb"),
                 P(f'{r["norm"]}%<br/><font size=6.1 color="#6B7684">{n(r["inc4"])}/{n(conv3(r))}건</font>', "tdb")])

t = Table(rows, colWidths=[13 * mm, 11 * mm, 20 * mm, 21 * mm, 19 * mm, 19 * mm, 19 * mm,
                           19 * mm, 27 * mm], repeatRows=1)
st = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
      ("GRID", (0, 0), (-1, -1), 0.4, LINE),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("TOPPADDING", (0, 0), (-1, -1), 2.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
      ("BACKGROUND", (0, total_at), (-1, total_at + 2), ROWALT),
      ("LINEABOVE", (0, total_at), (-1, total_at), 1.0, BLUE_DK)]
for r in hot:
    st.append(("BACKGROUND", (0, r), (-1, r), HOTBG))
for k in seps[1:]:
    st.append(("LINEABOVE", (0, k), (-1, k), 0.7, LINE))
t.setStyle(TableStyle(st))
A(t)
A(P("각 비율 아래 작은 숫자는 해당 건수다(증감은 실질소멸 건수의 차이, 신규 유입은 그날 늘어난 매물 수). "
    "‘정상 대비’ 아래 분수는 ‘8월 4일 유입 / 평소라면 들어왔을 유입’이다"
    "(평소 유입률을 이번 주 매물 재고에 적용해 환산했다 — 그래야 옆의 비율과 맞는다).<br/>"
    "‘정상 대비’는 이번 주 신규 유입 증가폭을 직전 3주 평균으로 나눈 값이다. 100%면 평소와 "
    "같고, 붉은색은 90% 미만(위축), 초록색은 110% 초과(활발)를 뜻한다. ‘신규 유입’은 월요일 "
    "대비 화요일 매물 수 증가율로, 요일 효과를 없애려 직전 3주 같은 요일 쌍과 비교했다.", "cap"))

A(box(
    "<b>‘실질소멸’이란 — 광고 기간만료는 제외한 수치다</b><br/>"
    "네이버 부동산 매물 광고는 확인일자로부터 <b>31일이 지나면 자동으로 내려간다.</b> "
    "중개사가 갱신하지 않아 사라지는 이 물량은 시장 상황과 무관하게 매일 대량으로 발생한다"
    "(8월 4일 매매 26,141건, 전세 2,020건, 월세 1,979건).<br/>"
    "이 보고서의 <b>실질소멸은 기간만료분을 전부 걷어낸 뒤 남은 건수</b>다. 즉 "
    "<b>거래가 성사됐거나 매도자·임대인이 매물을 거둬들인 경우</b>만 센다. 제외 기준을 "
    "29일·25일로 바꿔 다시 계산해도 감소폭은 27.7~29.0%로 같았다."))

# ── 2 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("2. 전세가 매매보다 더 강하게 멈춘 이유", "h"))
A(P(
    "5분위에서는 <b>전세 신규 유입이 평소의 52%</b>로, 매매(60%)보다 더 크게 꺾였다. "
    "이는 이번 개편안의 핵심 방향이 <b>‘보유’에서 ‘거주’로</b> 옮겨간 데 따른 것으로 보인다."))
A(box(
    "<b>세제 혜택을 받으려면 집주인이 직접 살아야 한다</b><br/>"
    "· <b>장기보유특별공제</b>가 거주 중심으로 이원화된다. 1세대 1주택 거주공제는 연 8%·최대 "
    "80%(2029년)로 올라가는 반면, <b>보유공제는 2029년 폐지</b>된다. 전세를 놓고 다른 곳에 "
    "살면 공제가 사실상 사라진다.<br/>"
    "· <b>종부세 기본공제</b>도 1주택 <b>거주 14억원 / 비거주 9억원</b>으로 갈린다. "
    "세액공제 역시 보유기간이 아닌 <b>거주기간</b> 기준으로 바뀐다.<br/>"
    "→ 고가 주택 보유자가 세 부담을 줄이려면 <b>본인이 입주</b>해야 하고, 그러면 "
    "<b>그 집을 전세로 내놓을 수 없다.</b> 5분위 전세 매물이 가장 먼저 잠긴 배경이다."))
A(Spacer(1, 6))
A(P(
    "반대로 <b>1~3분위에서는 전월세 매물이 오히려 늘었다.</b> 3분위 전세는 평소의 126%, "
    "월세는 176%, 2분위 월세는 161%로 유입이 활발했다. 이 구간은 종부세 과세선(공시가격 "
    "9억원)과 장기보유특별공제 고가주택 기준에 걸리지 않아 거주 요건 강화의 영향을 받지 "
    "않는다. 같은 날 같은 시장에서 <b>가격대에 따라 정반대 움직임</b>이 나타난 것이다."))

# ── 3 ───────────────────────────────────────────────────────────────────
A(P("3. 세금이 바뀌는 지역에서만 반응이 나왔다", "h"))
A(P(
    "이번 개편안의 부동산 항목은 대부분 고가 주택과 조정대상지역에 집중돼 있다. "
    "종합부동산세 과세 기준은 1세대 1주택 공시가격 14억원(시가 약 20억원), 그 외 9억원이며, "
    "세율 인상 구간도 과세표준 12억원 초과부터다. 다주택자 양도세 중과 한시 완화와 일시적 "
    "2주택 처분기한 단축(3년→2년)은 모두 조정대상지역에 적용된다."))
A(P(
    "5분위에는 서울 강남·서초·송파·용산·성동구와 경기 과천시, 성남시 분당구 등이 포함된다. "
    "세 부담이 실제로 바뀌는 지역에서만 매도자와 임대인이 동시에 움직임을 멈춘 것으로 "
    "해석된다."))
A(box(
    "<b>왜 매도를 미루나</b><br/>"
    "다주택자 조정대상지역 양도세 중과는 2027년 +5%p, 2028년 +10%p로 한시 완화된다"
    "(현행 +20%p). 3주택 이상은 +30%p에서 2027년 +10%p로 낮아진다. "
    "특히 <b>2026년 양도분도 2027년 1월 1일 이후 신고하면 완화 세율이 적용</b>돼, "
    "올해 안에 서둘러 팔 이유가 사라졌다."))
A(Spacer(1, 6))

# ── 4 ───────────────────────────────────────────────────────────────────
_h4 = [P("4. 최상위 지역 참고 수치 (매매)", "h"),
       P("평당가 상위 10개 시군구의 개별 수치다. 시군구 단위는 표본이 작아 편차가 크므로 "
         "개별 값보다 분위 단위 추세로 읽는 것이 적절하다.")]
rows = [hdr(["지역", "평당가", "매매 매물", "실질소멸<br/>직전 3주 평균",
             "실질소멸<br/>8월 4일", "증감"])]
for r in TOP:
    rows.append([P(r["지역"], "tdl"), P(f"{n(r['평당가만원'])}만", "td"),
                 P(n(r["매물수"]), "td"), P(n(r["실질소멸_3주평균"]), "td"),
                 P(n(r["실질소멸_84"]), "td"),
                 P(f'{pc(r["소멸증감"])}<br/><font size=6.1 color="#6B7684">'
                   f'{sn(int(r["실질소멸_84"]) - int(r["실질소멸_3주평균"]))}건</font>', "td")])
t = Table(rows, colWidths=[44 * mm, 21 * mm, 23 * mm, 29 * mm, 23 * mm, 28 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
]))
A(KeepTogether(_h4 + [t]))
A(Spacer(1, 4))

# ── 5 유의사항 ──────────────────────────────────────────────────────────
A(KeepTogether([
    P("5. 해석 시 유의사항", "h"),
    box("<b>· 하루치 관측이다.</b> 발표 다음 날 하루를 직전 3주 같은 요일과 비교한 결과로, "
        "추세 확정에는 며칠간의 누적 확인이 필요하다.<br/>"
        "<b>· 매도 보류와 매수 위축은 이 지표만으로 구분되지 않는다.</b> 매물이 덜 사라진 것이 "
        "파는 쪽이 멈춰서인지, 사는 쪽이 줄어서인지는 실거래 확정 후 판단이 가능하다.<br/>"
        "<b>· 1분위는 표본이 작다.</b> 1분위 전세 실질소멸은 하루 50건 안팎이어서 증감률의 "
        "진폭이 크다. 해당 구간은 방향만 참고하는 것이 적절하다.<br/>"
        "<b>· 실거래 통계로는 아직 확인할 수 없다.</b> 부동산 거래는 계약 후 30일 이내 "
        "신고여서, 8월 초 계약분은 9월 초에야 집계가 채워진다. 일시적 2주택 특례 경과조치 "
        "기준일인 8월 3일 전후의 계약 변화도 그때 확인 가능하다.<br/>"
        "<b>· 개정 ‘안’이다.</b> 국회 논의 과정에서 내용이 바뀔 수 있다.", WARNBG, WARNLN),
]))
A(Spacer(1, 10))

# ── 발행 ────────────────────────────────────────────────────────────────
A(Table([[P("<b>런투온라인</b> 대표 <b>황인찬</b> &nbsp;|&nbsp; 부동산 데이터 서비스 ‘콕집’ "
            "&nbsp; koczip.com", "credit")],
         [P("010-5942-8014 &nbsp; runtoonline@gmail.com", "credit")]],
        colWidths=[168 * mm],
        style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.8, LINE),
                          ("TOPPADDING", (0, 0), (-1, 0), 8),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                          ("TOPPADDING", (0, 1), (-1, -1), 1)])))

# ── 부록 ────────────────────────────────────────────────────────────────
A(PageBreak())
A(P("부록", "tag"))
A(P("분위별 지역 구분", "title"))
A(P("전국 219개 시군구를 최근 1년(2025년 8월~2026년 7월) 아파트 매매 실거래 평당가 "
    "중위값 순으로 5등분했다. 5분위가 최고가이며, 각 분위 안에서는 평당가가 높은 순으로 "
    "나열했다.", "sub"))
rows = [hdr(["분위", "평당가 범위", "지역"])]
for r in TIERS:
    rows.append([P(f"<b>{T2Q[r['급지']]}</b>", "tdb"), P(r["평당가범위"], "td"),
                 P(r["지역"], "tier")])
t = Table(rows, colWidths=[16 * mm, 27 * mm, 125 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
A(t)
A(P("실거래 100건 미만인 시군구는 평당가 신뢰도가 낮아 분위 산정에서 제외했다.", "cap"))

SimpleDocTemplate(str(OUT), pagesize=A4,
                  leftMargin=21 * mm, rightMargin=21 * mm,
                  topMargin=17 * mm, bottomMargin=15 * mm,
                  title="세제개편안 발표 직후 매물 시장 반응",
                  author="런투온라인 콕집").build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
