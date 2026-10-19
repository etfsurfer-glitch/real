# -*- coding: utf-8 -*-
"""1기 신도시 선도지구 보도자료 → PDF 조판.

수치는 손으로 적지 않는다. 박스에서 뽑은 집계를 STAT 에 모아 두고 본문·표가 같은
값을 쓰도록 한다 — 본문과 표가 어긋날 자리를 없앤다.

실행: python3 design/press/선도지구/make_report.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent.parent / "fonts"
CHART = HERE / "chart_분당_84㎡추이.png"
OUT = HERE / "콕집_선도지구_보도자료.pdf"
DATE = "2026년 10월 19일"

INK, MUTE, LINE = colors.HexColor("#1b2430"), colors.HexColor("#5b6775"), colors.HexColor("#d9e0e8")
BRAND, UP, DOWN = colors.HexColor("#1268d3"), colors.HexColor("#b3261e"), colors.HexColor("#1268d3")
BAND = colors.HexColor("#f2f7ff")

for nm, fn in (("P", "Pretendard-Regular.ttf"), ("P-B", "Pretendard-Bold.ttf"),
               ("P-M", "Pretendard-Medium.ttf"), ("P-EB", "Pretendard-ExtraBold.ttf")):
    pdfmetrics.registerFont(TTFont(nm, str(FONTS / fn)))
pdfmetrics.registerFontFamily("P", normal="P", bold="P-B", italic="P", boldItalic="P-B")

ss = getSampleStyleSheet()


def st(name, size, font="P", lead=None, color=INK, space=0, align=0):
    return ParagraphStyle(name, parent=ss["Normal"], fontName=font, fontSize=size,
                          leading=lead or size * 1.55, textColor=color,
                          spaceAfter=space, alignment=align)


TITLE = st("t", 20, "P-EB", lead=28, space=5)
SUB = st("s", 11.5, "P-M", lead=18, color=BRAND, space=3)
H = st("h", 13, "P-B", lead=19, space=6)
BODY = st("b", 10.3, "P", lead=17.5, space=7)
NOTE = st("n", 8.8, "P", lead=14.5, color=MUTE, space=4)
CELL = st("c", 9.2, "P", lead=13.5)
CAP = st("cap", 8.8, "P-M", lead=13, color=MUTE, space=3)

# ── 집계값(박스 산출) ──────────────────────────────────────────────
STAT = {
    "lead_pre": 13.83, "lead_post": 15.82, "ctrl_pre": 13.89, "ctrl_post": 14.90,
    "lead_chg": 14.4, "ctrl_chg": 7.3,
    "n_lead_pre": 63, "n_lead_post": 48, "n_ctrl_pre": 77, "n_ctrl_post": 78,
    "zone": [("샛별마을(분당동)", 11.74, 12.77, 8.8),
             ("양지마을(수내동)", 15.94, 17.66, 10.8),
             ("시범단지(서현동)", 14.54, 15.60, 7.3)],
    "seg": [("발표 12~6개월 전", "12.96", "—", "12.77", "—"),
            ("발표 6~0개월 전", "13.83", "+6.7%", "13.89", "+8.8%"),
            ("발표 0~6개월 후", "15.82", "+14.4%", "14.90", "+7.3%"),
            ("발표 6~12개월 후", "17.74", "+12.1%", "16.97", "+13.9%"),
            ("발표 12~18개월 후", "19.15", "+7.9%", "19.05", "+12.3%"),
            ("발표 18개월~현재", "20.74", "+8.3%", "20.45", "+7.3%")],
    "sens": [("최근 3개월", "5 / 12", "+60.7%", "+50.8%", "+9.9%p"),
             ("최근 6개월", "41 / 46", "+42.4%", "+44.9%", "-2.4%p"),
             ("최근 12개월", "90 / 81", "+41.4%", "+41.2%", "+0.2%p")],
    "spec": [("분당 선도지구 12개 단지", "895세대", "196.4%", "1992년"),
             ("분당 비지정 77개 단지", "890세대", "182.5%", "1994년"),
             ("대전 둔산 4개 단지", "1,313세대", "225.0%", "1992년")],
    "zone_scale": [("분당 샛별마을", "4개", "2,777세대", "178%"),
                   ("분당 양지마을", "6개", "4,392세대", "210%"),
                   ("분당 시범단지", "2개", "3,569세대", "192%"),
                   ("대전 둔산 13구역", "2개", "2,798세대", "229%"),
                   ("대전 둔산 14구역", "2개", "2,454세대", "221%")],
    "cand": [("산본", "산본동", "26개", "26,967세대", "207%"),
             ("중동", "중동", "34개", "27,941세대", "210%"),
             ("일산", "주엽동", "30개", "18,538세대", "175%"),
             ("분당", "정자동", "17개", "13,744세대", "182%"),
             ("일산", "일산동", "20개", "13,144세대", "194%"),
             ("분당", "야탑동", "13개", "12,620세대", "185%"),
             ("분당", "서현동", "9개", "12,265세대", "185%"),
             ("평촌", "호계동", "20개", "11,916세대", "206%"),
             ("평촌", "비산동", "9개", "10,987세대", "204%"),
             ("중동", "상동", "11개", "10,170세대", "218%")],
}


def keep(*items):
    """소제목이 쪽 맨 아래 혼자 남는 걸 막는다 — 제목과 첫 블록을 한 덩어리로."""
    return KeepTogether(list(items))


def table(rows, widths, head=1, hi=(), align_right=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=head)
    cmds = [("FONT", (0, 0), (-1, -1), "P", 9.2),
            ("TEXTCOLOR", (0, 0), (-1, -1), INK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("FONT", (0, 0), (-1, head - 1), "P-B", 9),
            ("TEXTCOLOR", (0, 0), (-1, head - 1), MUTE),
            ("LINEBELOW", (0, head - 1), (-1, head - 1), 0.9, INK),
            ("LINEBELOW", (0, head), (-1, -2), 0.4, LINE)]
    if align_right:
        cmds.append(("ALIGN", (1, 0), (-1, -1), "RIGHT"))
    for r in hi:
        cmds += [("BACKGROUND", (0, r), (-1, r), BAND), ("FONT", (0, r), (0, r), "P-B", 9.2)]
    t.setStyle(TableStyle(cmds))
    return KeepTogether(t)


def sec(title):
    """소제목이 쪽 맨 아래 혼자 남는 걸 막는다. 남은 공간이 45mm 미만이면 다음 장부터."""
    return [CondPageBreak(45 * mm), Paragraph(title, H)]


def page(cv, doc):
    cv.saveState()
    cv.setFont("P-B", 8.5); cv.setFillColor(MUTE)
    cv.drawString(20 * mm, A4[1] - 12 * mm, "콕집 부동산 데이터 리포트")
    cv.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, DATE)
    cv.setStrokeColor(LINE); cv.setLineWidth(0.6)
    cv.line(20 * mm, A4[1] - 15 * mm, A4[0] - 20 * mm, A4[1] - 15 * mm)
    cv.setFont("P", 8.5)
    cv.drawString(20 * mm, 12 * mm, "koczip.com")
    cv.drawRightString(A4[0] - 20 * mm, 12 * mm, str(cv.getPageNumber()))
    cv.restoreState()


S = STAT
f = []
f.append(Paragraph("추가 지정 앞둔 1기 신도시, ‘묶일 수 있는 동’을 노려라", TITLE))
f.append(Paragraph(
    "분당 선도지구, 발표 직후 6개월에 바로 옆 단지보다 +7.1%p<br/>"
    "지정 안 돼도 같은 동은 2년간 나란히 올랐다 … 기준선은 ‘통합 2,500세대’", SUB))
f.append(Paragraph(
    "배포일: 2026년 10월 · 즉시 보도 가능 &nbsp;&nbsp; 문의: 조용호 공동창업자 · "
    "albooooza@gmail.com · 010-4692-4946", CAP))
f.append(Spacer(1, 7))

f.append(Paragraph(
    "공급이 마르는 자리를 노후계획도시 정비가 메우고 있다. 2024년 11월 1기 신도시 선도지구 "
    "13개 구역 3만 5,897가구가 지정됐고, 2026년 7월에는 대전 둔산·송촌 3개 구역 7,797가구가 "
    "뒤를 이었다. 성남시는 분당 2차 특별정비구역 1만 3,429가구를 12월 지정·고시하고, "
    "<b>2027년 물량 1만호와 2028~2030년 예비 물량 1만 5,000호</b>를 미리 뽑는 "
    "‘예비 특별정비구역’도 도입했다. 다음 차례가 줄을 서 있다는 뜻이다.", BODY))
f.append(Paragraph(
    f"콕집이 국토교통부 실거래가로 분당 1차 선도지구 3개 구역 12개 단지의 2년치를 "
    f"<b>같은 동에 있는 비지정 단지 10곳</b>과 비교했다. 입지·연식·가격대를 맞춰야 지정 효과만 "
    f"남는다. 발표 직전 6개월 평균이 선도지구 {S['lead_pre']}억, 최인근 {S['ctrl_pre']}억으로 "
    f"차이는 0.4%였다.", BODY))

f += sec("1. 발표 직후 6개월, 7.1%포인트가 갈렸다")
f.append(table(
    [["구분", "발표 전 6개월", "발표 후 6개월", "변동"],
     ["선도지구 12개 단지", f"{S['lead_pre']}억", f"{S['lead_post']}억",
      Paragraph(f'<font color="{UP.hexval()}"><b>+{S["lead_chg"]}%</b></font>', CELL)],
     ["최인근 비지정 10개 단지", f"{S['ctrl_pre']}억", f"{S['ctrl_post']}억", f"+{S['ctrl_chg']}%"]],
    [62 * mm, 33 * mm, 33 * mm, 28 * mm], hi=(1,)))
f.append(Paragraph("전용 84㎡ 평균 실거래가 · 발표일 2024년 11월 27일 기준", CAP))
f.append(Spacer(1, 3))
f.append(Paragraph(
    "같은 동, 같은 연식, 같은 가격대에서 지정 여부 하나가 <b>7.1%포인트</b>를 만들었다. "
    "구역별로는 양지마을 +10.8%, 샛별마을 +8.8%, 시범단지 +7.3%였다.", BODY))
f.append(Paragraph(
    f"거래는 오히려 줄었다. 선도지구 84㎡ 거래는 발표 전 {S['n_lead_pre']}건에서 "
    f"{S['n_lead_post']}건으로 24% 감소했다. 최인근 단지는 {S['n_ctrl_pre']}건에서 "
    f"{S['n_ctrl_post']}건으로 변화가 없었다. <b>가격은 오르는데 물건은 들어갔다.</b>", BODY))

if CHART.exists():
    f.append(Spacer(1, 2))
    f.append(Image(str(CHART), width=168 * mm, height=82 * mm))
    f.append(Paragraph("자료: 국토교통부 실거래가(해제거래 제외) · 분석: 콕집", CAP))

f += sec("2. 발표 전에는 덜 올랐다 — 선반영은 없었다")
f.append(table(
    [["구간", "선도지구", "변동", "최인근", "변동"]] +
    [[a, f"{b}억", c, f"{d}억", e] for a, b, c, d, e in S["seg"]],
    [44 * mm, 28 * mm, 24 * mm, 28 * mm, 24 * mm], hi=(3,)))
f.append(Paragraph(
    "발표 직전 6개월에는 선도지구가 <b>오히려 덜 올랐다</b>(+6.7% vs +8.8%). 시장이 어디가 "
    "뽑힐지 미리 알고 움직이지는 않았다는 뜻이다. 초과 상승이 찍힌 구간은 <b>발표 직후 "
    "6개월 하나뿐</b>이고, 이후 구간에서는 두 그룹이 비슷하거나 최인근이 앞섰다.", BODY))
f.append(table(
    [["누적 상승률(발표 직전 기준)", "거래건수", "선도지구", "최인근", "격차"]] +
    [list(r) for r in S["sens"]],
    [50 * mm, 24 * mm, 26 * mm, 26 * mm, 24 * mm], hi=(3,)))
f.append(Paragraph(
    "누적 격차는 종료 시점에 따라 −2.4%p에서 +9.9%p까지 흔들린다. 최근 3개월은 거래가 "
    "5건뿐이라 숫자로 쓸 수 없다. 표본이 가장 두꺼운 12개월 기준으로는 <b>+0.2%p, 사실상 "
    "0</b>이다. 지정은 발표 시점에 한 번 레벨을 올렸고 그 레벨은 유지됐지만, 이후 추가 "
    "초과수익은 확인되지 않았다.", BODY))
f.append(Paragraph(
    "<b>발표 후에 따라 들어가면 이미 레벨업이 끝난 가격을 산다.</b> 추가 지정을 노린다면 "
    "지정된 다음이 아니라 가능성이 높은 곳을 미리 고르는 쪽이어야 한다.", BODY))
f.append(Paragraph(
    "뒤집어 보면 이 숫자는 <b>떨어졌을 때의 이야기</b>이기도 하다. 같은 동 비지정 단지는 "
    "발표 직전 13.89억에서 최근 1년 평균 19.61억으로 <b>+41.2%</b> 올랐다. 같은 기간 "
    "선도지구는 +41.4%다. <b>0.2%포인트 차이</b>, 사실상 같이 움직였다. 지정이라는 한 번의 "
    "레벨업을 못 받았을 뿐 정비 기대가 붙은 동네는 함께 갔다는 뜻이다. "
    "<b>묶일 수 있는 동을 고르면 그 구역이 뽑히지 않아도 동네가 따라온다.</b>", BODY))

f += sec("3. 대전 둔산은 3개월 시점에서 아직 조용하다")
f.append(Paragraph(
    "2026년 7월 15일 지정된 대전 둔산은 13구역(크로바·목련 2,798가구)과 14구역(한가람·"
    "공작한양 2,454가구) 합쳐 5,252가구다. 비수도권으로는 부산에 이어 두 번째다.", BODY))
f.append(table(
    [["구분", "발표 전", "발표 후", "변동"],
     ["14구역 한가람·공작한양 85㎡", "5.82억 (15건)", "6.63억 (19건)", "+13.9%"],
     ["대전 서구 비지정 85㎡", "3.92억 (577건)", "4.41억 (272건)", "+12.5%"],
     ["13구역 크로바·목련 102㎡", "11.59억 (21건)", "14.33억 (3건)", "+23.6%"]],
    [62 * mm, 33 * mm, 33 * mm, 28 * mm], hi=(1,)))
f.append(Paragraph(
    "14구역의 초과분은 <b>1.4%포인트</b>에 그쳤다. 분당 1차의 7.1%포인트와는 결이 다르다. "
    "13구역은 +23.6%로 크게 뛴 것처럼 보이지만 발표 후 거래가 3건뿐이라 단정할 단계가 "
    "아니다. 발표 3개월 시점이라는 점을 감안해 방향성 참고로만 읽어야 한다.", BODY))

f += sec("4. 정부가 고른 기준은 ‘덩치’였다 — 투자 기준과는 다르다")
f.append(table(
    [["구분", "평균 세대수", "평균 용적률", "평균 준공"]] + [list(r) for r in S["spec"]],
    [62 * mm, 32 * mm, 32 * mm, 30 * mm], hi=(1,)))
f.append(Paragraph(
    "재건축 사업성은 용적률이 낮을수록 좋다. 그런데 선정 단지의 용적률이 비지정보다 "
    "<b>13.9%포인트 높았다</b>. 단일 단지 세대수는 895세대 대 890세대로 사실상 같았다. "
    "사업성만 보면 뽑힐 이유가 없는 조합이다.", BODY))
f.append(Paragraph(
    "<b>여기서 오해가 생기기 쉽다.</b> 용적률 높은 단지가 뽑혔다는 것은 그 단지들의 "
    "사업성이 좋다는 뜻이 <b>아니다</b>. 정부가 ‘빨리 추진될 곳’을 골랐다는 뜻이다. "
    "용적률이 높을수록 일반분양으로 뽑아낼 물량이 적어 조합원 분담금은 오히려 커진다. "
    "<b>선정 기준과 투자 기준은 다르다.</b> 지정 여부는 속도를, 용적률과 대지지분은 "
    "내가 낼 돈을 가른다. 둘은 따로 봐야 한다.", BODY))
f.append(table(
    [["구역", "묶은 단지", "통합 세대수", "평균 용적률"]] + [list(r) for r in S["zone_scale"]],
    [62 * mm, 28 * mm, 34 * mm, 32 * mm]))
f.append(Paragraph(
    "답은 ‘구역’ 단위에 있다. 선정 구역의 평균 통합 규모는 <b>3,198세대</b>로 단일 단지 "
    "평균(890세대)의 3.6배다. 2~6개 단지가 손을 잡아 덩치를 만든 곳이 뽑혔다. 심사에서 "
    "앞선 것은 낮은 용적률이 아니라 <b>통합 규모와 주민 동의율</b>이었다. 둔산 13구역 "
    "동의율은 96.2%였다.", BODY))

f += sec("5. 다음 후보는 어디인가")
f.append(Paragraph(
    "조건을 뒤집으면 윤곽이 나온다. ①1990년대 초중반 준공 ②인접 단지를 묶어 2,500세대 이상 "
    "③통합 추진이 가능한 생활권이다. 1기 신도시에서 1988~1996년 준공·300세대 이상 단지를 "
    "동 단위로 묶은 결과다.", BODY))
f.append(table(
    [["신도시", "동", "단지 수", "통합 세대수", "평균 용적률"]] + [list(r) for r in S["cand"]],
    [26 * mm, 30 * mm, 26 * mm, 36 * mm, 32 * mm]))
f.append(Paragraph(
    "규모만으로 지정이 결정되지는 않는다. 다만 <b>묶을 단지가 없으면 출발선에 서지 못한다.</b> "
    "분당 2차에는 43건·50개 구역 6만 6,037가구가 몰려 지정 물량의 5.5배가 경쟁했다.", BODY))
f.append(Paragraph(
    "선도지구에서 떨어져도 정비는 계속된다. 그때부터는 사업성이 전면에 선다. 주엽동 175%, "
    "정자동 182%, 야탑동 185%는 용적률에 여유가 있고, 상동 218%·중동 210%·산본동 207%는 "
    "일반분양으로 뽑아낼 물량이 그만큼 적어 분담금 부담이 커진다. 다만 분담금을 최종적으로 "
    "가르는 것은 <b>세대당 대지지분</b>이다. 같은 용적률이라도 고층·소형 위주 단지는 지분이 "
    "얇다.", BODY))

QUOTE = st("q", 10.3, "P-M", lead=17.5, color=INK, space=7)
f.append(Spacer(1, 2))
f.append(Paragraph(
    "조용호 콕집 공동창업자는 “선도지구에 뽑히면 오른다는 말만 돌지만, 숫자를 2년치로 "
    "펴 보면 초과수익이 찍힌 구간은 발표 직후 여섯 달 하나였다”며 “더 중요한 것은 "
    "같은 동의 비지정 단지가 사실상 같은 폭으로 올랐다는 점이다. 지정은 속도를 당길 뿐, "
    "값을 끌어올린 것은 그 동네가 정비 대상이라는 사실 자체였다”고 말했다. 이어 "
    "“그래서 특정 단지를 찍기보다 묶일 수 있는 동을 고르는 쪽이 위험이 적다. 다만 "
    "용적률이 높은 곳은 지정 뒤 분담금으로 되돌아온다는 점은 따로 봐야 한다”고 덧붙였다.",
    QUOTE))

f.append(Spacer(1, 4))
f.append(Paragraph("데이터와 기준", H))
f.append(Paragraph(
    "· 국토교통부 아파트 매매 실거래가. <b>해제(취소)된 거래는 전부 제외</b>했다. 포함하면 "
    "성사되지 않은 신고가가 통계에 섞인다.<br/>"
    "· 가격은 전용 81~87㎡ 평균 거래가(국민평형). 대전 13구역만 주력 면적이 달라 100~105㎡로 "
    "맞췄다.<br/>"
    "· 대조군은 선도지구와 <b>같은 동</b>의 비지정 단지다(분당동·수내동·서현동 10곳, "
    "1988~1996년 준공·300세대 이상). 분당 전역(77곳)을 쓰면 입지·가격대가 섞여 상승률 비교가 "
    "흔들린다. 대전은 서구 69곳.<br/>"
    "· 용적률·세대수는 단지 등록정보, 구역 통합 세대수는 구역 포함 단지의 합이다.<br/>"
    "· 발표 직후 6개월 초과분(+7.1%p)은 표본 48건·78건으로, 비교 구간을 바꿔도 유지된다.", NOTE))
f.append(Spacer(1, 5))
f.append(Spacer(1, 3))
f.append(Paragraph("자료 제공·분석: 콕집(koczip.com)<br/>문의: 조용호 공동창업자 · albooooza@gmail.com · 010-4692-4946", CAP))

SimpleDocTemplate(str(OUT), pagesize=A4,
                  leftMargin=20 * mm, rightMargin=20 * mm,
                  topMargin=22 * mm, bottomMargin=18 * mm,
                  title="콕집 선도지구 보도자료", author="조용호 · 콕집").build(f, onFirstPage=page, onLaterPages=page)
print(f"저장: {OUT}")
