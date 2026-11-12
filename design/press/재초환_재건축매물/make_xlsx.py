# -*- coding: utf-8 -*-
"""press_jaecho.json → 기자 전달용 엑셀. 보도자료(make_report.py)와 같은 논리: 내린 집·올린 집을 함께, 직전 수요일 대비.
시트: 단계별 주간 / 방향별 단지 수 / 단지별 주간 / 매물 수 / 재건축 단지 / 인하 폭."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
J = json.loads((HERE.parent / "data" / "press_jaecho.json").read_text())
ZONES = json.loads((HERE.parent / "data" / "press_jaecho_zones.json").read_text())
MG, SI, AR, PRE, GEN = J["order"]
ALL, SIX = "재건축 전체", "사업시행인가(은마·잠실5 제외)"
STAGES = [MG, SI, SIX, AR, PRE, ALL, GEN]
WC, WX, W, F = J["weekly_change"], J["weekly_complex"], J["weekly"], J["focus"]
WEEKS = list(WC)
thin = Side(style="thin", color="BBBBBB")
PCT, SPCT, INT = "0.0%", "+0.00%;-0.00%;0.00%", "#,##0"
STAGE_FIX = {"은마아파트": ("사업시행", "2026-07-02"), "잠실주공5단지": ("사업시행", "2026-07-01")}
NOTES = ["기준",
         "· 서울 아파트 매매 매물. 매주 수요일 하루치 수집분을 직전 수요일과 비교(9월 30일은 추석 주를 건너뛴 9월 16일 대비).",
         "· 같은 집 = 두 날 모두 매물로 나와 있던 집(단지·동·층·공급·전용·방향이 같은 광고). 여러 광고는 한 채로 묶고 호가는 중앙값. ±30% 넘는 변동은 오기재로 보고 제외.",
         "· 내린 집·올린 집 = 같은 집 가운데 직전 수요일보다 호가가 낮아진·높아진 집의 비율. 나머지는 호가를 그대로 둔 집. 평균 변동은 그대로 둔 집(0%) 포함 평균.",
         "· 사업 단계: 서울시 「정비사업 추진현황」(2026년 6월 말 기준, 서울 열린데이터광장)의 아파트 재건축 구역(공동주택재건축·아파트지구재건축). "
         "은마·잠실주공5단지는 2026년 7월 사업시행인가 반영. 착공 단계 구역 제외. 건축심의 전 = 구역지정·추진위원회·조합설립.",
         "· 일반 아파트 = 정비구역이 아닌 서울 아파트. 재건축 전체 = 네 단계 합계.",
         "· 출처: 콕집(koczip.com)"]


def head(ws, title, rows):
    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    for r in rows:
        ws.append(r)
        for c in ws[ws.max_row]:
            c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="EEEEEE")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def finish(ws, widths, extra=()):
    for rr in ws.iter_rows(min_row=3, max_row=ws.max_row):
        for c in rr:
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.append([])
    for n in list(NOTES) + list(extra):
        ws.append([n])


wb = Workbook()
# 1) 단계별 주간
ws = wb.active; ws.title = "단계별 주간"
h1 = ["주(끝나는 날)"] + [x for g in STAGES for x in (g, None, None, None)]
h2 = [None] + [x for _ in STAGES for x in ("내린 집", "올린 집", "평균 변동", "같은 집 수")]
head(ws, "서울 재건축 단지 사업 단계별 — 같은 집 호가 변동(직전 수요일 대비)", [h1, h2])
for i in range(len(STAGES)):
    ws.merge_cells(start_row=3, start_column=2 + i * 4, end_row=3, end_column=5 + i * 4)
ws.merge_cells("A3:A4")
for d in WEEKS:
    row = [d]
    for g in STAGES:
        x = WC[d].get(g)
        row += [x["cut"], x["rise"], x["mean"], x["n"]] if x else [None] * 4
    ws.append(row)
    for i, c in enumerate(ws[ws.max_row][1:]):
        c.number_format = (PCT, PCT, SPCT, INT)[i % 4]
finish(ws, [14] + [9, 9, 10, 9] * len(STAGES))

# 2) 방향별 단지 수
ws = wb.create_sheet("방향별 단지 수")
head(ws, "재건축 단지 수 — 그 주에 내린 집이 더 많은 단지 / 올린 집이 더 많은 단지(같은 집 5채 이상 단지)",
     [["주(끝나는 날)", "단계", "내린 집이 더 많은 단지", "올린 집이 더 많은 단지", "같은 단지", "대상 단지"]])
for d in WEEKS:
    for g in [None, MG, SI, AR, PRE]:
        c = r = n = 0
        for no, x in WX[d].items():
            if no not in F or (g and F[no]["group"] != g):
                continue
            n += 1; c += x["cut"] > x["rise"]; r += x["rise"] > x["cut"]
        ws.append([d, g or "재건축 전체", c, r, n - c - r, n])
        if not g:
            for cc in ws[ws.max_row]:
                cc.font = Font(bold=True)
finish(ws, [14, 16, 20, 20, 10, 10])

# 3) 단지별 주간
ws = wb.create_sheet("단지별 주간")
DS = [d for d in WEEKS if d >= "2026-09-30"]
h1 = ["자치구", "단지", "단계"] + [x for d in DS for x in (d, None, None)]
h2 = [None, None, None] + [x for _ in DS for x in ("내린 집", "올린 집", "같은 집 수")]
head(ws, "재건축 단지별 — 같은 집 호가 변동(직전 수요일 대비)", [h1, h2])
for i in range(len(DS)):
    ws.merge_cells(start_row=3, start_column=4 + i * 3, end_row=3, end_column=6 + i * 3)
for col in "ABC":
    ws.merge_cells(f"{col}3:{col}4")
order = {g: i for i, g in enumerate([MG, SI, AR, PRE])}
for no in sorted(F, key=lambda n: (order[F[n]["group"]], -F[n]["counts"]["2026-11-11"])):
    x = F[no]
    row = [x["gu"], x["name"], x["group"]]
    for d in DS:
        y = WX[d].get(no)
        row += [y["cut"], y["rise"], y["n"]] if y else [None, None, None]
    ws.append(row)
    for i, c in enumerate(ws[ws.max_row][3:]):
        c.number_format = (PCT, PCT, INT)[i % 3]
finish(ws, [9, 24, 13] + [9, 9, 9] * len(DS), ["· 같은 집이 5채 미만인 주는 비워 둠."])

# 4) 매물 수
ws = wb.create_sheet("매물 수")
head(ws, "실매물 수(같은 집 중복 광고를 한 채로) — 매주 수요일", [["날짜", MG, SI, AR, PRE, GEN, "은마", "잠실주공5단지"]])
for d in W:
    ws.append([d] + [round(W[d].get(g, 0)) for g in (MG, SI, AR, PRE, GEN)] + [F["236"]["counts"][d], F["639"]["counts"][d]])
    for c in ws[ws.max_row][1:]:
        c.number_format = INT
ws.append(["단지 수"] + [J["groups"][g] for g in (MG, SI, AR, PRE, GEN)] + [1, 1])
finish(ws, [14, 13, 13, 13, 13, 13, 10, 13])

# 5) 재건축 단지 목록
ws = wb.create_sheet("재건축 단지")
head(ws, "재건축 단지 목록 — 서울시 구역과 콕집 단지 연결", [["자치구", "구역(서울시 자료)", "단계", "단계 날짜", "단지", "매물 10/28", "매물 11/4", "매물 11/11"]])
zone_by = {n: z for z in ZONES for n in z["complex_nos"]}
for no in sorted(F, key=lambda n: (order[F[n]["group"]], -F[n]["counts"]["2026-11-11"])):
    x, z = F[no], zone_by.get(no, {})
    stage, sd = STAGE_FIX.get(z.get("name"), (z.get("stage"), None))
    sd = sd or {"관리처분": z.get("mgmt"), "사업시행": z.get("impl"), "건축심의": z.get("arch"), "조합설립": z.get("union"),
                "추진위": z.get("committee"), "구역지정": z.get("designate")}.get(stage)
    ws.append([x["gu"], z.get("name"), x["group"], sd, x["name"], x["counts"]["2026-10-28"], x["counts"]["2026-11-04"], x["counts"]["2026-11-11"]])
    for c in ws[ws.max_row][5:]:
        c.number_format = INT
finish(ws, [10, 30, 13, 11, 26, 11, 11, 11], ["· 단계 날짜 = 그 단계의 인가·통과일(관리처분은 변경 인가가 있으면 변경일)."])

# 6) 인하 폭(기자 요청 추가) — measure_cut.py → press_jaecho_cut.json
C = json.loads((HERE.parent / "data" / "press_jaecho_cut.json").read_text())
CW, CS, CXW, CE = C["weekly"], C["span"], C["weekly_complex"], C["examples"]
ws = wb.create_sheet("인하 폭")
CWEEKS = list(CW)
h1 = ["구분", "주(끝나는 날)", "같은 집 수", "같은 집 평균 변동", "한 채당 평균 변동(원)", "내린 집 수", "내린 집 인하율(중앙값)",
      "내린 집 인하액(중앙값, 원)", "올린 집 수", "올린 집 인상률(중앙값)", "올린 집 인상액(중앙값, 원)", "3% 넘게 내린 집 비율"]
head(ws, "같은 집 호가 인하 폭 — 직전 수요일 대비(주간), 10/14→10/28·10/28→11/11(2주)", [h1])


def crow(label, d, x):
    c_, r_ = x["cut"] or {}, x["rise"] or {}
    ws.append([label, d, x["n"], x["net_pct_mean"], round(x["net_amt_mean"]), c_.get("n", 0), c_.get("pct_med"), c_.get("amt_med"),
               r_.get("n", 0), r_.get("pct_med"), r_.get("amt_med"), x["cut_ge3"]])
    for i, c in enumerate(ws[ws.max_row][2:]):
        c.number_format = (INT, SPCT, INT, INT, SPCT, INT, INT, SPCT, INT, PCT)[i]


for g in STAGES:
    for d in CWEEKS:
        crow(g, d, CW[d][g])
    for k, lab in (("pre", "2주 10/14→10/28"), ("post", "2주 10/28→11/11")):
        crow(g, lab, CS[k]["groups"][g])
for no in ("236", "639"):
    for d in CWEEKS:
        crow(F[no]["name"], d, CXW[d][no])
    for k, lab in (("pre", "2주 10/14→10/28"), ("post", "2주 10/28→11/11")):
        crow(F[no]["name"], lab, CS[k]["complex"][no])
ws.append([])
ws.append(["10/28→11/11 호가를 가장 많이 내린 같은 집"])
ws.append(["단지", "동", "층", "전용(㎡)", "10월 28일 호가(원)", "11월 11일 호가(원)", "인하(원)"])
for c in ws[ws.max_row]:
    c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="EEEEEE")
for no in ("236", "639"):
    for e in CE[no]:
        ws.append([F[no]["name"], e["dong"], e["floor"], e["area2"], e["before"], e["after"], e["after"] - e["before"]])
        for c in ws[ws.max_row][4:]:
            c.number_format = INT
finish(ws, [26, 18, 10, 12, 16, 10, 14, 16, 10, 14, 16, 12],
       ["· 같은 집 평균 변동 = 내린 집·그대로 둔 집(0%)·올린 집을 모두 넣은 평균. 2주는 두 날 모두 나와 있던 같은 집.",
        "· 층은 '해당 층/전체 층', 저·중·고는 광고 표시 그대로."])

# 7) 강남3구 1,000세대 이상 16개 구역 — measure_zones.py → press_jaecho_zones16.json
Z16 = json.loads((HERE.parent / "data" / "press_jaecho_zones16.json").read_text())
ws = wb.create_sheet("강남3구 16개 구역")
head(ws, "강남3구 1,000세대 이상 재건축 16개 구역(반포주공1 두 구역 제외) — 같은 집 호가 변동",
     [["자치구", "구역", "기간", "같은 집 수", "내린 집", "올린 집", "평균 변동", "한 채당 평균 변동(원)", "내린 집 인하액(중앙값, 원)"]])
for z in Z16["zones"] + [{"gu": "", "name": Z16["total"]}]:
    for lab, x in [(d, Z16["weekly"][d].get(z["name"])) for d in Z16["weekly"]] + \
                  [("2주 10/14→10/28", Z16["span"]["pre"].get(z["name"])), ("2주 10/28→11/11", Z16["span"]["post"].get(z["name"]))]:
        if not x:
            continue
        ws.append([z["gu"], z["name"], lab, x["n"], x["cut"], x["rise"], x["net_pct"], round(x["net_amt"]), x["cut_amt_med"]])
        for i, c in enumerate(ws[ws.max_row][3:]):
            c.number_format = (INT, PCT, PCT, SPCT, INT, INT)[i]
finish(ws, [9, 40, 18, 10, 9, 9, 10, 16, 18], ["· 압구정은 특별계획구역 단위(2구역=신현대, 3구역=구현대). 주간은 직전 수요일 대비."])

out = HERE / "콕집_서울재건축_사업단계별_매물동향.xlsx"
wb.save(out); print(out)
