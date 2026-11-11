# -*- coding: utf-8 -*-
"""press_hoga_band_gu.json → 기자 전달용 엑셀(자치구 × 20~25·25~30·30~35억, 8/3·11/11)."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
HERE = Path(__file__).resolve().parent
j = json.loads((HERE.parent / "data" / "press_hoga_band_gu.json").read_text())
A, Z = "2026-08-03", "2026-11-11"
B, GUS = j["bands"], j["gus"]
wb = Workbook(); thin = Side(style="thin", color="BBBBBB")


def sheet(ws, key, tkey, title):
    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append(["자치구"] + [x for b in B for x in (b, None, None)])
    ws.append([None] + [x for _ in B for x in ("8월 3일", "11월 11일", "증감")])
    for i in range(len(B)):
        ws.merge_cells(start_row=3, start_column=2 + i * 3, end_row=3, end_column=4 + i * 3)
    ws.merge_cells("A3:A4")
    for r in (3, 4):
        for c in ws[r]:
            c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="EEEEEE"); c.alignment = Alignment(horizontal="center", vertical="center")
    row = ["서울 전체"]
    for b in B:
        a, z = j["dates"][A][b][tkey], j["dates"][Z][b][tkey]
        row += [a, z, z - a]
    ws.append(row)
    for c in ws[ws.max_row]: c.font = Font(bold=True)
    for g in GUS:
        row = [g]
        for b in B:
            a, z = j["dates"][A][b][key][g], j["dates"][Z][b][key][g]
            row += [a, z, z - a]
        ws.append(row)
    for rr in ws.iter_rows(min_row=3, max_row=ws.max_row):
        for c in rr:
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            if isinstance(c.value, int):
                c.alignment = Alignment(horizontal="right")
                c.number_format = "+#,##0;-#,##0;0" if (c.column - 2) % 3 == 2 else "#,##0"
    ws.column_dimensions["A"].width = 12
    for col in "BCDEFGHIJ":
        ws.column_dimensions[col].width = 11
    for n in ["", "기준",
              "· 서울 아파트 매매 매물(아파트·재건축·아파트 분양권). 오피스텔 제외.",
              "· 각 날짜 하루치 수집분. 8월 3일은 세제개편안 발표(18시) 전 수집분.",
              "· 구간은 호가 기준, 하한 포함·상한 미포함(예: 25~30억 = 25억 이상 30억 미만).",
              "· 실매물 = 같은 집을 여러 중개사무소가 올린 광고를 한 채로 합친 수. 서울 전체는 앞서 드린 구간별 표와 같은 값입니다.",
              "· 광고 = 중개사무소가 올린 광고 전부(같은 집 중복 포함).",
              "· 같은 단지·같은 면적 호가 중앙값과 자릿수가 다른 오기재 광고는 뺐습니다.",
              "· 출처: 콕집(koczip.com)"]:
        ws.append([n])


sheet(wb.active, "obj", "obj_total", "서울 아파트 매매 매물 — 자치구별 실매물 수(중복 광고 합침), 20~35억 세 구간")
wb.active.title = "실매물(중복 합침)"
sheet(wb.create_sheet("광고 건수"), "ad", "ad_total", "서울 아파트 매매 매물 — 자치구별 광고 건수, 20~35억 세 구간")
out = HERE / "콕집_서울아파트_20~35억_자치구별_매물수.xlsx"; wb.save(out); print(out)
