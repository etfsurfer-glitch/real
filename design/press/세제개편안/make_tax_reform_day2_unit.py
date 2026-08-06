# -*- coding: utf-8 -*-
"""2026년 세제개편안 발표 이틀째 — 실매물(중복광고 합침) 기준 보고서 (기자 배포용).

수치는 design/press/data/press_unit.csv · press_top_unit.csv · press_tiers.csv 를
그대로 읽어 조판한다(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
Run: python3 design/press/세제개편안/make_tax_reform_day2_unit.py
  → design/press/세제개편안/세제개편안_발표이틀째_매물시장반응.pdf
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
FONTS = HERE.parent.parent / "fonts"
DATA = HERE.parent / "data"
OUT = HERE / "세제개편안_발표이틀째_실매물기준.pdf"

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


def conv3(r):
    """평소 신규 유입을 그 주 재고 기준으로 환산한 건수.
    '정상 대비'는 재고 대비 비율의 비여서 실제 3주 평균 건수로 나누면 표기 %가 재현되지 않는다."""
    g3, g4 = float(r["g3"]), float(r["g4"])
    return round(int(r["inc4"]) * g3 / g4) if g4 else 0


def P(t, s="body"):
    return Paragraph(t, ss[s])


def read(fn):
    with open(DATA / fn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


D1, D2 = "1일차", "2일차"
RAW = read("press_unit.csv")
T = {(r["일차"], r["거래"], r["구분"]): r for r in RAW}
TOPA = read("press_top_unit.csv")
TOP = [r for r in TOPA if r["일차"] == "2일차"]
TOP1 = {r["지역"]: r for r in TOPA if r["일차"] == "1일차"}
# 평당가는 1일차 배포본 값을 그대로 쓴다. 그 뒤 실거래가 더 신고되면서 중위값이
# 몇 만원씩 움직이는데, 두 보도자료의 같은 표에서 값이 달라지면 안 된다.
PUB = {r["지역"]: r for r in read("press_top.csv")}
TIERS = read("press_tiers.csv")
# CSV 는 급지 표기(1급지=최고가) — 보도자료는 5분위=최고가 관행을 따른다
T2Q = {"1급지": "5분위", "2급지": "4분위", "3급지": "3분위", "4급지": "2분위", "5급지": "1분위"}
QS = ("5분위", "4분위", "3분위", "2분위", "1분위")
TRS = ("매매", "전세", "월세")
n = lambda v: f"{int(float(v)):,}"          # noqa: E731


pc = lambda v: f"{float(v):+.1f}%"          # noqa: E731
sn = lambda v: f"{int(float(v)):+,}"        # 부호 붙은 건수(증감) # noqa: E731

ADS, UNITS = 1820678, 798211

story = []
A = story.append
QS = ("5분위", "4분위", "3분위", "2분위", "1분위")
TRS = ("매매", "전세", "월세")


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


d1 = lambda t, q, f: T[(D1, t, q)][f]                          # noqa: E731
d2 = lambda t, q, f: T[(D2, t, q)][f]                          # noqa: E731

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트", "tag"))
A(P("세제개편안 이틀째 — 중복 광고를 걷어내도 고가는 더 멈췄다", "title"))
A(P(f"실매물 기준 5분위 매매 소멸 {d1('매매','5분위','chg')}% → {d2('매매','5분위','chg')}% · "
    f"전세 {d1('전세','5분위','chg')}% → {d2('전세','5분위','chg')}% · "
    "같은 집 중복 광고를 1건으로 합쳐 다시 계산했다", "sub"))
A(P("발표 2026. 8. 3.(월) 18:00　|　관측 2026. 8. 4.(화)~8. 5.(수)　|　"
    "자료 콕집(koczip.com) 전국 아파트 매물 전수(실매물 기준)", "cap"))
A(Spacer(1, 10))

A(P(
    "이 보고서는 같은 집을 여러 중개사무소가 올린 <b>중복 광고를 1건으로 합친 ‘실매물’ 기준</b>이다. "
    "광고 건수 기준으로 낸 앞선 보고서와 같은 기간·같은 방법을 쓰되, 세는 단위만 바꿨다. "
    "결론은 같았다 — 고가 지역의 매물 정지는 이틀째에 더 깊어졌고, 중저가는 하루 만에 돌아왔다.", "lead"))

# ── 1 ───────────────────────────────────────────────────────────────────
A(P("1. 실매물로 세어도 5분위는 더 멈췄다", "h"))
A(P(
    "전국 219개 시군구를 최근 1년 아파트 실거래 평당가 중위값으로 5등분했다(5분위가 최고가). "
    "아래 모든 수치는 <b>실매물 기준</b>이다. 발표 1일차(8월 4일)와 2일차(8월 5일)의 "
    "<b>실질소멸</b>(거래·회수로 사라진 매물) 증감과, <b>신규 유입</b>이 평소의 몇 %인지를 "
    "나란히 놓았다."))

rows = [hdr(["구분", "거래", "실질소멸 증감<br/>1일차 → 2일차", "",
             "신규 유입 정상 대비<br/>1일차 → 2일차", "", "매물 회전<br/>이틀째"])]
hot, seps = [], []
for q in QS:
    seps.append(len(rows))
    for ti, tr in enumerate(TRS):
        a, b = T[(D1, tr, q)], T[(D2, tr, q)]
        ca, cb = float(a["chg"]), float(b["chg"])
        na, nb = int(a["norm"]), int(b["norm"])
        deep = cb < ca - 1.5          # 소멸이 더 줄었다 = 더 멈췄다
        back = cb > ca + 1.5
        isq = q in ("5분위",)
        if isq:
            hot.append(len(rows))
        arrow = ("더 멈춤" if deep else "되살아남" if back else "비슷")
        rows.append([
            P(f"<b>{q}</b>" if ti == 0 else "", "tdb"),
            P(tr, "tdb" if isq else "td"),
            P(f'{pc(ca)}<br/><font size=6.1 color="#6B7684">{sn(a["dchg"])}건</font>', "td"),
            P(f'{pc(cb)}<br/><font size=6.1 color="#6B7684">{sn(b["dchg"])}건</font>',
              "tdr" if cb < 0 and isq else "tdb" if isq else "td"),
            P(f'{na}%<br/><font size=6.1 color="#6B7684">{n(a["inc4"])}/{n(conv3(a))}건</font>', "td"),
            P(f'{nb}%<br/><font size=6.1 color="#6B7684">{n(b["inc4"])}/{n(conv3(b))}건</font>',
              "tdr" if nb < 90 else ("tdg" if nb > 110 else "td")),
            P(arrow, "tdr" if deep else ("tdg" if back else "td"))])
total_at = len(rows)
for ti, tr in enumerate(TRS):
    a, b = T[(D1, tr, "전국")], T[(D2, tr, "전국")]
    rows.append([P("<b>전국</b>" if ti == 0 else "", "tdb"), P(tr, "tdb"),
                 P(f'{pc(a["chg"])}<br/><font size=6.1 color="#6B7684">{sn(a["dchg"])}건</font>', "tdb"),
                 P(f'{pc(b["chg"])}<br/><font size=6.1 color="#6B7684">{sn(b["dchg"])}건</font>', "tdb"),
                 P(f'{a["norm"]}%<br/><font size=6.1 color="#6B7684">{n(a["inc4"])}/{n(conv3(a))}건</font>', "tdb"),
                 P(f'{b["norm"]}%<br/><font size=6.1 color="#6B7684">{n(b["inc4"])}/{n(conv3(b))}건</font>', "tdb"),
                 P("유지", "tdb")])

t = Table(rows, colWidths=[15 * mm, 12 * mm, 27 * mm, 27 * mm, 30 * mm, 30 * mm, 20 * mm],
          repeatRows=1)
st = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
      ("SPAN", (2, 0), (3, 0)), ("SPAN", (4, 0), (5, 0)),
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
A(P("<b>앞선 보고서(광고 건수 기준)와 숫자가 다른 것은 세는 단위가 달라서다.</b> 기간·비교 방법·"
    "기간만료 제외 기준은 모두 같고, 광고를 실매물로 환산한 점만 다르다.", "cap"))
A(P("‘실질소멸 증감’은 그날 사라진 매물(광고 기간만료 제외)을 직전 3주 같은 요일 평균과 비교한 값이다. "
    "‘신규 유입 정상 대비’는 그날의 매물 순증가율을 직전 3주 같은 요일쌍 평균으로 나눈 값으로, "
    "100%면 평소와 같다. 각 비율 아래 작은 숫자는 해당 건수이며, 정상 대비 분수는 "
    "‘그날 유입 / 평소라면 들어왔을 유입’이다(평소 유입률을 그 주 재고에 적용해 환산). "
    "1일차는 8월 3일 대비 4일, 2일차는 4일 대비 5일 기준이며 요일 효과를 없애려 같은 요일끼리 비교했다. "
    "맨 오른쪽 ‘매물 회전’은 실질소멸 증감만 놓고 본 방향이다 — 신규 유입과 방향이 다른 칸도 있다.", "cap"))

A(Spacer(1, 8))
A(box(
    "<b>‘실매물’이란 — 같은 집을 여러 중개사가 올린 광고를 1건으로 합친 수</b><br/>"
    "네이버 부동산은 같은 주소·같은 호실의 매물을 여러 중개사무소가 올리면 이를 한 묶음으로 "
    "표시한다. 콕집은 그 묶음 크기(N)를 받아 <b>광고 1건을 1/N건으로 환산해 더한다</b>. "
    "10곳이 같은 집을 올렸으면 10건이 아니라 1건으로 센다.<br/>"
    f"현재 전국 아파트 매물은 <b>광고 {int(ADS):,}건 = 실매물 약 {int(UNITS):,}건</b>"
    f"(집 1채당 광고 {ADS/UNITS:.2f}건)이다. 묶음 크기는 1~126까지 있고 상한이 없어 "
    "환산이 한쪽으로 치우치지 않는다.<br/>"
    "· <b>주의</b> — 한 집에 붙은 광고 10건 중 1건만 내려가면 집이 사라진 것은 아니지만 "
    "0.1건 사라진 것으로 센다. 재고·소멸·유입을 모두 같은 방식으로 환산했으므로 "
    "<b>증감률과 정상 대비 비율은 그대로 비교할 수 있다.</b>", WARNBG, WARNLN))

A(Spacer(1, 8))
A(box(
    "<b>이틀째에 드러난 것 — 방향이 갈렸다</b><br/>"
    f"· <b>5분위(최고가)</b>는 매매 소멸이 {d1('매매','5분위','chg')}%에서 "
    f"{d2('매매','5분위','chg')}%로, 전세는 {d1('전세','5분위','chg')}%에서 "
    f"{d2('전세','5분위','chg')}%로 <b>이틀째 더 깊어졌다</b>. 신규 유입은 매매가 "
    f"{d1('매매','5분위','norm')}%→{d2('매매','5분위','norm')}%로 다소 돌아왔지만, "
    f"<b>전세는 {d1('전세','5분위','norm')}%→{d2('전세','5분위','norm')}%로 이틀 연속 "
    "평소의 절반 수준</b>에 머물렀다.<br/>"
    f"· <b>2분위</b>는 매매 소멸이 {d1('매매','2분위','chg')}%에서 "
    f"{d2('매매','2분위','chg')}%로 <b>감소에서 증가로 돌아섰고</b>, 전세도 "
    f"{d1('전세','2분위','chg')}%→{d2('전세','2분위','chg')}%로 전환했다. "
    f"신규 매물은 평소의 {d2('매매','2분위','norm')}%(매매)·"
    f"{d2('전세','2분위','norm')}%(전세)로 오히려 늘었다.<br/>"
    f"· <b>1분위</b> 전세·월세 신규 유입은 평소의 {d2('전세','1분위','norm')}%·"
    f"{d2('월세','1분위','norm')}%로 크게 늘었다(다만 하루 수십 건 규모라 진폭이 크다).<br/>"
    f"· <b>전국 합계</b>는 매매 {d1('매매','전국','chg')}%→{d2('매매','전국','chg')}%로 "
    "거의 변화가 없다. 전체 숫자만 보면 '그대로'지만, 그 안에서 고가와 중저가가 "
    "<b>반대 방향으로 움직여 서로를 상쇄</b>하고 있다."))

# ── 2 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("2. 왜 고가만 더 멈추나", "h"))
A(P(
    "이번 개편안의 부동산 항목은 대부분 <b>고가 주택과 조정대상지역</b>에 집중돼 있다. "
    "종합부동산세 과세 기준은 1세대 1주택 공시가격 14억원(시가 약 20억원), 그 외 9억원이며, "
    "세율 인상 구간도 과세표준 12억원 초과부터다. 5분위에는 서울 강남·서초·송파·용산·성동구와 "
    "경기 과천시, 성남시 분당구 등이 포함된다."))
A(box(
    "<b>파는 쪽과 빌려주는 쪽이 동시에 멈췄다</b><br/>"
    "· <b>매도 보류</b> — 다주택자 조정대상지역 양도세 중과가 2027년 +5%p, 2028년 +10%p로 "
    "한시 완화된다(현행 +20%p). 2026년 양도분도 2027년 1월 1일 이후 신고하면 완화 세율이 "
    "적용돼, 올해 안에 서둘러 팔 이유가 사라졌다.<br/>"
    "· <b>전세 잠김</b> — 장기보유특별공제가 거주 중심으로 이원화되고(1세대 1주택 거주공제 "
    "연 8%·최대 80%, 2029년), 종부세 기본공제도 1주택 거주 14억원 / 비거주 9억원으로 갈린다. "
    "세제 혜택을 받으려면 본인이 들어가 살아야 하고, 그러면 그 집을 전세로 내놓을 수 없다.<br/>"
    f"→ 5분위 전세 신규 유입이 이틀 연속 평소의 {d2('전세','5분위','norm')}% 수준에 "
    f"머문 것은(매매는 {d2('매매','5분위','norm')}%로 회복) 이 방향과 맞는다. "
    "집주인이 들어가 살기로 하면 그 집은 전세로 나오지 않는다."))

# ── 3 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("3. 중저가는 왜 하루 만에 돌아왔나", "h"))
A(P(
    "1~3분위는 종부세 과세선(공시가격 9억원)과 장기보유특별공제 고가주택 기준에 대부분 "
    "걸리지 않는다. 발표 당일에는 시장 전체가 관망하며 함께 멈췄지만, 내용이 알려지자 "
    "<b>자기 구간에는 해당이 없다는 판단이 서면서 하루 만에 평소 흐름으로 돌아온 것</b>으로 "
    "보인다. 2분위 매매·전세가 감소에서 증가로 전환하고, 1분위 전세·월세 신규 매물이 평소를 "
    "크게 웃돈 것이 그 신호다."))

# ── 4 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h4 = [P("4. 최상위 지역 2일차 수치 (매매)", "h"),
       P("평당가 상위 10개 시군구의 8월 5일 개별 수치다. 시군구 단위는 표본이 작아 편차가 "
         "크므로 개별 값보다 분위 단위 추세로 읽는 것이 적절하다.")]
rows = [hdr(["지역", "평당가", "매매 매물", "실질소멸<br/>직전 3주 평균",
             "실질소멸<br/>8월 5일", "증감"])]
for r in TOP:
    rows.append([P(r["지역"], "tdl"), P(f"{n(PUB.get(r['지역'], r)['평당가만원'])}만", "td"),
                 P(n(r["매물수"]), "td"), P(n(r["실질소멸_3주평균"]), "td"),
                 P(n(r["실질소멸_당일"]), "td"),
                 P(f'{pc(r["소멸증감"])}<br/><font size=6.1 color="#6B7684">'
                   f'{sn(int(r["실질소멸_당일"]) - int(r["실질소멸_3주평균"]))}건</font>', "td")])
t = Table(rows, colWidths=[44 * mm, 21 * mm, 23 * mm, 29 * mm, 23 * mm, 28 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
]))
A(KeepTogether(_h4 + [t]))

# ── 5 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(KeepTogether([
    P("5. 해석 시 유의사항", "h"),
    box(
        "· <b>이틀치 관측이다.</b> 발표 다음 날과 이튿날을 각각 직전 3주 같은 요일과 비교한 "
        "결과로, 추세 확정에는 며칠간의 누적 확인이 필요하다.<br/>"
        "· <b>매도 보류와 매수 위축은 이 지표만으로 구분되지 않는다.</b> 매물이 덜 사라진 것이 "
        "파는 쪽이 멈춰서인지, 사는 쪽이 줄어서인지는 실거래 확정 후 판단이 가능하다.<br/>"
        "· <b>1·2분위는 표본이 작다.</b> 전세·월세는 하루 수십~수백 건이어서 증감률의 진폭이 "
        "크다. 해당 구간은 방향만 참고하는 것이 적절하다.<br/>"
        "· <b>실거래 통계로는 아직 확인할 수 없다.</b> 부동산 거래는 계약 후 30일 이내 신고여서 "
        "8월 초 계약분은 9월 초에야 집계가 채워진다. 일시적 2주택 특례 경과조치 기준일인 "
        "8월 3일 전후의 계약 변화도 그때 확인 가능하다.<br/>"
        "· <b>‘실질소멸’은 광고 기간만료를 뺀 수치다.</b> 네이버 부동산 광고는 확인일자로부터 "
        "31일이 지나면 자동으로 내려간다. 이 물량은 시장 상황과 무관하므로 전부 걷어낸 뒤 "
        "남은 건수만 셌다.<br/>"
        "· <b>개정 ‘안’이다.</b> 국회 논의 과정에서 내용이 바뀔 수 있다.", WARNBG, WARNLN),
]))
A(Spacer(1, 12))
A(P("런투온라인 대표 황인찬　|　부동산 데이터 서비스 ‘콕집’　<font color='#1268D3'>koczip.com</font>", "small"))
A(P("010-5942-8014　runtoonline@gmail.com", "small"))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="세제개편안 발표 이틀째 매물 시장 반응", author="런투온라인")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
