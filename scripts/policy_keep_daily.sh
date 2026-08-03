#!/usr/bin/env bash
# 세제개편안(2026-08-03 발표) 관측용 — 그날의 매물 parquet를 정책 폴더로 빼돌리고
# 기준선 대비 관측 리포트를 만든다.
#
# 매물 parquet 아카이브는 로컬 30일 회수 후 오프박스로 넘어간다. 정책 효과는 몇 달에
# 걸쳐 나타나므로 그 순환에서 빼둬야 나중에 비교가 된다.
#   /mnt/backup/policy_2026_tax_reform/daily/YYYY-MM-DD/*.parquet
#   /mnt/backup/policy_2026_tax_reform/watch/YYYY-MM-DD.md
#
# 크론: 23:40 (비단지 아카이브 22:30 이후)
set -u
ROOT=/opt/koczip
POL=/mnt/backup/policy_2026_tax_reform
D=$(date +%F)
CATS="villa oneroom house sangga office knowledge redev building factory land"

# 보관 상한 — 넘으면 복사를 멈추고 알린다(백업 볼륨을 정책 관측이 잡아먹으면 안 된다).
LIMIT_GB=15

used_gb=$(du -sBG "$POL" 2>/dev/null | cut -dG -f1)
if [ "${used_gb:-0}" -ge "$LIMIT_GB" ]; then
  echo "[$D] policy 폴더 ${used_gb}GB — 상한 ${LIMIT_GB}GB 도달, 일별 보관 중단"
  exit 0
fi

mkdir -p "$POL/daily/$D"
n=0
src="$ROOT/data/archive/listings/${D:0:4}/${D:5:2}/listings_$D.parquet"
[ -f "$src" ] && cp -n "$src" "$POL/daily/$D/" && n=$((n+1))
for c in $CATS; do
  f="$ROOT/data/archive/$c/${D:0:4}/${D:5:2}/${c}_$D.parquet"
  [ -f "$f" ] && cp -n "$f" "$POL/daily/$D/" && n=$((n+1))
done
echo "[$D] parquet $n개 보관 ($(du -sh "$POL/daily/$D" | cut -f1))"

cd "$ROOT" && .venv/bin/python scripts/policy_watch.py "$D" > /dev/null 2>&1 \
  && echo "[$D] 관측 리포트 생성" || echo "[$D] 관측 리포트 실패"
