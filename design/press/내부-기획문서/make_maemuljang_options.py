# -*- coding: utf-8 -*-
"""매물장 개선안 4가지 — 비교 PDF.

같은 내용의 웹 버전과 짝이다(아티팩트). 인쇄해서 놓고 고르라고 만든 것이라
목업은 화면을 그대로 그리지 않고 '무엇이 어떻게 보이는지'가 전달되는 선까지만 그린다.
Run: python3 design/press/내부-기획문서/make_maemuljang_options.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
OUT = HERE / "매물장_개선안_4가지.pdf"

for nm, fn in [("P", "Pretendard-Regular.ttf"), ("PM", "Pretendard-Medium.ttf"),
               ("PS", "Pretendard-SemiBold.ttf"), ("PB", "Pretendard-Bold.ttf"),
               ("PX", "Pretendard-ExtraBold.ttf")]:
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))

W, H = A4
M = 17 * mm                      # 좌우 여백
NAVY = (0x15 / 255, 0x31 / 255, 0x5E / 255)
BLUE = (0x12 / 255, 0x68 / 255, 0xD3 / 255)
SALE = (0xD2 / 255, 0x3B / 255, 0x3B / 255)
WOLSE = (0x1A / 255, 0x7F / 255, 0x4B / 255)
WARN = (0xB4 / 255, 0x53 / 255, 0x09 / 255)
INK = (0x16 / 255, 0x20 / 255, 0x2E / 255)
INK2 = (0x2C / 255, 0x3A / 255, 0x4D / 255)
MUT = (0x6B / 255, 0x72 / 255, 0x80 / 255)
LINE = (0xE3 / 255, 0xE8 / 255, 0xEE / 255)
LINE2 = (0xEE / 255, 0xF1 / 255, 0xF5 / 255)
STRIPE = (0xFA / 255, 0xFB / 255, 0xFC / 255)
TINT = (0xF3 / 255, 0xF7 / 255, 0xFE / 255)
SOFT = (0xE8 / 255, 0xF0 / 255, 0xFF / 255)

TRADE_COLOR = {"매매": SALE, "전세": BLUE, "월세": WOLSE}


class Doc:
    def __init__(self, path):
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.y = H - M
        self.page = 1

    # ── 기본 도구 ────────────────────────────────────────────
    def need(self, h):
        """남은 높이가 부족하면 새 쪽으로. 표·목업이 쪽을 걸치지 않게 한다."""
        if self.y - h < M + 12 * mm:
            self.footer()
            self.c.showPage()
            self.page += 1
            self.y = H - M
            return True
        return False

    def footer(self):
        c = self.c
        c.setFont("P", 7.5)
        c.setFillColorRGB(*MUT)
        c.drawString(M, M - 4 * mm, "콕집 · 매물장 개선안")
        c.drawRightString(W - M, M - 4 * mm, f"{self.page}")

    def text(self, s, size=9.5, font="P", color=INK2, dy=5.2 * mm, x=None, lead=None):
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*color)
        self.c.drawString(x if x is not None else M, self.y, s)
        self.y -= (lead or dy)

    def wrap(self, s, size=9.5, font="P", color=INK2, width=None, lead=4.9 * mm, x=None):
        """폭에 맞춰 접어 쓰기. 한국어라 어절 단위로 자른다."""
        width = width or (W - 2 * M)
        x = M if x is None else x
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*color)
        line, out = "", []
        for w in s.split(" "):
            t = (line + " " + w).strip()
            if pdfmetrics.stringWidth(t, font, size) > width and line:
                out.append(line)
                line = w
            else:
                line = t
        if line:
            out.append(line)
        for ln in out:
            self.c.drawString(x, self.y, ln)
            self.y -= lead
        return len(out)

    def rule(self, gap=3 * mm):
        self.c.setStrokeColorRGB(*LINE)
        self.c.setLineWidth(0.5)
        self.c.line(M, self.y, W - M, self.y)
        self.y -= gap

    def box(self, x, y, w, h, fill=None, stroke=LINE, r=2.4 * mm, lw=0.6):
        c = self.c
        if fill:
            c.setFillColorRGB(*fill)
        c.setStrokeColorRGB(*stroke)
        c.setLineWidth(lw)
        c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1 if fill else 0)

    def pill(self, x, y, label, bg, fg=(1, 1, 1), size=6.4, pad=1.9 * mm):
        c = self.c
        w = pdfmetrics.stringWidth(label, "PB", size) + pad * 2
        c.setFillColorRGB(*bg)
        c.roundRect(x, y - 0.9 * mm, w, 3.5 * mm, 1.1 * mm, stroke=0, fill=1)
        c.setFillColorRGB(*fg)
        c.setFont("PB", size)
        c.drawString(x + pad, y + 0.15 * mm, label)
        return w


def tri(c, x, y, size=1.5 * mm, down=True, color=MUT):
    """접기 화살표. ▾▸ 는 Pretendard 에 없어 두부로 나온다 — 직접 그린다."""
    c.setFillColorRGB(*color)
    pth = c.beginPath()
    if down:
        pth.moveTo(x, y + size)
        pth.lineTo(x + size * 1.7, y + size)
        pth.lineTo(x + size * 0.85, y)
    else:
        pth.moveTo(x, y)
        pth.lineTo(x, y + size * 1.7)
        pth.lineTo(x + size, y + size * 0.85)
    pth.close()
    c.drawPath(pth, stroke=0, fill=1)


def head(d: Doc):
    c = d.c
    h = 30 * mm
    c.setFillColorRGB(*NAVY)
    c.roundRect(M, H - M - h, W - 2 * M, h, 3.5 * mm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("PX", 19)
    c.drawString(M + 9 * mm, H - M - 12.5 * mm, "매물장 개선안 — 4가지 방향")
    c.setFont("P", 8.8)
    c.drawString(M + 9 * mm, H - M - 18.5 * mm,
                 "매물 100~200개를 가진 사무소 기준. 엑셀처럼 훑으면서 폰에서도 쓸 수 있어야 합니다.")
    x = M + 9 * mm
    # 알파(4번째 인자)를 쓰면 그래픽 상태에 남아 이후 모든 요소가 반투명해진다(실측:
    # 표·알약 글자가 통째로 흐려짐). 반투명 대신 밝은 남색 단색으로 칠한다.
    tint = (0x2E / 255, 0x4A / 255, 0x7A / 255)
    for t in ("지금 카드 1개 ≈ 320px", "한 화면에 2개", "200개 = 100화면"):
        c.setFillColorRGB(*tint)
        w = pdfmetrics.stringWidth(t, "PB", 7.4) + 5 * mm
        c.roundRect(x, H - M - 25.5 * mm, w, 4.6 * mm, 2.3 * mm, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("PB", 7.4)
        c.drawString(x + 2.5 * mm, H - M - 24.1 * mm, t)
        x += w + 2 * mm
    d.y = H - M - h - 8 * mm


def section(d: Doc, title, lead=None, gap=2.4 * mm):
    d.need(20 * mm)
    d.text(title, 13, "PX", INK, dy=gap + 2.4 * mm)
    if lead:
        d.wrap(lead, 9, "P", MUT, lead=4.6 * mm)
        d.y -= 1.4 * mm


def opt_head(d: Doc, tag, title, density):
    c = d.c
    c.setFillColorRGB(*NAVY)
    c.roundRect(M, d.y - 1.2 * mm, 7 * mm, 5.2 * mm, 1.4 * mm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("PX", 9)
    c.drawCentredString(M + 3.5 * mm, d.y + 0.5 * mm, tag)
    c.setFillColorRGB(*INK)
    c.setFont("PB", 11)
    c.drawString(M + 9.5 * mm, d.y + 0.4 * mm, title)
    c.setFillColorRGB(*SOFT)
    w = pdfmetrics.stringWidth(density, "PB", 7.2) + 5 * mm
    c.roundRect(W - M - w, d.y - 0.6 * mm, w, 4.6 * mm, 2.3 * mm, stroke=0, fill=1)
    c.setFillColorRGB(*BLUE)
    c.setFont("PB", 7.2)
    c.drawString(W - M - w + 2.5 * mm, d.y + 0.7 * mm, density)
    d.y -= 7.4 * mm


# ── 목업 ─────────────────────────────────────────────────────
def mock_frame(d: Doc, x, y, w, h, caption):
    c = d.c
    d.box(x, y, w, h, fill=(1, 1, 1))
    c.setFillColorRGB(*STRIPE)
    c.rect(x + 0.3, y + h - 5 * mm, w - 0.6, 4.7 * mm, stroke=0, fill=1)
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(0.5)
    c.line(x, y + h - 5 * mm, x + w, y + h - 5 * mm)
    c.setFillColorRGB(*MUT)
    c.setFont("PB", 6.4)
    c.drawString(x + 3 * mm, y + h - 3.5 * mm, caption)
    return y + h - 5 * mm          # 내용 시작 y


ROWS = [
    ("한마루럭키", "104-1003", "매매", "12억", "37평", "10/15", "11월", "9/12"),
    ("고덕그라시움", "142-2004", "매매", "24억", "25평", "20/29", "10월", "12/12"),
    ("고덕그라시움", "131-701", "전세", "13억", "34평", "7/29", "협의", "12/12"),
    ("래미안힐스", "105-1203", "월세", "1,000/80", "25평", "12/25", "10.15", "10/12"),
    ("신주리버빌", "601", "매매", "3억5,000", "14평", "6/6", "즉시", "12/12"),
    ("탕정푸르지오", "205-1503", "전세", "3억5,000", "34평", "15/29", "9월", "8/12"),
    ("한마루삼성", "3-502", "월세", "3,000/120", "31평", "5/15", "협의", "9/12"),
]


def draw_table(d: Doc, x, top, w, rows, cols):
    """밀집 표. cols = [(제목, 상대폭, 정렬)]"""
    c = d.c
    tot = sum(cw for _, cw, _ in cols)
    xs, acc = [], x
    for _, cw, _ in cols:
        xs.append(acc)
        acc += w * cw / tot
    rh = 4.4 * mm
    # 헤더
    c.setFillColorRGB(*STRIPE)
    c.rect(x, top - rh, w, rh, stroke=0, fill=1)
    c.setFillColorRGB(*MUT)
    c.setFont("PB", 5.9)
    for (t, cw, al), cx in zip(cols, xs):
        cwid = w * cw / tot
        if al == "r":
            c.drawRightString(cx + cwid - 1.6 * mm, top - rh + 1.4 * mm, t)
        else:
            c.drawString(cx + 1.6 * mm, top - rh + 1.4 * mm, t)
    y = top - rh
    for i, r in enumerate(rows):
        if i % 2:
            c.setFillColorRGB(*STRIPE)
            c.rect(x, y - rh, w, rh, stroke=0, fill=1)
        c.setStrokeColorRGB(*LINE2)
        c.setLineWidth(0.4)
        c.line(x, y - rh, x + w, y - rh)
        for j, ((t, cw, al), cx) in enumerate(zip(cols, xs)):
            cwid = w * cw / tot
            v = r[j]
            if t == "거래":
                d.pill(cx + 1.6 * mm, y - rh + 1.2 * mm, v, TRADE_COLOR[v], size=5.6, pad=1.4 * mm)
                continue
            if t == "광고":
                col = WOLSE if v.split("/")[0] == v.split("/")[1] else WARN
                c.setFillColorRGB(*col)
                c.setFont("PB", 6.1)
            elif al == "r":
                c.setFillColorRGB(*INK)
                c.setFont("PB", 6.4)
            elif j == 0:
                c.setFillColorRGB(*INK)
                c.setFont("PB", 6.4)
            else:
                c.setFillColorRGB(*INK2)
                c.setFont("P", 6.2)
            if al == "r":
                c.drawRightString(cx + cwid - 1.6 * mm, y - rh + 1.4 * mm, v)
            else:
                c.drawString(cx + 1.6 * mm, y - rh + 1.4 * mm, v)
        y -= rh
    return y


def draw_rows2(d: Doc, x, top, w, n=5):
    """2줄 압축 행"""
    c = d.c
    y = top
    detail = ["37평(102㎡) · 10/15층 · 방4/욕2 · 주차 1.18 · 잔금 11월 · 광고 9/12",
              "25평(59㎡) · 20/29층 · 방3/욕2 · 남향 · 잔금 10월 · 광고 12/12",
              "34평(85㎡) · 7/29층 · 방3/욕2 · 남동 · 잔금 협의 · 광고 12/12",
              "25평(59㎡) · 12/25층 · 방3/욕2 · 남서 · 잔금 10.15 · 광고 10/12",
              "14평(34㎡) · 6/6층 · 방2/욕1 · 남향 · 즉시입주 · 광고 12/12"]
    for i, r in enumerate(ROWS[:n]):
        rh = 8.6 * mm
        c.setStrokeColorRGB(*LINE2)
        c.setLineWidth(0.4)
        c.line(x, y - rh, x + w, y - rh)
        px = x + 2.2 * mm
        px += d.pill(px, y - 3.2 * mm, r[2], TRADE_COLOR[r[2]], size=5.6, pad=1.4 * mm) + 1.6 * mm
        c.setFillColorRGB(*INK)
        c.setFont("PB", 7)
        c.drawString(px, y - 3.4 * mm, r[0])
        px += pdfmetrics.stringWidth(r[0], "PB", 7) + 2 * mm
        c.setFillColorRGB(*MUT)
        c.setFont("P", 6.2)
        c.drawString(px, y - 3.4 * mm, r[1])
        c.setFillColorRGB(*INK)
        c.setFont("PB", 7.4)
        c.drawRightString(x + w - 2.2 * mm, y - 3.4 * mm, r[3])
        c.setFillColorRGB(*MUT)
        c.setFont("P", 5.9)
        c.drawString(x + 2.2 * mm, y - 7 * mm, detail[i])
        y -= rh
    return y


def draw_groups(d: Doc, x, top, w):
    """단지별 묶음"""
    c = d.c
    y = top
    groups = [("고덕그라시움", 14, "매매 22~26억 · 전세 12~14억", True),
              ("한마루럭키", 9, "매매 11~13억 · 월세 3,000/120", False),
              ("래미안힐스테이트", 12, "매매 18~21억 · 전세 11~12억", False),
              ("탕정푸르지오리버파크", 31, "전세 3~4억 · 월세 다수", False),
              ("신주리버빌", 4, "매매 3~4억", False),
              ("단지 없음(빌라·상가)", 17, "주소별", False)]
    inner = [("매매", "142동 2004호", "25평 · 20/29층 · 남향", "24억"),
             ("전세", "131동 701호", "34평 · 7/29층 · 남동", "13억"),
             ("매매", "128동 1502호", "34평 · 15/29층 · 남향", "26억")]
    for name, cnt, rng, opened in groups:
        gh = 5.6 * mm
        c.setFillColorRGB(*TINT)
        c.rect(x, y - gh, w, gh, stroke=0, fill=1)
        tri(c, x + 2.4 * mm, y - gh + 2 * mm, down=opened)
        c.setFillColorRGB(*INK)
        c.setFont("PB", 7.2)
        c.drawString(x + 6 * mm, y - gh + 1.8 * mm, name)
        nx = x + 6 * mm + pdfmetrics.stringWidth(name, "PB", 7.2) + 2 * mm
        d.pill(nx, y - gh + 1.7 * mm, str(cnt), BLUE, size=5.8, pad=1.6 * mm)
        c.setFillColorRGB(*MUT)
        c.setFont("PB", 6.1)
        c.drawRightString(x + w - 2.2 * mm, y - gh + 1.8 * mm, rng)
        y -= gh
        if opened:
            for tr, ho, spec, pr in inner:
                rh = 4.6 * mm
                c.setStrokeColorRGB(*LINE2)
                c.setLineWidth(0.4)
                c.line(x, y - rh, x + w, y - rh)
                px = x + 6.5 * mm
                px += d.pill(px, y - rh + 1.2 * mm, tr, TRADE_COLOR[tr], size=5.4, pad=1.3 * mm) + 1.6 * mm
                c.setFillColorRGB(*INK2)
                c.setFont("P", 6.2)
                c.drawString(px, y - rh + 1.5 * mm, ho)
                c.setFillColorRGB(*MUT)
                c.setFont("P", 5.9)
                c.drawString(px + 17 * mm, y - rh + 1.5 * mm, spec)
                c.setFillColorRGB(*INK)
                c.setFont("PB", 6.6)
                c.drawRightString(x + w - 2.2 * mm, y - rh + 1.5 * mm, pr)
                y -= rh
            c.setFillColorRGB(*MUT)
            c.setFont("P", 5.9)
            c.drawString(x + 6.5 * mm, y - 3.4 * mm, "…외 11건")
            y -= 4.6 * mm
    return y


def draw_master_detail(d: Doc, x, top, w):
    c = d.c
    lw = w * 0.62
    ybot = draw_table(d, x, top, lw, ROWS[:6],
                      [("단지", 2.2, "l"), ("동·호", 1.6, "l"), ("거래", 1.1, "l"),
                       ("가격", 1.6, "r"), ("전용", 1.2, "l"), ("층", 1.0, "l")])
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(0.6)
    c.line(x + lw, top, x + lw, ybot)
    # 선택 행 표시 — 행을 덮으면 내용이 지워지니 왼쪽에 색 막대만 세운다
    c.setFillColorRGB(*BLUE)
    c.rect(x, top - 8.8 * mm, 0.9 * mm, 4.4 * mm, stroke=0, fill=1)
    dx = x + lw + 3 * mm
    dy = top - 4 * mm
    c.setFillColorRGB(*INK)
    c.setFont("PB", 7.6)
    c.drawString(dx, dy, "한마루럭키 104동 1003호")
    dy -= 5 * mm
    c.setFillColorRGB(*SALE)
    c.setFont("PX", 9.5)
    c.drawString(dx, dy, "매매 12억")
    dy -= 5.4 * mm
    for k, v in (("전용", "37평(102㎡)"), ("공급", "122.59㎡"), ("층", "10/15층"),
                 ("방·욕실", "4 / 2"), ("주차", "1.18대"), ("준공", "1992.12"),
                 ("잔금", "11월"), ("매도인", "김태열"), ("광고항목", "9/12")):
        c.setStrokeColorRGB(*LINE2)
        c.setLineWidth(0.4)
        c.line(dx, dy - 1.4 * mm, x + w - 1 * mm, dy - 1.4 * mm)
        c.setFillColorRGB(*MUT)
        c.setFont("P", 6.2)
        c.drawString(dx, dy, k)
        c.setFillColorRGB(*(WARN if k == "광고항목" else INK))
        c.setFont("PB", 6.4)
        c.drawRightString(x + w - 1 * mm, dy, v)
        dy -= 4.6 * mm
    return min(ybot, dy)


def procon(d: Doc, pros, cons):
    """장단점 두 칸"""
    c = d.c
    gap = 4 * mm
    cw = (W - 2 * M - gap) / 2
    lines = max(len(pros), len(cons))
    h = 6.4 * mm + lines * 4.4 * mm + 2.6 * mm
    d.need(h + 4 * mm)
    for i, (title, items, col) in enumerate((("좋은 점", pros, WOLSE), ("대가", cons, WARN))):
        x = M + i * (cw + gap)
        c.setFillColorRGB(*(0.96, 0.99, 0.97) if i == 0 else (1, 0.985, 0.955))
        c.setStrokeColorRGB(*col)
        c.setLineWidth(0.5)
        c.roundRect(x, d.y - h, cw, h, 2 * mm, stroke=1, fill=1)
        c.setFillColorRGB(*col)
        c.setFont("PX", 7)
        c.drawString(x + 3.4 * mm, d.y - 4.8 * mm, title)
        yy = d.y - 9.6 * mm
        c.setFont("P", 7.4)
        for it in items:
            c.setFillColorRGB(*col)
            c.drawString(x + 3.4 * mm, yy, "·")
            c.setFillColorRGB(*INK2)
            # 칸 안에서 접어 쓰기
            words, line = it.split(" "), ""
            first = True
            for wd in words:
                t = (line + " " + wd).strip()
                if pdfmetrics.stringWidth(t, "P", 7.4) > cw - 9 * mm and line:
                    c.drawString(x + 6.2 * mm, yy, line)
                    yy -= 3.6 * mm
                    line, first = wd, False
                else:
                    line = t
            if line:
                c.drawString(x + 6.2 * mm, yy, line)
            yy -= 4.4 * mm
            _ = first
    d.y -= h + 5 * mm


def build():
    d = Doc(OUT)
    head(d)

    section(d, "무엇이 문제인가",
            "지금 매물장은 카드 하나에 뱃지·주소·스펙·조건칩·태그·특징·광고항목·담당자·연락처·메모까지 "
            "다 들어 있습니다. 한 건을 볼 때는 친절하지만 200건을 훑을 때는 100번 스크롤해야 합니다. "
            "중개사가 실제로 하는 일은 “이 손님 조건에 맞는 게 뭐가 있지”를 훑는 것인데, "
            "지금 화면은 훑기에 맞지 않습니다.")
    d.rule(5 * mm)

    # A
    opt_head(d, "A", "밀집 표 (엑셀형)", "한 화면 21행 · 200개 = 10화면")
    d.wrap("데스크톱은 엑셀 그대로입니다. 단지·가격 열을 고정하고 헤더를 눌러 정렬하며, 칸을 눌러 바로 "
           "고칩니다. 폰에서는 표를 가로로 밀어 보되 첫 열은 붙어 있고, 행을 누르면 상세가 올라옵니다.",
           8.6, "P", INK2, lead=4.5 * mm)
    d.y -= 2 * mm
    mh = 42 * mm
    d.need(mh + 4 * mm)
    top = mock_frame(d, M, d.y - mh, W - 2 * M, mh, "데스크톱 — 매물장")
    draw_table(d, M + 1.5 * mm, top - 1.5 * mm, W - 2 * M - 3 * mm, ROWS,
               [("단지", 2.2, "l"), ("동·호", 1.5, "l"), ("거래", 1.0, "l"), ("가격", 1.5, "r"),
                ("전용", 1.4, "l"), ("층", 1.0, "l"), ("잔금", 1.0, "l"), ("광고", 1.0, "l")])
    d.y -= mh + 4 * mm
    procon(d, ["엑셀 쓰던 사람이 설명 없이 바로 씁니다",
               "열 선택·정렬·필터로 “내가 보는 방식”을 만듭니다",
               "칸을 눌러 바로 수정, 범위 복사·붙여넣기까지 갈 수 있습니다"],
           ["데스크톱·모바일 화면을 두 벌 만들어야 합니다",
            "폰에서는 결국 가로로 밀어야 합니다",
            "표 라이브러리가 번들에 들어갑니다"])

    # B
    d.need(70 * mm)
    opt_head(d, "B", "2줄 압축 행", "한 화면 13행 · 200개 = 16화면")
    d.wrap("표가 아니라 아주 촘촘한 목록입니다. 첫 줄은 단지·거래·가격, 둘째 줄은 스펙을 점으로 이어 "
           "붙입니다. 데스크톱과 폰이 같은 화면이고 폭에 따라 둘째 줄 항목만 줄어듭니다.",
           8.6, "P", INK2, lead=4.5 * mm)
    d.y -= 2 * mm
    mh = 50 * mm
    d.need(mh + 4 * mm)
    top = mock_frame(d, M, d.y - mh, W - 2 * M, mh, "데스크톱·폰 공통 — 폭만 다름")
    draw_rows2(d, M + 1.5 * mm, top - 1.5 * mm, W - 2 * M - 3 * mm, 5)
    d.y -= mh + 4 * mm
    procon(d, ["화면이 한 벌입니다. 만들고 고치는 비용이 절반",
               "폰에서 가로로 밀 필요가 없습니다",
               "지금 카드에서 이어 만들 수 있어 가장 빨리 나옵니다"],
           ["열이 안 맞아 눈으로 세로 비교가 어렵습니다",
            "“엑셀 같다”는 느낌은 덜합니다",
            "범위 선택·붙여넣기는 어렵습니다"])

    # C
    d.need(80 * mm)
    opt_head(d, "C", "단지별 묶음 + 한 줄", "200개 = 단지 22개 → 접으면 1~2화면")
    d.wrap("매물 200개라도 단지는 보통 20~30개입니다. 단지로 묶으면 전체가 한두 화면에 들어옵니다. "
           "손님이 “고덕그라시움 있어요?”라고 물으면 그 단지만 펼치면 됩니다.",
           8.6, "P", INK2, lead=4.5 * mm)
    d.y -= 2 * mm
    mh = 60 * mm
    d.need(mh + 4 * mm)
    top = mock_frame(d, M, d.y - mh, W - 2 * M, mh, "데스크톱·폰 공통 — 단지 접기")
    draw_groups(d, M + 1.5 * mm, top - 1.5 * mm, W - 2 * M - 3 * mm)
    d.y -= mh + 4 * mm
    procon(d, ["압축률이 가장 큽니다. 200개가 한 화면에 들어옵니다",
               "“그 단지 뭐 있어요?” 라는 실제 질문에 바로 답합니다",
               "단지 줄에 가격대가 나와 시세 감이 잡힙니다"],
           ["“전체를 가격순으로” 같은 훑기에는 안 맞습니다",
            "단지 없는 빌라·상가는 따로 묶어야 합니다",
            "한 단지에 매물이 몰린 사무소는 효과가 작습니다"])

    # D
    d.need(80 * mm)
    opt_head(d, "D", "표 + 옆 상세", "한 화면 21행 + 상세 동시")
    d.wrap("A안의 표에 상세 패널을 붙인 형태입니다. 손님과 통화하면서 표를 훑다가 하나를 누르면 "
           "오른쪽에 광고에 필요한 값이 전부 뜹니다. 화면을 옮기지 않아도 됩니다.",
           8.6, "P", INK2, lead=4.5 * mm)
    d.y -= 2 * mm
    mh = 54 * mm
    d.need(mh + 4 * mm)
    top = mock_frame(d, M, d.y - mh, W - 2 * M, mh, "데스크톱 — 표 + 상세")
    draw_master_detail(d, M + 1.5 * mm, top - 1.5 * mm, W - 2 * M - 3 * mm)
    d.y -= mh + 4 * mm
    procon(d, ["통화 중에 화면을 옮기지 않아도 됩니다",
               "표는 좁게 유지하고 정보는 옆에서 다 봅니다"],
           ["표가 좁아져 한 번에 보는 열이 줄어듭니다",
            "폰에서는 이점이 없습니다",
            "A안을 먼저 만든 뒤에야 얹을 수 있습니다"])

    # 비교표
    d.need(60 * mm)
    section(d, "한눈에 비교")
    cmp_rows = [
        ("200개 훑기", "10화면", "16화면", "1~2화면", "10화면", (0, 2, 3)),
        ("엑셀 같은가", "가장 비슷", "보통", "다름", "비슷", (0, 3)),
        ("폰에서 쓰기", "가로 스크롤", "그대로 편함", "그대로 편함", "보통", (1, 2)),
        ("화면 벌 수", "2벌", "1벌", "1벌", "2벌", (1, 2)),
        ("세로 비교", "쉬움", "어려움", "단지 안에서만", "쉬움", (0, 3)),
        ("만드는 정도", "큼", "작음", "중간", "가장 큼", (1,)),
        ("붙여넣기·범위 편집", "가능", "어려움", "어려움", "가능", (0, 3)),
    ]
    c = d.c
    tw = W - 2 * M
    cw0 = tw * 0.24
    cwn = (tw - cw0) / 4
    rh = 6.2 * mm
    th = rh * (len(cmp_rows) + 1)
    d.need(th + 4 * mm)
    top = d.y
    c.setFillColorRGB(*STRIPE)
    c.rect(M, top - rh, tw, rh, stroke=0, fill=1)
    c.setFillColorRGB(*MUT)
    c.setFont("PB", 7.2)
    c.drawString(M + 2.5 * mm, top - rh + 2.2 * mm, "기준")
    for i, t in enumerate(("A 밀집 표", "B 2줄 행", "C 단지 묶음", "D 표+상세")):
        c.drawCentredString(M + cw0 + cwn * (i + 0.5), top - rh + 2.2 * mm, t)
    y = top - rh
    for label, *vals, best in cmp_rows:
        c.setStrokeColorRGB(*LINE2)
        c.setLineWidth(0.4)
        c.line(M, y - rh, M + tw, y - rh)
        c.setFillColorRGB(*STRIPE)
        c.rect(M, y - rh, cw0, rh, stroke=0, fill=1)
        c.setFillColorRGB(*INK)
        c.setFont("PB", 7.2)
        c.drawString(M + 2.5 * mm, y - rh + 2.2 * mm, label)
        for i, v in enumerate(vals):
            if i in best:
                c.setFillColorRGB(*WOLSE)
                c.setFont("PB", 7.2)
            else:
                c.setFillColorRGB(*INK2)
                c.setFont("P", 7.2)
            c.drawCentredString(M + cw0 + cwn * (i + 0.5), y - rh + 2.2 * mm, v)
        y -= rh
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(0.6)
    c.roundRect(M, top - th, tw, th, 2 * mm, stroke=1, fill=0)
    d.y = top - th - 7 * mm

    # 추천
    d.need(56 * mm)
    bh = 50 * mm
    c.setFillColorRGB(*TINT)
    c.setStrokeColorRGB(*BLUE)
    c.setLineWidth(0.7)
    c.roundRect(M, d.y - bh, tw, bh, 3 * mm, stroke=1, fill=1)
    yy = d.y - 7 * mm
    c.setFillColorRGB(0x0F / 255, 0x57 / 255, 0xB3 / 255)
    c.setFont("PX", 11.5)
    c.drawString(M + 6 * mm, yy, "추천 — C를 기본으로, A를 옆에")
    yy -= 6.4 * mm
    save_y, save_M = d.y, M
    d.y = yy
    for para in (
        "넷 중 하나만 고르라면 C(단지 묶음)입니다. 200개를 한 화면에 넣는 건 C뿐이고, "
        "“그 단지 뭐 있어요?”가 중개사가 실제로 가장 많이 받는 질문이기 때문입니다. "
        "폰에서도 구조가 그대로라 화면을 두 벌 만들 필요가 없습니다.",
        "다만 “엑셀처럼”이라는 요구는 C만으로는 못 채웁니다. 그래서 보기 전환을 둡니다 — "
        "같은 데이터, 버튼 하나로 [단지별] ↔ [전체목록(표)]. 데스크톱에서 전체목록을 고르면 "
        "A의 밀집 표가, 폰에서는 B의 2줄 행이 나옵니다.",
    ):
        d.wrap(para, 8.4, "P", INK2, width=tw - 12 * mm, lead=4.3 * mm, x=save_M + 6 * mm)
        d.y -= 1.2 * mm
    for i, s in enumerate((
        "1단계 — C(단지 묶음) + 필터·검색. 폰·데스크톱 공통. 여기서 100화면이 1~2화면이 됩니다.",
        "2단계 — 전체목록 보기. 데스크톱은 밀집 표(정렬·열 선택), 폰은 2줄 행.",
        "3단계 — 표에 인라인 편집·범위 붙여넣기. 엑셀에서 옮겨오는 길까지 엽니다.",
    )):
        tri(c, save_M + 6.2 * mm, d.y + 0.2 * mm, size=1.4 * mm, down=False, color=BLUE)
        d.wrap(s, 8.4, "P", INK2, width=tw - 16 * mm, lead=4.3 * mm, x=save_M + 10 * mm)
        _ = i
    d.y = save_y - bh - 5 * mm
    d.text("셋 다 지금 데이터 그대로 씁니다. 새로 모을 정보는 없고 화면만 바뀝니다. "
           "D는 2단계가 끝난 뒤에 얹으면 되는 것이라 지금 고르실 필요는 없습니다.",
           7.8, "P", MUT)

    d.footer()
    d.c.save()
    print(f"생성: {OUT}  ({d.page}쪽)")


if __name__ == "__main__":
    build()
