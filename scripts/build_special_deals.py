# -*- coding: utf-8 -*-
"""매물 설명(article_feature_desc)에서 '특수조건 매매'를 분류해 색인한다.

중개사들이 설명란에 적어 광고하는 조건들:
  owner  주인전세 — 매도인이 팔고 그 집에 전세로 눌러앉는 조건(sale-leaseback)
  tenant 세안고  — 기존 임차인을 낀 채로 매수(갭투자)
  loan   승계    — 매도인의 담보대출·근저당을 승계

매번 LIKE '%..%' 전수 스캔(175만행·1.6초)을 돌 수는 없어 색인 테이블로 뽑아둔다.
daily_run에서 재생성.

Run: python3 scripts/build_special_deals.py [--db PATH]
"""
from __future__ import annotations
import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collector.config import settings  # noqa: E402

# ── 분류 규칙 ──
# 부정형을 반드시 걷어내야 한다. '근저당없음·무근저당·주인대출無·집주인대출X'는
# 오히려 '빚 없는 깨끗한 물건'이라는 정반대 홍보 문구다. 실측:
#   근저당 포함 408건 중 270건(66%)이 부정형
#   주인/집주인+대출 29건 중 24건(83%)이 부정형
# 그냥 LIKE '%근저당%' 하면 찾으려는 것과 정반대가 잡힌다.
NEG_LOAN = ("승계없", "승계 없", "근저당없", "근저당 없", "무근저당", "근저당해지",
            "근저당 해지", "근저당말소", "근저당 말소", "대출없", "융자없", "융자 없")
# 분양권·조합원의 중도금/이주비 승계는 '매도인 근저당 승계'와 다른 개념이라 제외한다.
NOT_LOAN = ("중도금", "이주비", "조합")

# 매도인이 **직접 자금을 대주고** 매수인을 구하는 형태만 본다.
#   '집주인대출6억' · '매도인 대출 가능' · '매도인근저당가능' · '매도인 잔금5억 대여가능'
# 주체어(매도인)와 자금어가 붙어있거나 한 칸 띄어진 경우만 — 문장 안에서 멀리 떨어져
# 따로 놀면 '대출 6억 가능'(=매수인 LTV 광고)까지 딸려와 개념이 뒤섞인다.
OWNER_FIN = re.compile(r"(주인|집주인|매도인|매도자|소유자|소유주)\s?(대출|융자|근저당|담보)")
# 대여·빌려·융통은 그 자체로 뜻이 분명해 주체어와 조금 떨어져도 안전하다
# ('매도인 잔금5억 대여가능' — 위 붙임 규칙만으로는 놓친다).
OWNER_LEND = re.compile(r"(주인|집주인|매도인|매도자|소유자|소유주).{0,10}(대여|빌려|융통)")
#
# 아래 셋은 의도적으로 제외한다 — 매도인이 돈을 대주는 것과 다른 개념이다.
#   · 기존대출승계·담보대출승계 : 매수인이 매도인의 은행 대출을 넘겨받는 것
#   · 맨 '대출승계'            : 실측 157건 중 150건이 분양권·입주권 중도금/분담금
#   · 잔금유예                 : 411건 중 대부분이 시행사의 신축·미분양 마케팅
#                               ('잔금유예 30프로 3년', '주택수 미포함', '무피 할인')
# '무융자·융자무'처럼 대출어 앞에 붙는 부정형(뒤가 아니라 앞에 온다).
NEG_HEAD = ("무융자", "융자무", "무대출", "대출무", "무근저당", "근저당무")
# 집주인이 '대출을 끼고 있다'는 **상태 서술**. 우리가 찾는 건 매도인이 돈을 대주는 **조건 제시**라
# 정반대는 아니어도 다른 이야기다. 실측: '집주인 융자형 주임사'(=융자 낀 주택임대사업자 매물)가
# 집주인+융자에 걸려 들어왔다. 접미사 '형/낀/있음'과 임대사업 맥락으로 갈라낸다.
NEG_STATE = ("융자형", "대출형", "융자낀", "대출낀", "융자 낀", "대출 낀",
             "융자있", "대출있", "주임사", "임대사업")
# 대출어 바로 뒤에 붙는 부정 표기. 無·X 같은 기호형이 실제로 다수라 반드시 포함해야 한다.
NEG_TAIL = ("없", "무", "無", "X", "x", "ｘ", "제로", "해지", "말소", "0원")
NEG_TAIL_WINDOW = 6


def _loan_hit(desc: str) -> str | None:
    """매도인이 직접 자금을 대주는 매물('집주인대출6억', '매도인 잔금5억 대여가능')."""
    if (any(k in desc for k in NEG_HEAD) or any(k in desc for k in NOT_LOAN)
            or any(k in desc for k in NEG_STATE)):
        return None
    for pat in (OWNER_FIN, OWNER_LEND):
        m = pat.search(desc)
        if not m:
            continue
        if any(k in desc[m.end():m.end() + NEG_TAIL_WINDOW] for k in NEG_TAIL):
            continue
        return m.group(0)
    return None


# loan 은 인접성 판정이 필요해 RULES 밖에서 _loan_hit 이 따로 본다.
RULES = {
    "owner":  {"any": ("주인전세", "집주인전세", "매도인전세", "주인 전세",
                       "주인세대전세", "매도인 전세"), "neg": (), "not": ()},
    "tenant": {"any": ("세안고", "세끼고", "세 끼고", "갭투", "임대차승계", "임차인승계",
                       "임대차 승계", "임차인 승계"), "neg": (), "not": ()},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS special_deals (
  article_no TEXT NOT NULL,
  kind       TEXT NOT NULL,          -- owner | tenant | loan
  matched    TEXT,                   -- 어떤 표현에 걸렸는지(검수용)
  PRIMARY KEY (article_no, kind)
);
CREATE INDEX IF NOT EXISTS special_deals_kind_idx ON special_deals(kind);
"""


def classify(desc: str) -> list[tuple[str, str]]:
    """설명 한 건 → [(kind, 걸린표현), ...]. 한 매물이 여러 조건에 걸릴 수 있다."""
    out = []
    for kind, r in RULES.items():
        hit = next((k for k in r["any"] if k in desc), None)
        if not hit:
            continue
        if r.get("need") and not any(k in desc for k in r["need"]):
            continue
        if any(k in desc for k in r.get("neg", ())):
            continue
        if any(k in desc for k in r.get("not", ())):
            continue
        out.append((kind, hit))
    hit = _loan_hit(desc)
    if hit:
        out.append(("loan", hit))
    return out


def build(db_path: str) -> dict:
    t0 = time.time()
    conn = sqlite3.connect(db_path, timeout=60)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_size_limit=1073741824")

    rows, seen = [], 0
    cur = conn.execute(
        "SELECT article_no, article_feature_desc FROM listings_current "
        "WHERE article_feature_desc IS NOT NULL AND article_feature_desc <> ''")
    for art, desc in cur:
        seen += 1
        for kind, hit in classify(desc):
            rows.append((art, kind, hit))

    # 전량 교체 — 내려간 매물이 남지 않게 한다(매물수 뻥튀기 사고와 같은 유형의 실수 방지).
    with conn:
        conn.execute("DELETE FROM special_deals")
        conn.executemany(
            "INSERT OR REPLACE INTO special_deals(article_no,kind,matched) VALUES(?,?,?)", rows)

    stat = dict(conn.execute(
        "SELECT kind, COUNT(*) FROM special_deals GROUP BY kind").fetchall())
    conn.close()
    stat["_scanned"] = seen
    stat["_sec"] = round(time.time() - t0, 1)
    return stat


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=settings.local_db_path)
    a = ap.parse_args()
    s = build(a.db)
    print(f"[*] 스캔 {s.pop('_scanned'):,}건 · {s.pop('_sec')}초")
    for k, v in sorted(s.items(), key=lambda x: -x[1]):
        print(f"    {k:7s} {v:,}건")
