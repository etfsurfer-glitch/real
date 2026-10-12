# -*- coding: utf-8 -*-
"""카드뉴스 v2 이미지 개선안 → PDF 조판.

근거 이미지는 ev/ 아래의 **실제 출력물 크롭**이다(mkcrops 로 생성, 손으로 안 그림).
본문에서 지목하는 코드 위치는 nfind 박스 /opt/koczip-carosell 기준이다.

실행: python3 design/cardnews_v2/make_review.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image as RLImage, KeepTogether,
                                PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
EV = HERE / "ev"
FONTS = HERE.parent / "fonts"
OUT = HERE / "콕집_카드뉴스v2_이미지개선안.pdf"

INK = colors.HexColor("#1b2430")
MUTE = colors.HexColor("#5b6775")
LINE = colors.HexColor("#d9e0e8")
BRAND = colors.HexColor("#1268d3")
BAD = colors.HexColor("#b3261e")
GOOD = colors.HexColor("#0f7b4f")
BAND = colors.HexColor("#f2f7ff")
WARM = colors.HexColor("#fff8e8")

for nm, fn in (("P", "Pretendard-Regular.ttf"), ("P-B", "Pretendard-Bold.ttf"),
               ("P-M", "Pretendard-Medium.ttf"), ("P-EB", "Pretendard-ExtraBold.ttf")):
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
# <b> 가 먹으려면 패밀리 등록이 필요하다 — 안 하면 조용히 무시된다
pdfmetrics.registerFontFamily("P", normal="P", bold="P-B", italic="P", boldItalic="P-B")
pdfmetrics.registerFontFamily("P-M", normal="P-M", bold="P-B", italic="P-M", boldItalic="P-B")

ss = getSampleStyleSheet()


def st(name, size, font="P", lead=None, color=INK, space=0, align=0, left=0):
    return ParagraphStyle(name, parent=ss["Normal"], fontName=font, fontSize=size,
                          leading=lead or size * 1.6, textColor=color,
                          spaceAfter=space, alignment=align, leftIndent=left)


TITLE = st("t", 23, "P-EB", lead=30, space=4)
LEAD = st("l", 11.5, "P-M", lead=19, color=BRAND, space=4)
H1 = st("h1", 15, "P-EB", lead=22, space=8)
H2 = st("h2", 12, "P-B", lead=18, space=5)
BODY = st("b", 10.2, "P", lead=17.5, space=6)
NOTE = st("n", 9, "P", lead=14.5, color=MUTE, space=4)
CAP = st("cap", 8.6, "P-M", lead=13, color=MUTE, space=2)
CELL = st("c", 8.8, "P", lead=13)
CELLB = st("cb", 8.8, "P-B", lead=13)
CELLW = st("cw", 8.8, "P-B", lead=13, color=colors.white)

PW = A4[0] - 36 * mm          # 본문 폭


def p(txt, s=BODY):
    return Paragraph(txt, s)


def pic(name, w=PW, cap=None):
    """근거 이미지 — 폭을 본문에 맞추고 비율을 지킨다."""
    from PIL import Image as PILImage
    src = EV / name
    iw, ih = PILImage.open(src).size
    img = RLImage(str(src), width=w, height=w * ih / iw)
    img.hAlign = "LEFT"
    out = [img]
    if cap:
        out += [Spacer(1, 2.5 * mm), p(cap, CAP)]
    return out


def twocol(a, b):
    """근거 이미지 두 장을 나란히 — 세로로 쌓으면 장이 넘어가 한 장이 비어 버린다."""
    from PIL import Image as PILImage
    w = (PW - 6 * mm) / 2
    cells, caps = [], []
    for name, cap in (a, b):
        iw, ih = PILImage.open(EV / name).size
        img = RLImage(str(EV / name), width=w, height=w * ih / iw)
        img.hAlign = "LEFT"
        cells.append(img)
        caps.append(Paragraph(cap, CAP))
    t = Table([cells, caps], colWidths=[w, w], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 6 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [t]


def table(rows, widths, head=True, zebra=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1 if head else 0)
    cmds = [
        ("FONT", (0, 0), (-1, -1), "P", 8.8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
    ]
    if head:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), BRAND),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.8, BRAND)]
    if zebra:
        for i in range(2 if head else 1, len(rows), 2):
            cmds.append(("BACKGROUND", (0, i), (-1, i), BAND))
    t.setStyle(TableStyle(cmds))
    return t


def head(*cols):
    return [Paragraph(c, CELLW) for c in cols]


def box(flow, bg=WARM, border=colors.HexColor("#f0d9a8")):
    t = Table([[flow]], colWidths=[PW], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def rule(h=1.4, color=INK):
    t = Table([[""]], colWidths=[PW], rowHeights=[h], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color)]))
    return t


def section(no, title, lead):
    """문제 한 건의 머리 — 번호·제목·한 줄 요약.
    CondPageBreak 으로 자리가 모자랄 때만 장을 넘긴다(고정 PageBreak 은 빈 장을 만든다)."""
    return [CondPageBreak(62 * mm), Spacer(1, 4 * mm), rule(1.2, BRAND), Spacer(1, 2.5 * mm),
            p(f"{no}. {title}", H1), p(lead, LEAD)]


S = []
A = S.append

# ══════════════════════════════════════════════════════════════════════════
# 표지
# ══════════════════════════════════════════════════════════════════════════
A(p("카드뉴스 v2 이미지 개선안", TITLE))
A(p("koczip.com/admin/cardnews-v2 · 2026년 10월 13일", LEAD))
A(Spacer(1, 2 * mm))
A(rule(2.2))
A(Spacer(1, 5 * mm))

A(p(
    "최근 25건의 출력물을 전부 열어 보고 렌더러(<b>lib/render/onepage.js</b>)와 "
    "카드 빌더(<b>lib/compose/cards.js</b>)를 읽었다. 조판 자체는 탄탄하다 — "
    "숫자가 크고, 칸 수에 따라 글자 크기가 따라 움직이고, 넘침 방지도 들어가 있다. "
    "고칠 것은 <b>조판이 아니라 '한 장이 피드에서 어떻게 읽히는가'</b> 쪽에 몰려 있다.", BODY))

A(box([
    p("핵심 세 줄", H2),
    p("① <b>인스타 프로필 격자에서 브랜드가 통째로 사라진다.</b> 1:1 중앙 크롭이 "
      "위아래 135px 씩 잘라내는데, 하단 브랜드바(koczip.com)가 정확히 그 안에 있다.", BODY),
    p("② <b>카드 종류가 달라도 그림이 같다.</b> 청약·줍줍·거래량이 같은 사진, 같은 격자, "
      "같은 노란 박스다. 연달아 올리면 같은 글을 두 번 올린 것처럼 보인다.", BODY),
    p("③ <b>빨강·파랑이 두 가지 뜻으로 쓰인다.</b> 시장 카드에서는 등락인데, "
      "청약 카드에서는 접수 임박 여부다. 한 계정 안에서 색이 거짓말을 한다.", BODY),
], bg=BAND, border=colors.HexColor("#bcd6f5")))

A(Spacer(1, 6 * mm))
A(p("우선순위", H1))
A(p("‘효과’는 피드에서 눈에 띄는 정도, ‘비용’은 손대는 범위다. "
    "①~④ 는 CSS·상수만 고치면 되는데 효과가 가장 크다.", NOTE))

rows = [head("#", "항목", "효과", "비용", "손대는 곳")]
for r in [
    ("1", "1:1 크롭에서 브랜드 생존", "매우 큼", "낮음", "onepage.js 레이아웃"),
    ("2", "카드 종류별 시각 신호 분리", "매우 큼", "중간", "onepage.js + cards.js"),
    ("3", "색 의미 분리(등락 ↔ 상태)", "큼", "낮음", "cards.js 326행 등"),
    ("4", "워터마크 7개 → 1개", "큼", "낮음", "onepage.js watermarks()"),
    ("5", "히어로 사진 재설계·애셋 교체", "큼", "중간", "assets/bg + bgFor()"),
    ("6", "1위 강조(격자 → 포디움)", "중간", "낮음", "cards.js 카드별 format"),
    ("7", "제목 서체·그림자 정리", "중간", "낮음", "onepage.js CSS"),
    ("8", "뉴스 줄 높이·썸네일 폴백", "중간", "중간", "onepage.js .ni"),
    ("9", "하단 3층 구조 압축", "중간", "낮음", "onepage.js bottomBar"),
    ("10", "규격 확장(1:1 · 9:16)", "중간", "높음", "onepage.js + 렌더 파이프"),
]:
    eff = BAD if r[2] == "매우 큼" else (BRAND if r[2] == "큼" else MUTE)
    rows.append([p(f"<b>{r[0]}</b>", CELL), p(r[1], CELLB),
                 Paragraph(f'<font color="{eff.hexval()}"><b>{r[2]}</b></font>', CELL),
                 p(r[3], CELL), p(r[4], CELL)])
A(Spacer(1, 3 * mm))
A(table(rows, [10 * mm, 54 * mm, 20 * mm, 16 * mm, 48 * mm]))

A(PageBreak())

# ══════════════════════════════════════════════════════════════════════════
# 1. 1:1 크롭
# ══════════════════════════════════════════════════════════════════════════
S += section("1", "프로필 격자에서 브랜드가 사라진다",
             "효과 매우 큼 · 비용 낮음 · onepage.js 레이아웃")

A(p("카드는 1080×1350(4:5)이다. 그런데 인스타 프로필 격자와 대부분의 미리보기는 "
    "<b>1:1 중앙 크롭</b>으로 보여 준다 — 위 135px, 아래 135px 이 잘린다. "
    "지금 그 안에 들어 있는 것은:", BODY))
A(p("· 위: 출처 표기(* 출처 : 청약홈 …), 카테고리 배지, @koczip 배지<br/>"
    "· 아래: <b>브랜드바 전체(콕집어 주는 부동산뉴스 / koczip.com)</b>, 꼬리말", BODY))
A(p("즉 <b>격자에서는 콕집이라는 글자가 한 번도 안 보인다.</b> 남는 건 5.5% 투명도의 "
    "워터마크뿐인데 그건 읽히지 않는다. 출처 표기가 잘리는 것도 좋지 않다.", BODY))
A(Spacer(1, 3 * mm))
S += twocol(("ev_crop.png", "빨간 영역이 1:1 격자에서 잘려 나가는 자리."),
            ("ev_brandbar.png", "잘려 나가는 하단부. 브랜딩이 가장 또렷한 구간이다."))

A(Spacer(1, 4 * mm))
A(p("개선", H2))
A(p("· <b>안전 영역을 레이아웃 규칙으로 못 박는다.</b> 상·하 135px 은 ‘잘려도 되는 것’만 "
    "둔다(배경 사진의 여백, 장식). 출처·브랜드는 그 안쪽으로 옮긴다.", BODY))
A(p("· <b>브랜드 표식을 세로 중앙대로 이동.</b> 하단 브랜드바는 그대로 두되, "
    "히어로 띠 우측에 <b>koczip.com 배지</b>를 하나 더 둔다(현재 @koczip 배지 자리를 "
    "‘@koczip · koczip.com’ 으로 합친다). y=135~1215 안에 있으므로 격자에서도 살아남는다.", BODY))
A(p("· <b>출처 줄을 히어로 사진 안쪽 아래로.</b> 지금은 사진 맨 위 모서리라 잘리는 데다 "
    "흰 글씨 21px 이 하늘 위에 얹혀 대비도 약하다.", BODY))

# ══════════════════════════════════════════════════════════════════════════
# 2. 카드 종류별 구분
# ══════════════════════════════════════════════════════════════════════════
S += section("2", "카드 종류가 달라도 그림이 같다",
             "효과 매우 큼 · 비용 중간 · onepage.js + cards.js")

A(p("아래는 <b>무순위 줍줍</b>(10/13)과 <b>청약 일정</b>(10/8)이다. 다른 것은 제목 글자와 "
    "배지 텍스트뿐이고, 사진·격자·칩·노란 박스·브랜드바가 전부 같다. "
    "피드를 내리는 사람에게 이 둘은 같은 게시물이다.", BODY))
A(Spacer(1, 3 * mm))
S += pic("ev_same.png", w=PW * 0.88, cap="좌: 무순위 줍줍 / 우: 청약 일정. 배경 사진까지 같은 날짜 풀에서 나온다.")

A(Spacer(1, 4 * mm))
A(p("왜 이렇게 됐나", H2))
A(p("배경은 <b>날짜</b>로만 돌아간다 — <b>cards.js</b>의 "
    "<font name='P-B'>bgFor(date, idx)</font> 가 "
    "<font name='P-B'>BG_POOL[(dayNo + idx) % 4]</font> 를 쓴다. "
    "한 장짜리 모드는 항상 idx=0 이라 <b>같은 날 만든 카드는 종류가 달라도 사진이 같다.</b> "
    "배경이 카드 주제를 전혀 안 가리킨다.", BODY))

A(Spacer(1, 3 * mm))
A(p("개선 — 카드마다 ‘서명’을 준다", H2))
A(p("색 하나만 바꾸는 걸로는 부족하다. 세 축(배경 계열 · 강조색 · 골격)을 묶어 "
    "타입별 세트로 고정한다.", BODY))

rows = [head("카드", "배경 계열", "강조색", "골격")]
for r in [
    ("오늘의 급매", "해질녘 단지 · 저채도", "코발트 블루", "포디움(1위 강조)"),
    ("신고가 경신", "맑은 낮 · 고채도", "레드", "포디움"),
    ("청약 일정", "아침 · 신축 외관", "브랜드 블루", "격자 2×3"),
    ("무순위 줍줍", "야간 · 조명 켜진 동", "앰버/오렌지", "격자 2×3 + 마감 타이머"),
    ("오늘의 시장", "사진 없음 · 그래프 지면", "먹색 + 블루", "병렬 빅넘버"),
    ("부동산 달력", "사진 없음 · 종이 질감", "보라", "달력"),
    ("부동산 뉴스", "기사 사진", "먹색", "목록"),
]:
    rows.append([p(r[0], CELLB), p(r[1], CELL), p(r[2], CELL), p(r[3], CELL)])
A(table(rows, [30 * mm, 48 * mm, 30 * mm, 40 * mm]))

A(Spacer(1, 3 * mm))
A(box([p("줍줍을 <b>야간 + 앰버</b>로 돌리는 것만으로도 청약 카드와 즉시 구분된다. "
         "주제도 맞다 — ‘남은 물량, 마감 임박’ 이라는 성격이 밝은 아침 사진과 안 어울린다.", BODY)]))


# ══════════════════════════════════════════════════════════════════════════
# 3. 색 의미
# ══════════════════════════════════════════════════════════════════════════
S += section("3", "빨강·파랑이 두 가지 뜻으로 쓰인다",
             "효과 큼 · 비용 낮음 · cards.js")

A(p("아래 네 칸은 전부 <b>분양가</b>다. 왼쪽 위만 빨강이고 나머지는 파랑이다. "
    "가격이 높아서가 아니라 <b>오늘 접수냐 아니냐</b>로 갈린 것이다.", BODY))
A(Spacer(1, 3 * mm))
S += pic("ev_color.png",
         cap="같은 값(분양가)인데 색이 다르다. 색이 가리키는 것은 가격이 아니라 D-day 다.")

A(Spacer(1, 3 * mm))
A(p("원인은 <b>cards.js 326행</b>이다.", BODY))
A(box([p("<font name='P-B'>chipDir: it.dday &lt;= 3 ? 'up' : 'down'</font>", CELL),
       p("‘급하다’를 등락 팔레트(up=빨강 / down=파랑)에 그대로 꽂았다. "
         "렌더러는 이 값을 칩 색과 <b>금액 색</b>에 동시에 쓴다.", NOTE)],
      bg=colors.HexColor("#fdf0ef"), border=colors.HexColor("#f0c4c0")))

A(Spacer(1, 2 * mm))
A(p("문제는 같은 계정의 <b>오늘의 시장</b> 카드가 빨강=상승, 파랑=하락으로 쓴다는 것이다. "
    "한쪽에서 색을 배운 사람이 다른 쪽에서 반대로 읽는다. "
    "D-6 이 연한 파랑이라 ‘내렸다’로 보이는 것도 같은 이유다.", BODY))

A(Spacer(1, 3 * mm))
A(p("개선 — 팔레트를 둘로 쪼갠다", H2))
rows = [head("쓰임", "지금", "바꿀 것")]
for r in [
    ("등락(시장·신고가·급매)", "빨강 / 파랑", "그대로 — 이것만 빨강·파랑을 쓴다"),
    ("접수 상태(청약·줍줍·LH)", "빨강 / 파랑 전용", "오늘=앰버, D-3 이내=브랜드 블루, 그 외=회색"),
    ("금액 숫자", "상태에 따라 색이 변함", "항상 먹색 — 숫자는 색으로 말하지 않는다"),
    ("칩", "up/down/flat 3종", "urgent/soon/normal 3종을 따로 둔다"),
]:
    rows.append([p(r[0], CELLB), p(r[1], CELL), p(r[2], CELL)])
A(table(rows, [40 * mm, 48 * mm, 60 * mm]))
A(Spacer(1, 2 * mm))
A(p("금액을 먹색으로 통일하면 손해 보는 것 같지만, 오히려 칩(접수중 / D-6)이 "
    "유일한 색이 되어 시선이 거기로 간다. 지금은 숫자와 칩이 같은 색이라 서로 먹는다.", NOTE))


# ══════════════════════════════════════════════════════════════════════════
# 4. 워터마크
# ══════════════════════════════════════════════════════════════════════════
S += section("4", "워터마크 7개가 숫자 위에 얹혀 있다",
             "효과 큼 · 비용 낮음 · onepage.js watermarks()")

A(p("<font name='P-B'>watermarks()</font> 가 @koczip 을 7곳에 −14° 로 뿌린다. "
    "자리를 내용과 맞춰 보지 않아 단지명·금액 위에 바로 올라간다.", BODY))
A(Spacer(1, 3 * mm))
S += pic("ev_wm.png", w=PW * 0.8,
         cap="‘도안 푸르지오 디아델 31블록’ 글자 위에 워터마크가 정확히 겹친다.")

A(Spacer(1, 3 * mm))
A(p("5.5% 투명도라 원본에서는 희미하지만, 인스타 재압축을 거치면 얼룩으로 드러난다. "
    "도난 방지 효과도 크지 않다 — 이미 배지·브랜드바·사이트 주소로 "
    "<b>한 장에 브랜드가 세 번</b> 박혀 있다.", BODY))
A(Spacer(1, 2 * mm))
A(p("개선", H2))
A(p("· 7개 → <b>1개</b>. 위치는 우하단 여백 한 곳, 내용 영역 밖.<br/>"
    "· 투명도는 5.5% → <b>9%</b>로 올리되 겹치지 않으므로 더 깨끗하다.<br/>"
    "· 또는 전부 빼고, 1번 항목에서 추가할 <b>중앙대 koczip.com 배지</b>로 대체한다. "
    "읽히는 브랜드 하나가 안 읽히는 일곱보다 낫다.", BODY))

A(Spacer(1, 5 * mm))

# ══════════════════════════════════════════════════════════════════════════
# 5. 히어로 사진
# ══════════════════════════════════════════════════════════════════════════
S += section("5", "히어로 사진 330px 의 절반이 하늘이다",
             "효과 큼 · 비용 중간 · assets/bg + bgFor()")

A(p("카드 높이의 <b>24%</b>를 사진이 쓴다. 그런데 지금 그 자리에 담기는 것은:", BODY))
A(Spacer(1, 2.5 * mm))
S += pic("ev_hero.png", cap="실제로 렌더되는 띠 1080×330. 위쪽 절반이 하늘과 건물 상단이다.")

A(Spacer(1, 3 * mm))
A(p("원본은 16:9 가로 사진인데 <b>1080×330(3.3:1)</b> 로 잘라 쓴다. "
    "<font name='P-B'>background-position: center 62%</font> 라 건물 중단이 걸리고, "
    "제목이 올라가는 왼쪽 위는 거의 빈 하늘이다. "
    "사진 네 장이 전부 비슷한 각도·비슷한 낮 시간이라 바꿔도 티가 안 난다.", BODY))

A(Spacer(1, 3 * mm))
A(p("개선", H2))
A(p("· <b>3.3:1 전용 애셋을 만든다.</b> 지금은 16:9 를 잘라 쓰는 중이라 구도가 맞을 수가 없다. "
    "가로로 긴 화면에 맞춰 스카이라인이 아래쪽 1/3 에 오도록 생성한다.", BODY))
A(p("· <b>왼쪽 45%는 비워 둔다(네거티브 스페이스).</b> 제목이 거기 앉는다. "
    "지금은 제목이 건물 위에 겹쳐 그림자로 버티고 있다.", BODY))
A(p("· <b>타입별 세트로 나눈다</b>(2번 항목의 표). 종류×시간대 조합으로 12~15장이면 "
    "한 달 내내 안 겹친다.", BODY))
A(p("· 띠 높이를 330 → <b>300px</b>로 줄여 격자에 30px 을 돌려준다(격자 글자가 한 단계 커진다).", BODY))


# ══════════════════════════════════════════════════════════════════════════
# 6~9 묶음
# ══════════════════════════════════════════════════════════════════════════
S += section("6", "6칸이 똑같아서 ‘1위’가 1위로 안 보인다",
             "효과 중간 · 비용 낮음 · cards.js 카드별 format")

A(p("격자 2×3 은 여섯 칸이 같은 크기·같은 테두리·같은 반경이다. 순번 배지만 다르다. "
    "눈이 어디부터 봐야 할지 모른다.", BODY))
A(Spacer(1, 2.5 * mm))
S += pic("ev_flat.png", w=PW * 0.74,
         cap="1번과 6번의 시각적 무게가 같다. 순위 정보가 디자인에 반영되지 않았다.")

A(Spacer(1, 3 * mm))
A(p("<b>이미 해법이 코드에 있다.</b> <font name='P-B'>podium</font> 포맷(1위 전폭 + 나머지 격자)이 "
    "구현돼 있는데 <b>급매 카드에만</b> 걸려 있고, 급매는 최근 25건 중 한 번도 생성되지 않았다. "
    "청약·줍줍·거래량·신고가에 포디움을 적용하면 코드를 새로 짤 일이 없다.", BODY))
A(Spacer(1, 2 * mm))
A(p("다만 청약·줍줍은 ‘순위’가 아니라 ‘일정’이다. 1위 자리에는 "
    "<b>가장 임박한 건</b>을 올리고 왕관 라벨을 ‘오늘 마감’ / ‘D-1’ 로 바꾼다.", BODY))

A(Spacer(1, 5 * mm))
S += section("7", "제목 서체와 그림자가 ‘자동 생성’ 티를 낸다",
             "효과 중간 · 비용 낮음 · onepage.js CSS")

A(p("제목은 <b>Black Han Sans</b> + <font name='P-B'>text-shadow: 6px 6px 0 rgba(17,24,39,.14)</font> 다. "
    "두 가지가 문제다.", BODY))
A(p("· Black Han Sans 는 굵기가 하나뿐인 무료 폰트로, 한국어 자동 생성 카드뉴스에서 "
    "가장 흔하게 쓰인다. 서체 자체가 ‘기계가 만든 것’ 이라는 신호다.<br/>"
    "· 14% 짜리 6px 오프셋 그림자는 입체로 보이지도, 깔끔하지도 않다. 글자 모서리만 흐려진다.", BODY))
A(Spacer(1, 2 * mm))
A(p("개선", H2))
A(p("· 제목을 <b>Pretendard 900</b> + 자간 −0.045em 로 바꾸고 그림자를 뺀다. "
    "본문과 같은 가족이라 카드가 한 벌로 묶인다.<br/>"
    "· 입체감이 필요하면 그림자 대신 <b>제목 뒤 색 블록</b>(핵심 단어에 형광 밑줄/박스)을 쓴다. "
    "이미 <font name='P-B'>accentTitle()</font> 이 숫자·TOP N 을 잡아내고 있으니 "
    "그 span 에 배경만 주면 된다.<br/>"
    "· 사진 위 제목에는 그림자 대신 <b>사진 자체를 더 어둡게</b>(5번의 네거티브 스페이스) 간다.", BODY))


S += section("8", "뉴스 카드의 줄 높이가 들쭉날쭉하다",
             "효과 중간 · 비용 중간 · onepage.js .ni")

A(p("기사 썸네일이 있는 줄과 없는 줄이 섞인다. 썸네일이 없으면 본문이 폭 전체로 퍼져 "
    "줄마다 글자 길이가 달라지고, 오른쪽 가장자리가 톱니처럼 된다.", BODY))
A(Spacer(1, 2.5 * mm))
S += pic("ev_news.png", w=PW * 0.66,
         cap="1번 줄만 썸네일이 없다. 오른쪽 라인이 맞지 않고 1번 줄만 비어 보인다.")

A(Spacer(1, 3 * mm))
A(p("개선", H2))
A(p("· <b>썸네일 폴백을 만든다.</b> 기사 사진이 없으면 브랜드 패턴 타일(카드 타입 색 + 콕집 "
    "마크)을 넣는다. 자리는 항상 차지한다.<br/>"
    "· 또는 <b>한 장 안에서는 전원 텍스트</b>로 통일한다 — 한 줄이라도 썸네일이 비면 "
    "그 카드는 썸네일을 아예 안 쓴다.<br/>"
    "· 세로 사진이 들어오면 <font name='P-B'>object-fit</font> 특성상 인물 얼굴이 잘린다"
    "(10/12 카드의 3번 줄). 얼굴 중심 크롭 대신 상단 정렬로 바꾼다.", BODY))

A(Spacer(1, 5 * mm))
S += section("9", "하단 3층(노란 박스 + 꼬리말 + 브랜드바)이 220px 을 먹는다",
             "효과 중간 · 비용 낮음 · onepage.js bottomBar")

A(p("세 블록이 세로로 쌓여 카드의 <b>16%</b>를 쓴다. 게다가 "
    "노란 박스는 ‘주의/경고’ 색인데 거기 들어가는 내용은 경고가 아니라 "
    "요약 한 줄이다(‘청약통장 없이 넣을 수 있는 무순위 물량이에요’).", BODY))
A(Spacer(1, 2 * mm))
A(p("개선", H2))
A(p("· 노란 박스 → <b>왼쪽 굵은 세로줄 + 흰 바탕</b>의 인용구로. 색은 카드 타입 강조색을 쓴다.<br/>"
    "· 꼬리말(출처 보조)을 브랜드바 안 왼쪽으로 합쳐 한 층을 없앤다.<br/>"
    "· 돌려받은 ~60px 을 격자에 준다. 칸이 커지면 금액 글자도 같이 커진다"
    "(<font name='P-B'>valueSize()</font> 가 칸 수 기준이므로 패딩만 늘려도 여유가 생긴다).", BODY))


S += section("10", "규격이 1080×1350 하나뿐이다",
             "효과 중간 · 비용 높음 · 렌더 파이프라인")

A(p("지금은 4:5 한 가지만 나온다. v1(/admin/cardnews)은 1:1 도 지원했는데 v2 에서 빠졌다. "
    "필요한 규격은 넷이다.", BODY))
rows = [head("규격", "쓰는 곳", "지금", "필요한 손질")]
for r in [
    ("1080×1350 (4:5)", "인스타 피드", "있음", "안전 영역 규칙 추가(1번)"),
    ("1080×1080 (1:1)", "프로필 격자 · 블로그 · 오픈그래프", "없음", "격자 2×2 로 줄인 변형"),
    ("1080×1920 (9:16)", "스토리 · 릴스 커버 · 쇼츠", "없음", "세로 1열 + 큰 숫자"),
    ("1200×630", "링크 미리보기(OG)", "없음", "제목+숫자 하나만"),
]:
    rows.append([p(r[0], CELLB), p(r[1], CELL), p(r[2], CELL), p(r[3], CELL)])
A(table(rows, [34 * mm, 48 * mm, 16 * mm, 50 * mm]))
A(Spacer(1, 2 * mm))
A(p("렌더러가 이미 <font name='P-B'>.card</font> 단위 스크린샷이라 "
    "<font name='P-B'>W/H</font> 를 인자로 받고 격자 열 수만 분기하면 된다. "
    "다만 글자 크기 상수가 전부 4:5 기준으로 손으로 맞춰져 있어 규격마다 재조정이 필요하다 "
    "— 그래서 비용이 높다.", NOTE))

A(Spacer(1, 6 * mm))

# ══════════════════════════════════════════════════════════════════════════
# 애셋 제작
# ══════════════════════════════════════════════════════════════════════════
A(PageBreak())
A(rule(1.2, BRAND))
A(Spacer(1, 2.5 * mm))
A(p("애셋 제작 계획", H1))
A(p("힉스필드 / 아트리스트로 생성 · 총 15장 + 패턴 4종", LEAD))

A(p("지금 배경은 <b>네 장</b>이고 전부 비슷한 낮·비슷한 각도의 생성 이미지다. "
    "새로 만들 때 중요한 것은 ‘예쁜 사진’이 아니라 <b>한 벌로 보이는 규칙</b>이다. "
    "아래 다섯 가지를 전 장에 고정한다.", BODY))

rows = [head("고정값", "지정")]
for r in [
    ("화면비", "3.3:1 (1080×330 전용). 16:9 를 잘라 쓰지 않는다"),
    ("구도", "스카이라인이 아래 1/3. 왼쪽 45% 는 하늘·여백(제목 자리)"),
    ("카메라", "지상 눈높이, 광각 아님. 드론 부감은 쓰지 않는다 — 제목 자리가 안 나온다"),
    ("색온도", "타입별 시간대 고정(아침 5600K / 해질녘 3200K / 야간 2800K)"),
    ("채도", "저채도 통일. 강조색은 UI(칩·배지)가 맡는다"),
]:
    rows.append([p(r[0], CELLB), p(r[1], CELL)])
A(Spacer(1, 2 * mm))
A(table(rows, [24 * mm, 114 * mm]))

A(Spacer(1, 4 * mm))
A(p("장수 배분", H2))
rows = [head("용도", "장수", "방향")]
for r in [
    ("청약 일정", "3", "아침 햇살, 신축 단지 외관, 입주 전 깨끗한 조경"),
    ("무순위 줍줍", "3", "야간, 일부 세대만 불 켜진 동 — ‘남은 물량’ 의 은유"),
    ("신고가 · 거래량", "3", "맑은 낮, 고층 밀집, 멀리 트인 시야"),
    ("오늘의 급매", "3", "해질녘, 저채도, 약간 가라앉은 톤"),
    ("LH · 임대", "3", "오후, 중저층 단지와 생활 동선(상가·버스 정류장)"),
    ("패턴 타일", "4", "사진 아닌 기하 패턴 — 뉴스 썸네일 폴백·시장·달력 카드용"),
]:
    rows.append([p(r[0], CELLB), p(r[1], CELL), p(r[2], CELL)])
A(table(rows, [30 * mm, 14 * mm, 94 * mm]))

A(Spacer(1, 3 * mm))
A(box([
    p("프롬프트 뼈대(공통 꼬리를 붙여 쓴다)", H2),
    p("<font name='P-B'>Korean apartment complex, {시간대}, eye-level wide shot, "
      "skyline occupying lower third, empty sky across left half, desaturated color grade, "
      "no text, no people, cinematic, 3.3:1 ultrawide</font>", CELL),
    p("‘no text’ 는 반드시 넣는다 — 생성 이미지에 가짜 한글 간판이 박히면 그대로 못 쓴다. "
      "생성 후 왼쪽 45% 에 실제로 여백이 있는지 눈으로 확인하고 고른다.", NOTE),
]))

A(Spacer(1, 3 * mm))
A(p("<b>검수 기준</b> — ① 왼쪽 45% 에 글자를 올렸을 때 읽히는가 ② 네 장을 나란히 놓았을 때 "
    "한 벌로 보이는가 ③ 1:1 로 잘랐을 때도 말이 되는가. 셋 중 하나라도 걸리면 버린다.", BODY))


# ══════════════════════════════════════════════════════════════════════════
# 적용 순서
# ══════════════════════════════════════════════════════════════════════════
A(CondPageBreak(70 * mm))
A(p("적용 순서", H1))
A(p("애셋 없이 먼저 할 수 있는 것부터", LEAD))

rows = [head("차수", "할 일", "애셋", "결과")]
for r in [
    ("1차", "① 1:1 안전 영역 · ③ 색 분리 · ④ 워터마크 · ⑦ 제목 · ⑨ 하단 압축",
     "없음", "격자에서 브랜드가 보이고, 색이 거짓말을 안 한다"),
    ("2차", "⑥ 포디움 확대 · ⑧ 뉴스 폴백 · ② 타입별 강조색·골격",
     "패턴 4종", "카드 종류가 섞여도 구분된다"),
    ("3차", "⑤ 배경 애셋 교체 · ② 타입별 배경 세트",
     "15장", "자동 생성 티가 사라진다"),
    ("4차", "⑩ 1:1 · 9:16 · OG 규격", "기존 재사용", "스토리·블로그·링크 미리보기까지 한 번에"),
]:
    rows.append([p(f"<b>{r[0]}</b>", CELL), p(r[1], CELL), p(r[2], CELLB), p(r[3], CELL)])
A(Spacer(1, 2 * mm))
A(table(rows, [13 * mm, 60 * mm, 17 * mm, 48 * mm]))

A(Spacer(1, 5 * mm))
A(p("덧붙여 — 디자인 밖의 두 가지", H2))
A(p("· <b>카드 11종 중 5종만 쓰인다.</b> 최근 25건은 줍줍·뉴스·청약·시장·달력뿐이고 "
    "급매·신고가·거래량·분양가비교·LH 는 한 번도 안 나왔다. "
    "가장 공들인 포디움 레이아웃이 그중 급매에만 걸려 있어 사실상 죽은 코드다. "
    "데이터가 안 모이는 것인지, 손이 안 가는 것인지 확인이 필요하다.", BODY))
A(p("· <b>생성기 소스가 레포에 없다.</b> /opt/koczip-carosell 은 git 저장소가 아니다. "
    "이번 개선으로 CSS 를 크게 손대면 되돌릴 방법이 없으므로, "
    "작업 전에 레포로 올리거나 최소한 박스에서 git init 을 한다.", BODY))

A(Spacer(1, 8 * mm))
A(rule(0.8, LINE))
A(Spacer(1, 2 * mm))
A(p("콕집 · koczip.com · 2026.10.13 · 근거 이미지는 최근 출력물 원본 크롭", NOTE))

doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                        leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=16 * mm, bottomMargin=15 * mm,
                        title="콕집 카드뉴스 v2 이미지 개선안", author="콕집")
doc.build(S)
print("wrote", OUT)
