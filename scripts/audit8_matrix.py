# -*- coding: utf-8 -*-
"""⑧ 방 수·욕실 수 — 경우의 수 전수를 실제 엔진에 돌려 표로 찍는다.
기대값을 같이 적어 두고 불일치가 있으면 그 자리에서 드러나게 한다.

실행: python3 scripts/audit8_matrix.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector.listing_audit import audit_listing

# 상가주택 층별개요 — 1층 근생 + 2·4층 다가구주택(실측 2650379876 구조)
MIX = [{"flr_gb": "지상", "flr_no": 4, "purps": "다가구주택", "etc": "단독주택-다가구주택(1가구)"},
       {"flr_gb": "지상", "flr_no": 2, "purps": "다가구주택", "etc": "단독주택-다가구주택(2가구)"},
       {"flr_gb": "지상", "flr_no": 1, "purps": "일반음식점", "etc": "제2종근린생활시설(일반음식점)"}]
# 전부 근생(실측 2651804996)
COM = [{"flr_gb": "지상", "flr_no": 1, "purps": "기타사무소", "etc": "사무실,식당"},
       {"flr_gb": "지상", "flr_no": 1, "purps": "일반음식점", "etc": "식당,차고"}]

MISS = "미입력"


def run(rt, ret, room, bath, floors=None, cf=None):
    f = {"article_no": "T", "realestate_type_name": rt, "real_estate_type": ret, "price": 1}
    if room is not MISS:
        f["room_count"] = room
    if bath is not MISS:
        f["bathroom_count"] = bath
    if floors is not None:
        f["led_floors"] = floors
    if cf is not None:
        f["corresponding_floor"] = cf
    for x in audit_listing(f)["findings"]:
        if x["no"] == 8:
            return x["status"], (x["reason"] or "")
    return "?", ""


def val(v):
    return "미입력" if v is MISS else (f"{v}개")


CASES = [
    # (구분, 유형, 코드, 방, 욕실, 층별개요, 해당층, 기대)
    ("A 비주거", "사무실", "D01", MISS, 2, None, None, "통과"),
    ("A 비주거", "사무실", "D01", 3, 2, None, None, "통과"),
    ("A 비주거", "사무실", "D01", MISS, 0, None, None, "주의"),
    ("A 비주거", "사무실", "D01", 3, 0, None, None, "주의"),
    ("A 비주거", "사무실", "D01", MISS, MISS, None, None, "위반"),
    ("A 비주거", "사무실", "D01", 3, MISS, None, None, "위반"),
    ("A 비주거", "상가", "SG", MISS, 1, None, None, "통과"),
    ("A 비주거", "지식산업센터", "APTHGJ", MISS, MISS, None, None, "위반"),

    ("B 주거", "빌라", "VL", 3, 2, None, None, "통과"),
    ("B 주거", "빌라", "VL", 3, 0, None, None, "위반"),
    ("B 주거", "빌라", "VL", 3, MISS, None, None, "위반"),
    ("B 주거", "빌라", "VL", MISS, 2, None, None, "위반"),
    ("B 주거", "빌라", "VL", MISS, MISS, None, None, "위반"),
    ("B 주거", "아파트", "APT", 3, 2, None, None, "통과"),
    ("B 주거", "오피스텔", "OPST", MISS, 1, None, None, "위반"),
    ("B 주거", "단독", "DDDGG", 5, 3, None, None, "통과"),

    ("C 상가주택", "상가주택", "GJCG", 16, 12, MIX, "-", "통과"),
    ("C 상가주택", "상가주택", "GJCG", MISS, 12, MIX, "-", "위반"),
    ("C 상가주택", "상가주택", "GJCG", 16, 0, MIX, "-", "위반"),
    ("C 상가주택", "상가주택", "GJCG", MISS, 1, COM, "-", "통과"),
    ("C 상가주택", "상가주택", "GJCG", MISS, 0, COM, "-", "주의"),
    ("C 상가주택", "상가주택", "GJCG", MISS, MISS, COM, "-", "위반"),
    ("C 상가주택", "상가주택", "GJCG", MISS, 1, MIX, "1", "통과"),
    ("C 상가주택", "상가주택", "GJCG", MISS, 1, MIX, "2", "위반"),
    ("C 상가주택", "상가주택", "GJCG", 2, 1, MIX, "2", "통과"),
    ("C 상가주택", "상가주택", "GJCG", MISS, 1, None, None, "통과"),
    ("C 상가주택", "건물", "GJCG", MISS, 1, MIX, "-", "위반"),
    ("C 상가주택", "사무실", "D01", MISS, 1, MIX, "-", "통과"),
]

print(f"{'구분':<10}{'유형':<12}{'방':>7}{'욕실':>7}{'해당층':>7}  {'판정':<5}{'기대':<5} {'사유'}")
print("─" * 104)
bad = 0
for grp, rt, ret, room, bath, fl, cf, want in CASES:
    st, why = run(rt, ret, room, bath, fl, cf)
    mark = "" if st == want else "   ★불일치"
    if st != want:
        bad += 1
    print(f"{grp:<10}{rt:<12}{val(room):>7}{val(bath):>7}{(cf or '-'):>7}  "
          f"{st:<5}{want:<5} {why[:40]}{mark}")
print("─" * 104)
print(f"{len(CASES)}개 경우 · 불일치 {bad}개")
raise SystemExit(1 if bad else 0)
