# -*- coding: utf-8 -*-
"""KST 달력 날짜를 UTC now 와 비교하는 SQL을 잡아내는 회귀 검사.

배경(2026-07-23):
  SQLite 의 date('now') 는 **UTC** 다. deal_ymd·snapshot_date 같은 업무 일자는
  KST 달력 날짜라, 둘을 그냥 비교하면 매일 00~09시(KST)에 하루가 밀린다.
  실측: KST 08:26 시점 '최근 1일' 실거래가 684건으로 잡혔다(정상 213건, 3.2배).
  범위가 길면 오차가 묻히지만 짧은 창(1~7일)·'오늘' 화면에서는 그대로 드러난다.

  UTC 타임스탬프(inserted_at·ts·created_at)끼리 비교하는 곳은 이미 정합하므로 건드리지 않는다.

Run: python3 scripts/check_kst_dates.py        # 위반 있으면 exit 1
"""
from __future__ import annotations
import glob
import sys

# 업무 일자(YYYY-MM-DD / YYYYMMDD) — 한국 달력 기준으로 기록된다
KST_COLS = ("deal_ymd", "snapshot_date", "article_confirm_ymd", "use_approve_ymd",
            "first_seen_date", "last_seen_date", "record_date", "confirm_ymd")
# UTC 타임스탬프 — datetime('now') 로 저장되므로 UTC now 와 비교하는 게 맞다
UTC_COLS = ("inserted_at", "matched_at", "detail_fetched_at", "ts", "created_at",
            "computed_at", "built_at", "agreed_terms_at", "updated_at")

TARGETS = ["scripts/*.py", "collector/**/*.py"]


def scan() -> list[tuple[str, int, str]]:
    bad = []
    seen = set()
    for pat in TARGETS:
        for f in glob.glob(pat, recursive=True):
            if f in seen or f.endswith("check_kst_dates.py"):
                continue
            seen.add(f)
            try:
                lines = open(f, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for i, l in enumerate(lines, 1):
                if "date('now'" not in l and 'date("now"' not in l:
                    continue
                if "+9 hours" in l:
                    continue                      # 이미 KST 보정됨
                if not any(c in l for c in KST_COLS):
                    continue                      # 업무 일자와 비교하는 줄이 아님
                if any(c in l for c in UTC_COLS):
                    continue                      # UTC 끼리 비교 — 정상
                bad.append((f, i, l.strip()[:100]))
    return bad


if __name__ == "__main__":
    bad = scan()
    if not bad:
        print("[OK] KST 업무일자를 UTC now 와 비교하는 곳 없음")
        sys.exit(0)
    print(f"[FAIL] {len(bad)}곳 — 업무 일자를 UTC date('now') 와 비교하고 있다")
    print("       date('now', ...) → date('now','+9 hours', ...) 로 고칠 것")
    for f, i, l in bad:
        print(f"  {f}:{i}\n    {l}")
    sys.exit(1)
