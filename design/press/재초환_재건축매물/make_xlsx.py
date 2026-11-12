# -*- coding: utf-8 -*-
"""press_jaecho.json → 기자 전달용 엑셀(사업 단계별 주간 호가·매물 수, 재건축 단지 목록)."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

HERE = Path(__file__).resolve().parent
J = json.loads((HERE.parent / "data" / "press_jaecho.json").read_text())
ZONES = json.loads((HERE.parent / "data" / "press_jaecho_zones.json").read_text())
G = J["order"]
WEEKS = list(J["weekly"])
thin = Side(style="thin", color="BBBBBB")
STAGE_FIX = {"은마아파트": ("사업시행", "2026-07-02"), "잠실주공5단지": ("사업시행", "2026-07-01")}


def head(ws, title, cols):
    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append(cols)
    for c in ws[3]:
        c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="EEEEEE")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def finish(ws, widths, notes):
    for rr in ws.iter_rows(min_row=3, max_row=ws.max_row):
        for c in rr:
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.append([])
    for n in notes:
        ws.append([n])


NOTES = ["기준",
         "· 서울 아파트 매매 매물. 각 날짜 하루치 수집분.",
         "· 사업 단계: 서울시 「정비사업 추진현황」(2026년 6월 말 기준, 서울 열린데이터광장)의 아파트 재건축 구역(공동주택재건축·아파트지구재건축). "
         "은마·잠실주공5단지는 2026년 7월 사업시행인가를 반영. 착공 단계 구역은 제외.",
         "· 건축심의 전 = 구역지정·추진위원회·조합설립 단계. 일반 아파트 = 정비구역이 아닌 서울 아파트.",
         "· 실매물 = 같은 집을 여러 중개사무소가 올린 광고를 한 채로 합친 수.",
         "· 같은 집 = 두 날 모두 매물로 나와 있던 집(단지·동·층·공급·전용·방향이 같은 광고). 호가는 광고들의 중앙값, ±30% 넘는 변동은 오기재로 보고 제외.",
         "· 9월 23일 주는 추석 연휴로 9월 16일 → 9월 30일(2주) 비교.",
         "· 출처: 콕집(koczip.com)"]

wb = Workbook()
# 1) 주간 호가 내림 비율
ws = wb.active; ws.title = "주간 호가 변동"
head(ws, "서울 재건축 단지 사업 단계별 — 같은 집 주간 호가 변동(직전 주 대비)",
     ["주(끝나는 날)"] + [x for g in G for x in (f"{g}\n호가 내린 집", "올린 집", "평균 변동", "같은 집 수")])
for d, v in J["weekly_change"].items():
    row = [d]
    for g in G:
        x = v.get(g)
        row += [x["cut"], x["rise"], x["mean"], x["n"]] if x else [None] * 4
    ws.append(row)
    for i, c in enumerate(ws[ws.max_row][1:]):
        c.number_format = "0.0%" if i % 4 in (0, 1) else ("+0.00%;-0.00%;0.00%" if i % 4 == 2 else "#,##0")
finish(ws, [14] + [12, 9, 10, 10] * len(G), NOTES)

# 2) 매물 수
ws = wb.create_sheet("매물 수")
head(ws, "서울 재건축 단지 사업 단계별 — 실매물 수(중복 광고 합침), 매주 수요일", ["날짜"] + G)
for d in WEEKS:
    ws.append([d] + [round(J["weekly"][d].get(g, 0)) for g in G])
    for c in ws[ws.max_row][1:]:
        c.number_format = "#,##0"
ws.append(["단지 수"] + [J["groups"][g] for g in G])
finish(ws, [14] + [14] * len(G), NOTES)

# 3) 구간 누적
ws = wb.create_sheet("구간 비교")
head(ws, "같은 집 호가 — 구간별 비교", ["구간", "단계", "같은 집 수", "호가 내린 집", "올린 집", "평균 변동"])
LBL = {"post": "11월 4일 → 11월 11일", "oct28_nov11": "10월 28일 → 11월 11일", "since_aug": "8월 5일 → 11월 11일"}
for k, lab in LBL.items():
    for g in G:
        x = J["span"][k]["groups"].get(g)
        if x:
            ws.append([lab, g, x["n"], x["cut"], x["rise"], x["mean"]])
            r = ws[ws.max_row]
            r[2].number_format = "#,##0"; r[3].number_format = r[4].number_format = "0.0%"; r[5].number_format = "+0.00%;-0.00%;0.00%"
finish(ws, [22, 14, 11, 12, 10, 11], NOTES)

# 4) 단지 목록
ws = wb.create_sheet("재건축 단지")
head(ws, "서울 재건축 단지별 — 매물 수와 같은 집 호가",
     ["자치구", "구역(서울시 자료)", "단계", "단계 날짜", "단지", "매물 8/5", "매물 10/28", "매물 11/4", "매물 11/11",
      "11/4→11/11\n호가 내린 집", "같은 집 수", "8/5→11/11\n평균 변동", "같은 집 수"])
zone_by = {}
for z in ZONES:
    for n in z["complex_nos"]:
        zone_by[n] = z
rows = []
for no, f in J["focus"].items():
    z = zone_by.get(no, {})
    stage, sd = STAGE_FIX.get(z.get("name"), (z.get("stage"), None))
    if not sd:
        sd = {"관리처분": z.get("mgmt"), "사업시행": z.get("impl"), "건축심의": z.get("arch"), "조합설립": z.get("union"),
              "추진위": z.get("committee"), "구역지정": z.get("designate")}.get(stage)
    c = f["counts"]
    post = J["span"]["post"]["complex"].get(no) or {}
    aug = J["span"]["since_aug"]["complex"].get(no) or {}
    rows.append([f["gu"], z.get("name"), f["group"], sd, f["name"], c["2026-08-05"], c["2026-10-28"], c["2026-11-04"], c["2026-11-11"],
                 post.get("cut"), post.get("n"), aug.get("mean"), aug.get("n")])
order = {g: i for i, g in enumerate(G)}
rows.sort(key=lambda r: (order[r[2]], -(r[8] or 0)))
for r in rows:
    ws.append(r)
    x = ws[ws.max_row]
    for i in (5, 6, 7, 8):
        x[i].number_format = "#,##0"
    x[9].number_format = "0.0%"; x[11].number_format = "+0.00%;-0.00%;0.00%"
finish(ws, [10, 28, 13, 11, 24, 9, 9, 9, 9, 12, 9, 12, 9],
       NOTES + ["· 같은 집 호가 칸은 그 단지 같은 집이 10채 이상일 때만 표시."])
out = HERE / "콕집_서울재건축_사업단계별_매물동향.xlsx"
wb.save(out); print(out)
