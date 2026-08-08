#!/usr/bin/env bash
# 수집이 끝나기를 기다렸다가 1단계 측정을 돌린다. 전부 읽기 전용.
LOG=/tmp/step1.log
echo "[$(date '+%F %T')] 수집 종료 대기 시작" > $LOG
while pgrep -f 'collect_region_listings.py|run_collect.py|collect_listings.sh' >/dev/null; do
  sleep 60
done
echo "[$(date '+%F %T')] 수집 종료 확인 — 측정 시작" >> $LOG
sleep 30   # 마무리 쓰기가 가라앉기를 기다린다
nice -n 19 ionice -c3 /opt/koczip/.venv/bin/python /opt/koczip/scripts/step1_measure.py >> $LOG 2>&1
echo "[$(date '+%F %T')] 측정 끝" >> $LOG
