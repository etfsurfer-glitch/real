# -*- coding: utf-8 -*-
"""press_hoga_band.json → 기자 전달용 엑셀."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
HERE = Path(__file__).resolve().parent
j = json.load(open(HERE.parent / "data" / "press_hoga_band.json"))
D = list(j["dates"]); L = [f"{int(d[5:7])}월 {int(d[8:])}일" for d in D]
wb = Workbook(); thin = Side(style="thin", color="BBBBBB")
def sheet(ws, key, title):
    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([]); ws.append(["호가 구간"] + L)
    for c in ws[3]: c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="EEEEEE")
    for b in j["bands"]:
        ws.append([b] + [j["dates"][d]["all"][b][key] for d in D])
    ws.append(["합계"] + [j["dates"][d]["total"][key] for d in D])
    for c in ws[ws.max_row]: c.font = Font(bold=True)
    for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
        for c in row:
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            if isinstance(c.value, int): c.number_format = "#,##0"; c.alignment = Alignment(horizontal="right")
    ws.column_dimensions["A"].width = 14
    for col in "BCDE": ws.column_dimensions[col].width = 13
    notes = ["", "기준",
             "· 서울 전체 아파트 매매 매물(아파트·재건축·아파트 분양권). 오피스텔 제외.",
             "· 각 날짜 하루치 수집분. 8월 3일은 세제개편안 발표(18시) 전 수집분.",
             "· 구간은 호가 기준, 하한 포함·상한 미포함(예: 10~15억 = 10억 이상 15억 미만).",
             "· 실매물 = 같은 집을 여러 중개사무소가 올린 광고를 한 채로 합친 수.",
             "· 광고 = 중개사무소가 올린 광고 전부(같은 집 중복 포함).",
             "· 같은 단지·같은 면적 호가 중앙값과 자릿수가 다른 오기재 광고(하루 0~3건)는 뺐습니다.",
             "· 호가가 정확히 15억·20억 등인 매물은 위 구간에 넣었습니다(15억 → 15~20억). '초과~이하'로 세어도 증감률 차이 4%p 이내.",
             "· 실매물은 하루 사이 1~2% 출렁입니다. 8월 3일(월)은 전후일보다 0.7~1.4% 적습니다.",
             "· 출처: 콕집(koczip.com)"]
    for n in notes: ws.append([n])
sheet(wb.active, "obj", "서울 아파트 매매 매물 — 호가 구간별 실매물 수(중복 광고 합침)"); wb.active.title = "실매물(중복 합침)"
sheet(wb.create_sheet("광고 건수"), "ad", "서울 아파트 매매 매물 — 호가 구간별 광고 건수")
out = HERE / "콕집_서울아파트_호가구간별_매물수.xlsx"; wb.save(out); print(out)
