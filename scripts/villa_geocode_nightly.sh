#!/bin/bash
# 빌라 좌표 지오코딩 야간 자동 재개 — villa_master pending 을 두 키로 채운다.
# VWorld 지오코더 키당 일일한도(OVER_REQUEST_LIMIT) 때문에 하루치만 처리되고 멈추므로,
# cron 으로 매일 00:10 KST 에 실행해 며칠에 걸쳐 완성. pending 0 이면 즉시 종료.
cd /opt/koczip || exit 1
K1=$(grep '^VWORLD_KEY=' .env | cut -d= -f2)
K2=$(grep '^VWORLD_KEY2=' .env | cut -d= -f2)
K3=$(grep '^VWORLD_KEY3=' .env | cut -d= -f2)
K4=$(grep '^VWORLD_KEY4=' .env | cut -d= -f2)
PEND=$(sqlite3 data/naverreal.sqlite "SELECT COUNT(*) FROM villa_master WHERE status IN ('pending','error')")
echo "[$(date '+%F %T')] nightly start — pending+error=${PEND:-?}" >> data/villa_master.log
[ "${PEND:-0}" -eq 0 ] && { echo "  완료됨 — skip" >> data/villa_master.log; exit 0; }
sqlite3 data/naverreal.sqlite "UPDATE villa_master SET status='pending' WHERE status='error'"
for K in "$K1" "$K2" "$K3" "$K4"; do
  [ -n "$K" ] && .venv/bin/python -u scripts/build_villa_master.py --geocode --concurrency 8 --key "$K" >> data/villa_master.log 2>&1
done
echo "[$(date '+%F %T')] nightly done" >> data/villa_master.log
