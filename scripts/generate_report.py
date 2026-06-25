"""테이블 구조 + 데이터 수집 파이프라인 + 통계 HTML 보고서 생성."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402

OUT = Path("D:/auto/naverreal/db_report.html")


TABLE_DESC = {
    "regions": ("행정구역 트리 (시도/시군구/동/리)",
                "수집 단계 0. naver `/api/regions/list` 재귀 호출로 트리 구축. cortar_no 10자리(2-3-3-2).",
                ["Naver"]),
    "complexes": ("아파트/오피스텔 단지 마스터",
                  "수집 단계 1. naver `/api/regions/complexes` 동 단위 호출 → 단지 메타데이터. detail_address/lat/lon/세대수/준공일.",
                  ["Naver"]),
    "listings_current": ("현재 매물 (최신 스냅샷)",
                         "수집 단계 2 (run_collect.py). 단지×거래유형(매매/전세/월세)별 `/api/articles/complex/{cno}` 페이지네이션. 일별 갱신 시 upsert.",
                         ["Naver"]),
    "articles": ("매물 이력 (시계열)",
                 "listings_current 변경 시 자동 기록 (가격 변동, 신규/삭제).",
                 ["Naver", "derived"]),
    "article_events": ("매물 이벤트 (NEW/PRICE/DELISTED)",
                       "변동 추적용. listings_current 비교로 자동 생성.",
                       ["derived"]),
    "complex_daily_agg": ("단지별 일별 매물 집계",
                          "일별 스냅샷 — 단지×거래유형 행수/최저/평균/최고가.",
                          ["derived"]),
    "region_daily_agg": ("시군구별 일별 집계",
                         "일별 스냅샷 — 시군구×거래유형 매물수/단지수.",
                         ["derived"]),
    "collection_log": ("수집 완료 로그",
                       "단지×거래유형별 성공/실패 기록. 중단 시 이어받기.",
                       ["meta"]),
    "transactions": ("아파트 실거래 매매 (국토부)",
                     "data.go.kr 4개 endpoint (매매·전월세·오피매매·오피전월세). 시군구×월 단위.",
                     ["data.go.kr"]),
    "rentals": ("아파트 실거래 전월세 (국토부)",
                "전월세 신고. 갱신/재계약은 별도 행.",
                ["data.go.kr"]),
    "offi_transactions": ("오피스텔 실거래 매매",
                          "오피스텔 별도 endpoint.",
                          ["data.go.kr"]),
    "offi_rentals": ("오피스텔 실거래 전월세",
                     "오피스텔 별도 endpoint.",
                     ["data.go.kr"]),
    "match_suggestions": ("실거래↔단지 매칭 후보 (관리)",
                          "auto/manual review용.",
                          ["meta"]),
    "vworld_brokers": ("국토부 부동산중개업 사무소",
                       "vworld 직접 크롤 (`dtld_list_s001.do` 시군구별). detail 페이지에서 phone 보강.",
                       ["vworld"]),
    "vworld_employees": ("사무소 소속 직원",
                         "vworld svcCode=118 (직원 검색). 사무소(sys_regno) FK.",
                         ["vworld"]),
    "vworld_crawl_log": ("vworld 시군구 크롤 로그",
                         "재실행/누락 보강 추적.",
                         ["meta"]),
    "naver_realtors": ("Naver 중개사 마스터",
                       "두 채널: `/api/articles/{no}` 의 articleRealtor (등록번호 포함) + `/api/realtors/{id}` (article 무관).",
                       ["Naver"]),
    "realtor_match": ("Naver↔vworld 매칭 결과",
                      "3단계 규칙: 등록번호→주소+동+이름→대표+전화. + vworld_status (정지/휴업 표시).",
                      ["derived"]),
}


def open_db():
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.row_factory = sqlite3.Row
    return c


def get_cols(conn, table):
    return [(r[1], r[2]) for r in conn.execute(f"PRAGMA table_info({table})")]


def row_count(conn, table):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return None


def fmt_int(n):
    return f"{n:,}" if isinstance(n, int) else "-"


def main():
    conn = open_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 매칭 통계
    match_stats = dict(conn.execute("SELECT match_type, COUNT(*) FROM realtor_match GROUP BY match_type").fetchall())
    total_realtors = sum(match_stats.values())
    matched = total_realtors - match_stats.get("none", 0)
    match_rate = matched / total_realtors * 100 if total_realtors else 0

    suspended = conn.execute("SELECT COUNT(*) FROM realtor_match WHERE vworld_status IS NOT NULL").fetchone()[0]
    vworld_phone = conn.execute("SELECT COUNT(*) FROM vworld_brokers WHERE phone IS NOT NULL").fetchone()[0]
    vworld_total = conn.execute("SELECT COUNT(*) FROM vworld_brokers").fetchone()[0]

    html = []
    html.append("""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>naverreal — 데이터 수집 & 테이블 보고서</title>
<style>
:root { color-scheme: light; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif;
       max-width: 1100px; margin: 24px auto; padding: 0 16px; color: #1a1a1a; }
h1 { font-size: 24px; border-bottom: 2px solid #1268d3; padding-bottom: 8px; }
h2 { font-size: 18px; margin-top: 28px; color: #1268d3; }
h3 { font-size: 14px; margin: 18px 0 4px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 18px; font-size: 13px; background: white;
        border: 1px solid #ddd; border-radius: 6px; overflow: hidden; }
th, td { padding: 6px 10px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }
th { background: #f6f8fa; font-weight: 600; }
tr:last-child td { border-bottom: none; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.src { display: inline-block; padding: 1px 6px; margin-right: 4px; border-radius: 3px; font-size: 11px;
       font-weight: 600; }
.src.Naver { background: #03c75a; color: white; }
.src.vworld { background: #2a6cdf; color: white; }
.src.data\\.go\\.kr { background: #e67e22; color: white; }
.src.derived { background: #555; color: white; }
.src.meta { background: #aaa; color: white; }
.box { background: #f8fafc; padding: 12px 16px; border-left: 4px solid #1268d3; margin: 12px 0;
       border-radius: 0 6px 6px 0; }
.row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; margin: 12px 0; }
.card { background: white; border: 1px solid #e3e3e3; border-radius: 6px; padding: 12px; }
.card .lbl { font-size: 12px; color: #666; }
.card .val { font-size: 20px; font-weight: 700; margin-top: 2px; }
.card .sub { font-size: 11px; color: #999; margin-top: 2px; }
.muted { color: #888; font-size: 12px; }
.flow { font-family: "SF Mono", Consolas, monospace; font-size: 12px; background: #f0f3f7;
        padding: 10px; border-radius: 4px; white-space: pre; overflow-x: auto; }
.cols { font-family: "SF Mono", Consolas, monospace; font-size: 11px; color: #555; }
</style>
</head>
<body>
""")

    html.append(f"<h1>naverreal — 데이터 수집 & 테이블 보고서</h1>")
    html.append(f"<p class='muted'>생성: {now} · DB: {escape(str(settings.local_db_path))}</p>")

    # 요약 카드
    html.append("<h2>📊 현재 상태</h2>")
    listings = row_count(conn, "listings_current")
    complexes = row_count(conn, "complexes")
    txs = (row_count(conn, "transactions") or 0) + (row_count(conn, "offi_transactions") or 0)
    rents = (row_count(conn, "rentals") or 0) + (row_count(conn, "offi_rentals") or 0)
    employees = row_count(conn, "vworld_employees")
    naver_r = row_count(conn, "naver_realtors")

    html.append("<div class='row'>")
    html.append(f"<div class='card'><div class='lbl'>현재 매물</div><div class='val'>{fmt_int(listings)}</div></div>")
    html.append(f"<div class='card'><div class='lbl'>단지</div><div class='val'>{fmt_int(complexes)}</div></div>")
    html.append(f"<div class='card'><div class='lbl'>실거래 매매</div><div class='val'>{fmt_int(txs)}</div></div>")
    html.append(f"<div class='card'><div class='lbl'>실거래 전월세</div><div class='val'>{fmt_int(rents)}</div></div>")
    html.append(f"<div class='card'><div class='lbl'>vworld 사무소</div><div class='val'>{fmt_int(vworld_total)}</div><div class='sub'>phone: {fmt_int(vworld_phone)} ({vworld_phone/vworld_total*100:.1f}%)</div></div>")
    html.append(f"<div class='card'><div class='lbl'>vworld 직원</div><div class='val'>{fmt_int(employees)}</div></div>")
    html.append(f"<div class='card'><div class='lbl'>Naver 중개사</div><div class='val'>{fmt_int(naver_r)}</div></div>")
    html.append(f"<div class='card'><div class='lbl'>매칭 1:1</div><div class='val'>{matched:,}</div><div class='sub'>{match_rate:.2f}% · 정지/휴업 {suspended}</div></div>")
    html.append("</div>")

    # 데이터 소스 + 흐름
    html.append("<h2>🔄 데이터 수집 파이프라인</h2>")
    html.append("<div class='box'>")
    html.append("<p><b>매일 02:00 (또는 수동) <code>daily_run.ps1</code> 실행</b> — 6단계:</p>")
    html.append("<ol style='margin: 4px 0; padding-left: 20px;'>")
    html.append("<li><b>run_collect.py --all</b> — Naver 매물 전국 수집 (~5h, 192k 단지×거래유형)</li>")
    html.append("<li><b>upload_to_supabase.py</b> — 클라우드 동기화 (현재 schema 미확정)</li>")
    html.append("<li><b>archive_listings.py</b> — 일별 raw parquet 백업</li>")
    html.append("<li><b>backfill_realprice.py --months 6</b> — 매매 실거래 incremental (~10분)</li>")
    html.append("<li><b>backfill_rentals.py --months 6</b> — 아파트 전월세 (~10분)</li>")
    html.append("<li><b>backfill_offi.py --months 6</b> — 오피스텔 매매+전월세 (~12분)</li>")
    html.append("</ol>")
    html.append("</div>")

    html.append("<h3>외부 데이터 소스</h3>")
    html.append("<table><tr><th>소스</th><th>endpoint / 파일</th><th>역할</th><th>수집 주기</th></tr>")
    html.append("<tr><td><span class='src Naver'>Naver</span></td><td><code>new.land.naver.com/api/regions/list</code></td><td>행정구역 트리</td><td>1회성 (수동)</td></tr>")
    html.append("<tr><td><span class='src Naver'>Naver</span></td><td><code>/api/regions/complexes</code></td><td>동 단위 단지 목록</td><td>14일 캐시 (daily_run에서 만료 시 갱신)</td></tr>")
    html.append("<tr><td><span class='src Naver'>Naver</span></td><td><code>/api/articles/complex/{complexNo}</code></td><td>단지 매물 페이지네이션</td><td><b>매일</b> (daily_run step 1, ~5h)</td></tr>")
    html.append("<tr><td><span class='src Naver'>Naver</span></td><td><code>/api/articles/{articleNo}</code></td><td>매물 detail — articleRealtor (등록번호 포함)</td><td>1회성 / 신규 realtor 발견 시 (fetch_naver_realtors.py)</td></tr>")
    html.append("<tr><td><span class='src Naver'>Naver</span></td><td><code>/api/realtors/{realtorId}</code></td><td>중개사 정보 (article 만료 무관)</td><td>1회성 / 만료된 realtor 회복 시 (fetch_naver_realtors_direct.py)</td></tr>")
    html.append("<tr><td><span class='src vworld'>vworld</span></td><td><code>vworld.kr/dtld/broker/dtld_list_s001.do</code></td><td>사무소 list (시군구별, 영업중만 default)</td><td>1회성 / 분기별 추천 (crawl_vworld_brokers.py --list)</td></tr>")
    html.append("<tr><td><span class='src vworld'>vworld</span></td><td><code>/dtld/broker/dtld_view_d001.do</code></td><td>사무소 detail — phone</td><td>1회성 / list 갱신 후 (--detail)</td></tr>")
    html.append("<tr><td><span class='src vworld'>vworld</span></td><td><code>list_s001.do?svcCode=118</code></td><td>직원/공인중개사 list (정지/휴업 노출)</td><td>1회성 / 정지·휴업 lookup 시 (find_suspended_brokers.py)</td></tr>")
    html.append("<tr><td><span class='src data.go.kr'>data.go.kr</span></td><td><code>RTMSDataSvcAptTrade</code> 등 4종</td><td>매매·전월세·오피매매·오피전월세 실거래</td><td><b>매일</b> (daily_run step 4·5·6, 최근 6개월 incremental)</td></tr>")
    html.append("</table>")

    # 매칭 결과 분포
    html.append("<h2>🔗 중개사 매칭 결과</h2>")
    html.append("<table><tr><th>match_type</th><th>건수</th><th>%</th><th>설명</th></tr>")
    desc = {
        "regno_exact": "등록번호 정확 일치 (공인중개사법 13조의2 분사무소 일련번호 포함)",
        "addr_name": "시도+시군구+동+상호명 정규화 일치",
        "sgg_name": "시도+시군구+상호명 정규화 일치 (동 정보 없을 때)",
        "rep_phone": "대표자명 + 전화번호 substring 일치",
        "none": "매칭 실패 (등록 안 됨/폐업/정지 등)",
    }
    for k in ["regno_exact", "addr_name", "sgg_name", "rep_phone", "none"]:
        n = match_stats.get(k, 0)
        pct = n / total_realtors * 100 if total_realtors else 0
        html.append(f"<tr><td><code>{k}</code></td><td class='num'>{n:,}</td><td class='num'>{pct:.2f}%</td><td>{desc.get(k, '')}</td></tr>")
    html.append("</table>")

    # 테이블별 컬럼
    html.append("<h2>🗂️ 테이블 구조</h2>")
    tables_all = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for tbl in tables_all:
        cnt = row_count(conn, tbl)
        cols = get_cols(conn, tbl)
        desc_info = TABLE_DESC.get(tbl, ("(기타)", "", []))
        title, how, sources = desc_info
        html.append(f"<h3><code>{tbl}</code> · {escape(title)} · <span class='muted'>{fmt_int(cnt)} rows</span></h3>")
        if sources:
            html.append("<p>" + " ".join(f"<span class='src {s}'>{s}</span>" for s in sources) + "</p>")
        if how:
            html.append(f"<p class='muted'>{escape(how)}</p>")
        html.append("<div class='cols'>")
        html.append(" · ".join(f"{c[0]} <span style='color:#aaa'>{c[1]}</span>" for c in cols))
        html.append("</div>")

    html.append("</body></html>")

    OUT.write_text("\n".join(html), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"size: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
