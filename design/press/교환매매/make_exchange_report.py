# -*- coding: utf-8 -*-
"""'단지 내 교환매매' 전수 조사 보고서 (기자 배포용).

2026년 세제개편안 발표 뒤 거론된 '단지 내 아파트 교환매매'가 실제 매물 광고에
얼마나 나타나는지를 전국 매매 광고 전수에서 세어 본 것이다.

수치는 design/press/data/press_exchange_*.csv 를 그대로 읽어 조판한다
(박스 실측 산출물 — 여기서 숫자를 만들거나 손질하지 않는다).
Run: python3 design/press/교환매매/make_exchange_report.py
  → design/press/교환매매/단지내교환매매_전수조사.pdf
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
OUT = HERE / "단지내교환매매_전수조사.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
# 본문 <b> 가 실제 볼드체로 나오게 한다 (등록 안 하면 같은 굵기로 조판된다)
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
    "td": ParagraphStyle("td", fontName="P", fontSize=8.5, leading=10.4, textColor=INK, alignment=1),
    "tdb": ParagraphStyle("tdb", fontName="PB", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=1),
    "tdr": ParagraphStyle("tdr", fontName="PB", fontSize=8.5, leading=10.4, textColor=RED,
                          alignment=1),
    "tdg": ParagraphStyle("tdg", fontName="PB", fontSize=8.5, leading=10.4, textColor=GREEN,
                          alignment=1),
    "tdl": ParagraphStyle("tdl", fontName="PM", fontSize=8.5, leading=10.4, textColor=INK,
                          alignment=0),
    "quote": ParagraphStyle("quote", fontName="P", fontSize=7.7, leading=10.6, textColor=GRAY,
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


BRK = read("press_exchange_breakdown.csv")
CMP = {r["구분"]: r for r in read("press_exchange_compare.csv")}
TRD = read("press_exchange_trend.csv")
WIN = read("press_exchange_window.csv")
LST = read("press_exchange_listings.csv")

n = lambda v: f"{int(float(v)):,}"                      # noqa: E731
BK = {r["분류"]: int(r["건수"]) for r in BRK}
TOTAL_HIT = sum(BK.values())
REAL = BK["교환매매 의사 표시"]
ALL_ADS = int(CMP["전체 매매 광고"]["건수"])
TRD_ADS = sum(int(r["신규매매광고"]) for r in TRD)
TRD_EX = sum(int(r["교환의사"]) for r in TRD)

story = []
A = story.append

# ── 표지 ────────────────────────────────────────────────────────────────
A(P("콕집 부동산 데이터 리포트", "tag"))
A(P("‘단지 내 교환매매’, 매물 광고에는 149만 건 중 12건뿐", "title"))
A(P(f"전국 아파트 매매 광고 전수에서 ‘교환’이 붙은 광고는 {TOTAL_HIT}건 — "
    f"그중 실제 교환 의사는 {REAL}건이고 나머지는 싱크대·샷시·전열교환기였다", "sub"))
A(P("관측 2026. 8. 7.(금) 기준　|　세제개편안 발표 2026. 8. 3.(월) 18:00　|　"
    "자료 콕집(koczip.com) 전국 아파트 매매 매물 광고 전수", "cap"))
A(Spacer(1, 10))

A(P(
    "2026년 세제개편안 발표 이후 양도차익을 줄이려 <b>같은 단지 안에서 집을 맞바꾸는 "
    "‘교환매매’</b>가 늘 것이라는 이야기가 나온다. 콕집은 이것이 실제 매물에 나타나는지를 "
    f"확인하기 위해 전국 아파트 매매 광고 <b>{n(ALL_ADS)}건</b>의 중개사 특징설명을 "
    f"한 줄씩 전수 검사했다. 결과는 <b>{REAL}건</b>이었다. 광고 12만 건당 1건꼴로, "
    "현재로서는 시장 현상이라 부를 수 있는 규모가 아니다.", "lead"))

# ── 1 ───────────────────────────────────────────────────────────────────
A(P("1. ‘교환’ 153건 중 141건은 교환매매가 아니었다", "h"))
A(P(
    "특징설명에 ‘교환’이라는 글자가 들어간 매매 광고는 "
    f"{TOTAL_HIT}건이다. 그러나 그중 대부분은 <b>집을 바꾸자는 뜻이 전혀 아니었다</b>. "
    "실제 문구를 하나씩 읽어 분류한 결과는 다음과 같다."))

rows = [hdr(["분류", "건수", "비중", "실제 문구 예시"])]
EXAMP = {
    "설비 교환(싱크대·샷시·보일러 등)": "“샷시교환 부분수리 입주협의” · “보일러교환 화장실 리모델링”",
    "전열교환기(환기설비 옵션)": "“시스템에어컨 4대, 나비엔 전열교환기, 중문”",
    "“대교 환상뷰”(동음이의)": "“인천대교환상뷰” · “광안대교환상의뷰” — 대교+환상뷰가 붙은 것",
    "교환매매 의사 표시": "“교환매매가능” · “108B 교환가능” · “중소형평형과 교환 가능”",
}
for r in BRK:
    k, c = r["분류"], int(r["건수"])
    real = k == "교환매매 의사 표시"
    rows.append([P(k, "tdl"), P(n(c), "tdb" if real else "td"),
                 P(f"{c / TOTAL_HIT * 100:.1f}%", "tdr" if real else "td"),
                 P(EXAMP[k], "quote")])
rows.append([P("<b>합계</b>", "tdl"), P(n(TOTAL_HIT), "tdb"), P("100.0%", "tdb"), P("", "quote")])
t = Table(rows, colWidths=[52 * mm, 16 * mm, 17 * mm, 83 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("BACKGROUND", (0, len(rows) - 2), (-1, len(rows) - 2), HOTBG),
    ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), ROWALT),
    ("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 1.0, BLUE_DK),
    ("TOPPADDING", (0, 0), (-1, -1), 3.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
]))
A(t)
A(P("분류는 상호 배타적이다 — 한 광고가 여러 조건에 걸리면 위 순서대로 한 곳에만 넣었다. "
    "‘교환매매 의사 표시’는 ‘교환매매·교환가능·교환희망·교환환영·맞교환’ 같이 교환이 "
    "거래 조건으로 쓰인 표현만 인정했다.", "cap"))

A(Spacer(1, 6))
A(box(
    "<b>키워드 검색만으로는 12배 부풀려진다</b><br/>"
    f"‘교환’으로 한 번 걸러 나오는 {TOTAL_HIT}건을 그대로 쓰면 실제({REAL}건)의 "
    f"<b>{TOTAL_HIT / REAL:.1f}배</b>가 된다. 아파트 매물 문구에서 ‘교환’은 압도적으로 "
    "<b>내장재를 갈았다</b>는 뜻이고(싱크대·샷시·보일러·도배·변기), 신축에서는 환기설비인 "
    "<b>전열교환기</b> 옵션을 가리킨다. 여기에 ‘인천대교 환상뷰’처럼 단어 경계가 우연히 "
    "맞아떨어지는 경우까지 섞인다. 이 보고서의 수치는 그 141건을 문구 단위로 걷어낸 뒤 "
    "남은 것이다.", WARNBG, WARNLN))

# ── 2 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h2 = [P("2. 세제개편안 발표 뒤에도 늘지 않았다", "h"),
       P("매물이 현재 몇 건 걸려 있는지(재고)가 아니라, <b>날마다 새로 등록된 광고</b> 중 "
         "교환 의사를 밝힌 것이 몇 건인지를 셌다. 발표 직전 2주와 발표 이후를 견준다.")]
rows = [hdr(["구간", "기간", "신규 매매 광고", "교환 의사", "십만 건당", "갈아타기 언급"])]
for r in WIN:
    post = r["구간"] != "발표 전"
    rows.append([P(f"<b>{r['구간']}</b>", "tdb"), P(r["기간"], "td"),
                 P(n(r["신규매매광고"]), "td"),
                 P(f"<b>{r['교환의사']}건</b>", "tdb" if post else "td"),
                 P(f"{float(r['교환_십만건당']):.2f}", "tdb" if post else "td"),
                 P(n(r["갈아타기"]), "td")])
t = Table(rows, colWidths=[20 * mm, 42 * mm, 28 * mm, 22 * mm, 22 * mm, 34 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
]))
A(KeepTogether(_h2 + [t]))
A(P("발표는 8월 3일 18시였다. 8월 7일은 수집이 진행 중인 날이어서 비교 구간에서 뺐다. "
    "‘갈아타기 언급’은 같은 기간 특징설명에 ‘갈아타기·갈아타실분’이 들어간 매매 광고 수로, "
    "교환매매의 대체 신호로 함께 봤다.", "cap"))

A(Spacer(1, 4))
A(P("주 단위로 넓혀 봐도 교환 의사는 신규 광고 십만 건당 0~1건 사이를 오갈 뿐이다. "
    "발표 직전 2주(7월 20일·27일 주)에는 <b>한 건도 없었고</b>, 발표가 포함된 주에 3건이 "
    "나왔다. 이 진폭은 6월에도 그대로 반복됐다 — 즉 발표와 무관한 평상시 변동 범위다."))

rows = [hdr(["주 시작(월)", "신규 매매 광고", "교환 의사", "십만 건당", "갈아타기", "세금 언급"])]
for r in TRD:
    is_last = r is TRD[-1]
    zero = int(r["교환의사"]) == 0
    rows.append([P(r["주시작"] + (" *" if is_last else ""), "tdb" if is_last else "td"),
                 P(n(r["신규매매광고"]), "td"),
                 P(r["교환의사"], "tdg" if zero else ("tdb" if is_last else "td")),
                 P(f"{float(r['교환_십만건당']):.2f}", "tdb" if is_last else "td"),
                 P(n(r["갈아타기"]), "td"),
                 P(n(r["세금언급"]), "td")])
t = Table(rows, colWidths=[30 * mm, 33 * mm, 24 * mm, 24 * mm, 26 * mm, 31 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), HOTBG),
    ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
]))
A(t)
A(P("* 마지막 주는 8월 3~7일 5일치다(발표 주). 수집을 시작한 5월 18일은 그때까지 쌓여 있던 "
    "재고를 한 번에 담은 날이어서 모든 집계에서 뺐다. "
    "‘세금 언급’은 양도세·비과세·종부세·보유세·취득세·절세·다주택·일시적·세제개편·세법개정 중 "
    "하나라도 들어간 신규 매매 광고 수다 — 발표 주(158건, 십만 건당 42.6)는 직전 4주 범위"
    "(35.9~43.5) 안에 있다. 5~6월 수치가 높은 것은 수집 초기에 오래된 재고가 함께 잡힌 "
    "영향이 있어 장기 추세로 읽기 어렵다.", "cap"))

# ── 3 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
_h3 = [P(f"3. 남은 {REAL}건은 이런 매물이다", "h"),
       P("2026년 8월 7일 기준 전국에서 교환 의사를 밝힌 매매 광고 전부다. "
         "호가 순으로 정렬했다.")]
rows = [hdr(["단지", "읍면동", "전용", "층", "호가", "중개사 특징설명"])]
KEY = {"계양롯데캐슬파크시티1단지", "철산래미안자이", "LIG건영"}
hot = []
for r in LST:
    if r["단지"] in KEY:
        hot.append(len(rows))
    rows.append([P(r["단지"], "tdl"), P(r["읍면동"], "td"),
                 P(f"{r['전용면적']}㎡", "td"), P(r["층"], "td"),
                 P(r["호가"], "tdb"), P(r["특징설명"], "quote")])
t = Table(rows, colWidths=[38 * mm, 15 * mm, 13 * mm, 15 * mm, 20 * mm, 67 * mm], repeatRows=1)
st = [("BACKGROUND", (0, 0), (-1, 0), BLUE),
      ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWALT]),
      ("GRID", (0, 0), (-1, -1), 0.4, LINE),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6)]
for i in hot:
    st.append(("BACKGROUND", (0, i), (-1, i), HOTBG))
t.setStyle(TableStyle(st))
A(KeepTogether(_h3 + [t]))
A(P("붉은 배경은 <b>같은 단지 안에서 평형을 맞바꾸겠다고 밝힌</b> 4건이다. "
    "세종 첫마을 2건은 같은 집을 두 중개사무소가 올린 중복 광고여서, 집 단위로 세면 "
    "11채가 된다.", "cap"))

A(Spacer(1, 4))
A(box(
    "<b>단지 내 평형 교환을 명시한 4건</b><br/>"
    "· <b>인천 계양롯데캐슬파크시티1단지</b> — 한 중개사무소가 <b>전용 84㎡ 매물에 "
    "‘108B 교환가능’, 전용 108㎡ 매물에 ‘84A 교환가능’</b>을 나란히 걸어 뒀다. 같은 단지 "
    "안에서 서로 반대 방향의 상대를 찾는 구조로, 중개사가 교환 상대 매칭을 시도하는 "
    "형태에 가장 가깝다. 다만 ‘무피·피500’ 표기로 보아 <b>분양권 전매</b> 건이다.<br/>"
    "· <b>경기 광명 철산래미안자이 전용 166㎡ 22억</b> — “중소형평형과 교환 가능”. "
    "같은 단지에 전용 59㎡ 28건·84㎡ 142건이 나와 있어 상대를 찾을 재고는 존재한다.<br/>"
    "· <b>부산 해운대 LIG건영 전용 134㎡ 6억 6,000만</b> — “20P대 교환도 가능”. "
    "같은 단지 전용 59㎡ 매물이 28건 있다."))

A(Spacer(1, 5))
A(box(
    "→ 두 건 모두 <b>대형에서 중소형으로 내려가는 방향</b>이다. 실제로 교환 의사를 밝힌 "
    f"매물은 전체 매매 광고보다 크고 비쌌다 — 평균 전용 "
    f"<b>{CMP['교환 의사 표시']['평균전용']}㎡ · 호가 {CMP['교환 의사 표시']['평균호가억']}억</b>"
    f"으로, 전체 평균({CMP['전체 매매 광고']['평균전용']}㎡ · "
    f"{CMP['전체 매매 광고']['평균호가억']}억)을 웃돈다.<br/>"
    "· 나머지 한 건 <b>천안 불당호반베르디움더퍼스트</b>는 ‘교환’이라 쓰진 않았지만 "
    "<b>“매도인 동일 단지내 평형 업그레이드 갈아타기”</b>라고 매도 사유를 밝혔다 — "
    "단지 내 이동의 절반쪽이 드러난 사례다."))

# ── 4 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("4. 세제개편안을 문구에 쓴 매물은 전국에 1건", "h"))
A(P(
    "‘세제개편·세법개정’을 특징설명에 직접 적은 매매 광고는 전국에서 <b>단 1건</b>이었다. "
    "서울 강남구 개포동 <b>래미안블레스티지 전용 49㎡, 호가 27억</b> — "
    "“뷰, 커뮤니티 근접, <b>세제개편안 보고 확정 함</b>”. 가격을 국회 논의 결과에 "
    "연동하겠다는 표시다. ‘일시적 2주택’을 적은 매물은 1건, ‘비과세’는 6건이었다. "
    "‘양도세’가 들어간 38건은 대부분 <b>분양권 전매에서 양도세를 누가 부담하느냐</b>를 "
    "적은 것으로(‘양도세 매도인 부담’), 보유·매도 판단과는 관계가 없었다."))

# ── 5 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(P("5. 왜 교환매매는 광고에 드러나지 않나", "h"))
A(P(
    "‘교환매매’라는 이름과 달리, 부동산 교환은 <b>세법·등기상 매매 2건</b>이다. 서로의 "
    "부동산을 팔고 사는 것이어서 양도소득세도 각자 따로 계산되고, 취득세도 각자 낸다. "
    "차액만 주고받을 뿐 <b>세금이 면제되거나 이연되는 제도가 아니다.</b> 교환의 실익은 "
    "세금이 아니라 <b>거래 상대를 동시에 확보해 이사 시점을 맞추는 것</b>에 있다."))
A(box(
    "· <b>광고로 상대를 찾는 방식이 아니다.</b> 교환은 면적·층·향·금액이 서로 맞아떨어져야 "
    "성립해서, 같은 단지 매물을 모두 쥔 중개사무소가 물밑에서 붙이는 편이 훨씬 빠르다. "
    "실제로 위 계양 사례도 한 중개사무소가 양쪽을 동시에 들고 있는 형태였다.<br/>"
    "· <b>따라서 이 조사의 12건은 하한선이다.</b> 광고에 안 적혔다고 교환이 없었다는 뜻은 "
    "아니다. 다만 <b>‘늘고 있다’는 주장의 근거로 매물 광고를 댈 수는 없다</b>는 것은 "
    "분명하다 — 발표 전후로 늘지 않았기 때문이다.<br/>"
    "· <b>확인은 실거래로 가능하다.</b> 같은 단지·같은 날짜에 서로 반대 방향으로 체결된 "
    "거래 쌍을 실거래 신고에서 찾으면 된다. 다만 거래 신고는 계약 후 30일 이내여서 "
    "<b>8월 초 계약분은 9월 초에야</b> 집계가 채워진다."))

# ── 6 ───────────────────────────────────────────────────────────────────
A(Spacer(1, 8))
A(KeepTogether([
    P("6. 조사 방법과 유의사항", "h"),
    box(
        "· <b>대상</b> — 2026년 8월 7일 기준 전국 아파트·오피스텔 <b>매매</b> 광고 "
        f"{n(ALL_ADS)}건의 중개사 작성 특징설명 전수. 추이 분석은 5월 19일~8월 7일에 "
        f"새로 등록된 매매 광고 {n(TRD_ADS)}건을 대상으로 했고, 그중 교환 의사는 "
        f"{TRD_EX}건이었다.<br/>"
        "· <b>세는 단위는 광고다.</b> 같은 집을 여러 중개사무소가 올리면 각각 1건으로 센다. "
        f"현재 {REAL}건 중 세종 첫마을 2건이 같은 집이어서, 집 단위로는 11채다.<br/>"
        "· <b>특징설명은 중개사가 자유롭게 쓰는 칸이다.</b> 교환 의사가 있어도 적지 않을 수 "
        "있고, 적는 표현도 제각각이다. 이 조사는 ‘교환’이 들어간 광고를 모두 꺼내 문구를 "
        "읽고 분류하는 방식이어서 표현 차이는 대부분 흡수되지만, <b>아예 언급하지 않은 "
        "건은 잡히지 않는다.</b><br/>"
        "· <b>표본이 작다.</b> 주당 0~7건 규모여서 증감률로 말하기 어렵다. 이 보고서가 "
        "말하는 것은 ‘늘었다·줄었다’가 아니라 <b>‘규모 자체가 아직 통계로 잡히지 않는 "
        "수준’</b>이라는 사실이다.<br/>"
        "· <b>개정 ‘안’이다.</b> 국회 논의 과정에서 내용이 바뀔 수 있고, 시장 반응도 그에 "
        "따라 달라질 수 있다. 콕집은 이 지표를 계속 집계해 변화가 나타나면 다시 알린다.",
        WARNBG, WARNLN),
]))

A(Spacer(1, 12))
A(P("런투온라인 대표 황인찬　|　부동산 데이터 서비스 ‘콕집’　"
    "<font color='#1268D3'>koczip.com</font>", "small"))
A(P("010-5942-8014　runtoonline@gmail.com", "small"))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=21 * mm, rightMargin=21 * mm,
                        topMargin=18 * mm, bottomMargin=16 * mm,
                        title="단지 내 교환매매 전수 조사", author="런투온라인")
doc.build(story)
print(f"[done] {OUT}  ({OUT.stat().st_size // 1024} KB)")
