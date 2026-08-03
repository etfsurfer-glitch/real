# -*- coding: utf-8 -*-
"""2026 세제개편안(2026-08-03 18:00 발표) 전후 매물·거래 흐름 관측.

기준선은 policy_baseline_snapshot.py 가 만든 발표 직전 스냅샷이고, 이 스크립트는
그날 이후 매일의 상태를 그것과 비교해 보도자료 소재가 될 만한 움직임을 뽑는다.

  python scripts/policy_watch.py            # 오늘
  python scripts/policy_watch.py 2026-08-10 # 특정일(그날 매물 스냅샷이 DB에 있어야)

출력: /mnt/backup/policy_2026_tax_reform/watch/YYYY-MM-DD.md

읽기만 한다. 본DB(27GB)에 긴 트랜잭션을 걸면 WAL 체크포인트가 막혀 디스크가 찬 적이
있어(2026-08-03) 쿼리마다 커넥션을 새로 연다.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

DATA = Path("/opt/koczip/data")
MAIN = DATA / "naverreal.sqlite"
ROOT = Path("/mnt/backup/policy_2026_tax_reform")
BASE = ROOT / "2026-08-03_pre" / "baseline.sqlite"
OUT_DIR = ROOT / "watch"
ANNOUNCE = "2026-08-03"          # 발표일. 일시적 2주택 경과조치 기준일이기도 하다.

# 규제지역(투기과열지구·조정대상지역) = 서울 25개구 전역 + 경기 15곳.
# frontend/src/lib/buyregion.ts 와 같은 목록 — 지정이 바뀌면 양쪽 다 고쳐야 한다.
REGULATED_GG = {
    "41290", "41210", "41135", "41131", "41133", "41117", "41111", "41115",
    "41173", "41465", "41430", "41450", "41597", "41463", "41310",
}
NONRESI = ["land", "sangga", "office", "villa", "house", "building",
           "factory", "knowledge", "oneroom", "redev"]


def q(db: Path, sql: str, args=()) -> list:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def zone(sgg: str) -> str:
    """시군구 5자리 → 규제지역 / 수도권 / 지방."""
    if not sgg:
        return "미상"
    if sgg.startswith("11") or sgg in REGULATED_GG:
        return "규제지역"
    if sgg[:2] in ("11", "41", "28"):
        return "수도권(비규제)"
    return "지방"


def pct(now: float, was: float) -> str:
    if not was:
        return "—"
    d = (now - was) / was * 100
    return f"{d:+.1f}%"


def bar(v: float, lo: float, hi: float, w: int = 18) -> str:
    if hi <= lo:
        return ""
    return "█" * max(0, min(w, round((v - lo) / (hi - lo) * w)))


# ── 1. 매물 총량 ──────────────────────────────────────────────────────────
def listings_by_zone(db: Path, table: str, where: str = "") -> dict:
    rows = q(db, f"""
        SELECT substr(c.cortar_no,1,5), l.trade_type, COUNT(*)
          FROM {table} l LEFT JOIN complexes c ON c.complex_no = l.complex_no
         {where}
         GROUP BY 1, 2""")
    out: dict = {}
    for sgg, trade, n in rows:
        out.setdefault(zone(sgg or ""), {}).setdefault(trade or "?", 0)
        out[zone(sgg or "")][trade or "?"] += n
    return out


def base_listings_by_zone() -> dict:
    out: dict = {}
    for sgg, trade, n in q(BASE, "SELECT sgg, trade_type, SUM(n) FROM listings_summary GROUP BY 1,2"):
        out.setdefault(zone(sgg or ""), {}).setdefault(trade or "?", 0)
        out[zone(sgg or "")][trade or "?"] += n
    return out


def day_parquet(day: str) -> Path | None:
    """그날 02:2x에 확정된 단지형 스냅샷. 정책 폴더 사본을 먼저 본다."""
    for p in (ROOT / "daily" / day / f"listings_{day}.parquet",
              DATA / "archive" / "listings" / day[:4] / day[5:7] / f"listings_{day}.parquet"):
        if p.exists():
            return p
    return None


def parquet_by_zone(f: Path) -> dict:
    """parquet → 지역구분×거래 집계. 기준선과 같은 방식이라 사과 대 사과가 된다."""
    import pyarrow.parquet as pq
    cortar = {c: (n or "")[:5]
              for c, n in q(BASE, "SELECT complex_no, cortar_no FROM complexes")}
    t = pq.read_table(f, columns=["complex_no", "trade_type"]).to_pydict()
    out: dict = {}
    for cn, tt in zip(t["complex_no"], t["trade_type"]):
        z = zone(cortar.get(cn, ""))
        out.setdefault(z, {}).setdefault(tt or "?", 0)
        out[z][tt or "?"] += 1
    return out


# ── 2. 매물 흐름(신규·소멸·호가변동) ─────────────────────────────────────
def flow(since: str) -> list:
    return q(MAIN, """
        SELECT event_date, event_type, COUNT(*)
          FROM article_events
         WHERE event_date >= ? AND trade_type = 'A1'
         GROUP BY 1, 2 ORDER BY 1""", (since,))


def price_moves(since: str) -> list:
    return q(MAIN, """
        SELECT event_date,
               SUM(CASE WHEN new_price < old_price THEN 1 ELSE 0 END),
               SUM(CASE WHEN new_price > old_price THEN 1 ELSE 0 END)
          FROM article_events
         WHERE event_date >= ? AND event_type = 'PRICE_CHANGE'
           AND trade_type = 'A1' AND old_price > 0 AND new_price > 0
         GROUP BY 1 ORDER BY 1""", (since,))


# ── 3. 고가 구간(종부세 사정권) ──────────────────────────────────────────
# 공시 14억 ≈ 시가 20억(1주택 과세선), 공시 9억 ≈ 시가 13억(그 외 과세선).
# listings_current.deal_or_warrant_price 는 **원 단위**다(2,000,000,000 = 20억).
EOK = 100_000_000


def high_tier(db: Path, table: str) -> dict:
    rows = q(db, f"""
        SELECT CASE WHEN deal_or_warrant_price >= {20*EOK} THEN '20억 이상'
                    WHEN deal_or_warrant_price >= {13*EOK} THEN '13~20억'
                    ELSE '13억 미만' END, COUNT(*)
          FROM {table} WHERE trade_type='A1' AND deal_or_warrant_price > 0
         GROUP BY 1""")
    return dict(rows)


def high_tier_parquet(f: Path | None) -> dict:
    """고가 구간을 parquet에서 센다(baseline.sqlite에는 집계만 있으므로)."""
    try:
        import pyarrow.compute as pc
        import pyarrow.parquet as pq
    except ImportError:
        return {}
    if not f or not f.exists():
        return {}
    t = pq.read_table(f, columns=["trade_type", "deal_or_warrant_price"])
    t = t.filter(pc.and_(pc.equal(t["trade_type"], "A1"),
                         pc.greater(t["deal_or_warrant_price"], 0)))
    p = t["deal_or_warrant_price"]
    hi = pc.sum(pc.cast(pc.greater_equal(p, 20 * EOK), "int64")).as_py() or 0
    mid = pc.sum(pc.cast(pc.and_(pc.greater_equal(p, 13 * EOK),
                                 pc.less(p, 20 * EOK)), "int64")).as_py() or 0
    return {"20억 이상": hi, "13~20억": mid, "13억 미만": t.num_rows - hi - mid}


# ── 4. 급매 ──────────────────────────────────────────────────────────────
def special(db: Path) -> dict:
    return dict(q(db, "SELECT kind, COUNT(*) FROM special_deals GROUP BY 1"))


# ── 5. 비단지(토지·상가 — 비사업용 토지 중과 강화 관측) ────────────────
def nonresi_counts() -> dict:
    out = {}
    for cat in NONRESI:
        p = DATA / f"listings_{cat}.sqlite"
        if not p.exists():
            continue
        try:
            snap, n = q(p, """SELECT MAX(snapshot_date),
                                     COUNT(*) FROM listings
                               WHERE snapshot_date=(SELECT MAX(snapshot_date) FROM listings)""")[0]
            out[cat] = (snap, n)
        except sqlite3.Error:
            pass
    return out


def nonresi_base() -> dict:
    """기준선은 parquet만 있으므로 MANIFEST 행수 대신 parquet 메타로 읽는다."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {}
    d = ROOT / "2026-08-03_pre" / "parquet"
    out = {}
    for cat in NONRESI:
        f = d / f"{cat}_{ANNOUNCE}.parquet"
        if f.exists():
            out[cat] = pq.ParquetFile(f).metadata.num_rows
    return out


# ── 6. 실거래 신고 흐름 ──────────────────────────────────────────────────
def tx_by_ymd(db: Path, table: str, since: str) -> dict:
    return dict(q(db, f"""SELECT deal_ymd, COUNT(*) FROM {table}
                           WHERE deal_ymd >= ? AND is_cancelled = 0
                           GROUP BY 1""", (since,)))


# ── 리포트 ───────────────────────────────────────────────────────────────
def main() -> int:
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    if not BASE.exists():
        print(f"기준선이 없습니다: {BASE}")
        return 2

    L: list[str] = []
    A = L.append
    A(f"# 세제개편안 전후 관측 — {today}")
    A("")
    A(f"기준선: **{ANNOUNCE} 18:00 발표 직전** (매물은 당일 오전 수집분)  ")
    A(f"생성: {datetime.now():%Y-%m-%d %H:%M} · 정책 요약 `design/policy/2026_세제개편안_부동산.md`")
    A("")

    # 1. 매물 총량
    # 당일 수집이 저녁까지 이어져 listings_current 에는 진행분이 섞인다. 매일 같은
    # 시각(02:2x)에 확정되는 parquet 끼리 비교해야 수집 진척이 증감으로 둔갑하지 않는다.
    pf = day_parquet(today)
    now = parquet_by_zone(pf) if pf else listings_by_zone(MAIN, "listings_current")
    was = base_listings_by_zone()
    src = (f"`{pf.name}` — 당일 02시대 확정분(기준선과 같은 방식)" if pf
           else "라이브 `listings_current` **— 당일 수집 진행분이 섞여 있어 참고용**")
    A("## 1. 매물 총량 (단지형 아파트·오피스텔)")
    A("")
    A(f"비교 대상: {src}")
    A("")
    A("| 지역구분 | 거래 | 발표 직전 | 현재 | 증감 |")
    A("|---|---|---:|---:|---:|")
    TR = {"A1": "매매", "B1": "전세", "B2": "월세"}
    for z in ("규제지역", "수도권(비규제)", "지방"):
        for t, tn in TR.items():
            b, n = was.get(z, {}).get(t, 0), now.get(z, {}).get(t, 0)
            if not (b or n):
                continue
            A(f"| {z} | {tn} | {b:,} | {n:,} | {pct(n, b)} |")
    A("")
    A("> 다주택 중과가 '27년부터 완화되므로 **'26년 매도를 미루는** 움직임이면 매물이 줄고, "
      "일시적 2주택 처분기한 단축(3년→2년)이 세면 규제지역 매매 매물이 는다. "
      "두 힘이 반대라 **규제지역 매매**의 방향이 이번 개편의 순효과를 보여준다.")
    A("")

    # 2. 흐름
    A("## 2. 매물 유입·이탈 (매매)")
    A("")
    ev: dict = {}
    for d, t, n in flow("2026-07-06"):
        ev.setdefault(d, {})[t] = n
    pm = {d: (dn, up) for d, dn, up in price_moves("2026-07-06")}
    A("| 날짜 | 신규 | 소멸 | 호가↓ | 호가↑ | |")
    A("|---|---:|---:|---:|---:|---|")
    news = [v.get("NEW", 0) for v in ev.values()] or [0]
    for d in sorted(ev):
        e = ev[d]
        dn, up = pm.get(d, (0, 0))
        mark = " ←발표" if d == ANNOUNCE else ""
        A(f"| {d}{mark} | {e.get('NEW',0):,} | {e.get('DELISTED',0):,} | {dn:,} | {up:,} | "
          f"`{bar(e.get('NEW',0), min(news), max(news))}` |")
    A("")
    # 요일이 맞아야 비교가 된다 — 일요일은 수집 범위가 좁아 신규가 1/10로 떨어진다.
    dow = datetime.strptime(today, "%Y-%m-%d").weekday()
    same = [(d, v.get("NEW", 0)) for d, v in ev.items()
            if datetime.strptime(d, "%Y-%m-%d").weekday() == dow]
    pre = [n for d, n in same if d < ANNOUNCE]
    cur = [n for d, n in same if d == today]
    if pre and cur:
        a = sum(pre) / len(pre)
        A(f"같은 요일 발표 전 평균 신규 **{a:,.0f}건** → 오늘 **{cur[0]:,}건** ({pct(cur[0], a)})")
        A("")
    A("> 네이버는 같은 물건에도 새 매물번호를 붙일 때가 있어 신규·소멸 절대값은 실제 "
      "유입·이탈보다 크다. **같은 요일끼리** 비교해야 하고(일요일은 수집 범위가 좁다), "
      "읽을 값은 절대량이 아니라 *추세*다.")
    A("")

    # 3. 고가 구간
    A("## 3. 고가 구간 매물 (종부세 사정권)")
    A("")
    hb = high_tier_parquet(ROOT / "2026-08-03_pre" / "parquet" / f"listings_{ANNOUNCE}.parquet")
    hn = high_tier_parquet(pf) or high_tier(MAIN, "listings_current")
    A("| 호가 구간 | 발표 직전 | 현재 | 증감 | 비고 |")
    A("|---|---:|---:|---:|---|")
    for k, note in (("20억 이상", "1주택 종부세 과세선(공시 14억) 근처"),
                    ("13~20억", "다주택 과세선(공시 9억) 근처"),
                    ("13억 미만", "")):
        A(f"| {k} | {hb.get(k,0):,} | {hn.get(k,0):,} | {pct(hn.get(k,0), hb.get(k,0))} | {note} |")
    A("")
    A("> 종부세는 세율·공정가액비율·세부담상한이 함께 오르는데 다주택 중과는 없어진다. "
      "**고가 1주택**이 가장 세게 맞으므로 20억 구간 매물이 늘면 그 신호다.")
    A("")

    # 4. 급매
    A("## 4. 급매 신호")
    A("")
    sn, sb = special(MAIN), special(BASE)
    KIND = {"owner": "주인(집주인) 급매", "tenant": "세입자 사정", "loan": "대출 승계"}
    A("| 유형 | 발표 직전 | 현재 | 증감 |")
    A("|---|---:|---:|---:|")
    for k, kn in KIND.items():
        A(f"| {kn} | {sb.get(k,0):,} | {sn.get(k,0):,} | {pct(sn.get(k,0), sb.get(k,0))} |")
    A("")

    # 5. 비단지
    A("## 5. 비단지 매물 (토지·상가 — 비사업용 토지 중과 +10→+20%p)")
    A("")
    nn, nb = nonresi_counts(), nonresi_base()
    NAME = {"land": "토지", "sangga": "상가", "office": "사무실", "villa": "빌라",
            "house": "단독", "building": "건물", "factory": "공장", "knowledge": "지식산업센터",
            "oneroom": "원룸", "redev": "재개발"}
    A("| 종류 | 발표 직전 | 현재 | 증감 |")
    A("|---|---:|---:|---:|")
    for c in NONRESI:
        b = nb.get(c, 0)
        n = nn.get(c, (None, 0))[1]
        A(f"| {NAME.get(c,c)} | {b:,} | {n:,} | {pct(n, b)} |")
    A("")

    # 6. 실거래
    A("## 6. 실거래 신고 (아파트 매매)")
    A("")
    A("계약 후 **30일 이내 신고**라 최근 계약분은 아직 다 차지 않았다. "
      "기준선과 비교하면 *발표 이후 추가로 신고된 건*을 가를 수 있다.")
    A("")
    tn = tx_by_ymd(MAIN, "transactions", "2026-07-01")
    tb = tx_by_ymd(BASE, "transactions", "2026-07-01")
    A("| 계약일 | 발표 직전까지 신고 | 현재 신고 | 추가 |")
    A("|---|---:|---:|---:|")
    for d in sorted(set(tn) | set(tb)):
        b, n = tb.get(d, 0), tn.get(d, 0)
        mark = " ←경과조치 기준" if d == ANNOUNCE else ""
        A(f"| {d}{mark} | {b:,} | {n:,} | {n-b:+,} |")
    A("")
    A(f"> **일시적 2주택 경과조치가 '{ANNOUNCE[2:]}' 이전 계약** 기준이라, 이 날짜 전후의 "
      "계약 건수가 갈리는지가 핵심이다. 9월 초는 되어야 8월 계약분이 다 찬다.")
    A("")
    A("---")
    A("")
    A("개정 **안**이다. 국회 통과·수정 가능성을 기사에 반드시 명시할 것. "
      "매물 수에는 계절성이 있으니 전년 동기·직전 4주 추세와 함께 봐야 한다.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{today}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n[saved] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
