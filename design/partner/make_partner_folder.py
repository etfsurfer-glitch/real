# -*- coding: utf-8 -*-
"""콕집 인증 파트너 폴더파일(브로슈어) — 매물맛집·언제나 믿고가는 부동산(아산 탕정).
콕집 소개 + 파트너 사무소 홍보를 담은 2페이지 A4 PDF. reportlab canvas 직접 드로잉.
Run: python3 design/partner/make_partner_folder.py → design/partner/콕집_인증_믿고가는부동산.pdf
데이터(2026-07-07 DB 실측): 단지형 823개(매매665·전세98·월세60), 전국 3위·충남 1위.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "fonts"
OUT = HERE / "콕집_인증_믿고가는부동산.pdf"

pdfmetrics.registerFont(TTFont("P", str(FONTS / "Pretendard-Regular.ttf")))
pdfmetrics.registerFont(TTFont("PM", str(FONTS / "Pretendard-Medium.ttf")))
pdfmetrics.registerFont(TTFont("PS", str(FONTS / "Pretendard-SemiBold.ttf")))
pdfmetrics.registerFont(TTFont("PB", str(FONTS / "Pretendard-Bold.ttf")))
pdfmetrics.registerFont(TTFont("PX", str(FONTS / "Pretendard-ExtraBold.ttf")))

W, H = A4
BLUE = colors.HexColor("#1268D3")
BLUE_DK = colors.HexColor("#0C4EA0")
BLUE_SOFT = colors.HexColor("#E7F0FC")
GOLD = colors.HexColor("#F5A623")
GOLD_DK = colors.HexColor("#C97F12")
INK = colors.HexColor("#18233A")
GRAY = colors.HexColor("#5A6B80")
LGRAY = colors.HexColor("#8A99AC")
LIGHT = colors.HexColor("#F5F8FC")
LINE = colors.HexColor("#E2E9F2")
WHITE = colors.white


def logo(c, x0, y0, s, house=WHITE, check=BLUE):
    """콕집 로고(집+체크) — SVG viewBox 100 기준을 reportlab 좌표로 매핑."""
    def P(sx, sy):
        return (x0 + sx / 100 * s, y0 + (1 - sy / 100) * s)
    pts = [P(50, 10), P(92, 46), P(92, 92), P(8, 92), P(8, 46)]
    c.setFillColor(house)
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColor(check)
    c.setLineWidth(s * 0.10)
    c.setLineCap(1)
    c.setLineJoin(1)
    ck = [P(28, 58), P(44, 73), P(74, 42)]
    p2 = c.beginPath()
    p2.moveTo(*ck[0])
    p2.lineTo(*ck[1])
    p2.lineTo(*ck[2])
    c.drawPath(p2, fill=0, stroke=1)


def pill(c, x, y, w, h, text, fill, fg, font="PB", size=9, r=None):
    r = r if r is not None else h / 2
    c.setFillColor(fill)
    c.roundRect(x, y, w, h, r, fill=1, stroke=0)
    c.setFillColor(fg)
    c.setFont(font, size)
    c.drawCentredString(x + w / 2, y + h / 2 - size * 0.36, text)


def center(c, x, y, text, font, size, col):
    c.setFont(font, size)
    c.setFillColor(col)
    c.drawCentredString(x, y, text)


def fit_center(c, x, y, text, font, target, col, maxw):
    """maxw 안에 들어가도록 폰트 크기를 줄여 가운데 정렬."""
    size = target
    while size > 8 and pdfmetrics.stringWidth(text, font, size) > maxw:
        size -= 0.5
    center(c, x, y, text, font, size, col)
    return size


def left(c, x, y, text, font, size, col):
    c.setFont(font, size)
    c.setFillColor(col)
    c.drawString(x, y, text)


# ─────────────────────────────────────────────────────────── PAGE 1 (표지)
def page1(c):
    c.setFillColor(LIGHT)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # 상단 블루 헤더
    hh = 96 * mm
    c.setFillColor(BLUE)
    c.rect(0, H - hh, W, hh, fill=1, stroke=0)
    # 헤더 하단 골드 라인
    c.setFillColor(GOLD)
    c.rect(0, H - hh, W, 2.4 * mm, fill=1, stroke=0)

    # 로고 + 워드마크
    logo(c, W / 2 - 9 * mm, H - 30 * mm, 18 * mm)
    center(c, W / 2, H - 42 * mm, "콕집", "PX", 30, WHITE)
    center(c, W / 2, H - 50 * mm, "koczip.com", "PS", 11, colors.HexColor("#BBD6F5"))
    center(c, W / 2, H - 60 * mm, "부동산 매물 · 실거래 · 중개사 데이터 분석", "PM", 11.5,
           colors.HexColor("#DDEAFB"))

    # 인증 배지
    bw, bh = 78 * mm, 12 * mm
    pill(c, W / 2 - bw / 2, H - 82 * mm, bw, bh, "콕집 인증 파트너  ·  KOCZIP CERTIFIED",
         GOLD, colors.HexColor("#3A2600"), "PB", 11)

    # 사무소 소개 블록
    center(c, W / 2, H - hh - 15 * mm, "충청남도 아산 탕정 · 콕집 인증 중개사무소", "PS", 11, BLUE)
    fit_center(c, W / 2, H - hh - 29 * mm, "매물맛집.믿고가는부동산중개", "PX", 30, INK, W - 34 * mm)
    center(c, W / 2, H - hh - 39 * mm, "대표 김소연", "PM", 12.5, GRAY)

    # 실적 카드 2개
    cy = 92 * mm
    ch = 46 * mm
    gap = 6 * mm
    cw = (W - 2 * 22 * mm - gap) / 2
    x1 = 22 * mm
    x2 = x1 + cw + gap
    # 카드1 — 전국 3위 (블루)
    c.setFillColor(BLUE)
    c.roundRect(x1, cy, cw, ch, 6 * mm, fill=1, stroke=0)
    center(c, x1 + cw / 2, cy + ch - 12 * mm, "전국", "PS", 12, colors.HexColor("#CFE1FA"))
    center(c, x1 + cw / 2, cy + ch - 30 * mm, "3위", "PX", 40, WHITE)
    center(c, x1 + cw / 2, cy + 7 * mm, "단지형 부동산", "PM", 10.5, colors.HexColor("#DDEAFB"))
    # 카드2 — 충남 1위 (골드)
    c.setFillColor(GOLD)
    c.roundRect(x2, cy, cw, ch, 6 * mm, fill=1, stroke=0)
    center(c, x2 + cw / 2, cy + ch - 12 * mm, "충청남도", "PS", 12, colors.HexColor("#FFF3DC"))
    center(c, x2 + cw / 2, cy + ch - 30 * mm, "1위", "PX", 40, WHITE)
    center(c, x2 + cw / 2, cy + 7 * mm, "단지형 부동산", "PM", 10.5, colors.HexColor("#FFF3DC"))

    # 실적 부연 — 콕집 데이터 기준 순위(구체 수치 없이)
    center(c, W / 2, cy - 11 * mm, "콕집 데이터로 검증된 아산 탕정 대표 부동산", "PB", 14, INK)
    center(c, W / 2, cy - 18.5 * mm, "실거래·매물 데이터가 증명하는 지역 전문 중개사무소",
           "PM", 10.5, GRAY)

    # 하단 연락처 밴드
    fb = 34 * mm
    c.setFillColor(INK)
    c.rect(0, 0, W, fb, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, fb, W, 1.6 * mm, fill=1, stroke=0)
    center(c, W / 2, fb - 12 * mm, "041 - 545 - 5553      010 - 7772 - 1133", "PX", 19, WHITE)
    center(c, W / 2, fb - 20 * mm,
           "충청남도 아산시 탕정면 한들물빛도시로 70, D동 201호 (지웰시티센트럴푸르지오2단지 상가)",
           "PM", 9.5, colors.HexColor("#AEB9CC"))
    center(c, W / 2, fb - 26 * mm, "탕정 신도시 아파트 · 분양권 · 전월세 전문", "PS", 9.5,
           colors.HexColor("#7FA8E0"))


# ─────────────────────────────────────────────────────────── PAGE 2 (내용)
def section_head(c, x, y, kicker, title):
    c.setFillColor(BLUE)
    c.roundRect(x, y - 1 * mm, 4.5 * mm, 4.5 * mm, 1.2 * mm, fill=1, stroke=0)
    left(c, x + 8 * mm, y, kicker, "PS", 10, BLUE)
    left(c, x, y - 9 * mm, title, "PB", 16, INK)


def wrap(c, x, y, text, font, size, col, lead, maxw):
    c.setFont(font, size)
    c.setFillColor(col)
    words = text.split(" ")
    line = ""
    yy = y
    for w in words:
        t = (line + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) > maxw and line:
            c.drawString(x, yy, line)
            yy -= lead
            line = w
        else:
            line = t
    if line:
        c.drawString(x, yy, line)
    return yy


def page2(c):
    c.setFillColor(WHITE)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # 상단 얇은 블루 헤더
    hh = 30 * mm
    c.setFillColor(BLUE)
    c.rect(0, H - hh, W, hh, fill=1, stroke=0)
    logo(c, 20 * mm, H - 21 * mm, 12 * mm)
    left(c, 36 * mm, H - 15 * mm, "콕집이 인증한 부동산입니다", "PB", 16, WHITE)
    left(c, 36 * mm, H - 22 * mm, "데이터로 검증된 매물, 믿고 거래하세요", "PM", 10.5,
         colors.HexColor("#CFE1FA"))
    c.setFillColor(GOLD)
    c.rect(0, H - hh, W, 1.6 * mm, fill=1, stroke=0)

    mx = 20 * mm
    mw = W - 2 * mx
    y = H - hh - 16 * mm

    # 섹션 1 — 콕집이란?
    section_head(c, mx, y, "ABOUT KOCZIP", "콕집은 어떤 서비스인가요?")
    y -= 17 * mm
    wrap(c, mx, y,
         "콕집(koczip.com)은 전국 아파트·오피스텔 매물 184만 건과 국토교통부 실거래 신고 "
         "658만 건을 매일 함께 수집해 단지·면적 단위로 교차 분석하는 부동산 데이터 플랫폼입니다. "
         "‘지금 나온 호가’와 ‘실제 거래가’를 나란히 비교해, 어떤 매물이 진짜 싼지 데이터로 보여줍니다.",
         "P", 10.5, GRAY, 6 * mm, mw)
    y -= 20 * mm
    # 기능 칩 3개
    chips = [("급매찾기", "실거래보다 싼 매물"), ("우리동네 중개사", "매물·업력 랭킹"),
             ("매물 자가점검", "과태료 사전 예방")]
    cw = (mw - 2 * 5 * mm) / 3
    for i, (t, s) in enumerate(chips):
        cx = mx + i * (cw + 5 * mm)
        c.setFillColor(BLUE_SOFT)
        c.roundRect(cx, y - 14 * mm, cw, 14 * mm, 3 * mm, fill=1, stroke=0)
        center(c, cx + cw / 2, y - 6 * mm, t, "PB", 11.5, BLUE_DK)
        center(c, cx + cw / 2, y - 11 * mm, s, "PM", 8.5, GRAY)
    y -= 26 * mm

    # 섹션 2 — 콕집 인증의 의미
    section_head(c, mx, y, "WHY CERTIFIED", "‘콕집 인증’이 뜻하는 것")
    y -= 16 * mm
    bullets2 = [
        ("매물 표시·광고 자가점검 통과", "건축물대장과 대조해 층수·면적·사용승인일 등 법정 명시사항을 검증"),
        ("데이터로 검증되는 부동산 매물", "매물 정보가 콕집 데이터와 대조돼 신뢰도가 확인되는 사무소"),
        ("‘모르고 내는 과태료’ 사전 관리", "표시·광고 위반(건당 최대 500만원)을 미리 점검하는 성실 중개"),
    ]
    for t, s in bullets2:
        c.setFillColor(GOLD)
        c.circle(mx + 1.6 * mm, y + 1.2 * mm, 1.6 * mm, fill=1, stroke=0)
        left(c, mx + 6 * mm, y, t, "PB", 11, INK)
        left(c, mx + 6 * mm, y - 5 * mm, s, "PM", 9.3, GRAY)
        y -= 13 * mm
    y -= 3 * mm

    # 섹션 3 — 이 부동산과 거래하면 (정성적 가치)
    section_head(c, mx, y, "OUR PROMISE", "이 부동산과 거래하면")
    y -= 15 * mm
    promises = [
        ("실거래로 검증하는 시세 상담", "국토교통부 실거래 데이터로 적정 가격을 함께 확인하고 안내합니다."),
        ("정확한 매물 정보", "표시·광고를 성실히 관리하는, 허위·과장 없는 정직한 중개를 약속합니다."),
        ("아산 탕정 지역 전문", "매매·전세·월세·분양권까지, 지역을 가장 잘 아는 전문가가 직접 상담합니다."),
    ]
    rh = 17 * mm
    for i, (t, s) in enumerate(promises):
        by = y - i * rh
        c.setFillColor(LIGHT)
        c.roundRect(mx, by - rh + 3 * mm, mw, rh - 3 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(BLUE)
        c.circle(mx + 8 * mm, by - 4 * mm, 4 * mm, fill=1, stroke=0)
        center(c, mx + 8 * mm, by - 5.6 * mm, str(i + 1), "PB", 12, WHITE)
        left(c, mx + 17 * mm, by - 3 * mm, t, "PB", 11.5, INK)
        left(c, mx + 17 * mm, by - 9 * mm, s, "PM", 9.3, GRAY)
    y -= 3 * rh + 6 * mm

    # 하단 CTA 밴드
    fb = 26 * mm
    c.setFillColor(BLUE)
    c.roundRect(mx, 16 * mm, mw, fb, 4 * mm, fill=1, stroke=0)
    left(c, mx + 8 * mm, 16 * mm + fb - 10 * mm, "koczip.com에서 이 부동산 매물 전체 보기", "PB", 13, WHITE)
    left(c, mx + 8 * mm, 16 * mm + 7 * mm, "koczip.com  ·  검색창에 ‘매물맛집 믿고가는부동산’", "PM", 10.5,
         colors.HexColor("#CFE1FA"))
    logo(c, W - mx - 22 * mm, 16 * mm + 6 * mm, 14 * mm, house=WHITE, check=BLUE)

    center(c, W / 2, 9 * mm,
           "koczip.com · 운영 런투온라인   |   매물맛집.믿고가는부동산중개 · 041-545-5553",
           "PM", 8, LGRAY)


def main():
    c = canvas.Canvas(str(OUT), pagesize=A4)
    page1(c)
    c.showPage()
    page2(c)
    c.showPage()
    c.save()
    print("pdf:", OUT)


if __name__ == "__main__":
    main()
