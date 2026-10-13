# -*- coding: utf-8 -*-
"""카드뉴스 v2 — 실제 출력물 모음 PDF.

목업이 아니라 생성기가 **방금 실제로 뽑은** PNG 를 그대로 싣는다.
cards/ 아래의 <key>.png 를 읽어 카드 한 장당 한 쪽으로 조판한다.

실행: python3 design/cardnews_v2/make_gallery.py
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as RLImage, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "shots"
FONTS = HERE.parent / "fonts"
OUT = HERE / "콕집_카드뉴스v2_실제출력물.pdf"

INK = colors.HexColor("#16202e")
MUTE = colors.HexColor("#6b7280")
FAINT = colors.HexColor("#9ca3af")
LINE = colors.HexColor("#e3e8ee")
BRAND = colors.HexColor("#1268d3")
SOFT = colors.HexColor("#e8f0ff")

for nm, fn in (("P", "Pretendard-Regular.ttf"), ("P-B", "Pretendard-Bold.ttf"),
               ("P-M", "Pretendard-Medium.ttf"), ("P-EB", "Pretendard-ExtraBold.ttf")):
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="P-B", italic="P", boldItalic="P-B")

ss = getSampleStyleSheet()


def st(name, size, font="P", lead=None, color=INK, space=0, align=0):
    return ParagraphStyle(name, parent=ss["Normal"], fontName=font, fontSize=size,
                          leading=lead or size * 1.6, textColor=color,
                          spaceAfter=space, alignment=align)


TITLE = st("t", 23, "P-EB", lead=30, space=4)
LEAD = st("l", 11.5, "P-M", lead=19, color=BRAND, space=4)
H1 = st("h1", 16, "P-EB", lead=23, space=3)
BODY = st("b", 10.2, "P", lead=17.5, space=6)
NOTE = st("n", 9, "P", lead=14.5, color=MUTE, space=4)
CAP = st("cap", 8.8, "P-M", lead=13, color=FAINT, space=2)
CELL = st("c", 8.8, "P", lead=13)
CELLW = st("cw", 8.8, "P-B", lead=13, color=colors.white)

PW = A4[0] - 36 * mm

# 카드 한 장당: (파일키, 제목, 무엇을 보는 카드인가, 이번에 달라진 점)
CARDS = [
    ("deal", "오늘의 급매", "오늘 새로 올라온 매물 중 같은 단지·평형 실거래 평균보다 싼 것",
     "1위를 전폭으로 키웠다. 낙폭이 가장 큰 건이 왕관을 쓴다."),
    ("record", "신고가 경신", "직전 최고가를 깨고 팔린 아파트",
     "금액에 상승 빨강을 쓰는 몇 안 되는 카드다 — 여기선 색이 방향을 뜻한다."),
    ("market", "오늘의 시장", "매매·전세 매물 수와 평균 호가를 나란히",
     "사진 없는 카드. 얇은 색 리본 아래 흰 바탕에 검은 제목으로 간다."),
    ("volume", "거래량 상위 단지", "최근 손바뀜이 많았던 단지",
     "거래가 가장 많은 단지가 1위 칸을 차지한다."),
    ("apply", "청약 일정", "이번 주 아파트 청약(청약홈)",
     "왕관이 등수가 아니라 '접수 진행중'·'오늘 접수' 같은 마감 상태를 적는다."),
    ("remndr", "무순위 줍줍", "무순위·잔여세대 모집(청약홈)",
     "분양가는 먹색, 접수 상태만 색을 가져간다. 예전엔 둘 다 빨강·파랑이었다."),
    ("calendar", "이달의 부동산 달력", "청약·발표·임대 일정을 한 달 달력에",
     "범례 세 색(청약·당첨발표·임대마감)은 의미를 지므로 브랜드 색으로 합치지 않았다."),
    ("gap", "분양가 시세 비교", "분양가와 주변 실거래 평당가를 견줌",
     "콕집만 자동으로 만들 수 있는 카드. 1위 개념이 없어 격자를 유지한다."),
    ("lh", "LH 임대", "행복주택·국민임대·매입임대 모집",
     "큰 숫자 자리에 금액 대신 마감 D-day 가 들어간다."),
    ("news", "부동산 뉴스", "오늘의 부동산 기사 목록",
     "기사 사진이 없는 줄에도 브랜드 타일을 깔아 줄 높이를 맞췄다."),
    ("newsTop", "헤드라인 뉴스", "기사 한 건을 사진 전면으로",
     "유일하게 사진이 카드 전면을 쓰는 형식이다."),
]

S = []
A = S.append

meta = {}
mp = SHOTS / "meta.json"
if mp.exists():
    meta = json.loads(mp.read_text())

have = [c for c in CARDS if (SHOTS / f"{c[0]}.png").exists()]
miss = [c for c in CARDS if not (SHOTS / f"{c[0]}.png").exists()]

# ── 표지 ──────────────────────────────────────────────────────────────────
A(Paragraph("카드뉴스 v2 — 실제 출력물", TITLE))
A(Paragraph(f"koczip.com/admin/cardnews-v2 · 2026년 10월 13일 · {len(have)}종", LEAD))
A(Spacer(1, 2 * mm))
t = Table([[""]], colWidths=[PW], rowHeights=[2.2], hAlign="LEFT")
t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK)]))
A(t)
A(Spacer(1, 5 * mm))

A(Paragraph(
    "목업이 아니다. 오늘 개선을 끝낸 생성기로 <b>방금 실제로 뽑은 PNG</b> 를 그대로 실었다. "
    "숫자·단지명·일정은 전부 그 시점의 실데이터다.", BODY))

A(Spacer(1, 3 * mm))
A(Paragraph("오늘 바뀐 것", H1))
rows = [[Paragraph(x, CELLW) for x in ("", "전", "후")]]
for a, b, c in [
    ("프로필 격자(1:1)", "출처·배지·브랜드가 전부 잘려 나감", "제목부터 koczip.com 까지 전부 생존"),
    ("색", "같은 분양가가 접수중이면 빨강, D-4면 파랑", "등락만 빨강·파랑 / 상태는 앰버·회색"),
    ("카드 강조색", "종류마다 다른 색(앰버·보라·초록…)", "전부 콕집 블루 #1268d3"),
    ("배경 사진", "AI 렌더 4장, 16:9 를 잘라 써 윗절반이 하늘", "신축 단지 실사풍 4장, 띠 비율로 미리 크롭"),
    ("워터마크", "@koczip 7개가 단지명·금액 위에 겹침", "없앰 — 브랜드는 칩과 하단 줄이 짐"),
    ("순위 표현", "여섯 칸이 전부 같은 크기", "1위 전폭 + 나머지 2×2"),
    ("하단", "노란 경고 박스 + 꼬리말 + 그라디언트 띠 3층", "세로줄 인용구 + 선 하나 1층"),
]:
    rows.append([Paragraph(f"<b>{a}</b>", CELL), Paragraph(b, CELL), Paragraph(c, CELL)])
tb = Table(rows, colWidths=[30 * mm, 59 * mm, 59 * mm], hAlign="LEFT", repeatRows=1)
cmds = [("FONT", (0, 0), (-1, -1), "P", 8.8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), BRAND)]
for i in range(2, len(rows), 2):
    cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f3f7fe")))
tb.setStyle(TableStyle(cmds))
A(tb)

if miss:
    A(Spacer(1, 4 * mm))
    A(Paragraph(
        "<b>이번에 못 뽑은 카드</b> — " +
        ", ".join(f"{m[1]}" for m in miss) +
        ". 오늘 자 재료가 모자라 생성기가 거부했다(카드가 요구하는 최소 건수 미달). "
        "디자인 문제가 아니라 데이터 문제다.", NOTE))

A(PageBreak())

# ── 카드 한 장당 한 쪽 ────────────────────────────────────────────────────
IMG_W = PW
for key, name, what, changed in have:
    p = SHOTS / f"{key}.png"
    from PIL import Image as PILImage
    iw, ih = PILImage.open(p).size
    # 설명 블록을 남기고 남는 높이에 맞춘다
    max_h = A4[1] - 31 * mm - 52 * mm
    w = min(IMG_W, max_h * iw / ih)
    img = RLImage(str(p), width=w, height=w * ih / iw)
    img.hAlign = "CENTER"

    A(Paragraph(name, H1))
    A(Paragraph(what, NOTE))
    A(Spacer(1, 3 * mm))
    A(img)
    A(Spacer(1, 3 * mm))
    tag = meta.get(key, {})
    foot = changed
    if tag.get("folder"):
        foot += f"  <font color='#9ca3af'>· {tag['folder']} · {tag.get('label', '')}</font>"
    A(Paragraph(foot, CAP))
    A(PageBreak())

if S and isinstance(S[-1], PageBreak):
    S.pop()

doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                        leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=14 * mm,
                        title="콕집 카드뉴스 v2 실제 출력물", author="콕집")
doc.build(S)
print("wrote", OUT, f"({len(have)} cards)")
