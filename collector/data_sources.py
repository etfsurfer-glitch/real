"""수집 데이터 소스 신선도 판정 — 관리자 '데이터 출처' 화면(/admin/data-sources)과
매일 텔레그램 점검(scripts/datasource_watch.py)이 같은 기준을 쓰도록 한 곳에 둔다.

신선도 신호: 실거래=inserted_at(수집시각), 매물=snapshot_date, 중개사=fetched_at,
vworld=list_fetched_at. 상태: ok(주기 이내) / delay(주기×2 이내) / stale(그 이상, '점검 필요').
"""
from __future__ import annotations

import sqlite3
from datetime import datetime as _dt, timezone as _tz
from pathlib import Path

# (table, 친화이름, 분류, 출처, 수집주기, 정상주기일수, 마지막수집표현, 최신데이터표현)
SRC = [
    ("transactions",      "아파트 매매 실거래",     "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("offi_transactions", "오피스텔 매매 실거래",   "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("rentals",           "아파트 전·월세 실거래",  "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("offi_rentals",      "오피스텔 전·월세 실거래", "실거래 (국토부)", "국토교통부 실거래가",        "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("silv_transactions", "분양권·입주권 전매 실거래", "실거래 (국토부)", "국토교통부 실거래가",      "매일",            2,  "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("rh_transactions",   "연립·다세대(빌라) 매매 실거래",   "실거래 (국토부)", "국토교통부 실거래가",  "매일", 2, "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("rh_rentals",        "연립·다세대(빌라) 전·월세 실거래", "실거래 (국토부)", "국토교통부 실거래가",  "매일", 2, "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("sh_transactions",   "단독·다가구 매매 실거래",         "실거래 (국토부)", "국토교통부 실거래가",  "매일", 2, "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("sh_rentals",        "단독·다가구 전·월세 실거래",      "실거래 (국토부)", "국토교통부 실거래가",  "매일", 2, "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("nrg_transactions",  "상업·업무용 매매 실거래",         "실거래 (국토부)", "국토교통부 실거래가",  "매일", 2, "MAX(date(inserted_at))", "MAX(deal_ymd)"),
    ("listings_current",  "아파트·오피 매물 (호가)",   "매물",           "부동산 매물 플랫폼",         "매일",            2,  "MAX(snapshot_date)",     "MAX(snapshot_date)"),
    ("complex_daily_agg", "단지별 일일 매물 집계",   "매물",           "내부 집계 (매물 보관)",       "매일",            2,  "MAX(snapshot_date)",     "MAX(snapshot_date)"),
    ("naver_realtors",    "중개사무소 정보",         "단지·중개사",    "부동산 매물 플랫폼",         "매일 (신규 보강)", 3,  "MAX(date(fetched_at))",  None),
    ("vworld_brokers",    "공인중개사 공식 등록",    "단지·중개사",    "브이월드 (국토교통부)",      "월 1회",          35, "MAX(date(list_fetched_at))", None),
    ("complexes",         "아파트·오피 단지 정보",   "단지·중개사",    "부동산 매물 플랫폼",         "매일 (매물과 함께)",  2, "_listings_snap",         None),
]

# 비단지 호가 — 별도 DB(9종, listings_*.sqlite). snapshot_date 신선도.
REGION_DBS = [
    ("listings_sangga", "상가 매물 (호가)"), ("listings_office", "사무실 매물 (호가)"),
    ("listings_villa", "빌라·연립 매물 (호가)"), ("listings_house", "단독·다가구 매물 (호가)"),
    ("listings_land", "토지 매물 (호가)"), ("listings_factory", "공장·창고 매물 (호가)"),
    ("listings_building", "건물 매물 (호가)"), ("listings_knowledge", "지식산업센터 매물 (호가)"),
    ("listings_redev", "재개발 매물 (호가)"),
]


def check(c: sqlite3.Connection, data_dir: Path) -> list[dict]:
    """소스별 행수·최신 데이터·마지막 수집·신선도 상태."""
    today = _dt.now(_tz.utc).date()

    def days_since(s):
        if not s:
            return None
        try:
            return (today - _dt.strptime(str(s)[:10], "%Y-%m-%d").date()).days
        except Exception:
            return None

    out = []
    existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, name, cat, source, cycle, cyd, fexpr, dexpr in SRC:
        if table not in existing:
            continue
        n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        # complexes는 자체 타임스탬프가 없음 — 매물 수집(listings snapshot)과 함께 갱신되므로 이를 신선도 proxy로 사용.
        if fexpr == "_listings_snap":
            last = c.execute("SELECT MAX(snapshot_date) FROM listings_current").fetchone()[0]
        elif fexpr:
            last = c.execute(f"SELECT {fexpr} FROM {table}").fetchone()[0]
        else:
            last = None
        latest = c.execute(f"SELECT {dexpr} FROM {table}").fetchone()[0] if dexpr else None
        da = days_since(last)
        if da is None:
            status = "unknown"
        elif da <= cyd:
            status = "ok"
        elif da <= cyd * 2:
            status = "delay"
        else:
            status = "stale"
        out.append({"key": table, "name": name, "category": cat, "source": source,
                    "cycle": cycle, "rows": n, "last_collected": last, "days_ago": da,
                    "latest_data": latest, "status": status})

    for fname, name in REGION_DBS:
        path = data_dir / f"{fname}.sqlite"
        if not path.exists():
            continue
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as rc:
                n = rc.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
                last = rc.execute("SELECT MAX(snapshot_date) FROM listings").fetchone()[0]
        except sqlite3.Error:
            continue
        da = days_since(last)
        status = ("unknown" if da is None else "ok" if da <= 2 else "delay" if da <= 4 else "stale")
        out.append({"key": fname, "name": name, "category": "매물 (비단지)",
                    "source": "부동산 매물 플랫폼", "cycle": "매일", "rows": n,
                    "last_collected": last, "days_ago": da, "latest_data": last, "status": status})
    return out
