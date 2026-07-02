#!/usr/bin/env bash
# 캐시 워밍 — 데이터 재빌드(daily·listings·catchup) 직후와 API 재시작 직후 핵심
# 엔드포인트를 미리 호출해 런타임캐시·OS페이지캐시를 데운다. → 캐시 무효화(정확성)
# 후에도 첫 사용자가 항상 빠름(속도 보장). localhost 직행이라 CF·인증 무관.
B=http://127.0.0.1:8000
ROOT=/opt/koczip
H(){ curl -4 -s -o /dev/null --max-time 60 "$B$1"; }

# API 기동 대기(재시작 직후 ExecStartPost로 불릴 수 있음)
for i in $(seq 1 30); do
  curl -s -o /dev/null --max-time 2 "$B/health" && break
  sleep 1
done

# ── 홈(우리동네) 위젯 — 전국 기본(아파트·오피스텔) ──
for asset in apt offi; do
  H "/stats/tx-top-volume?asset=$asset&limit=7"
  H "/stats/tx-top-price?asset=$asset&trade=A1&limit=7"
  H "/stats/tx-price-change?asset=$asset&order=desc&limit=7"
  H "/stats/quick-deals?asset=$asset&days=90&min_samples=3&min_discount=0.05&limit=8"
done
H "/stats/changes/sido-list"
H "/stats/avg-price-trend?days=90&asset=apt"

# ── 중개사 랭킹(홈·랭킹 페이지) ──
H "/stats/realtors/national?limit=20&scope=complex"
H "/stats/realtors/by-sido?limit=10&scope=complex"
H "/stats/realtors/by-staff?limit=20"
H "/stats/realtors/by-tenure?limit=20"

# ── 인기 단지(최근 90일 거래량 상위 12) 상세 — OS 페이지캐시 워밍 ──
for cno in $("$ROOT/.venv/bin/python" - <<'PY'
import sqlite3
c = sqlite3.connect("/opt/koczip/data/naverreal.sqlite")
rows = c.execute(
    "SELECT matched_complex_no FROM transactions "
    "WHERE deal_ymd >= date('now','-90 days') AND matched_complex_no IS NOT NULL "
    "  AND is_cancelled = 0 AND matched_score >= 0.85 "
    "GROUP BY matched_complex_no ORDER BY COUNT(*) DESC LIMIT 12").fetchall()
print("\n".join(str(r[0]) for r in rows))
PY
); do
  H "/complex/$cno/summary"
  H "/complex/$cno/transactions?months=24"
  H "/complex/$cno/quick-deals?min_discount=0.05"
  H "/complex/$cno/nearby-transactions?months=12&radius_km=1.5&limit=12"
done

echo "[warm] done $(date '+%F %T')"
