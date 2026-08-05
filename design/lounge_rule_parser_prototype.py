# -*- coding: utf-8 -*-
from __future__ import annotations
"""AI 없는 순수 규칙 파서 — 음성/타이핑 원문에서 요건 필드를 뽑는다."""
import re

_NUM = "영일이삼사오육칠팔구십백천"
_SINO = {"영":0,"일":1,"이":2,"삼":3,"사":4,"오":5,"육":6,"칠":7,"팔":8,"구":9}

def _kor_num(s: str) -> int | None:
    """'이십사'→24, '팔십사'→84, '구'→9. 순수 한글 수사만."""
    if not s or any(c not in _NUM for c in s):
        return None
    total, cur = 0, 0
    for ch in s:
        if ch == "십": cur = (cur or 1) * 10
        elif ch == "백": cur = (cur or 1) * 100
        elif ch == "천": cur = (cur or 1) * 1000
        else:
            d = _SINO[ch]
            cur = cur + d if cur % 10 == 0 and cur else d if not cur else cur * 10 + d
    return total + cur

def _num(tok: str) -> int | None:
    tok = tok.strip()
    if tok.isdigit(): return int(tok)
    return _kor_num(tok)

# 금액: '24억' '이십사억' '24억 5천' '9억'
_MONEY = re.compile(rf"([0-9]+|[{_NUM}]+)\s*억(?:\s*([0-9]+|[{_NUM}]+)\s*(천|백)?만?)?")
def money(text: str) -> list[int]:
    out = []
    for m in _MONEY.finditer(text):
        eok = _num(m.group(1))
        if eok is None: continue
        v = eok * 100_000_000
        if m.group(2):
            sub = _num(m.group(2))
            if sub is not None:
                v += sub * (10_000_000 if m.group(3) == "천" else 1_000_000 if m.group(3) == "백" else 10_000)
        out.append(v)
    return out

# 면적: '84제곱' '84㎡' '34평' '팔십사제곱'
_AREA_M2 = re.compile(rf"([0-9]+|[{_NUM}]+)\s*(?:제곱|㎡|m2|평방)")
_AREA_PY = re.compile(rf"([0-9]+|[{_NUM}]+)\s*평(?!당)")
def area_m2(text: str) -> float | None:
    m = _AREA_M2.search(text)
    if m and (v := _num(m.group(1))): return float(v)
    m = _AREA_PY.search(text)
    if m and (v := _num(m.group(1))): return round(v * 3.3058, 1)
    return None

# 전화
_PHONE = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
def phone(text: str) -> str | None:
    m = _PHONE.search(text)
    return re.sub(r"[^0-9]", "", m.group()) if m else None

# 월: '10월' '십월' '시월'
_MON = re.compile(rf"([0-9]{{1,2}}|[{_NUM}]+|시)\s*월")
def move_month(text: str) -> int | None:
    for m in _MON.finditer(text):
        g = m.group(1)
        v = 10 if g == "시" else _num(g)
        if v and 1 <= v <= 12: return v
    return None

# 이름: '김철수 사장님/대표님/님' 앞의 2~4자 한글
_NAME = re.compile(r"([가-힣]{2,4})\s*(?:사장님|대표님|고객님|씨|님)")
def name(text: str) -> str | None:
    m = _NAME.search(text)
    return m.group(1) if m else None

# 거래유형 / 선행조건 키워드
TRADE = {"매매": "A1", "전세": "B1", "월세": "B2"}
COND_WORDS = ("전세보증금 반환", "보증금 반환", "대출", "주담대", "잔금", "매도", "전입")

def parse(text: str) -> dict:
    t = re.sub(r"\s+", " ", text)
    ms = money(t)
    conds = [w for w in COND_WORDS if w.replace(" ", "") in t.replace(" ", "")]
    return {
        "고객명": name(t), "전화": phone(t),
        "전용_m2": area_m2(t),
        "금액들_원": ms,
        "예산_원": max(ms) if ms else None,
        "입주_월": move_month(t),
        "거래": [v for k, v in TRADE.items() if k in t],
        "선행조건후보": conds,
    }

CASES = [
  # ① Gemini 받아쓰기(구두점 있음)
  "김철수 사장님 통화했고요. 고덕동 래미안 힐스테이트 84제곱 24억까지 보시고 10월 입주 원하십니다. 전세 보증금 9억 반환이 안 되면 어렵다고 하시네요.",
  # ② 브라우저 STT 수준(구두점 없음)
  "김철수 사장님 통화했고요 고덕동 래미안 힐스테이트 84제곱 24억까지 보시고 10월 입주 원하십니다 전세 보증금 9억 반환이 안 되면 어렵다고 하시네요",
  # ③ 한글 수사로 나온 경우(STT가 숫자를 안 바꿔줄 때)
  "김철수 사장님 고덕동 팔십사제곱 이십사억까지 시월 입주 전세보증금 구억 반환",
  # ④ 타이핑 한 줄 입력
  "김철수 010-1234-5678 고덕동 84 24억까지 10월입주",
  # ⑤ 평 표기 + 만원 단위
  "이영희 고객님 34평 매매 18억 5천 찾으심 010-2222-3333",
]
for i, c in enumerate(CASES, 1):
    print(f"[{i}] {c[:52]}…")
    r = parse(c)
    print("    ", {k: v for k, v in r.items() if v})
